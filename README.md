# Jellyseerr to AniWorld-Downloader Bridge

This project is a Python FastAPI bridge that connects Jellyseerr to the [AniWorld-Downloader](https://github.com/phoenixthrush/AniWorld-Downloader). It listens for webhooks from Jellyseerr and, when an anime is approved, it automatically triggers the download process via the AniWorld-Downloader API.

## How It Works

1.  **Jellyseerr Webhook**: When a media request is approved in Jellyseerr, it sends a webhook notification to this bridge service.
2.  **Bridge Receives Webhook**: The bridge validates the webhook and confirms it's for an approved anime.
3.  **Find Anime**: The bridge takes the anime title and searches for it using the AniWorld-Downloader's search API.
4.  **Fetch Episodes**: It then fetches the list of all available episodes for the anime.
5.  **Filter and Download**: The bridge filters the episodes to match the seasons requested in Jellyseerr and sends a request to the AniWorld-Downloader to start downloading them.

## Prerequisites

-   **AniWorld-Downloader**: You must have a running instance of the AniWorld-Downloader (the `next` branch is recommended) with its web authentication enabled.
-   **Jellyseerr**: A running instance of Jellyseerr.
-   **Docker & Docker Compose**: Docker must be installed to run this bridge.
-   **Shared Docker Network**: For the services to communicate, both AniWorld-Downloader and this bridge must be part of the same Docker network (e.g., `media-network`).

## Installation

1.  **Clone the Repository**
    ```bash
    git clone <repository-url>
    cd jellyseerr-bridge
    ```

2.  **Configure Environment Variables**
    Create a `.env` file by copying the example file:
    ```bash
    cp .env.example .env
    ```
    Open the `.env` file and fill in the required details:
    -   `DOWNLOADER_URL`: The full URL to your AniWorld-Downloader instance (e.g., `http://aniworld-downloader:8080`).
    -   `DOWNLOADER_USER`: Your AniWorld-Downloader username.
    -   `DOWNLOADER_PASS`: Your AniWorld-Downloader password.
    -   `BRIDGE_API_KEY`: A secret API key that you create. This is used to secure the webhook endpoint.

3.  **Run with Docker Compose**
    Start the bridge service in detached mode:
    ```bash
    docker-compose up -d
    ```

## Jellyseerr Webhook Configuration

To properly emulate a Sonarr server, you need to provide the API key in a header.

1.  In Jellyseerr, go to **Settings > Notifications**.
2.  Click **Add > Webhook**.
3.  **Webhook URL**: `http://jellyseerr-bridge:8000/webhook/jellyseerr`
4.  Under **Custom Headers**, add a new header:
    -   **Name**: `X-Api-Key`
    -   **Value**: The same secret API key you set for `BRIDGE_API_KEY` in your `.env` file.
5.  **Notification Types**: Enable **Media Approved**.
6.  Save the webhook.

## API Endpoints

The primary endpoint is for receiving webhooks from Jellyseerr.

-   **`POST /webhook/jellyseerr`**
    -   This endpoint receives the webhook payload from Jellyseerr.
    -   **Example `curl` command to simulate a webhook:**
        ```bash
        curl -X POST http://localhost:8000/webhook/jellyseerr \\
        -H "Content-Type: application/json" \\
        -d '{
              "notification_type": "MEDIA_APPROVED",
              "media": {
                "name": "One-Punch Man"
              },
              "media_type": "anime",
              "request": {
                "seasons": [1]
              }
            }'
        ```

## Troubleshooting

-   **Authentication Errors (502 Bad Gateway)**: If you see errors related to authentication, double-check that your `DOWNLOADER_USER` and `DOWNLOADER_PASS` in the `.env` file are correct.
-   **Connection Errors**: Ensure the `DOWNLOADER_URL` is correct and that the bridge container is in the same Docker network as the AniWorld-Downloader container.
-   **Anime Not Found (404 Not Found)**: The bridge relies on the title from Jellyseerr. If the downloader's search can't find a match, this error will occur. Try searching for the anime manually in the downloader's UI to see if it's available.
-   **Successful Test Case (Reference)**: The development of this bridge was tested using the following successful case:
    -   **Action**: A Jellyseerr request for "One Punch Man" Season 1 was approved.
    -   **Webhook Payload**: Contained `anime_title: "One Punch Man"` and `seasons: [1]`.
    -   **AniWorld API Calls**:
        1.  `POST /login` -> Success, session token received.
        2.  `POST /api/search` with `anime_title: "One Punch Man"` -> Success, series URL found.
        3.  `POST /api/episodes` with series URL -> Success, list of all episodes returned.
        4.  `POST /api/download` with URLs for Season 1, `language: German Dub`, `provider: VOE` -> Success, download started.
    -   **Result**: The downloader reported `COMPLETED 12/12 episodes`.
