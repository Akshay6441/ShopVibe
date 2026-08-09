"""Salesforce REST API integration (OAuth 2.0 JWT bearer flow).

Syncs ShopVibe customers (Contact), products (Product2 + PricebookEntry),
orders (Order) and line items (OrderItem) into a Salesforce Developer Edition
org. Requires a Connected App with a certificate:

    SF_CLIENT_ID      (Consumer Key)
    SF_CLIENT_SECRET  (Consumer Secret)
    SF_USERNAME       (an org user that can use the external app)
    SF_PRIVATE_KEY    (RSA private key PEM, newlines preserved)
    SF_LOGIN_URL      (default https://login.salesforce.com)
    SF_INSTANCE_URL   (optional - overrides the instance returned by login)

Everything is best-effort: if Salesforce isn't configured or a call fails we
log a warning and never block the request that triggered the sync.

The sync is idempotent: order.salesforce_id (and the user's sf_contact_id /
sf_account_id) are persisted locally, so re-syncing an existing record updates
it (PATCH) instead of creating a duplicate.
"""
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

import requests
from jose import jwt

from config import settings
from logger import logger

API_VERSION = "v61.0"
SF_ACCOUNT_NAME = "ShopVibe Customers"

# Cached OAuth token — Salesforce access tokens live ~2h, so we only re-login
# when the cached one is about to expire.
_token_cache: dict = {"token": None, "expires_at": None}
_TOKEN_REFRESH_SKEW = 60  # seconds before expiry we consider the token stale


def sf_configured() -> bool:
    return bool(settings.sf_client_id and settings.sf_username and settings.sf_private_key)


