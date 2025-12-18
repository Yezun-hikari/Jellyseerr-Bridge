import pytest
from httpx import Response
from app.services.downloader_client import AniWorldDownloaderClient, DownloaderClientError

BASE_URL = "http://test-downloader:8080"
USERNAME = "testuser"
PASSWORD = "testpassword"

@pytest.fixture
def client():
    """Provides a clean instance of the AniWorldDownloaderClient for each test."""
    return AniWorldDownloaderClient(base_url=BASE_URL, username=USERNAME, password=PASSWORD)

@pytest.mark.asyncio
async def test_login_success(client: AniWorldDownloaderClient, respx_mock):
    """
    Tests a successful login, ensuring the session token is stored.
    """
    mock_route = respx_mock.post(f"{BASE_URL}/login").mock(
        return_value=Response(
            200,
            headers={"Set-Cookie": "session_token=test-token"},
            json={"message": "Login successful"}
        )
    )

    await client.login()

    assert mock_route.called
    assert "session_token" in client._client.cookies
    assert client._client.cookies["session_token"] == "test-token"

@pytest.mark.asyncio
async def test_login_failure_no_cookie(client: AniWorldDownloaderClient, respx_mock):
    """
    Tests that a DownloaderClientError is raised if the session token is not in the response.
    """
    respx_mock.post(f"{BASE_URL}/login").mock(return_value=Response(200))

    with pytest.raises(DownloaderClientError, match="Login failed: session_token not found"):
        await client.login()

@pytest.mark.asyncio
async def test_login_failure_http_error(client: AniWorldDownloaderClient, respx_mock):
    """
    Tests that a DownloaderClientError is raised on a 4xx/5xx HTTP error.
    """
    respx_mock.post(f"{BASE_URL}/login").mock(return_value=Response(500))

    with pytest.raises(DownloaderClientError):
        await client.login()

@pytest.mark.asyncio
async def test_search_anime_success(client: AniWorldDownloaderClient, respx_mock):
    """
    Tests a successful anime search, including the implicit login.
    """
    # Mock the implicit login call
    respx_mock.post(f"{BASE_URL}/login").mock(
        return_value=Response(200, headers={"Set-Cookie": "session_token=test-token"})
    )

    search_payload = [{"anime_title": "One Punch Man", "series_url": "/anime/stream/one-punch-man"}]
    search_route = respx_mock.post(f"{BASE_URL}/api/search").mock(return_value=Response(200, json=search_payload))

    result = await client.search_anime("One Punch Man")

    assert search_route.called
    assert result == search_payload

@pytest.mark.asyncio
async def test_request_auto_relogin(client: AniWorldDownloaderClient, respx_mock):
    """
    Tests the critical auto-re-login feature on a 401 Unauthorized response.
    """
    # Simulate an expired session token
    client._client.cookies["session_token"] = "expired-token"

    # Mock the sequence for the search API: first 401, then 200
    search_payload = [{"anime_title": "One Punch Man"}]
    search_route = respx_mock.post(f"{BASE_URL}/api/search").mock(
        side_effect=[
            Response(401),
            Response(200, json=search_payload),
        ]
    )

    # Mock the re-login attempt that should be triggered by the 401
    login_route = respx_mock.post(f"{BASE_URL}/login").mock(
        return_value=Response(200, headers={"Set-Cookie": "session_token=new-token"})
    )

    # This call should trigger the re-login flow
    result = await client.search_anime("One Punch Man")

    assert search_route.call_count == 2
    assert login_route.call_count == 1 # Should only be called once for the re-login
    assert "session_token" in client._client.cookies
    assert client._client.cookies["session_token"] == "new-token"
    assert result == search_payload

@pytest.mark.asyncio
async def test_request_relogin_fails_permanently(client: AniWorldDownloaderClient, respx_mock):
    """
    Tests that if re-login fails after the initial 401, the request ultimately fails.
    """
    # Simulate an expired session token
    client._client.cookies["session_token"] = "expired-token"

    # The search will always return 401, triggering re-login attempts
    respx_mock.post(f"{BASE_URL}/api/search").mock(return_value=Response(401))

    # The login attempt will also fail with 401
    respx_mock.post(f"{BASE_URL}/login").mock(return_value=Response(401))

    with pytest.raises(DownloaderClientError, match="Authentication failed"):
        await client.search_anime("One Punch Man")
