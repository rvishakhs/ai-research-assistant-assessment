import pytest
from unittest.mock import AsyncMock

def test_health_endpoint(client):
    result = client.get("/health")
    assert result.status_code == 200
    assert result.json() == {"status": "ok"}

def test_query_returns_200(client):
    result = client.post("/query", json={"question": "Tell me about DS001"})
    assert result.status_code == 200

def test_query_accepts_researcher_id(client):
    r = client.post("/query", json={"question": "Which projects can alice access?", "researcher_id": "alice"})
    assert r.status_code == 200

def test_query_missing_body_returns_422(client):
    r = client.post("/query", json={})
    assert r.status_code == 422

def test_query_response_has_required_fields(client):
    r = client.post("/query", json={"question": "List all projects"})
    data = r.json()
    for field in ("answer", "sources", "trace_id", "tools_invoked", "execution_time_ms"):
        assert field in data, f"Missing field: {field}"