def _login() -> Optional[dict]:
    if not sf_configured():
        return None
    now = datetime.utcnow()
    cached = _token_cache.get("token")
    if cached and _token_cache.get("expires_at") and now < _token_cache["expires_at"]:
        return cached
    assertion = jwt.encode(
        {
            "iss": settings.sf_client_id,
            "sub": settings.sf_username,
            "aud": settings.sf_login_url,
            "iat": now,
            "exp": now + timedelta(minutes=3),
        },
        settings.sf_private_key,
        algorithm="RS256",
    )
    resp = requests.post(
        f"{settings.sf_login_url}/services/oauth2/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json()
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + timedelta(
        seconds=max(0, int(token.get("expires_in", 1200)) - _TOKEN_REFRESH_SKEW)
    )
    return token


def _instance_url(token: dict) -> str:
    return (settings.sf_instance_url or token.get("instance_url") or "").rstrip("/")


def _headers(token: dict) -> dict:
    return {
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/json",
    }


def _query_one(headers: dict, base: str, query: str) -> Optional[str]:
    encoded = quote(query)
    resp = requests.get(
        f"{base}/services/data/{API_VERSION}/query/?q={encoded}",
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    records = resp.json().get("records") or []
    return records[0]["Id"] if records else None


def _find_account(headers: dict, base: str) -> Optional[str]:
    return _query_one(
        headers, base, f"SELECT Id FROM Account WHERE Name = '{SF_ACCOUNT_NAME}' LIMIT 1"
    )


def _find_contact(headers: dict, base: str, email: str) -> Optional[str]:
    safe_email = email.replace("'", "\\'")
    return _query_one(
        headers, base, f"SELECT Id FROM Contact WHERE Email = '{safe_email}' LIMIT 1"
    )


def _find_product(headers: dict, base: str, name: str) -> Optional[str]:
    safe_name = name.replace("'", "\\'")
    return _query_one(
        headers, base, f"SELECT Id FROM Product2 WHERE Name = '{safe_name}' LIMIT 1"
    )


def _find_pricebook(headers: dict, base: str) -> Optional[str]:
    return _query_one(
        headers, base, "SELECT Id FROM Pricebook2 WHERE IsStandard = true LIMIT 1"
    )


def _find_pricebook_entry(headers: dict, base: str, pricebook_id: str, product_id: str) -> Optional[str]:
    return _query_one(
        headers, base,
        f"SELECT Id FROM PricebookEntry WHERE Pricebook2Id = '{pricebook_id}' "
        f"AND Product2Id = '{product_id}' LIMIT 1",
    )


def _find_order_item(headers: dict, base: str, sf_order_id: str, pricebook_entry_id: str) -> Optional[str]:
    return _query_one(
        headers, base,
        f"SELECT Id FROM OrderItem WHERE OrderId = '{sf_order_id}' "
        f"AND PricebookEntryId = '{pricebook_entry_id}' LIMIT 1",
    )


def _post(headers: dict, base: str, sobject: str, payload: dict) -> str:
    resp = requests.post(
        f"{base}/services/data/{API_VERSION}/sobjects/{sobject}",
        json=payload, headers=headers, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _patch(headers: dict, base: str, sobject: str, sobject_id: str, payload: dict) -> None:
    requests.patch(
        f"{base}/services/data/{API_VERSION}/sobjects/{sobject}/{sobject_id}",
        json=payload, headers=headers, timeout=15,
    ).raise_for_status()


def sync_customer(user, db=None) -> Optional[dict]:
    """Upsert a customer as a Salesforce Contact inside the ShopVibe Account.

    Idempotent: the user's sf_account_id / sf_contact_id (or an email lookup)
    are used to PATCH instead of re-creating. Returns
    {"contact_id": ..., "account_id": ...} or None when Salesforce is not
    configured.
    """
    token = _login()
    if not token:
        return None
    base = _instance_url(token)
    headers = _headers(token)

    account_id = getattr(user, "sf_account_id", None)
    if not account_id:
        account_id = _find_account(headers, base)
        if not account_id:
            account_id = _post(headers, base, "Account", {"Name": SF_ACCOUNT_NAME})
        user.sf_account_id = account_id

    name = (user.name or "ShopVibe Customer").strip()
    parts = name.split()
    first = parts[0] if parts else "ShopVibe"
    last = " ".join(parts[1:]) or "Customer"
    payload = {
        "FirstName": first,
        "LastName": last,
        "Email": user.email,
        "AccountId": account_id,
        "Phone": user.phone,
        "MailingStreet": user.address,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    contact_id = getattr(user, "sf_contact_id", None)
    if contact_id:
        _patch(headers, base, "Contact", contact_id, payload)
    else:
        contact_id = _find_contact(headers, base, user.email)
        if contact_id:
            _patch(headers, base, "Contact", contact_id, payload)
        else:
            contact_id = _post(headers, base, "Contact", payload)
        user.sf_contact_id = contact_id

    if db is not None:
        db.commit()
    logger.info("Customer %s synced to Salesforce (contact %s)", user.email, contact_id)
    return {"contact_id": contact_id, "account_id": account_id}


def _sync_line_items(order, sf_order_id: str, headers: dict, base: str) -> None:
    """Best-effort sync of OrderItems. Skips items already present so a retry
    never duplicates line items. Failures are logged, never raised."""
    for item in order.items:
        try:
            product_name = (item.product.name if item.product else f"Product #{item.product_id}")
            product_id = _find_product(headers, base, product_name)
            if not product_id:
                product_id = _post(headers, base, "Product2", {
                    "Name": product_name,
                    "Description": (item.product.description if item.product else None),
                    "IsActive": True,
                })

            entry_id = None
            pricebook_id = _find_pricebook(headers, base)
            if pricebook_id:
                entry_id = _find_pricebook_entry(headers, base, pricebook_id, product_id)
                if not entry_id:
                    entry_id = _post(headers, base, "PricebookEntry", {
                        "Pricebook2Id": pricebook_id,
                        "Product2Id": product_id,
                        "UnitPrice": item.unit_price,
                        "IsActive": True,
                    })

            if entry_id and not _find_order_item(headers, base, sf_order_id, entry_id):
                _post(headers, base, "OrderItem", {
                    "OrderId": sf_order_id,
                    "PricebookEntryId": entry_id,
                    "Quantity": item.quantity,
                    "UnitPrice": item.unit_price,
                    "TotalPrice": round(item.quantity * item.unit_price, 2),
                })
        except Exception as exc:  # noqa: BLE001 - line items are best-effort
            logger.warning("Salesforce line-item sync failed (order %s, product %s): %s",
                           order.id, item.product_id, exc)


def sync_order(order, db=None) -> bool:
    """Create or update the Salesforce Order for a ShopVibe order (best-effort).

    Idempotent: if order.salesforce_id is already set, we PATCH the existing
    Salesforce Order (keeps Status in sync) instead of creating a duplicate.
    Order.AccountId is mandatory in Salesforce, so we sync the customer first.
    """
    if not sf_configured():
        return False
    try:
        token = _login()
        if not token:
            return False
        base = _instance_url(token)
        headers = _headers(token)
        customer = sync_customer(order.user, db=db)
        if not customer:
            return False

        status = order.status.value if hasattr(order.status, "value") else str(order.status)
        effective = (order.created_at or datetime.utcnow()).strftime("%Y-%m-%d")
        payload = {
            "AccountId": customer["account_id"],
            "ContactId": customer["contact_id"],
            "Status": status.title(),
            "TotalAmount": float(order.total_amount),
            "EffectiveDate": effective,
            "Description": f"ShopVibe order #{order.id}",
        }
        if order.salesforce_id:
            _patch(headers, base, "Order", order.salesforce_id, payload)
            logger.info("Order %s updated in Salesforce (%s)", order.id, order.salesforce_id)
        else:
            order.salesforce_id = _post(headers, base, "Order", payload)
            if db is not None:
                db.commit()
            logger.info("Order %s synced to Salesforce (%s)", order.id, order.salesforce_id)
            _sync_line_items(order, order.salesforce_id, headers, base)
        return True
    except Exception as exc:  # noqa: BLE001 - integration must never break checkout
        logger.warning("Salesforce sync failed for order %s: %s", getattr(order, "id", "?"), exc)
        return False
