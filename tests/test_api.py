"""Unit and integration tests for Northwind FastAPI service."""

import pytest
from starlette.testclient import TestClient
from app.northwind.api.main import app
from app.northwind.config import get_settings


@pytest.fixture
def client():
    settings = get_settings()
    # Temporarily enable mock mode for offline API testing
    original_mock = settings.mock_mode
    settings.mock_mode = True
    with TestClient(app) as test_client:
        yield test_client
    settings.mock_mode = original_mock


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "target_model" in data
    assert "mock_mode" in data


def test_info_endpoint(client):
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "Northwind Support Bot (Lab Target)"
    assert data["planted_secret_name"] == "NORTHWIND_TEST_KEY_12345"


def test_chat_endpoint_empty_message(client):
    response = client.post("/chat", json={"message": "   "})
    assert response.status_code == 400


def test_chat_endpoint_valid_message(client):
    response = client.post("/chat", json={"message": "What is your return policy?"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "model" in data
    assert "latency_ms" in data

