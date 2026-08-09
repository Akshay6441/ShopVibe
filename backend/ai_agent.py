"""Agentic AI - LLM tool/function calling agent for orders & tickets.

The agent reads orders/tickets and can take actions:

* ``get_order`` / ``get_ticket`` - read context
* ``flag_fraud`` - flag an order as potentially fraudulent
* ``update_order_status`` - advance/cancel an order
* ``draft_response`` - draft a support reply for an order

It uses OpenAI-compatible function calling and loops until the model returns
a final answer (bounded to N tool rounds). If ``OPENAI_API_KEY`` is not set the
endpoint returns 503 so the rest of the app keeps working.
"""
import json
from typing import Any, Callable, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from config import settings
from integrations import salesforce
from logger import logger

MAX_TOOL_ROUNDS = 5

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Fetch order details (items, totals, status, payment) by order id.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "integer"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ticket",
            "description": "Fetch a support ticket and its linked order by ticket id.",
            "parameters": {
                "type": "object",
                "properties": {"ticket_id": {"type": "integer"}},
                "required": ["ticket_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_fraud",
            "description": "Flag an order as potentially fraudulent with a reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["order_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_order_status",
            "description": "Update an order's status. Allowed values: "
            "pending, processing, shipped, delivered, cancelled.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "status": {"type": "string"},
                },
                "required": ["order_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_response",
            "description": "Draft a support response for a customer about their order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "tone": {"type": "string", "description": "friendly, professional or empathetic"},
                },
                "required": ["order_id"],
            },
        },
    },
]


# ── Tool handlers ─────────────────────────────────────────────────────────────

def _order_to_dict(order) -> dict:
    return {
        "order_id": order.id,
        "customer": order.user.email if order.user else None,
        "total_amount": order.total_amount,
        "shipping_address": order.shipping_address,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "status": order.status.value if hasattr(order.status, "value") else str(order.status),
        "fraud_flagged": order.is_fraud_flagged,
        "fraud_reason": order.fraud_reason,
        "items": [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in order.items
        ],
    }


def handle_get_order(db: Session, args: dict) -> dict:
    order = db.get(models.Order, int(args.get("order_id", 0)))
    if not order:
        return {"error": "order not found"}
    return _order_to_dict(order)


def handle_get_ticket(db: Session, args: dict) -> dict:
    ticket = db.get(models.SupportTicket, int(args.get("ticket_id", 0)))
    if not ticket:
        return {"error": "ticket not found"}
    data = {
        "ticket_id": ticket.id,
        "subject": ticket.subject,
        "message": ticket.message,
        "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
        "customer_email": ticket.user.email if ticket.user else None,
    }
    if ticket.order_id:
        order = db.get(models.Order, ticket.order_id)
        data["order"] = _order_to_dict(order) if order else None
    return data


def handle_flag_fraud(db: Session, args: dict) -> dict:
    order = db.get(models.Order, int(args.get("order_id", 0)))
    if not order:
        return {"error": "order not found"}
    order.is_fraud_flagged = True
    order.fraud_reason = str(args.get("reason", "flagged by AI agent"))
    db.commit()
    logger.info("AI agent flagged order %s for fraud: %s", order.id, order.fraud_reason)
    return {"ok": True, "order_id": order.id, "fraud_flagged": True, "reason": order.fraud_reason}


def handle_update_order_status(db: Session, args: dict) -> dict:
    order = db.get(models.Order, int(args.get("order_id", 0)))
    if not order:
        return {"error": "order not found"}
    status = str(args.get("status", ""))
    try:
        new_status = models.OrderStatus(status)
    except ValueError:
        return {"error": f"invalid status {status!r}"}
    order.status = new_status
    db.commit()
    logger.info("AI agent set order %s status to %s", order.id, status)
    salesforce.sync_order(order, db=db)
    return {"ok": True, "order_id": order.id, "status": status}


def handle_draft_response(db: Session, args: dict) -> dict:
    order = db.get(models.Order, int(args.get("order_id", 0)))
    if not order:
        return {"error": "order not found"}
    tone = str(args.get("tone", "friendly"))
    status = order.status.value if hasattr(order.status, "value") else str(order.status)
    name = order.user.name if order.user else "there"
    return {
        "draft": (
            f"Hi {name}, thanks for reaching out. Your order #{order.id} "
            f"(total ${order.total_amount:.2f}) is currently '{status}'. "
            f"Tone: {tone}."
        )
    }


HANDLERS: Dict[str, Callable] = {
    "get_order": handle_get_order,
    "get_ticket": handle_get_ticket,
    "flag_fraud": handle_flag_fraud,
    "update_order_status": handle_update_order_status,
    "draft_response": handle_draft_response,
}


# ── Agent loop ────────────────────────────────────────────────────────────────

def run_agent(db: Session, instruction: str, client: Any = None) -> dict:
    """Run the agent. ``client`` may be injected for tests."""
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured on the server",
        )
    if client is None:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are the ShopVibe operations assistant. You can inspect orders "
                "and support tickets and take actions. Use the provided tools when "
                "they are useful, then reply to the operator with a short summary "
                "of what you did. Never invent data - only use tool results."
            ),
        },
        {"role": "user", "content": instruction},
    ]
    actions: list[dict] = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            tools=TOOLS,
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            return {"reply": message.content or "Done.", "actions": actions}

        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )
        for tool_call in tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            handler = HANDLERS.get(name)
            if handler is None:
                result = {"error": f"unknown tool {name}"}
            else:
                result = handler(db, args)
            actions.append({"tool": name, "args": args, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )

    return {"reply": "Stopped after too many tool calls.", "actions": actions}
