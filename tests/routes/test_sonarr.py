import pytest
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
    mock.search_anime.return_value = [{"series_url": "/anime/stream/one-punch-man"}]
    mock.get_episodes.return_value = [{"season": 1, "episode_url": "/anime/stream/one-punch-man/staffel-1/episode-1"}]
    mock.start_download.return_value = {"status": "completed"}
    return mock

@pytest.fixture(autouse=True)
def override_dependencies(test_client, mock_downloader_client):
    """Overrides the downloader client dependency for all tests."""
    from app.routes.sonarr import get_downloader_client
    app.dependency_overrides[get_downloader_client] = lambda: mock_downloader_client
    yield
    app.dependency_overrides = {}

def get_valid_sonarr_payload():
    return {
        "title": "One-Punch Man",
        "seasons": [{"seasonNumber": 1, "monitored": True}],
        "addOptions": {"searchForMissingEpisodes": True},
    }

# --- Authentication Tests ---

def test_sonarr_endpoints_fail_with_invalid_api_key(test_client, monkeypatch):
    monkeypatch.setenv("BRIDGE_API_KEY", API_KEY)
    headers = {"X-Api-Key": "invalid-key"}

    response_rootfolder = test_client.get("/api/v3/rootfolder", headers=headers)
    assert response_rootfolder.status_code == 401

    response_series = test_client.post("/api/v3/series", headers=headers, json=get_valid_sonarr_payload())
    assert response_series.status_code == 401

def test_sonarr_endpoints_fail_with_missing_api_key(test_client, monkeypatch):
    monkeypatch.setenv("BRIDGE_API_KEY", API_KEY)
    response = test_client.get("/api/v3/rootfolder")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

# --- Mock Endpoint Tests ---

def test_get_root_folder_success(test_client, monkeypatch):
    monkeypatch.setenv("BRIDGE_API_KEY", API_KEY)
    response = test_client.get("/api/v3/rootfolder", headers={"X-Api-Key": API_KEY})
    assert response.status_code == 200
    assert response.json() == [{"path": "/downloads", "id": 1}]

def test_get_quality_profile_success(test_client, monkeypatch):
    monkeypatch.setenv("BRIDGE_API_KEY", API_KEY)
    response = test_client.get("/api/v3/qualityprofile", headers={"X-Api-Key": API_KEY})
    assert response.status_code == 200
    assert response.json() == [{"name": "Any", "id": 1}]

# --- Core Logic Tests ---

def test_add_series_success(test_client, monkeypatch, mock_downloader_client):
    monkeypatch.setenv("BRIDGE_API_KEY", API_KEY)
    response = test_client.post(
        "/api/v3/series",
        headers={"X-Api-Key": API_KEY},
        json=get_valid_sonarr_payload(),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "download_started"
    mock_downloader_client.search_anime.assert_called_once_with("One-Punch Man")
    mock_downloader_client.start_download.assert_called_once()

def test_add_series_ignored_when_not_monitored(test_client, monkeypatch, mock_downloader_client):
    monkeypatch.setenv("BRIDGE_API_KEY", API_KEY)
    payload = get_valid_sonarr_payload()
    payload["addOptions"]["searchForMissingEpisodes"] = False

    response = test_client.post(
        "/api/v3/series",
        headers={"X-Api-Key": API_KEY},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    mock_downloader_client.search_anime.assert_not_called()
