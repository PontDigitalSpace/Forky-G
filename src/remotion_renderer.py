"""
Remotion renderer — the EDITING layer for Forky-G.

Replaces the basic FFmpeg/PIL assembly (concat + text overlay + cards + watermark)
with a programmatic, brand-driven Remotion edit: Ken Burns, captions synced to each
scene, smooth transitions, branded intro/outro + watermark.

Higgsfield still does the AI animation of REAL footage; this module takes those
animated clips (or images) + the voiceover + the brand profile and renders the
final, polished reel.

Flow:
  build_job(...) -> dict   # describe the reel (scenes, brand, audio, cards)
  render(job, out_path)    # stage assets into remotion/public, write props, run CLI

Design notes:
- Assets are staged into remotion/public/jobs/<job_id>/ and referenced by paths
  RELATIVE to public/ (the composition wraps them in staticFile()). This is the
  reliable way to feed local files to a Remotion render.
- Pure stdlib + the `npx remotion` CLI. No Anthropic call here.
- Fallback: callers should catch RemotionError and fall back to the FFmpeg path
  (video_editor.py) — see Forky-G's "cadena de fallback" principle.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent          # ~/Forky-G
REMOTION_DIR = ROOT / "remotion"
PUBLIC_DIR = REMOTION_DIR / "public"
COMPOSITION_ID = "ForkyReel"


class RemotionError(RuntimeError):
    pass


def is_available() -> bool:
    """True if node + the remotion project deps are installed."""
    if not shutil.which("node") and not Path("/usr/local/bin/node").exists():
        return False
    return (REMOTION_DIR / "node_modules" / "remotion").exists()


def _node_env() -> dict:
    env = dict(os.environ)
    # make sure Homebrew node is reachable from non-login shells
    env["PATH"] = "/usr/local/bin:/opt/homebrew/bin:" + env.get("PATH", "")
    return env


def _stage(asset: str, job_dir: Path, rel_root: Path) -> str:
    """Copy an asset into the job's public dir; return its path relative to public/."""
    src = Path(asset)
    if not src.is_absolute():
        src = (ROOT / "src" / asset).resolve() if (ROOT / "src" / asset).exists() else src.resolve()
    if not src.exists():
        raise RemotionError(f"asset not found: {asset} (resolved {src})")
    dst = job_dir / src.name
    if not dst.exists():
        shutil.copy2(src, dst)
    return str(dst.relative_to(rel_root)).replace(os.sep, "/")


def build_job(
    *,
    brand: dict,
    scenes: list[dict],
    voiceover: Optional[str] = None,
    music: Optional[str] = None,
    intro: Optional[dict] = None,
    outro: Optional[dict] = None,
    fps: int = 30,
    width: int = 1080,
    height: int = 1920,
    job_id: Optional[str] = None,
) -> dict:
    """
    Stage all assets into remotion/public/jobs/<job_id>/ and return the inputProps
    dict (paths relative to public/) ready to render.

    scenes: [{ "src": <local path>, "kind": "video"|"image",
               "duration": <seconds>, "text": <str> }]
    brand:  { name, handle?, primaryColor, bgColor, textColor, titleFont?, bodyFont? }
    intro:  { "title", "subtitle"? }   outro: { "title", "cta"? }
    """
    job_id = job_id or uuid.uuid4().hex[:8]
    job_dir = PUBLIC_DIR / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    staged_scenes = []
    for s in scenes:
        staged_scenes.append({
            "src": _stage(s["src"], job_dir, PUBLIC_DIR),
            "kind": s.get("kind", "video"),
            "durationInSeconds": float(s.get("duration", 5)),
            "text": s.get("text", "") or "",
            "note": s.get("note", ""),
        })

    props: dict = {
        "brand": brand,
        "scenes": staged_scenes,
        "intro": intro,
        "outro": outro,
        "fps": fps,
        "width": width,
        "height": height,
        "voiceover": _stage(voiceover, job_dir, PUBLIC_DIR) if voiceover else None,
        "music": _stage(music, job_dir, PUBLIC_DIR) if music else None,
    }
    props["_job_id"] = job_id
    return props


def render(job: dict, out_path: str, log: bool = True) -> str:
    """Render the reel described by `job` (from build_job) to out_path (mp4)."""
    if not (REMOTION_DIR / "node_modules").exists():
        raise RemotionError("remotion deps not installed — run `npm install` in remotion/")

    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    props_path = REMOTION_DIR / f".props_{job.get('_job_id', 'job')}.json"
    props_path.write_text(json.dumps(job, ensure_ascii=False))

    cmd = [
        "npx", "remotion", "render", COMPOSITION_ID, str(out),
        f"--props={props_path}",
        "--codec=h264",
        "--crf=18",
        "--log=" + ("info" if log else "error"),
    ]
    proc = subprocess.run(cmd, cwd=str(REMOTION_DIR), env=_node_env(),
                          capture_output=True, text=True)
    if log:
        print(proc.stdout[-2000:])
    if proc.returncode != 0:
        raise RemotionError(f"remotion render failed:\n{proc.stderr[-1200:]}")
    if not out.exists():
        raise RemotionError("render reported success but output file is missing")
    return str(out)
