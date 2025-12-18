import logging
from fastapi import FastAPI, Request
from app.routes import sonarr

# Configure logging
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Jellyseerr to AniWorld-Downloader Bridge",
    description="A bridge service that emulates Sonarr to trigger downloads via the AniWorld-Downloader.",
    version="1.0.0",
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log every incoming request."""
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    logger.debug(f"Request headers: {request.headers}")
    response = await call_next(request)
    return response

app.include_router(sonarr.router)

@app.get("/")
async def root():
    return {"message": "Jellyseerr to AniWorld-Downloader Bridge is running!"}
