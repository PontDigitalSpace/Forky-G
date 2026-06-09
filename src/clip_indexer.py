"""
Clip Indexer — Analyzes client video clips using Claude Vision
Extracts one frame per clip, describes the content, saves to index.json
Run once per client to build the clip library.
"""
import os
import json
import base64
import subprocess
import requests
from pathlib import Path
from drive_downloader import sync_drive_folder, get_videos, get_images

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
INDEX_FILENAME = "clip_index.json"


def extract_frame(video_path: str, output_path: str, position: float = 0.33) -> str:
    """Extract a single frame from a video at the given position (0.0-1.0)."""
    # Get video duration first
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ], capture_output=True, text=True)

    duration = float(result.stdout.strip()) if result.stdout.strip() else 5.0
    timestamp = duration * position

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        output_path
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path


def describe_frame_with_claude(image_path: str) -> dict:
    """Send a frame to Claude Vision and get a structured description."""
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = Path(image_path).suffix.lower()
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext.lstrip("."), "image/jpeg")

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-haiku-4-5",
            "max_tokens": 300,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data
                        }
                    },
                    {
                        "type": "text",
                        "text": """Describe this video frame for a restaurant content agent. Be concise and specific.
Return JSON only:
{
  "subject": "main subject (e.g. pasta dish, restaurant interior, chef cooking, wine glass)",
  "setting": "where it was taken (e.g. dining room, kitchen, bar, exterior)",
  "mood": "visual mood (e.g. warm, elegant, intimate, lively)",
  "useful_for": ["list", "of", "post", "types", "this", "could", "illustrate"],
  "tags": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}"""
                    }
                ]
            }]
        },
        timeout=30
    )

    response.raise_for_status()
    text = response.json()["content"][0]["text"].strip()

    # Extract JSON from response
    if "```" in text:
        text = text.split("```")[1].replace("json", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"subject": "unknown", "setting": "unknown", "mood": "unknown", "useful_for": [], "tags": []}


def build_index(client: str, media_dir: str, output_index: str) -> dict:
    """
    Build a clip index for all videos and images in the client's media folder.
    Saves results to output_index (JSON file).
    """
    media_path = Path(media_dir)
    index = {}

    # Load existing index if it exists (to avoid re-processing)
    if Path(output_index).exists():
        with open(output_index) as f:
            index = json.load(f)
        print(f"  📂 Loaded existing index: {len(index)} clips")

    frames_dir = media_path / "_frames"
    frames_dir.mkdir(exist_ok=True)

    # Process videos
    all_videos = []
    for folder in ["fotos_videos", "joe"]:
        folder_path = media_path / folder
        if folder_path.exists():
            all_videos.extend(get_videos(str(folder_path)))

    new_clips = 0
    for video_path in all_videos:
        clip_name = Path(video_path).name
        if clip_name in index:
            continue  # Already indexed

        print(f"  🎬 Analyzing: {clip_name}")
        frame_path = str(frames_dir / f"{Path(video_path).stem}.jpg")

        try:
            extract_frame(str(video_path), frame_path)
            description = describe_frame_with_claude(frame_path)
            index[clip_name] = {
                "path": str(video_path),
                "type": "video",
                "folder": Path(video_path).parent.name,
                **description
            }
            new_clips += 1
            print(f"    ✅ {clip_name}: {description.get('subject', '?')} — {description.get('setting', '?')}")
        except Exception as e:
            print(f"    ⚠️ Failed to analyze {clip_name}: {e}")

    # Process images
    all_images = []
    for folder in ["fotos_png", "fotos_videos"]:
        folder_path = media_path / folder
        if folder_path.exists():
            all_images.extend(get_images(str(folder_path)))

    for img_path in all_images:
        clip_name = Path(img_path).name
        if clip_name in index:
            continue

        print(f"  🖼️  Analyzing: {clip_name}")
        try:
            description = describe_frame_with_claude(str(img_path))
            index[clip_name] = {
                "path": str(img_path),
                "type": "image",
                "folder": Path(img_path).parent.name,
                **description
            }
            new_clips += 1
            print(f"    ✅ {clip_name}: {description.get('subject', '?')}")
        except Exception as e:
            print(f"    ⚠️ Failed to analyze {clip_name}: {e}")

    # Save index
    with open(output_index, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n  📑 Index saved: {len(index)} total clips ({new_clips} new) → {output_index}")
    return index


def find_best_clip(index: dict, scene_description: str, used_clips: list = None) -> dict | None:
    """
    Find the best matching clip for a scene description.
    Uses keyword matching against tags, subject, setting, useful_for.
    Avoids reusing clips already used in the same reel.
    """
    if used_clips is None:
        used_clips = []

    scene_words = set(scene_description.lower().split())

    best_clip = None
    best_score = 0

    for clip_name, clip_data in index.items():
        if clip_name in used_clips:
            continue

        # Build searchable text from clip metadata
        searchable = " ".join([
            clip_data.get("subject", ""),
            clip_data.get("setting", ""),
            clip_data.get("mood", ""),
            " ".join(clip_data.get("tags", [])),
            " ".join(clip_data.get("useful_for", []))
        ]).lower()

        # Score: count matching words
        clip_words = set(searchable.split())
        score = len(scene_words & clip_words)

        if score > best_score:
            best_score = score
            best_clip = {**clip_data, "name": clip_name, "score": score}

    return best_clip if best_score > 0 else None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="la_medusa")
    args = parser.parse_args()

    media_dir = f"media/{args.client}"
    index_file = f"media/{args.client}/clip_index.json"

    # Sync Drive first
    Path(media_dir).mkdir(parents=True, exist_ok=True)
    for folder in ["fotos_videos", "fotos_png", "joe"]:
        try:
            sync_drive_folder(folder, f"{media_dir}/{folder}")
        except Exception as e:
            print(f"  ⚠️ Could not sync {folder}: {e}")

    build_index(args.client, media_dir, index_file)
