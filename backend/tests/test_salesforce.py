"""Tests for the Salesforce integration."""
import models
from integrations import salesforce
from tests.conftest import auth_headers


class FakeResponse:
    def __init__(self, json_data=None):
        self._json = json_data or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def _make_order(db, user):
    order = models.Order(user_id=user.id, total_amount=99.99,
                         shipping_address="123 Main St", payment_method="card")
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def test_sync_order_creates_salesforce_order(db, regular_user, monkeypatch):
    order = _make_order(db, regular_user)
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs.get("json")))
        return FakeResponse({"id": "ORDERID"})

    def fake_patch(url, **kwargs):
        calls.append((url, kwargs.get("json")))
        return FakeResponse({})

    monkeypatch.setattr(salesforce, "sf_configured", lambda: True)
    monkeypatch.setattr(salesforce, "_login",
                        lambda: {"access_token": "tok",
                                 "instance_url": "https://na1.salesforce.com"})
    monkeypatch.setattr(salesforce, "_find_account", lambda h, b: "001ACCOUNT")
    monkeypatch.setattr(salesforce, "_find_contact", lambda h, b, e: None)
    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.patch", fake_patch)

    assert salesforce.sync_order(order) is True
    order_calls = [c for c in calls if "/sobjects/Order" in c[0]]
    contact_calls = [c for c in calls if "/sobjects/Contact" in c[0]]
    assert contact_calls
    assert contact_calls[0][1]["Email"] == regular_user.email
    assert contact_calls[0][1]["AccountId"] == "001ACCOUNT"
    assert order_calls[0][1]["TotalAmount"] == 99.99
    assert order_calls[0][1]["AccountId"] == "001ACCOUNT"


def test_sync_order_skipped_when_not_configured(db, regular_user, monkeypatch):
    order = _make_order(db, regular_user)
    monkeypatch.setattr(salesforce, "sf_configured", lambda: False)
    assert salesforce.sync_order(order) is False


def test_sync_order_swallows_errors(db, regular_user, monkeypatch):
    order = _make_order(db, regular_user)
    monkeypatch.setattr(salesforce, "sf_configured", lambda: True)
    monkeypatch.setattr(salesforce, "_login", lambda: None)
    assert salesforce.sync_order(order) is False


def test_create_order_triggers_salesforce_sync(client, regular_user, product, monkeypatch):
    captured = {}

    def fake_sync(order):
        captured["order"] = order
        return True

    monkeypatch.setattr(salesforce, "sync_order", fake_sync)
    headers = auth_headers(client, "alice@test.com", "alicepass")
    client.post("/api/cart", json={"product_id": product.id, "quantity": 1}, headers=headers)
    resp = client.post("/api/orders", json={
        "shipping_address": "123 Main St, NY 10001", "payment_method": "card"},
        headers=headers)
    assert resp.status_code == 201
    assert captured["order"].id == resp.json()["id"]


def test_admin_sync_endpoint(client, admin_user, regular_user, db, monkeypatch):
    order = _make_order(db, regular_user)
    monkeypatch.setattr(salesforce, "sf_configured", lambda: True)
    monkeypatch.setattr(salesforce, "sync_order", lambda o: True)
    headers = auth_headers(client, "admin@test.com", "adminpass")
    resp = client.post(f"/api/admin/orders/{order.id}/sync-salesforce", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["message"].startswith("Order")


def test_admin_sync_endpoint_not_configured(client, admin_user, regular_user, db, monkeypatch):
    order = _make_order(db, regular_user)
    monkeypatch.setattr(salesforce, "sf_configured", lambda: False)
    headers = auth_headers(client, "admin@test.com", "adminpass")
    resp = client.post(f"/api/admin/orders/{order.id}/sync-salesforce", headers=headers)
    assert resp.status_code == 503


def test_admin_sync_endpoint_requires_admin(client, regular_user, db):
    order = _make_order(db, regular_user)
    headers = auth_headers(client, "alice@test.com", "alicepass")
    resp = client.post(f"/api/admin/orders/{order.id}/sync-salesforce", headers=headers)
    assert resp.status_code == 403
