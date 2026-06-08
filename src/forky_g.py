#!/usr/bin/env python3
"""
Forky G — AI Content Agent for Pont Digital
Orchestrates the full monthly content cycle via APIs
Usage: python3 forky_g.py --client "la_medusa" --month "junio_2026"
"""

import os
import json
import argparse
import requests
from pathlib import Path
from higgsfield_client import HiggsFieldClient
from openai_tts_client import OpenAITTSClient
from video_editor import merge_video_audio

# ── API Keys (set as GitHub Secrets / env vars) ──────────────────────────────
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
HIGGSFIELD_API_KEY = os.environ["HIGGSFIELD_API_KEY"]
OPENAI_API_KEY     = os.environ["OPENAI_API_KEY"]
GDRIVE_FOLDER_ID   = os.environ.get("GDRIVE_FOLDER_ID", "")

# ── Clients ───────────────────────────────────────────────────────────────────
higgsfield  = HiggsFieldClient(HIGGSFIELD_API_KEY)
tts         = OpenAITTSClient(OPENAI_API_KEY)

# ── Posts configuration for La Medusa Junio 2026 ─────────────────────────────
LA_MEDUSA_POSTS = [
    {
        "id": 1, "tipo": "reel", "plataformas": ["instagram", "tiktok", "facebook"],
        "titulo": "Si tu es à Montréal, tu dois goûter ça",
        "video_source": "reel_instagram_1.mp4",
        "voiceover_fr": "Si tu es à Montréal, tu dois goûter ça. Chez La Medusa, chaque plat est préparé à la main. C'est ça, la vraie cuisine italienne.",
        "usa_video_real": True
    },
    {
        "id": 4, "tipo": "reel", "plataformas": ["tiktok", "instagram"],
        "titulo": "Pour nos clients, nous sommes aussi…",
        "video_prompt": "Elegant Italian restaurant waiter in black uniform stands confidently, warm candlelight, Montreal restaurant, cinematic 9:16 vertical, natural bright lighting",
        "voiceover_fr": "À La Medusa, notre équipe fait bien plus qu'accueillir nos clients.",
        "usa_video_real": False
    },
    {
        "id": 5, "tipo": "reel", "plataformas": ["instagram", "facebook"],
        "titulo": "Le meilleur cadeau pour la fête des pères",
        "video_source": "reel_instagram_3.mp4",
        "voiceover_fr": "Le meilleur cadeau pour la fête des pères? Une vraie soirée italienne chez La Medusa.",
        "usa_video_real": True
    },
    {
        "id": 9, "tipo": "reel", "plataformas": ["instagram", "tiktok", "facebook"],
        "titulo": "Ainsi se prépare une vraie pasta italienne",
        "video_prompt": "Close up of hands kneading fresh pasta dough in Italian restaurant kitchen, warm golden light, steam rising, artisanal pasta being cut, 9:16 vertical cinematic",
        "voiceover_fr": "Voilà comment se prépare une vraie pasta italienne chez La Medusa. Fait maison. Toujours.",
        "usa_video_real": False
    },
    {
        "id": 10, "tipo": "reel", "plataformas": ["tiktok", "instagram"],
        "titulo": "Si tu cherches une bonne cuisine italienne",
        "video_source": "reel_instagram_4.mp4",
        "voiceover_fr": "Si tu cherches une bonne cuisine italienne à Montréal, tu sais déjà où aller. À deux pas du Bell Centre.",
        "usa_video_real": True
    },
    {
        "id": 13, "tipo": "reel", "plataformas": ["instagram", "tiktok"],
        "titulo": "Depuis 1996, certaines choses n'ont pas changé",
        "video_source": "reel_instagram_4.mp4",
        "voiceover_fr": "Depuis novembre 1996, certaines choses n'ont pas changé chez La Medusa. Vingt-neuf ans à Montréal. Et ce novembre, on fête les trente.",
        "usa_video_real": True
    },
    {
        "id": 14, "tipo": "reel", "plataformas": ["tiktok"],
        "titulo": "Montréal s'éveille. Et La Medusa aussi.",
        "video_prompt": "Montreal summer streets, people on terraces, warm sunny day, cut to elegant Italian restaurant interior with warm lighting and wine glasses, 9:16 vertical",
        "voiceover_fr": "Montréal s'éveille. Et La Medusa aussi. On vous attend cet été.",
        "usa_video_real": False
    },
    {
        "id": 18, "tipo": "reel", "plataformas": ["tiktok"],
        "titulo": "Ce novembre, La Medusa fête ses 30 ans",
        "video_prompt": "Elegant Italian restaurant through the years, vintage to modern, warm candlelight, wine glasses clinking, 9:16 vertical emotional cinematic",
        "voiceover_fr": "Ce novembre, La Medusa fête ses trente ans à Montréal. On a hâte de célébrer avec vous.",
        "usa_video_real": False
    },
    {
        "id": 2, "tipo": "carousel", "plataformas": ["instagram"],
        "titulo": "Ce sont ces petits détails qui font toute la différence",
        "image_prompts": [
            "Elegant Italian restaurant table with candle and wine glass, dark moody warm lighting, 1:1 square",
            "Handmade pasta close up, flour dusted, artisanal Italian kitchen, 1:1 square",
            "Fresh bread from oven, Italian restaurant, warm golden light, 1:1 square",
            "Warm intimate restaurant interior, soft candlelight, Montreal, 1:1 square",
            "Warm welcoming restaurant host greeting guests, Italian restaurant, 1:1 square",
            "Elegant Italian restaurant at night, warm interior glow, 1:1 square"
        ]
    },
    {
        "id": 6, "tipo": "carousel", "plataformas": ["instagram"],
        "titulo": "Les plats que vous ne pouvez pas manquer",
        "image_prompts": [
            "Elegant handmade pasta dish with rich tomato sauce, fine dining Italian restaurant, dark background, 1:1",
            "Perfectly plated risotto with truffle, Italian restaurant fine dining, dark elegant background, 1:1",
            "Fresh seafood pasta, Italian restaurant, elegant plating, dark background, 1:1",
            "Classic tiramisu dessert, Italian restaurant, elegant presentation, 1:1",
            "Wine being poured into crystal glass, Italian restaurant, 1:1"
        ]
    },
    {
        "id": 7, "tipo": "static", "plataformas": ["facebook"],
        "titulo": "Papa mérite mieux qu'un barbecue",
        "image_prompt": "Red wine glass on elegant restaurant table with candle, warm Italian restaurant ambiance, Father's Day, 1:1 square dark moody"
    },
    {
        "id": 8, "tipo": "static", "plataformas": ["instagram", "facebook"],
        "titulo": "Bonne fête des pères",
        "image_prompt": "Family dinner table with wine glasses raised in toast, warm Italian restaurant, emotional celebration, 1:1 square"
    },
    {
        "id": 11, "tipo": "carousel", "plataformas": ["instagram"],
        "titulo": "Qu'est-ce que ces soirées ont en commun?",
        "image_prompts": [
            "Elegant Italian restaurant interior full of happy guests, warm ambiance, 1:1",
            "Birthday celebration at Italian restaurant, cake and wine, warm lights, 1:1",
            "Wedding reception dinner, Italian restaurant, elegant table setting, 1:1",
            "Business dinner celebration, champagne toast, Italian restaurant, 1:1",
            "Romantic dinner for two, Italian restaurant, candles and wine, CTA reservation, 1:1"
        ]
    },
    {
        "id": 15, "tipo": "carousel", "plataformas": ["instagram"],
        "titulo": "On ne sait jamais qui peut être assis à la table d'à côté",
        "image_prompts": [
            "Full elegant Italian restaurant, diverse crowd of guests, warm ambiance, 1:1",
            "VIP guests at Italian restaurant, professional athletes dining, discreet elegant, 1:1",
            "Business people at Italian restaurant, power lunch, elegant setting, 1:1",
            "Happy family at Italian restaurant, multigenerational dinner, warm light, 1:1",
            "Elegant table setting at La Medusa restaurant, CTA reservation, 1:1"
        ]
    },
    {
        "id": 16, "tipo": "static", "plataformas": ["facebook"],
        "titulo": "Vous cherchez un espace privé au cœur du centre-ville?",
        "image_prompt": "Private dining room in Italian restaurant, long elegant table, candles, projector screen, 50 people capacity, Montreal downtown, 1:1"
    },
    {
        "id": 17, "tipo": "carousel", "plataformas": ["instagram"],
        "titulo": "Vous savez choisir votre plat. Mais le vin?",
        "image_prompts": [
            "Italian white wine bottle with seafood pasta, elegant pairing, 1:1",
            "Italian red wine with meat dish, perfect pairing, elegant, 1:1",
            "Rosé wine with aperitivo selection, Italian restaurant, 1:1",
            "Sommelier presenting wine bottle, Italian restaurant, elegant, 1:1",
            "Wine cellar selection, Italian restaurant, warm lighting, CTA, 1:1"
        ]
    },
]

