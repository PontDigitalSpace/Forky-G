"""
Drive Downloader — Downloads media from Google Drive using rclone
"""
import re
import subprocess
import os
from pathlib import Path

DRIVE_FOLDERS = {
    "fotos_videos": "1I-hKCbBTKxtRfT-D8_ft8xLuB4Y6nxcx",
    "fotos_png":    "1V4r1GD0wlKOrCLrAwLs2i71C7P5SihvV",
    "joe":          "17BBt1uKXWyo-4KoZja2XdbiXQGvE6YHc",
}


# --- Drive link parsing (the ClickUp-task → Drive-IDs connector) ---------------
#
# Pont Digital convention: ClickUp onboarding tasks store the real client info in
# Google Drive and only hold LINKS to it. To ingest those materials we must pull
# the folder/file IDs out of whatever Drive URLs appear in the task text.
#
# Supported URL shapes:
#   https://drive.google.com/drive/folders/<ID>
#   https://drive.google.com/drive/u/0/folders/<ID>
#   https://drive.google.com/file/d/<ID>/view
#   https://drive.google.com/open?id=<ID>
#   https://drive.google.com/uc?id=<ID>
#   https://docs.google.com/document/d/<ID>/edit   (Google Doc)
#   https://docs.google.com/spreadsheets/d/<ID>/edit
#   https://docs.google.com/presentation/d/<ID>/edit

_DRIVE_PATTERNS = [
    (re.compile(r"drive\.google\.com/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]+)"), "folder"),
    (re.compile(r"drive\.google\.com/file/d/([A-Za-z0-9_-]+)"),                    "file"),
    (re.compile(r"docs\.google\.com/(?:document|spreadsheets|presentation)/d/([A-Za-z0-9_-]+)"), "gdoc"),
    (re.compile(r"drive\.google\.com/(?:open|uc)\?[^ \n]*?id=([A-Za-z0-9_-]+)"),   "file"),
]


def extract_drive_links(text: str) -> list[dict]:
    """
    Find every Google Drive / Google Docs link in a blob of text (e.g. a ClickUp
    task description or comment) and return its ID + kind.
    Returns a list of {"id": ..., "kind": "folder"|"file"|"gdoc", "url": ...},
    de-duplicated by ID, in order of appearance.
    """
    if not text:
        return []
    found: list[dict] = []
    seen: set[str] = set()
    for pattern, kind in _DRIVE_PATTERNS:
        for m in pattern.finditer(text):
            drive_id = m.group(1)
            if drive_id in seen:
                continue
            seen.add(drive_id)
            found.append({"id": drive_id, "kind": kind, "url": m.group(0)})
    return found


def sync_drive_id(drive_id: str, local_path: str, is_file: bool = False) -> list:
    """
    Sync an arbitrary Drive folder (or single file) by ID to a local path.
    Generalizes sync_drive_folder() to any ID extracted from a ClickUp link.
    """
    Path(local_path).mkdir(parents=True, exist_ok=True)
    if is_file:
        # For a single file, the parent must be addressed; rclone copies by name
        # from the file's own root. Use backend 'copyid' which fetches by file ID.
        cmd = ["rclone", "backend", "copyid", "gdrive:", drive_id, local_path, "--quiet"]
    else:
        cmd = [
            "rclone", "copy", "gdrive:/", local_path,
            "--drive-root-folder-id", drive_id,
            "--transfers", "8", "--quiet",
        ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️ rclone warning ({drive_id[:8]}): {result.stderr[:200]}")
    files = [f for f in Path(local_path).rglob("*") if f.is_file()]
    print(f"  ✅ Synced {drive_id[:8]} ({'file' if is_file else 'folder'}): {len(files)} files → {local_path}")
    return files

def sync_drive_folder(folder_key: str, local_path: str) -> list:
    """Sync a Drive folder to a local path using rclone. Returns list of downloaded files."""
    folder_id = DRIVE_FOLDERS.get(folder_key)
    if not folder_id:
        raise ValueError(f"Unknown folder key: {folder_key}")

    Path(local_path).mkdir(parents=True, exist_ok=True)

    # Only pull formats the pipeline can actually use. Client folders mix in heavy
    # camera RAW (.CR3/.ARW/.NEF/.HEIC) that the pipeline can't use and that clog the
    # download — skip them by whitelisting usable video/image formats (any case).
    cmd = [
        "rclone", "copy",
        f"gdrive:/",
        local_path,
        "--drive-root-folder-id", folder_id,
        "--include", "*.{mp4,MP4,mov,MOV,m4v,M4V,jpg,JPG,jpeg,JPEG,png,PNG,webp,WEBP}",
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
