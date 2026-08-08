"""Salesforce REST API integration (OAuth 2.0 JWT bearer flow).

Syncs ShopVibe customers (Contact) and orders (Order) into a Salesforce
Developer Edition org. Requires a Connected App with a certificate:

    SF_CLIENT_ID      (Consumer Key)
    SF_CLIENT_SECRET  (Consumer Secret)
    SF_USERNAME       (an org user that can use the external app)
    SF_PRIVATE_KEY    (RSA private key PEM, newlines preserved)
    SF_LOGIN_URL      (default https://login.salesforce.com)
    SF_INSTANCE_URL   (optional - overrides the instance returned by login)

Everything is best-effort: if Salesforce isn't configured or a call fails we
log a warning and never block the request that triggered the sync.
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


def sf_configured() -> bool:
    return bool(settings.sf_client_id and settings.sf_username and settings.sf_private_key)


def _login() -> Optional[dict]:
    if not sf_configured():
        return None
    now = datetime.utcnow()
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
    return resp.json()


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


def sync_customer(user) -> Optional[dict]:
    """Upsert a customer as a Salesforce Contact inside the ShopVibe Account.

    Returns {"contact_id": ..., "account_id": ...} or None when Salesforce is
    not configured.
    """
    token = _login()
    if not token:
        return None
    base = _instance_url(token)
    headers = _headers(token)

    account_id = _find_account(headers, base)
    if not account_id:
        resp = requests.post(
            f"{base}/services/data/{API_VERSION}/sobjects/Account",
            json={"Name": SF_ACCOUNT_NAME},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        account_id = resp.json()["id"]

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

    contact_id = _find_contact(headers, base, user.email)
    sobject_url = f"{base}/services/data/{API_VERSION}/sobjects/Contact"
    if contact_id:
        requests.patch(
            f"{sobject_url}/{contact_id}", json=payload, headers=headers, timeout=15
        ).raise_for_status()
    else:
        resp = requests.post(sobject_url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        contact_id = resp.json()["id"]
    logger.info("Customer %s synced to Salesforce (contact %s)", user.email, contact_id)
    return {"contact_id": contact_id, "account_id": account_id}


def sync_order(order) -> bool:
    """Create the Salesforce Order record for a ShopVibe order (best-effort).

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
        customer = sync_customer(order.user)
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
        url = f"{base}/services/data/{API_VERSION}/sobjects/Order"
        requests.post(url, json=payload, headers=headers, timeout=15).raise_for_status()
        logger.info("Order %s synced to Salesforce", order.id)
        return True
    except Exception as exc:  # noqa: BLE001 - integration must never break checkout
        logger.warning("Salesforce sync failed for order %s: %s", getattr(order, "id", "?"), exc)
        return False
