"""Tests for the Google OAuth login flow."""
import google_oauth
import models


def test_google_login_redirects_to_google(client, monkeypatch):
    monkeypatch.setattr(google_oauth.settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(google_oauth.settings, "google_client_secret", "test-secret")
    resp = client.get("/api/auth/google/login", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith(google_oauth.GOOGLE_AUTH_URL)
    assert "client_id=test-client-id" in location
    assert "state=" in location


def test_google_login_not_configured(client):
    resp = client.get("/api/auth/google/login", follow_redirects=False)
    assert resp.status_code == 503


def test_google_callback_creates_user(client, db, monkeypatch):
    monkeypatch.setattr(google_oauth, "exchange_code",
                        lambda code: {"id_token": "fake-token"})
    monkeypatch.setattr(google_oauth, "verify_id_token",
                        lambda token: {"email": "google@test.com", "name": "Google User"})
    state = google_oauth.make_state()
    resp = client.get(f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("http://localhost:3000/oauth/callback?token=")
    user = db.query(models.User).filter(models.User.email == "google@test.com").first()
    assert user is not None
    assert user.name == "Google User"


def test_google_callback_existing_user(client, db, monkeypatch):
    db.add(models.User(name="Existing", email="google@test.com", hashed_password="x"))
    db.commit()
    monkeypatch.setattr(google_oauth, "exchange_code",
                        lambda code: {"id_token": "fake-token"})
    monkeypatch.setattr(google_oauth, "verify_id_token",
                        lambda token: {"email": "google@test.com", "name": "New Name"})
    state = google_oauth.make_state()
    resp = client.get(f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert resp.status_code == 302
    assert db.query(models.User).filter(models.User.email == "google@test.com").count() == 1
    user = db.query(models.User).filter(models.User.email == "google@test.com").first()
    assert user.name == "Existing"


def test_google_callback_rejects_forged_state(client):
    resp = client.get("/api/auth/google/callback?code=abc&state=forged", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "http://localhost:3000/login?error=invalid_state"


def test_google_callback_handles_oauth_failure(client, monkeypatch):
    def boom(code):
        raise RuntimeError("google down")

    monkeypatch.setattr(google_oauth, "exchange_code", boom)
    state = google_oauth.make_state()
    resp = client.get(f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert resp.status_code == 302
    assert "error=google_login_failed" in resp.headers["location"]
