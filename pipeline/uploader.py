"""YouTube upload pipeline.

Two credential paths, tried in this order:

1. **Refresh token from the environment** (`YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` /
   `YOUTUBE_REFRESH_TOKEN`). This is the headless path — the only one that works on a
   GitHub Actions runner. Mint the three values once with `chaosim youtube-auth`.
2. **Cached pickle + interactive browser consent** — the local developer path, unchanged.

There is no "draft" state in the YouTube Data API: `privacyStatus: "private"` is the
equivalent. Uploads from an API project that has not passed Google's compliance audit are
locked to private regardless, which suits this pipeline.
"""

import json
import os
import pickle
from datetime import datetime, timezone
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# youtube.force-ssl is required for thumbnails().set(); upload alone is insufficient.
# NOTE: if you previously authenticated with only youtube.upload, delete
# config/youtube_token.pickle so the new scope takes effect on next auth.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"
DEFAULT_TOKEN_PATH = "config/youtube_token.pickle"
DEFAULT_CLIENT_SECRET_PATH = "config/youtube_client_secret.json"
DEFAULT_CATEGORY_ID = "28"  # Science & Technology

_ENV_HINT = (
    "Set YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN. "
    "Run `python scripts/chaosim.py youtube-auth` on a machine with a browser to mint them, "
    "then store them as GitHub secrets. See docs/ci.md."
)


def token_path() -> Path:
    return Path(os.environ.get("YOUTUBE_TOKEN_PATH", DEFAULT_TOKEN_PATH))


def client_secret_path() -> Path:
    return Path(os.environ.get("YOUTUBE_CLIENT_SECRET_PATH", DEFAULT_CLIENT_SECRET_PATH))


def _headless() -> bool:
    """True on CI, where opening a consent browser is impossible."""
    return bool(os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"))


def _creds_from_env() -> Credentials | None:
    """Build credentials from a refresh token in the environment, or None if unset."""
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        return None

    return Credentials(
        None,                       # no access token yet; refresh() mints one
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )


def _refresh(creds: Credentials) -> Credentials:
    try:
        creds.refresh(Request())
    except RefreshError as exc:
        raise RuntimeError(
            f"YouTube refresh token rejected ({exc}). A token minted while the OAuth consent "
            "screen is still in 'Testing' expires after 7 days — publish the app to "
            "'In Production' in Google Cloud Console and re-run `chaosim youtube-auth`."
        ) from exc
    return creds


def get_authenticated_service():
    """Return an authenticated youtube/v3 client.

    Prefers the environment refresh token so CI never touches the filesystem cache.
    """
    creds = _creds_from_env()
    if creds:
        return build("youtube", "v3", credentials=_refresh(creds))

    cache = token_path()
    creds = None
    if cache.exists():
        with open(cache, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds = _refresh(creds)
        else:
            # Fail before run_local_server() blocks forever on a runner with no browser.
            if _headless():
                raise RuntimeError(
                    "No YouTube credentials available and no browser to obtain them. " + _ENV_HINT
                )
            secret = client_secret_path()
            if not secret.exists():
                raise RuntimeError(
                    f"OAuth client secret not found at {secret}. Download it from Google Cloud "
                    "Console (OAuth client of type 'Desktop app') or set "
                    "YOUTUBE_CLIENT_SECRET_PATH."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
            creds = flow.run_local_server(port=0)
        cache.parent.mkdir(parents=True, exist_ok=True)
        with open(cache, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def build_video_body(concept: dict, privacy: str = "private", fallback_title: str = "",
                     extra_description: str = "", category_id: str | None = None) -> dict:
    """Assemble the videos.insert request body. Pure — no network, no auth."""
    if category_id is None:
        from pipeline.config import load_settings
        category_id = (load_settings().get("youtube") or {}).get(
            "category_id", DEFAULT_CATEGORY_ID)

    description = (concept.get("description") or "") + "\n\n#Shorts"
    if extra_description:
        description = f"{description}\n\n{extra_description}"

    return {
        "snippet": {
            "title": (concept.get("caption") or fallback_title)[:100],
            "description": description,
            "tags": list(concept.get("hashtags") or []) + ["Shorts"],
            "categoryId": str(category_id),
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }


_THUMBNAIL_MIMETYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


def set_thumbnail(youtube, video_id: str, thumbnail_path: Path) -> bool:
    """Set a custom thumbnail. Returns False (without raising) on failure."""
    mimetype = _THUMBNAIL_MIMETYPES.get(Path(thumbnail_path).suffix.lower(), "image/png")
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype=mimetype),
        ).execute()
        print(f"Thumbnail set: {thumbnail_path}")
        return True
    except Exception as exc:  # noqa: BLE001 — channels w/o verification can't set thumbnails.
        print(f"Thumbnail upload skipped: {exc}")
        return False


def upload_video(video_path: Path, concept: dict, privacy: str = "private",
                 thumbnail_path: Path | None = None, extra_description: str = "") -> dict:
    """Upload video to YouTube. Returns a record dict (see write_upload_record)."""
    youtube = get_authenticated_service()

    body = build_video_body(concept, privacy, fallback_title=Path(video_path).stem,
                            extra_description=extra_description)

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
        # A private "draft" must not ping subscribers.
        notifySubscribers=False,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload {int(status.progress() * 100)}%")

    video_id = response["id"]
    url = f"https://youtube.com/shorts/{video_id}"
    print(f"Uploaded: {url}")

    thumbnail_set = False
    if thumbnail_path and Path(thumbnail_path).exists():
        thumbnail_set = set_thumbnail(youtube, video_id, Path(thumbnail_path))

    return {
        "video_id": video_id,
        "url": url,
        "privacy": privacy,
        "title": body["snippet"]["title"],
        "tags": body["snippet"]["tags"],
        "thumbnail_set": thumbnail_set,
    }


def write_upload_record(record_dir: Path, slug: str, result: dict, **extra) -> Path:
    """Persist an upload receipt to outputs/uploads/<slug>.json.

    The numbers in outputs/ are regenerable; which video id a concept became is not.
    """
    record_dir = Path(record_dir)
    record_dir.mkdir(parents=True, exist_ok=True)
    path = record_dir / f"{slug}.json"
    payload = {
        "slug": slug,
        "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **result,
        **{k: v for k, v in extra.items() if v is not None},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
