"""
Drive Downloader — Downloads media from Google Drive using rclone
"""
import subprocess
import os
from pathlib import Path

DRIVE_FOLDERS = {
    "fotos_videos": "1I-hKCbBTKxtRfT-D8_ft8xLuB4Y6nxcx",
    "fotos_png":    "1V4r1GD0wlKOrCLrAwLs2i71C7P5SihvV",
    "joe":          "17BBt1uKXWyo-4KoZja2XdbiXQGvE6YHc",
}

def sync_drive_folder(folder_key: str, local_path: str) -> list:
    """Sync a Drive folder to a local path using rclone. Returns list of downloaded files."""
    folder_id = DRIVE_FOLDERS.get(folder_key)
    if not folder_id:
        raise ValueError(f"Unknown folder key: {folder_key}")

    Path(local_path).mkdir(parents=True, exist_ok=True)

    cmd = [
        "rclone", "copy",
        f"gdrive:/",
        local_path,
        "--drive-root-folder-id", folder_id,
        "--transfers", "8",
        "--quiet"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️ rclone warning: {result.stderr[:200]}")

    files = list(Path(local_path).rglob("*"))
    files = [f for f in files if f.is_file()]
    print(f"  ✅ Synced {folder_key}: {len(files)} files → {local_path}")
    return files


def get_images(local_path: str) -> list:
    """Return sorted list of image files in a local folder."""
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    files = [f for f in Path(local_path).rglob("*") if f.suffix.lower() in exts]
    return sorted(files)


def get_videos(local_path: str) -> list:
    """Return sorted list of video files in a local folder."""
    exts = {".mp4", ".mov", ".avi", ".mkv"}
    files = [f for f in Path(local_path).rglob("*") if f.suffix.lower() in exts]
    return sorted(files)
