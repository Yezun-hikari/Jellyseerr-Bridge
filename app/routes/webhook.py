import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.downloader_client import AniWorldDownloaderClient, DownloaderClientError
from app.security import verify_api_key

# Configure logging
logger = logging.getLogger(__name__)

# Pydantic Models for Jellyseerr Webhook Payload Validation
class Media(BaseModel):
    name: str

class Request(BaseModel):
    seasons: List[int]

class JellyseerrWebhook(BaseModel):
    notification_type: str = Field(..., alias="notification_type")
    media: Media
    media_type: str = Field(..., alias="media_type")
    request: Optional[Request] = None

# API Router
router = APIRouter()

# Dependency to get the downloader client
def get_downloader_client() -> AniWorldDownloaderClient:
    """Initializes and returns an instance of the AniWorldDownloaderClient."""
    base_url = os.getenv("DOWNLOADER_URL")
    username = os.getenv("DOWNLOADER_USER")
    password = os.getenv("DOWNLOADER_PASS")

    if not all([base_url, username, password]):
        logger.critical("Downloader environment variables are not set.")
        raise HTTPException(
            status_code=500,
            detail="Server is not configured. Missing downloader credentials.",
        )
    return AniWorldDownloaderClient(base_url=base_url, username=username, password=password)


@router.post("/webhook/jellyseerr", dependencies=[Depends(verify_api_key)])
async def handle_jellyseerr_webhook(
    payload: JellyseerrWebhook,
    client: AniWorldDownloaderClient = Depends(get_downloader_client),
):
    """
    Handles incoming webhooks from Jellyseerr.

    - Validates the payload.
    - Searches for the anime.
    - Fetches episode list.
    - Filters episodes based on requested seasons.
    - Triggers the download.
    """
    logger.info(f"Received webhook notification: {payload.notification_type} for media type: {payload.media_type}")

    if payload.notification_type != "MEDIA_APPROVED" or payload.media_type != "anime":
        return {"status": "ignored", "reason": "Notification is not for an approved anime request."}

    if not payload.request or not payload.request.seasons:
        return {"status": "ignored", "reason": "No seasons requested in the payload."}

    anime_title = payload.media.name
    requested_seasons = payload.request.seasons

    logger.info(f"Processing approved request for '{anime_title}', seasons: {requested_seasons}")

    try:
        # 1. Search for the anime
        search_results = await client.search_anime(anime_title)
        if not search_results:
            logger.warning(f"Anime '{anime_title}' not found on AniWorld.")
            raise HTTPException(status_code=404, detail=f"Anime '{anime_title}' not found.")

        # Assume the first result is the best match
        series_url = search_results[0].get("series_url")
        if not series_url:
            raise HTTPException(status_code=500, detail="Search result did not contain a series URL.")

        # 2. Get all episodes for the series
        all_episodes = await client.get_episodes(series_url)

        # 3. Filter episodes by requested seasons
        episode_urls_to_download = [
            episode["episode_url"]
            for episode in all_episodes
            if episode.get("season") in requested_seasons and episode.get("episode_url")
        ]

        if not episode_urls_to_download:
            logger.warning(f"No episodes found for seasons {requested_seasons} of '{anime_title}'.")
            return {"status": "no_episodes_found", "detail": f"No episodes found for the requested seasons of '{anime_title}'."}

        # 4. Start the download
        logger.info(f"Found {len(episode_urls_to_download)} episodes to download for '{anime_title}'.")
        download_result = await client.start_download(
            episode_urls=episode_urls_to_download,
            anime_title=anime_title,
        )

        return {"status": "download_started", "result": download_result}

    except DownloaderClientError as e:
        logger.error(f"An error occurred while communicating with the downloader: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")
