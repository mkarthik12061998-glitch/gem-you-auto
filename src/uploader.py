import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import time

CREDENTIALS_FILE = Path("credentials.json")  # adjust path as needed
YOUTUBE_UPLOAD_SCOPE = ["https://www.googleapis.com/auth/youtube.upload"]

def get_upload_status():
    """
    Returns a dict with 'available' (bool), 'status' (str), and 'message' (str).
    """
    if not CREDENTIALS_FILE.exists():
        return {
            "available": False,
            "status": "MISSING",
            "message": f"Credentials file not found at {CREDENTIALS_FILE.resolve()}"
        }
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            data = json.load(f)
        # Basic validation: check if it's a dict with expected keys
        if not isinstance(data, dict):
            raise ValueError("Invalid credentials format")
        # You can add more checks (e.g., presence of 'client_id', 'refresh_token', etc.)
        return {
            "available": True,
            "status": "VALID",
            "message": "Credentials are valid"
        }
    except (json.JSONDecodeError, ValueError) as e:
        return {
            "available": False,
            "status": "INVALID",
            "message": f"Credentials file is corrupted: {e}"
        }

def get_authenticated_service():
    status = get_upload_status()
    if not status["available"]:
        print(f"⚠️ {status['message']}. Upload will be skipped.")
        return None
    try:
        credentials = Credentials.from_authorized_user_file(str(CREDENTIALS_FILE), YOUTUBE_UPLOAD_SCOPE)
        return build("youtube", "v3", credentials=credentials)
    except Exception as e:
        print(f"⚠️ Failed to authenticate with YouTube: {e}")
        return None

def upload_to_youtube(video_path, title, description, tags, thumbnail_path=None, max_retries=3):
    """
    Uploads a video to YouTube with retry logic.
    Returns video_id if successful, else None.
    """
    youtube = get_authenticated_service()
    if youtube is None:
        print("⏭️ Upload skipped: no valid YouTube credentials.")
        return None

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags.split(",") if tags else [],
            "categoryId": "22"  # People & Blogs
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)

    for attempt in range(1, max_retries + 1):
        try:
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            response = request.execute()
            video_id = response["id"]
            print(f"✅ Uploaded successfully! Video ID: {video_id}")

            if thumbnail_path and Path(thumbnail_path).exists():
                try:
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(str(thumbnail_path))
                    ).execute()
                    print("✅ Thumbnail uploaded.")
                except Exception as e:
                    print(f"⚠️ Thumbnail upload failed: {e}")
            return video_id

        except Exception as e:
            print(f"❌ Upload attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                wait = 2 ** attempt  # exponential backoff
                print(f"⏳ Retrying in {wait} seconds...")
                time.sleep(wait)
            else:
                print("❌ All upload attempts exhausted.")
                return None
