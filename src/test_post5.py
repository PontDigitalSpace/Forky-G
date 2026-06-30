"""
Single-post test runner — produces post #5 using the NEW system
(scriptwriter → director → Higgsfield) on ALREADY-DOWNLOADED footage,
skipping the slow full Drive sync (which hung on the heavy folders).

Uses media/la_medusa/fotos_videos (already on disk). Builds the clip index
from it, then runs produce_post with use_scriptwriter=True.
"""
from __future__ import annotations
import sys
from pathlib import Path

from forky_g import CONTENT_PLANS, BRAND_CONTEXTS, produce_post
from clip_indexer import build_index

CLIENT, MONTH, POST_ID = "la_medusa", "junio_2026", 5

media_dir = Path("media") / CLIENT
index_file = media_dir / "clip_index.json"

print("🔍 Building clip index from already-downloaded footage...")
build_index(CLIENT, str(media_dir), str(index_file))

post = next(p for p in CONTENT_PLANS[CLIENT][MONTH] if p["id"] == POST_ID)
out_dir = Path("output") / CLIENT / MONTH / f"post_{POST_ID:02d}"

print(f"\n🎬 Producing post #{POST_ID} with the new scriptwriter+director system...\n")
res = produce_post(post, media_dir, out_dir, logo_path=None,
                   brand_context=BRAND_CONTEXTS.get(CLIENT, ""),
                   use_scriptwriter=True, max_scenes=4)

print("\n" + "=" * 50)
print(f"✅ DONE — files produced: {len(res['files'])}")
for f in res["files"]:
    print(f"   {f}")
print("=" * 50)