def claude_ask(prompt: str, system: str = None) -> str:
    """Call Claude API directly"""
    messages = [{"role": "user", "content": prompt}]
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "messages": messages
    }
    if system:
        payload["system"] = system
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json=payload
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]

def process_reel(post: dict, output_dir: Path):
    """Process a Reel post — video + voice over"""
    print(f"\n🎬 POST #{post['id']} — {post['titulo']}")
    post_dir = output_dir / f"post_{post['id']:02d}"
    post_dir.mkdir(exist_ok=True)

    video_path  = post_dir / "video.mp4"
    audio_path  = post_dir / "voiceover_fr.mp3"
    final_path  = post_dir / "final.mp4"

    # 1. Video — generate image first, then animate using its URL
    if post.get("usa_video_real") and post.get("video_source"):
        src = Path("videos") / post["video_source"]
        if src.exists():
            import shutil
            shutil.copy(src, video_path)
            print(f"  ✅ Using real video: {post['video_source']}")
        else:
            print(f"  ⚠️ Real video not found — generating AI video...")
            prompt = post.get("video_prompt", post["titulo"])
            img_path = post_dir / "frame.jpg"
            print(f"  🎨 Generating base image...")
            img_job = higgsfield.generate_image(prompt=prompt, aspect_ratio="9:16")
            image_url = higgsfield.get_result_url(img_job)
            higgsfield.download_result(img_job, str(img_path))
            print(f"  🎬 Animating image to video...")
            vid_job = higgsfield.generate_video(
                prompt=prompt,
                model="higgsfield-ai/dop/standard",
                start_image_url=image_url,
                duration=5
            )
            higgsfield.download_result(vid_job, str(video_path))
    else:
        prompt = post["video_prompt"]
        img_path = post_dir / "frame.jpg"
        print(f"  🎨 Generating base image...")
        img_job = higgsfield.generate_image(prompt=prompt, aspect_ratio="9:16")
        image_url = higgsfield.get_result_url(img_job)
        higgsfield.download_result(img_job, str(img_path))
        print(f"  🎬 Animating to video...")
        vid_job = higgsfield.generate_video(
            prompt=prompt,
            model="higgsfield-ai/dop/standard",
            start_image_url=image_url,
            duration=5
        )
        higgsfield.download_result(vid_job, str(video_path))

    # 2. Voice over (FR primary; EN/ES also supported via lang param)
    if post.get("voiceover_fr"):
        print(f"  🎙️ Generating French voice over...")
        tts.generate_voiceover(
            text=post["voiceover_fr"],
            output_path=str(audio_path),
            lang="fr"
        )

    # 3. Merge video + voiceover with FFmpeg (zero quality loss)
    if video_path.exists() and audio_path.exists():
        print(f"  🎬 Merging video + voiceover with FFmpeg...")
        merge_video_audio(str(video_path), str(audio_path), str(final_path))
    elif video_path.exists():
        final_path = video_path  # no voiceover, use video as-is

    print(f"  ✅ POST #{post['id']} complete → {final_path}")
    return {"post_id": post["id"], "dir": str(post_dir), "final": str(final_path)}

