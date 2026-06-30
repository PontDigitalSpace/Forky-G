"""
Proof-of-concept: re-edit La Medusa post_09 with the new Remotion layer.

Takes the SAME real assets the FFmpeg pipeline used (4 Higgsfield-animated scene
clips + the real voiceover) and renders a polished, branded reel — so we can
compare the Remotion edit against the old final.mp4 side by side.
"""
import os
from pathlib import Path
import remotion_renderer as rr

SRC = Path(__file__).resolve().parent
POST = SRC / "output" / "la_medusa" / "junio_2026" / "post_09"

BRAND = {
    "name": "La Medusa",
    "handle": "lamedusarestaurant.ca",
    "primaryColor": "#d6b646",   # brand gold
    "bgColor": "#1d1c1a",        # deep black
    "textColor": "#f5f0e8",      # cream
    "titleFont": "PlayfairDisplay",
    "bodyFont": "Montserrat",
}

# The real animated clips from this post (in order).
scene_files = [POST / f"scene_0{i}.mp4" for i in range(1, 5)]
scene_files = [p for p in scene_files if p.exists() and p.stat().st_size > 0]

# On-screen captions: hook on the first beat, a CTA-ish line near the end.
texts = [
    "Ainsi se prépare une vraie pasta italienne.",  # the post's hook
    "",
    "Fait maison, comme depuis 1996.",
    "",
]

scenes = []
for i, p in enumerate(scene_files):
    scenes.append({
        "src": str(p),
        "kind": "video",
        "duration": 4,
        "text": texts[i] if i < len(texts) else "",
    })

voiceover = POST / "voiceover.mp3"

job = rr.build_job(
    brand=BRAND,
    scenes=scenes,
    voiceover=str(voiceover) if voiceover.exists() else None,
    intro={"title": "La Medusa", "subtitle": "Depuis 1996"},
    outro={"title": "La Medusa", "cta": "Réservation en bio 🔗"},
    job_id="poc_post09",
)

out = POST / "final_remotion.mp4"
print(f"Rendering {len(scenes)} scenes + intro/outro → {out}")
result = rr.render(job, str(out))
print(f"\n✅ Remotion POC rendered: {result}")
print(f"   Compare with the old FFmpeg edit: {POST / 'final.mp4'}")
