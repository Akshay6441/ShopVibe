"""Google OAuth 2.0 login - authorization-code flow.

Frontend redirects the browser to ``/api/auth/google/login``; Google sends the
user back to ``/api/auth/google/callback`` where we exchange the code, verify
the ID token, find-or-create the ShopVibe user, and redirect to the frontend
with a ShopVibe JWT (``?token=...``).
"""
import secrets
from urllib.parse import urlencode

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import jwt as jose_jwt

from config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def google_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def make_state() -> str:
    # Server-signed CSRF state so the callback can prove we issued the redirect.
    return jose_jwt.encode(
        {"type": "oauth_state", "nonce": secrets.token_urlsafe(8)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def verify_state(state: str) -> bool:
    try:
        payload = jose_jwt.decode(
            state,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_exp": False},
        )
        return payload.get("type") == "oauth_state"
    except Exception:  # noqa: BLE001 - malformed/signed states are rejected
        return False


def authorization_url(state: str) -> str:
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
    )
    return f"{GOOGLE_AUTH_URL}?{params}"


def exchange_code(code: str) -> dict:
    """Exchange the authorization code for tokens at Google's token endpoint."""
    resp = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def verify_id_token(id_token_str: str) -> dict:
    """Verify Google's ID token and return its claims (email, name, ...)."""
    info = google_id_token.verify_oauth2_token(
        id_token_str, google_requests.Request(), settings.google_client_id
    )
    if not info.get("email"):
        raise ValueError("Google account returned no email address")
    return info


def google_user_password() -> str:
    """Random unguessable password for users created via Google (they use OAuth)."""
    return secrets.token_urlsafe(24)
