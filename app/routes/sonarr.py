import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.downloader_client import AniWorldDownloaderClient, DownloaderClientError
from app.security import verify_api_key

# Configure logging
logger = logging.getLogger(__name__)

# API Router
router = APIRouter(prefix="/api/v3", dependencies=[Depends(verify_api_key)])

# --- Sonarr Emulation: Mock Endpoints ---

@router.get("/rootfolder")
async def get_root_folder():
    """
    Returns a mock root folder path. Jellyseerr requires this to connect.
    """
    return [{"path": "/downloads", "id": 1}]

@router.get("/qualityprofile")
async def get_quality_profile():
    """
    Returns a mock quality profile. Jellyseerr requires this to connect.
    """
    return [{"name": "Any", "id": 1}]

# --- Sonarr Emulation: Core Logic Endpoint ---

# Pydantic Models for Sonarr Series Payload
class Season(BaseModel):
    seasonNumber: int
    monitored: bool

class AddOptions(BaseModel):
    searchForMissingEpisodes: bool

class SonarrSeries(BaseModel):
    title: str
    seasons: List[Season]
    addOptions: AddOptions

# --- Dependency for Downloader Client ---

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

@router.post("/series")
async def add_series(
    payload: SonarrSeries,
    client: AniWorldDownloaderClient = Depends(get_downloader_client),
):
    """
    Handles the 'add series' request from Jellyseerr, emulating Sonarr.
    This is where the main download logic is triggered.
    """
    # Jellyseerr might send a request to check if a series exists before adding
    # It also sends requests for series we don't want to download immediately
    if not payload.addOptions.searchForMissingEpisodes:
        logger.info(f"Ignoring request for '{payload.title}' because searchForMissingEpisodes is false.")
        return {"status": "ignored", "reason": "Not a monitored request."}

    anime_title = payload.title
    requested_seasons = [
        season.seasonNumber for season in payload.seasons if season.monitored
    ]

    if not requested_seasons:
        return {"status": "ignored", "reason": "No seasons are monitored for download."}

    logger.info(f"Processing Sonarr request for '{anime_title}', seasons: {requested_seasons}")

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
