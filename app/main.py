from fastapi import FastAPI
from app.routes import sonarr

app = FastAPI(
    title="Jellyseerr to AniWorld-Downloader Bridge",
    description="A bridge service that listens for Jellyseerr webhooks to trigger downloads via the AniWorld-Downloader.",
    version="1.0.0",
)

app.include_router(sonarr.router)

@app.get("/")
async def root():
    return {"message": "Jellyseerr to AniWorld-Downloader Bridge is running!"}
