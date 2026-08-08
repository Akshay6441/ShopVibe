"""Tests for support tickets."""
import models
from tests.conftest import auth_headers


def test_create_ticket(client, regular_user):
    headers = auth_headers(client, "alice@test.com", "alicepass")
    resp = client.post("/api/tickets", json={
        "subject": "Where is my order?",
        "message": "I ordered a laptop and it has not arrived.",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "open"
    assert data["user_id"] == regular_user.id


def test_create_ticket_with_order(client, regular_user, db):
    order = models.Order(user_id=regular_user.id, total_amount=10.0,
                         shipping_address="123 Main St", payment_method="card")
    db.add(order)
    db.commit()
    headers = auth_headers(client, "alice@test.com", "alicepass")
    resp = client.post("/api/tickets", json={
        "subject": "Refund", "message": "Please refund.", "order_id": order.id},
        headers=headers)
    assert resp.status_code == 201
    assert resp.json()["order_id"] == order.id


def test_create_ticket_rejects_other_users_order(client, regular_user, admin_user, db):
    order = models.Order(user_id=admin_user.id, total_amount=10.0,
                         shipping_address="123 Main St", payment_method="card")
    db.add(order)
    db.commit()
    headers = auth_headers(client, "alice@test.com", "alicepass")
    resp = client.post("/api/tickets", json={
        "subject": "Refund", "message": "Please refund.", "order_id": order.id},
        headers=headers)
    assert resp.status_code == 404


def test_list_my_tickets(client, regular_user, db):
    db.add_all([
        models.SupportTicket(user_id=regular_user.id, subject="A", message="msg a"),
        models.SupportTicket(user_id=regular_user.id, subject="B", message="msg b"),
    ])
    db.commit()
    headers = auth_headers(client, "alice@test.com", "alicepass")
    resp = client.get("/api/tickets", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_tickets_require_auth(client):
    assert client.get("/api/tickets").status_code == 401
    assert client.post("/api/tickets",
                       json={"subject": "x", "message": "y"}).status_code == 401


def test_admin_resolves_ticket(client, regular_user, admin_user, db):
    ticket = models.SupportTicket(user_id=regular_user.id, subject="Bug", message="help")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    headers = auth_headers(client, "admin@test.com", "adminpass")
    resp = client.put(f"/api/tickets/{ticket.id}", json={"status": "resolved"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


def test_customer_cannot_resolve_ticket(client, regular_user, db):
    ticket = models.SupportTicket(user_id=regular_user.id, subject="Bug", message="help")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    headers = auth_headers(client, "alice@test.com", "alicepass")
    resp = client.put(f"/api/tickets/{ticket.id}", json={"status": "resolved"}, headers=headers)
    assert resp.status_code == 403


def test_admin_sees_all_tickets(client, regular_user, admin_user, db):
    db.add(models.SupportTicket(user_id=regular_user.id, subject="A", message="m"))
    db.commit()
    headers = auth_headers(client, "admin@test.com", "adminpass")
    resp = client.get("/api/tickets", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
