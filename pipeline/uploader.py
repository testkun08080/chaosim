"""YouTube upload pipeline."""

import os
from pathlib import Path
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# youtube.force-ssl is required for thumbnails().set(); upload alone is insufficient.
# NOTE: if you previously authenticated with only youtube.upload, delete
# config/youtube_token.pickle so the new scope takes effect on next auth.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
TOKEN_PATH = "config/youtube_token.pickle"
CLIENT_SECRET_PATH = os.environ.get("YOUTUBE_CLIENT_SECRET_PATH", "config/youtube_client_secret.json")


def get_authenticated_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def set_thumbnail(youtube, video_id: str, thumbnail_path: Path) -> bool:
    """Set a custom thumbnail. Returns False (without raising) on failure."""
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/png"),
        ).execute()
        print(f"Thumbnail set: {thumbnail_path}")
        return True
    except Exception as exc:  # noqa: BLE001 — channels w/o verification can't set thumbnails.
        print(f"Thumbnail upload skipped: {exc}")
        return False


def upload_video(video_path: Path, concept: dict, privacy: str = "private",
                 thumbnail_path: Path | None = None) -> str:
    """Upload video to YouTube. Returns video URL."""
    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": concept.get("caption", video_path.stem)[:100],
            "description": concept.get("description", "") + "\n\n#Shorts",
            "tags": concept.get("hashtags", []) + ["Shorts"],
            "categoryId": "28",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"Uploaded: https://youtube.com/shorts/{video_id}")

    if thumbnail_path and Path(thumbnail_path).exists():
        set_thumbnail(youtube, video_id, Path(thumbnail_path))

    return f"https://youtube.com/shorts/{video_id}"
