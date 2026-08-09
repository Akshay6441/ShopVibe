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


def _make_order(db, user, item=None):
    order = models.Order(user_id=user.id, total_amount=99.99,
                         shipping_address="123 Main St", payment_method="card")
    db.add(order)
    db.flush()
    if item:
        product, quantity, unit_price = item
        db.add(models.OrderItem(order_id=order.id, product_id=product.id,
                                quantity=quantity, unit_price=unit_price))
    db.commit()
    db.refresh(order)
    return order


def _patch_salesforce(monkeypatch, order_ids=None, contact_id=None, account_id="001ACCOUNT"):
    """Route all salesforce HTTP through fake_post/patch, returning ids."""
    calls = []

    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs.get("json")))
        if "/sobjects/Contact" in url:
            return FakeResponse({"id": contact_id or "003CONTACT"})
        if "/sobjects/Order" in url:
            return FakeResponse({"id": "801ORDER"})
        return FakeResponse({"id": "000MISC"})

    def fake_patch(url, **kwargs):
        calls.append(("PATCH", url, kwargs.get("json")))
        return FakeResponse({})

    monkeypatch.setattr(salesforce, "sf_configured", lambda: True)
    monkeypatch.setattr(salesforce, "_login",
                        lambda: {"access_token": "tok",
                                 "instance_url": "https://na1.salesforce.com"})
    monkeypatch.setattr(salesforce, "_find_account", lambda h, b: account_id)
    monkeypatch.setattr(salesforce, "_find_contact", lambda h, b, e: None)
    monkeypatch.setattr(salesforce, "_find_product", lambda h, b, n: None)
    monkeypatch.setattr(salesforce, "_find_pricebook", lambda h, b: "PRICEBOOK")
    monkeypatch.setattr(salesforce, "_find_pricebook_entry", lambda h, b, pb, p: None)
    monkeypatch.setattr(salesforce, "_find_order_item", lambda h, b, o, e: None)
    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.patch", fake_patch)
    return calls


def test_sync_order_creates_salesforce_order(db, regular_user, monkeypatch):
    order = _make_order(db, regular_user)
    calls = _patch_salesforce(monkeypatch)

    assert salesforce.sync_order(order, db) is True
    order_calls = [c for c in calls if "/sobjects/Order" in c[1]]
    contact_calls = [c for c in calls if "/sobjects/Contact" in c[1]]
    assert contact_calls
    assert contact_calls[0][2]["Email"] == regular_user.email
    assert contact_calls[0][2]["AccountId"] == "001ACCOUNT"
    assert order_calls[0][0] == "POST"
    assert order_calls[0][2]["TotalAmount"] == 99.99
    assert order_calls[0][2]["AccountId"] == "001ACCOUNT"
    assert order.salesforce_id == "801ORDER"
    assert regular_user.sf_contact_id == "003CONTACT"


def test_sync_order_is_idempotent(db, regular_user, monkeypatch):
    order = _make_order(db, regular_user)
    order.salesforce_id = "801EXISTING"
    db.commit()
    calls = _patch_salesforce(monkeypatch)

    assert salesforce.sync_order(order, db) is True
    order_calls = [c for c in calls if "/sobjects/Order" in c[1]]
    assert all(c[0] == "PATCH" for c in order_calls)
    assert order.salesforce_id == "801EXISTING"


def test_sync_order_propagates_status_change(db, regular_user, monkeypatch):
    order = _make_order(db, regular_user)
    order.salesforce_id = "801EXISTING"
    order.status = models.OrderStatus.shipped
    db.commit()
    calls = _patch_salesforce(monkeypatch)

    assert salesforce.sync_order(order, db) is True
    patch = [c for c in calls if "/sobjects/Order/801EXISTING" in c[1]][0]
    assert patch[2]["Status"] == "Shipped"


def test_sync_order_skipped_when_not_configured(db, regular_user, monkeypatch):
    order = _make_order(db, regular_user)
    monkeypatch.setattr(salesforce, "sf_configured", lambda: False)
    assert salesforce.sync_order(order, db) is False


def test_sync_order_swallows_errors(db, regular_user, monkeypatch):
    order = _make_order(db, regular_user)
    monkeypatch.setattr(salesforce, "sf_configured", lambda: True)
    monkeypatch.setattr(salesforce, "_login", lambda: None)
    assert salesforce.sync_order(order, db) is False


def test_sync_order_creates_line_items(db, regular_user, product, monkeypatch):
    order = _make_order(db, regular_user, item=(product, 2, 10.50))
    calls = _patch_salesforce(monkeypatch)

    assert salesforce.sync_order(order, db) is True
    paths = [c[1] for c in calls]
    assert any("/sobjects/Product2" in p for p in paths)
    assert any("/sobjects/PricebookEntry" in p for p in paths)
    assert any("/sobjects/OrderItem" in p for p in paths)


def test_sync_customer_reuses_stored_ids(db, regular_user, monkeypatch):
    regular_user.sf_account_id = "001ACCOUNT"
    regular_user.sf_contact_id = "003CONTACT"
    db.commit()
    calls = _patch_salesforce(monkeypatch)

    result = salesforce.sync_customer(regular_user, db)
    assert result == {"contact_id": "003CONTACT", "account_id": "001ACCOUNT"}
    assert all(not ("/sobjects/Contact" in c[1] and c[0] == "POST") for c in calls)
    assert not any("/sobjects/Account" in c[1] for c in calls)


def test_create_order_triggers_salesforce_sync(client, regular_user, product, monkeypatch):
    captured = {}

    def fake_sync(order, db=None):
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
    monkeypatch.setattr(salesforce, "sync_order", lambda o, db=None: True)
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
