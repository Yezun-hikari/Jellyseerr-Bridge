import pytest
from httpx import AsyncClient, Response
from fastapi.testclient import TestClient
from app.main import app

API_KEY = "test-api-key"

@pytest.fixture(scope="module")
def test_client():
    """Provides a test client for the FastAPI app."""
    return TestClient(app)

@pytest.fixture
def mock_downloader_client(mocker):
    """Mocks the AniWorldDownloaderClient."""
    mock = mocker.AsyncMock()
    # Configure mock methods to be awaitable
    mock.search_anime.return_value = [{"series_url": "/anime/stream/one-punch-man"}]
    mock.get_episodes.return_value = [{"season": 1, "episode_url": "/anime/stream/one-punch-man/staffel-1/episode-1"}]
    mock.start_download.return_value = {"status": "completed"}
    return mock

@pytest.fixture(autouse=True)
def override_dependencies(test_client, mock_downloader_client):
    """Overrides the downloader client dependency for all tests."""
    from app.routes.webhook import get_downloader_client
    app.dependency_overrides[get_downloader_client] = lambda: mock_downloader_client
    yield
    app.dependency_overrides = {}

def get_valid_payload():
    return {
        "notification_type": "MEDIA_APPROVED",
        "media": {"name": "One-Punch Man"},
        "media_type": "anime",
        "request": {"seasons": [1]},
    }

def test_webhook_success_with_valid_api_key(test_client, monkeypatch):
    """
    Tests that a request with a valid API key is successful.
    """
    monkeypatch.setenv("BRIDGE_API_KEY", API_KEY)
    response = test_client.post(
        "/webhook/jellyseerr",
        headers={"X-Api-Key": API_KEY},
        json=get_valid_payload(),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "download_started"

def test_webhook_fails_with_invalid_api_key(test_client, monkeypatch):
    """
    Tests that a request with an invalid API key is rejected.
    """
    monkeypatch.setenv("BRIDGE_API_KEY", API_KEY)
    response = test_client.post(
        "/webhook/jellyseerr",
        headers={"X-Api-Key": "invalid-key"},
        json=get_valid_payload(),
    )
    assert response.status_code == 401
    assert "Invalid or missing API Key" in response.json()["detail"]

def test_webhook_fails_with_missing_api_key(test_client, monkeypatch):
    """
    Tests that a request with a missing API key is rejected.
    """
    monkeypatch.setenv("BRIDGE_API_KEY", API_KEY)
    response = test_client.post("/webhook/jellyseerr", json=get_valid_payload())
    assert response.status_code == 401
    # FastAPI's APIKeyHeader returns "Not authenticated" when the header is missing
    assert response.json()["detail"] == "Not authenticated"

def test_webhook_fails_if_server_key_is_not_configured(test_client, monkeypatch):
    """
    Tests that the endpoint returns a 500 error if the API key is not configured on the server.
    """
    # Ensure the env var is not set
    monkeypatch.delenv("BRIDGE_API_KEY", raising=False)
    response = test_client.post(
        "/webhook/jellyseerr",
        headers={"X-Api-Key": API_KEY},
        json=get_valid_payload(),
    )
    assert response.status_code == 500
    assert "API Key is not configured on the server" in response.json()["detail"]
