"""Tests for the agentic AI module (tool calling)."""
from types import SimpleNamespace

import openai
import pytest
from fastapi import HTTPException

import models
from ai_agent import run_agent
from config import settings
from tests.conftest import auth_headers


class FakeMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message):
        self.message = message


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)

    def create(self, **kwargs):
        return SimpleNamespace(choices=[FakeChoice(self.responses.pop(0))])


class FakeChat:
    def __init__(self, responses):
        self.completions = FakeCompletions(responses)


class FakeClient:
    def __init__(self, responses):
        self.chat = FakeChat(responses)


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id,
                           function=SimpleNamespace(name=name, arguments=arguments))


def _make_order(db, user):
    order = models.Order(user_id=user.id, total_amount=75.0,
                         shipping_address="123 Main St", payment_method="card")
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def test_agent_flags_fraud(db, regular_user, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    order = _make_order(db, regular_user)
    responses = [
        FakeMessage(content=None, tool_calls=[
            _tool_call("call_1", "flag_fraud",
                       f'{{"order_id": {order.id}, "reason": "suspicious"}}')]),
        FakeMessage(content="Order flagged.", tool_calls=None),
    ]
    result = run_agent(db, "flag order as fraud", client=FakeClient(responses))
    assert result["reply"] == "Order flagged."
    assert result["actions"][0]["tool"] == "flag_fraud"
    db.refresh(order)
    assert order.is_fraud_flagged is True
    assert order.fraud_reason == "suspicious"


def test_agent_updates_order_status(db, regular_user, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    order = _make_order(db, regular_user)
    responses = [
        FakeMessage(content=None, tool_calls=[
            _tool_call("call_1", "update_order_status",
                       f'{{"order_id": {order.id}, "status": "shipped"}}')]),
        FakeMessage(content="Updated.", tool_calls=None),
    ]
    result = run_agent(db, "ship the order", client=FakeClient(responses))
    assert result["actions"][0]["result"]["status"] == "shipped"
    db.refresh(order)
    status = order.status.value if hasattr(order.status, "value") else order.status
    assert status == "shipped"


def test_agent_rejects_invalid_status(db, regular_user, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    order = _make_order(db, regular_user)
    responses = [
        FakeMessage(content=None, tool_calls=[
            _tool_call("call_1", "update_order_status",
                       f'{{"order_id": {order.id}, "status": "exploded"}}')]),
        FakeMessage(content="Cannot do that.", tool_calls=None),
    ]
    result = run_agent(db, "set status", client=FakeClient(responses))
    assert "error" in result["actions"][0]["result"]


def test_agent_drafts_response(db, regular_user, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    order = _make_order(db, regular_user)
    responses = [
        FakeMessage(content=None, tool_calls=[
            _tool_call("call_1", "draft_response", f'{{"order_id": {order.id}}}')]),
        FakeMessage(content="Here is the draft.", tool_calls=None),
    ]
    result = run_agent(db, "draft a reply", client=FakeClient(responses))
    draft = result["actions"][0]["result"]["draft"]
    assert str(order.id) in draft
    assert order.user.name in draft


def test_agent_handles_unknown_tool(db, regular_user, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    _make_order(db, regular_user)
    responses = [
        FakeMessage(content=None, tool_calls=[_tool_call("call_1", "delete_everything", "{}")]),
        FakeMessage(content="Done.", tool_calls=None),
    ]
    result = run_agent(db, "do it", client=FakeClient(responses))
    assert result["actions"][0]["result"]["error"] == "unknown tool delete_everything"


def test_agent_handles_missing_order(db, regular_user, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    responses = [
        FakeMessage(content=None, tool_calls=[
            _tool_call("call_1", "flag_fraud", '{"order_id": 99999, "reason": "x"}')]),
        FakeMessage(content="Not found.", tool_calls=None),
    ]
    result = run_agent(db, "flag it", client=FakeClient(responses))
    assert result["actions"][0]["result"]["error"] == "order not found"


def test_agent_reads_ticket(db, regular_user, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    order = _make_order(db, regular_user)
    ticket = models.SupportTicket(user_id=regular_user.id, order_id=order.id,
                                  subject="Late order", message="Where is it?")
    db.add(ticket)
    db.commit()
    responses = [
        FakeMessage(content=None, tool_calls=[
            _tool_call("call_1", "get_ticket", f'{{"ticket_id": {ticket.id}}}')]),
        FakeMessage(content="Ticket read.", tool_calls=None),
    ]
    result = run_agent(db, "read the ticket", client=FakeClient(responses))
    assert result["actions"][0]["result"]["subject"] == "Late order"
    assert result["actions"][0]["result"]["order"]["order_id"] == order.id


def test_agent_requires_api_key(db, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    with pytest.raises(HTTPException) as exc:
        run_agent(db, "anything")
    assert exc.value.status_code == 503


def test_ai_agent_endpoint_requires_admin(client, regular_user):
    headers = auth_headers(client, "alice@test.com", "alicepass")
    resp = client.post("/api/ai/agent", json={"instruction": "hi"}, headers=headers)
    assert resp.status_code == 403


def test_agent_uses_configured_base_url(db, regular_user, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "openai_base_url", "https://api.groq.com/openai/v1")
    _make_order(db, regular_user)

    captured = {}

    class SpyClient(FakeClient):
        def __init__(self, *args, **kwargs):
            captured["base_url"] = kwargs.get("base_url")
            super().__init__([
                FakeMessage(content="Done.", tool_calls=None),
            ])

    monkeypatch.setattr(openai, "OpenAI", SpyClient)
    run_agent(db, "hello", client=None)
    assert captured["base_url"] == "https://api.groq.com/openai/v1"


def test_ai_agent_endpoint_runs(client, admin_user, regular_user, db, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    order = _make_order(db, regular_user)
    responses = [
        FakeMessage(content=None, tool_calls=[
            _tool_call("call_1", "flag_fraud",
                       f'{{"order_id": {order.id}, "reason": "test"}}')]),
        FakeMessage(content="Flagged in test.", tool_calls=None),
    ]
    monkeypatch.setattr(openai, "OpenAI", lambda **kw: FakeClient(responses))
    headers = auth_headers(client, "admin@test.com", "adminpass")
    resp = client.post("/api/ai/agent", json={"instruction": "flag the order"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["reply"] == "Flagged in test."
    assert resp.json()["actions"][0]["tool"] == "flag_fraud"


def test_ai_agent_endpoint_requires_key(client, admin_user, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    headers = auth_headers(client, "admin@test.com", "adminpass")
    resp = client.post("/api/ai/agent", json={"instruction": "hi"}, headers=headers)
    assert resp.status_code == 503
