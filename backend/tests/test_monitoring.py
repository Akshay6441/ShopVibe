"""Tests for Prometheus metrics + health."""
def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_requests_are_recorded(client):
    client.get("/api/health")
    resp = client.get("/metrics")
    assert 'http_requests_total{method="GET",path="/api/health"' in resp.text


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