def process_images(post: dict, output_dir: Path):
    """Process carousel or static image posts"""
    print(f"\n🖼️  POST #{post['id']} — {post['titulo']}")
    post_dir = output_dir / f"post_{post['id']:02d}"
    post_dir.mkdir(exist_ok=True)

    prompts = post.get("image_prompts", [post.get("image_prompt", "")])

    for i, prompt in enumerate(prompts):
        print(f"  🎨 Generating image {i+1}/{len(prompts)}...")
        job = higgsfield.generate_image(
            prompt=f"Italian restaurant Montreal La Medusa, {prompt}, professional photography, warm elegant lighting",
            aspect_ratio="1:1"
        )
        higgsfield.download_result(job, str(post_dir / f"slide_{i+1:02d}.jpg"))

    print(f"  ✅ POST #{post['id']} complete → {post_dir}")
    return {"post_id": post["id"], "dir": str(post_dir)}

def run_cycle(client: str, month: str):
    """Run full monthly content cycle"""
    print(f"\n{'='*60}")
    print(f"  🍴 FORKY G — {client.upper()} — {month.upper()}")
    print(f"{'='*60}")

    output_dir = Path(f"output/{client}/{month}")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for post in LA_MEDUSA_POSTS:
        try:
            if post["tipo"] == "reel":
                result = process_reel(post, output_dir)
            else:
                result = process_images(post, output_dir)
            results.append({**result, "status": "ok"})
        except Exception as e:
            print(f"  ❌ POST #{post['id']} failed: {e}")
            results.append({"post_id": post["id"], "status": "error", "error": str(e)})

    # Save summary
    summary_path = output_dir / "cycle_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  ✅ CYCLE COMPLETE — {sum(1 for r in results if r['status']=='ok')}/{len(results)} posts")
    print(f"  📄 Summary: {summary_path}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forky G — Pont Digital AI Content Agent")
    parser.add_argument("--client", default="la_medusa")
    parser.add_argument("--month", default="junio_2026")
    args = parser.parse_args()
    run_cycle(args.client, args.month)
