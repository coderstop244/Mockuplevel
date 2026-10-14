"""Supabase Storage helpers."""

from pathlib import Path

from supabase import Client, create_client

from src.config import settings

VIDEO_BUCKET = "Mockvdo"

supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_KEY,
)


def download_video(storage_path: str, local_path: Path) -> Path:
    """Download a video object from Supabase Storage to a local file."""
    if not storage_path or Path(storage_path).is_absolute():
        raise ValueError("storage_path must be a non-empty relative Storage path")

    video_bytes = supabase.storage.from_(VIDEO_BUCKET).download(storage_path)
    local_path.write_bytes(video_bytes)
    return local_path
