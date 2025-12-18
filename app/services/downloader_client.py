import os
import logging
import httpx
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

class DownloaderClientError(Exception):
    """Custom exception for AniWorld-Downloader client errors."""
    pass

class AniWorldDownloaderClient:
    """
    A client for interacting with the AniWorld-Downloader API.

    Handles session management, authentication, and automatic re-login on token expiry.
    """

    def __init__(self, base_url: str, username: str, password: str):
        """
        Initializes the client.

        Args:
            base_url: The base URL of the AniWorld-Downloader instance.
            username: The username for authentication.
            password: The password for authentication.
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self._client = httpx.AsyncClient()
        self._login_attempts = 0

    async def login(self) -> None:
        """Logs into the downloader and stores the session cookie."""
        login_url = f"{self.base_url}/login"
        credentials = {"username": self.username, "password": self.password}

        logger.info(f"Attempting to log in to {self.base_url}")

        try:
            response = await self._client.post(login_url, data=credentials, timeout=10)
            response.raise_for_status()

            if "session_token" not in self._client.cookies:
                raise DownloaderClientError("Login failed: session_token not found in response cookies.")

            logger.info("Login successful. Session token acquired.")
            self._login_attempts = 0

        except httpx.HTTPStatusError as e:
            logger.error(f"Login failed with status code {e.response.status_code}")
            raise DownloaderClientError(f"Login failed with status {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Login failed due to a network error: {e}")
            raise DownloaderClientError(f"Could not connect to the downloader at {login_url}") from e

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """
        Makes a request to the downloader API, handling authentication and retries.
        """
        if "session_token" not in self._client.cookies and self._login_attempts == 0:
            await self.login()

        url = f"{self.base_url}{endpoint}"

        try:
            logger.debug(f"Making {method} request to {url}")
            response = await self._client.request(method, url, timeout=30, **kwargs)

            if response.status_code == 401:
                logger.warning("Received 401 Unauthorized. Attempting to re-login.")

                # Clear expired cookie to prevent httpx.CookieConflict
                if "session_token" in self._client.cookies:
                    del self._client.cookies["session_token"]

                self._login_attempts += 1
                if self._login_attempts >= 2:
                    logger.error("Re-login failed after multiple attempts. Aborting.")
                    raise DownloaderClientError("Authentication failed. Please check credentials.")

                try:
                    await self.login()
                except DownloaderClientError:
                    # If the re-login attempt itself fails, abort.
                    logger.error("Re-login attempt failed. Aborting for good.")
                    raise DownloaderClientError("Authentication failed. Please check credentials.")

                logger.info("Re-login successful. Retrying the original request.")
                return await self._request(method, endpoint, **kwargs)

            response.raise_for_status()
            return response.json()

        except httpx.RequestError as e:
            logger.error(f"API request to {url} failed: {e}")
            raise DownloaderClientError(f"Failed to communicate with the downloader API at {url}") from e

    async def search_anime(self, title: str) -> List[Dict[str, Any]]:
        """Searches for an anime by title."""
        logger.info(f"Searching for anime: '{title}'")
        return await self._request("POST", "/api/search", json={"anime_title": title})

    async def get_episodes(self, series_url: str) -> List[Dict[str, Any]]:
        """Gets all episodes for a given series URL."""
        logger.info(f"Fetching episodes for series: {series_url}")
        return await self._request("POST", "/api/episodes", json={"series_url": series_url})

    async def start_download(self, episode_urls: List[str], anime_title: str) -> Dict[str, Any]:
        """Starts a download for a list of episode URLs."""
        logger.info(f"Starting download for {len(episode_urls)} episodes of '{anime_title}'")

        language = "German Dub"
        provider = "VOE"

        payload = {
            "episode_urls": episode_urls,
            "anime_title": anime_title,
            "language": language,
            "provider": provider,
        }
        return await self._request("POST", "/api/download", json=payload)
