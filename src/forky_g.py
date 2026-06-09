"""
Forky-G — Automated Content Creation Agent
Pont Digital · github.com/PontDigitalSpace/Forky-G

Cycle:
  1. Read brand doc + strategy from ClickUp
  2. Create monthly plan (FASE 3)
  3. Download real media from Google Drive
  4. Produce posts (text overlay + voiceover + FFmpeg)
  5. Upload to Drive
  6. Schedule in Metricool
  7. Analyze + report (FASE 6)
"""
import os
import sys
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime

from drive_downloader import sync_drive_folder, get_images, get_videos
from post_creator import (create_static_post, create_carousel_slide,
                          add_text_overlay_to_video, create_brand_card_video,
                          add_watermark_to_video)
from openai_tts_client import OpenAITTSClient
from video_editor import merge_video_audio, trim_clip, crop_916, normalize_audio, concat_clips, grade_video, get_duration
from clip_indexer import build_index, find_best_clip
from higgsfield_client import HiggsFieldClient

# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
OPENAI_API_KEY     = os.environ["OPENAI_API_KEY"]
HIGGSFIELD_API_KEY = os.environ.get("HIGGSFIELD_API_KEY", "")
GDRIVE_FOLDER_ID   = os.environ.get("GDRIVE_FOLDER_ID", "")

# ── Clients ───────────────────────────────────────────────────────────────────
tts        = OpenAITTSClient(OPENAI_API_KEY)
higgsfield = HiggsFieldClient(HIGGSFIELD_API_KEY) if HIGGSFIELD_API_KEY else None

# ── Content Plan — La Medusa Junio 2026 ──────────────────────────────────────
# Loaded from ClickUp documents. Structure follows the Plan Mensual.
LA_MEDUSA_JUNIO_2026 = [
    {
        "id": 1, "date": "2026-06-03", "time": "07:00",
        "platforms": ["instagram", "tiktok", "facebook"],
        "format": "reel",
        "hook": "Si tu es à Montréal, tu dois goûter ça… 🍝",
        "caption_fr": "Si tu es à Montréal, tu dois goûter ça. 🍝\n\nChez La Medusa, chaque plat est préparé à la main, avec des ingrédients frais et des recettes transmises de génération en génération.\n\nC'est ça, la vraie cuisine italienne.\n\nRéservation en bio. 🔗\n\n#LaMedusaMontreal #RestaurantItalienMontreal #CuisineItalienne #MontrealFoodie #PastaFaite #DowntownMontreal",
        "media_folder": "fotos_videos",
        "media_type": "video",
        "voiceover": False,
        "pilar": "gastronomia",
        "scenes": [
            {"description": "restaurant interior dark elegant ambient warm", "duration": 3,  "text": ""},
            {"description": "pasta dish close up plate elegant handmade",    "duration": 4,  "text": "Les pâtes, faites à la main."},
            {"description": "salmon fish dish close up plate",               "duration": 4,  "text": ""},
            {"description": "risotto dish close up elegant cream",           "duration": 4,  "text": "Des recettes transmises de génération en génération."},
            {"description": "meat steak dish close up grill",                "duration": 4,  "text": ""},
            {"description": "dessert tiramisu chocolate close up",           "duration": 4,  "text": ""},
            {"description": "restaurant interior ambient warm tables wine",  "duration": 3,  "text": ""},
        ]
    },
    {
        "id": 2, "date": "2026-06-06", "time": "07:00",
        "platforms": ["instagram"],
        "format": "carousel",
        "hook": "Ce sont ces petits détails qui font toute la différence.",
        "slides": [
            {"text": "Ce sont ces petits détails qui font toute la différence.", "sub": ""},
            {"text": "Les pâtes, faites à la main.", "sub": ""},
            {"text": "Le pain, sorti du four.", "sub": ""},
            {"text": "La lumière, toujours chaleureuse.", "sub": ""},
            {"text": "L'accueil, toujours sincère.", "sub": ""},
            {"text": "Depuis 1996, certaines choses n'ont pas changé. 🍷", "sub": "Réservez votre table · lamedusarestaurant.ca", "is_cta": True},
        ],
        "caption_fr": "Ce sont ces petits détails qui font toute la différence. 🕯️\n\nLes pâtes faites à la main. Le pain sorti du four. La lumière qui réchauffe la salle. L'accueil qui fait qu'on se sent chez soi.\n\nDepuis 1996, c'est comme ça chez La Medusa.\n\nRéservation en bio. 🔗\n\n#LaMedusaMontreal #CuisineItalienneAuthentique #Depuis1996 #RestaurantItalienMontreal",
        "media_folder": "fotos_png",
        "media_type": "image",
        "voiceover": False,
        "pilar": "herencia"
    },
    {
        "id": 3, "date": "2026-06-07", "time": "13:00",
        "platforms": ["facebook"],
        "format": "static",
        "hook": "Un avis nous a adorés. L'autre… un peu moins.",
        "caption_fr": "Un avis est tombé amoureux de La Medusa. 🍷\nL'autre… un peu moins convaincu. 👀\n\nMaintenant, on veut l'avis de ceux qui connaissent vraiment :\n\nQui a raison selon toi ? 🔥\n\n#LaMedusaMontreal #RestaurantMontreal #CuisineItalienne",
        "media_folder": "fotos_png",
        "media_type": "image",
        "voiceover": False,
        "pilar": "comunidad"
    },
    {
        "id": 4, "date": "2026-06-10", "time": "07:00",
        "platforms": ["tiktok"],
        "format": "reel",
        "hook": "Pour nos clients, nous sommes aussi…",
        "caption_fr": "À La Medusa, notre équipe fait bien plus qu'accueillir nos clients 😂🍷\n#montreal #foodtok #restaurant #fyp #montrealfood #italianfood",
        "media_folder": "joe",
        "media_type": "image",
        "voiceover": False,
        "pilar": "comunidad",
        "priority": "max",
        "scenes": [
            {
                "description": "restaurant staff smiling welcoming guests entrance",
                "duration": 4,
                "text": "Pour nos clients, nous sommes aussi…",
                "higgsfield_prompt": "La Medusa Italian restaurant Montreal, warm and welcoming restaurant staff in elegant dining room, candlelight ambiance, gold tones, cinematic 9:16 vertical"
            },
            {
                "description": "chef cooking kitchen professional elegant",
                "duration": 4,
                "text": "…des amis. 🍷",
                "higgsfield_prompt": "Italian restaurant chef in professional kitchen Montreal, warm lighting, elegant atmosphere, gold and black tones, cinematic vertical 9:16"
            },
        ]
    {
        "id": 5, "date": "2026-06-12", "time": "07:00",
        "platforms": ["instagram"],
        "format": "reel",
        "hook": "Le meilleur cadeau pour la fête des pères ?",
        "caption_fr": "Le meilleur cadeau pour la fête des pères ? Une vraie soirée italienne. 🍷\n\nPas besoin de chercher loin — offrez-lui une table à La Medusa, à deux pas du centre-ville de Montréal.\n\nRéservation en bio. Les places partent vite ce week-end. 🔗\n\n#FeteDesPeres #LaMedusaMontreal #RestaurantItalienMontreal #CuisineItalienne",
        "media_folder": "fotos_videos",
        "media_type": "video",
        "voiceover": True,
        "voiceover_text": "Le meilleur cadeau pour la fête des pères ? Pas un barbecue. Une vraie soirée italienne. Offrez-lui une table à La Medusa.",
        "pilar": "celebraciones",
        "priority": "max",
        "scenes": [
            {"description": "wine glass pouring bottle elegant",               "duration": 3, "text": ""},
            {"description": "meat steak dish elegant restaurant",               "duration": 4, "text": "Une vraie soirée italienne."},
            {"description": "restaurant interior warm tables couple dining",    "duration": 4, "text": ""},
            {"description": "pasta dish close up handmade elegant",            "duration": 4, "text": "Offrez-lui La Medusa. 🍷"},
        ]
    },
    {
        "id": 6, "date": "2026-06-13", "time": "07:00",
        "platforms": ["instagram"],
        "format": "carousel",
        "hook": "Les plats que vous ne pouvez pas manquer, selon nos chefs.",
        "slides": [
            {"text": "Les plats que vous ne pouvez pas manquer, selon nos chefs.", "sub": "", "is_cover": True},
            {"text": "Osso Buco", "sub": "La spécialité de la maison depuis 1996."},
            {"text": "Linguine alle Vongole", "sub": "Palourdes fraîches, ail, vin blanc."},
            {"text": "Veau Marsala", "sub": "Sauce au vin Marsala, champignons."},
            {"text": "Et toi, lequel choisirais-tu ?", "sub": "Réservez · lamedusarestaurant.ca 🍷", "is_cta": True},
        ],
        "caption_fr": "Quand on a demandé à nos chefs quels plats ils recommandaient sans hésiter… voilà ce qu'ils ont dit. 🍝\n\nEt toi, lequel choisirais-tu ? Dis-nous en commentaire 👇\n\nRéservation en bio. 🔗\n\n#LaMedusaMontreal #CuisineItalienneAuthentique #PastaFaite #RestaurantItalienMontreal",
        "media_folder": "fotos_png",
        "media_type": "image",
        "voiceover": False,
        "pilar": "gastronomia"
    },
    {
        "id": 7, "date": "2026-06-14", "time": "09:00",
        "platforms": ["facebook"],
        "format": "static",
        "hook": "Papa mérite mieux qu'un barbecue.",
        "caption_fr": "Papa mérite mieux qu'un barbecue. 🍷\n\nOffrez-lui une soirée à La Medusa — cuisine italienne authentique, atmosphère chaleureuse, service attentionné.\n\n📍 1218 Rue Drummond, Montréal\n📞 (514) 878-4499\n🔗 lamedusarestaurant.ca\n\n#FeteDesPeres #LaMedusaMontreal #RestaurantMontreal #CuisineItalienne",
        "media_folder": "fotos_videos",
        "media_type": "image",
        "voiceover": False,
        "pilar": "celebraciones"
    },
    {
        "id": 8, "date": "2026-06-15", "time": "08:00",
        "platforms": ["instagram", "facebook"],
        "format": "static",
        "hook": "Bonne fête des pères.",
        "caption_fr": "Bonne fête des pères. 🍷\n\nÀ tous ceux qui partagent leur table, leur passion et leurs recettes.\n\nLa Medusa · Depuis 1996.\n\n#FeteDesPeres #LaMedusaMontreal #Depuis1996",
        "media_folder": "fotos_png",
        "media_type": "image",
        "voiceover": False,
        "pilar": "celebraciones"
    },
    {
        "id": 9, "date": "2026-06-17", "time": "07:00",
        "platforms": ["instagram"],
        "format": "reel",
        "hook": "Ainsi se prépare une vraie pasta italienne à La Medusa…",
        "caption_fr": "Voilà comment se prépare une vraie pasta italienne chez La Medusa. 🍝\n\nDe la farine, des mains, et des années de savoir-faire. Tout est fait maison, comme ça a toujours été depuis 1996.\n\nRéservation en bio. 🔗\n\n#LaMedusaMontreal #PastaFaite #CuisineItalienneAuthentique #FaitMaison #Depuis1996",
        "media_folder": "fotos_videos",
        "media_type": "video",
        "voiceover": True,
        "voiceover_text": "Voilà comment se prépare une vraie pasta italienne chez La Medusa. De la farine, des mains, et des années de savoir-faire. Fait maison. Toujours.",
        "pilar": "gastronomia",
        "scenes": [
            {"description": "pasta sauce cooking pan stovetop kitchen",      "duration": 4, "text": ""},
            {"description": "pasta dish close up plate elegant handmade",    "duration": 4, "text": "Fait à la main. Chaque jour."},
            {"description": "chef cooking kitchen professional",             "duration": 4, "text": ""},
            {"description": "restaurant interior warm lighting elegant",     "duration": 3, "text": ""},
        ]
    },
    {
        "id": 10, "date": "2026-06-18", "time": "07:00",
        "platforms": ["tiktok"],
        "format": "reel",
        "hook": "Si tu cherches une bonne cuisine italienne, tu sais déjà où aller.",
        "caption_fr": "Si tu cherches une bonne cuisine italienne à Montréal, tu sais déjà où aller. 📍\n#montreal #foodtok #italianfood #fyp #montrealfood #restaurant",
        "media_folder": "fotos_videos",
        "media_type": "video",
        "voiceover": False,
        "pilar": "comunidad",
        "priority": "max",
        "scenes": [
            {"description": "restaurant exterior storefront entrance street",  "duration": 3, "text": "Tu sais déjà où aller."},
            {"description": "food dish close up plate elegant",                "duration": 4, "text": ""},
            {"description": "restaurant interior atmosphere warm dining",      "duration": 3, "text": "📍 Montréal, Rue Drummond"},
        ]
    },
    {
        "id": 11, "date": "2026-06-20", "time": "07:00",
        "platforms": ["instagram"],
        "format": "carousel",
        "hook": "Qu'est-ce que ces soirées ont en commun ?",
        "slides": [
            {"text": "Qu'est-ce que ces soirées ont en commun ?", "sub": "", "is_cover": True},
            {"text": "🎂 Un anniversaire inoubliable.", "sub": "La table qui rend la soirée mémorable."},
            {"text": "💑 Un anniversaire de mariage.", "sub": "L'endroit où l'on revient chaque année."},
            {"text": "🥂 Une promotion célébrée.", "sub": "Parce que certains moments méritent mieux qu'un bar."},
            {"text": "Elles ont toutes eu lieu à La Medusa.", "sub": "Réservez votre moment · lamedusarestaurant.ca 🍷", "is_cta": True},
        ],
        "caption_fr": "Qu'est-ce que ces soirées ont en commun ? 🍷\n\nUn anniversaire. Un mariage. Une promotion. Un reencuentro. Une première date.\n\nElles ont toutes trouvé leur place à La Medusa.\n\nRéservation en bio — les week-ends se remplissent vite. 🔗\n\n#LaMedusaMontreal #SoireeItalienne #RestaurantItalienMontreal #FineDining",
        "media_folder": "fotos_png",
        "media_type": "image",
        "voiceover": False,
        "pilar": "celebraciones"
    },
    {
        "id": 12, "date": "2026-06-21", "time": "13:00",
        "platforms": ["facebook"],
        "format": "reel",
        "hook": "Saviez-vous que chez La Medusa, toutes les pâtes sont faites à la main ?",
        "caption_fr": "Saviez-vous que chez La Medusa, toutes les pâtes sont faites à la main ? 🍝\n\nChaque jour, avec les mêmes gestes et la même passion qu'en 1996.\n\nVenez goûter la différence : lamedusarestaurant.ca\n\n#LaMedusaMontreal #CuisineItalienne #FaitMaison #RestaurantMontreal",
        "media_folder": "fotos_videos",
        "media_type": "video",
        "reuse_from": 9,
        "voiceover": False,
        "pilar": "gastronomia"
    },
    {
        "id": 13, "date": "2026-06-24", "time": "07:00",
        "platforms": ["instagram"],
        "format": "reel",
        "hook": "Depuis 1996, certaines choses n'ont pas changé à La Medusa.",
        "caption_fr": "Depuis novembre 1996, certaines choses n'ont pas changé chez La Medusa. 🍷\n\nLa passion pour la vraie cuisine italienne. L'accueil chaleureux. Les recettes faites maison.\n\n29 ans à Montréal. Et ce novembre… on fête les 30.\n\nMerci à tous ceux qui font partie de cette histoire. 🙏\n\n#LaMedusaMontreal #Depuis1996 #RestaurantItalienMontreal #30Ans",
        "media_folder": "fotos_videos",
        "media_type": "video",
        "voiceover": True,
        "voiceover_text": "Depuis novembre 1996, certaines choses n'ont pas changé chez La Medusa. La passion. L'authenticité. La famiglia. Vingt-neuf ans à Montréal. Et ce novembre… on fête les trente.",
        "pilar": "herencia",
        "priority": "max",
        "scenes": [
            {"description": "restaurant interior elegant historic warm",      "duration": 4, "text": "Depuis 1996."},
            {"description": "pasta dish handmade close up elegant",          "duration": 4, "text": ""},
            {"description": "restaurant dining room warm guests atmosphere",  "duration": 4, "text": "29 ans de passion."},
            {"description": "wine glass elegant table setting fine dining",   "duration": 3, "text": ""},
        ]
    },
    {
        "id": 14, "date": "2026-06-25", "time": "07:00",
        "platforms": ["tiktok"],
        "format": "reel",
        "hook": "Montréal s'éveille. Et La Medusa aussi.",
        "caption_fr": "Montréal s'éveille. Et La Medusa aussi. 🍷 On vous attend cet été !\n#montreal #summer #foodtok #italianfood #fyp #montrealfood",
        "media_folder": "fotos_videos",
        "media_type": "video",
        "voiceover": False,
        "pilar": "celebraciones",
        "scenes": [
            {"description": "restaurant exterior storefront montreal street", "duration": 3, "text": "Montréal s'éveille."},
            {"description": "restaurant interior tables warm summer light",   "duration": 4, "text": ""},
            {"description": "food dish close up elegant plate",               "duration": 3, "text": "La Medusa aussi. 🍷"},
        ]
    },
    {
        "id": 15, "date": "2026-06-27", "time": "07:00",
        "platforms": ["instagram"],
        "format": "carousel",
        "hook": "On ne sait jamais qui peut être assis à la table d'à côté.",
        "slides": [
            {"text": "On ne sait jamais qui peut être assis à la table d'à côté.", "sub": "", "is_cover": True},
            {"text": "La Medusa est un véritable point de rencontre à Montréal.", "sub": ""},
            {"text": "Des joueurs. Des décideurs. Des familles. Des amis.", "sub": ""},
            {"text": "Tous autour de la même table italienne.", "sub": ""},
            {"text": "Et toi, à quelle table seras-tu ce soir ? 🍷", "sub": "Réservez · lamedusarestaurant.ca", "is_cta": True},
        ],
        "caption_fr": "On ne sait jamais qui peut être assis à la table d'à côté. 👀🍷\n\nChez La Medusa, c'est l'une des choses qui rend chaque soirée unique.\n\nRéservation en bio. 🔗\n\n#LaMedusaMontreal #RestaurantItalienMontreal #BellCentre #MontrealFoodie #FineDining",
        "media_folder": "fotos_png",
        "media_type": "image",
        "voiceover": False,
        "pilar": "sala_privada"
    },
    {
        "id": 16, "date": "2026-06-28", "time": "09:00",
        "platforms": ["facebook"],
        "format": "static",
        "hook": "Vous cherchez un espace privé au cœur du centre-ville de Montréal ?",
        "caption_fr": "Vous cherchez un espace privé au cœur du centre-ville de Montréal ? 🍷\n\nLa Medusa offre une salle privée au sous-sol, idéale pour :\n✓ Dîners d'affaires et réunions corporatives\n✓ Célébrations privées et événements exclusifs\n✓ Réceptions jusqu'à 50 personnes\n\n📍 À deux pas du Bell Centre\n📞 (514) 878-4499\n🔗 lamedusarestaurant.ca\n\n#LaMedusaMontreal #SallePrivee #EvenementsCorporatifs #RestaurantMontreal",
        "media_folder": "fotos_png",
        "media_type": "image",
        "voiceover": False,
        "pilar": "sala_privada"
    },
    {
        "id": 17, "date": "2026-06-27", "time": "07:00",
        "platforms": ["instagram"],
        "format": "carousel",
        "hook": "Vous savez choisir votre plat. Mais le vin ?",
        "slides": [
            {"text": "Vous savez choisir votre plat. Mais le vin ?", "sub": "", "is_cover": True},
            {"text": "Osso Buco + Barolo", "sub": "Un mariage classique du Nord de l'Italie."},
            {"text": "Linguine alle Vongole + Pinot Grigio", "sub": "Fraîcheur et légèreté pour les fruits de mer."},
            {"text": "Veau Marsala + Primitivo", "sub": "Richesse et profondeur pour la viande."},
            {"text": "Demandez conseil à notre équipe. 🍷", "sub": "Réservez · lamedusarestaurant.ca", "is_cta": True},
        ],
        "caption_fr": "Vous savez choisir votre plat. Mais le vin ? 🍷\n\nChez La Medusa, notre sélection de vins italiens est choisie pour accompagner chaque plat à la perfection.\n\nGlissez pour découvrir nos accords préférés 👉\n\nRéservation en bio. 🔗\n\n#LaMedusaMontreal #MaridageVin #CuisineItalienneAuthentique #VinItalien",
        "media_folder": "fotos_png",
        "media_type": "image",
        "voiceover": False,
        "pilar": "gastronomia"
    },
    {
        "id": 18, "date": "2026-06-28", "time": "07:00",
        "platforms": ["tiktok"],
        "format": "reel",
        "hook": "Ce novembre, La Medusa fête ses 30 ans à Montréal.",
        "caption_fr": "Ce novembre, La Medusa fête ses 30 ans à Montréal. 🍷 On a hâte de célébrer avec vous.\n#montreal #foodtok #italianfood #fyp #depuis1996 #30ans",
        "media_folder": "fotos_videos",
        "media_type": "video",
        "reuse_from": 13,
        "voiceover": False,
        "pilar": "herencia"
    },
]

CONTENT_PLANS = {
    "la_medusa": {
        "junio_2026": LA_MEDUSA_JUNIO_2026
    }
}

# ── Platform video duration limits (seconds) ─────────────────────────────────
# Based on 2026 algorithm data: completion rate is the #1 ranking factor.
# Ideal = sweet spot for engagement. Max = hard cap before trimming.
PLATFORM_DURATION = {
    "tiktok":    {"ideal": 20, "max": 35},   # viral sweet spot 11-18s, food ok to 35s
    "instagram": {"ideal": 25, "max": 45},   # 20-30s ideal, 90s limit but 45s is enough
    "facebook":  {"ideal": 25, "max": 45},   # same as instagram
}

def get_max_duration_for_post(post: dict) -> float:
    """Return the shortest max duration across the post's platforms."""
    platforms = post.get("platforms", ["instagram"])
    maxes = [PLATFORM_DURATION.get(p, {"max": 45})["max"] for p in platforms]
    return min(maxes)  # most restrictive platform wins


def produce_post(post: dict, media_dir: Path, post_dir: Path, logo_path: str = None) -> dict:
    """Produce one post: download media, create visuals, generate voiceover."""
    post_id = post["id"]
    fmt = post["format"]
    post_dir.mkdir(parents=True, exist_ok=True)

    result = {"post_id": post_id, "files": [], "caption": post["caption_fr"]}

    # Get media files
    folder_key = post.get("media_folder", "fotos_png")
    media_type  = post.get("media_type", "image")
    media_local = media_dir / folder_key

    if media_type == "video":
        media_files = get_videos(str(media_local))
    else:
        media_files = get_images(str(media_local))

    if not media_files:
        print(f"  ⚠️ No media found in {media_local} — skipping post #{post_id}")
        return result

    # Pick media file based on post index (cycle through available files)
    idx = (post_id - 1) % len(media_files)
    main_media = str(media_files[idx])

    # ── STATIC POST ──────────────────────────────────────────────────────────
    if fmt == "static":
        out = str(post_dir / "post.jpg")
        create_static_post(
            photo_path=main_media,
            output_path=out,
            text_lines=[
                {"text": post["hook"], "style": "subtitle", "color": "#d6b646"},
                {"text": "La Medusa · lamedusarestaurant.ca", "style": "body", "color": "#f5f0e8", "size": 28}
            ],
            logo_path=logo_path
        )
        result["files"].append(out)

    # ── CAROUSEL ─────────────────────────────────────────────────────────────
    elif fmt == "carousel":
        slides = post.get("slides", [])
        slide_files = []
        img_files = get_images(str(media_local))

        for i, slide in enumerate(slides):
            out = str(post_dir / f"slide_{i+1:02d}.jpg")
            is_cta = slide.get("is_cta", False)
            is_cover = slide.get("is_cover", i == 0)

            if is_cta:
                photo = main_media
            else:
                photo = str(img_files[i % len(img_files)]) if img_files else main_media

            create_carousel_slide(
                photo_path=photo,
                output_path=out,
                main_text=slide["text"],
                sub_text=slide.get("sub", ""),
                is_cover=is_cover,
                is_cta=is_cta,
                logo_path=logo_path if is_cta else None
            )
            slide_files.append(out)
            print(f"  🖼️  Slide {i+1}/{len(slides)} → {out}")

        result["files"] = slide_files

    # ── REEL ─────────────────────────────────────────────────────────────────
    elif fmt == "reel":
        import shutil

        # Handle reuse from another post
        reuse_from = post.get("reuse_from")
        if reuse_from:
            src_dir = post_dir.parent / f"post_{reuse_from:02d}"
            src_video = next(src_dir.glob("final*.mp4"), None) if src_dir.exists() else None
            if src_video:
                out = str(post_dir / "final.mp4")
                shutil.copy(str(src_video), out)
                result["files"].append(out)
                print(f"  ♻️  Reused video from post #{reuse_from}")
                return result

        # Load clip index
        index_file = media_dir / "clip_index.json"
        clip_index = {}
        if index_file.exists():
            with open(index_file) as f:
                clip_index = json.load(f)

        # Get scenes for this post
        scenes = post.get("scenes", [])
        if not scenes:
            # Fallback: 3-scene structure using hook as description
            scenes = [
                {"description": post["hook"], "duration": 4, "text": ""},
                {"description": "restaurant interior warm elegant", "duration": 4, "text": post["hook"]},
                {"description": "food dish close up plate elegant", "duration": 4, "text": ""},
            ]

        # ── INTRO CARD ──────────────────────────────────────────────────────
        intro_card = str(post_dir / "card_intro.mp4")
        try:
            create_brand_card_video(intro_card, post["hook"], card_type="intro", duration=2.0)
        except Exception as e:
            print(f"  ⚠️ Intro card failed: {e}")
            intro_card = None

        # ── PRODUCE EACH SCENE ──────────────────────────────────────────────
        scene_clips = []
        used_clips = []

        for i, scene in enumerate(scenes):
            scene_out = str(post_dir / f"scene_{i+1:02d}.mp4")
            scene_desc = scene.get("description", "")
            scene_dur  = scene.get("duration", 5)
            scene_text = scene.get("text", "")

            # RULE: Use real client footage first. Only use Higgsfield if scene missing.
            best = find_best_clip(clip_index, scene_desc, used_clips) if clip_index else None

            if best:
                # ✅ Real footage found — edit with FFmpeg
                print(f"  🎬 Scene {i+1}: using real clip '{best['name']}' ({best.get('subject','?')})")
                used_clips.append(best["name"])
                raw = str(post_dir / f"raw_{i+1:02d}.mp4")

                if best["type"] == "video":
                    trim_clip(best["path"], raw, start=0, duration=scene_dur)
                else:
                    # Photo → animate with Ken Burns
                    from video_editor import image_to_video
                    image_to_video(best["path"], raw, duration=scene_dur)

                # Crop to 9:16
                cropped = str(post_dir / f"cropped_{i+1:02d}.mp4")
                crop_916(raw, cropped)

                # Color grading
                grade_video(cropped, scene_out, style="warm_gold")

                # Add text overlay if scene has text
                if scene_text:
                    graded = scene_out
                    scene_out = str(post_dir / f"scene_text_{i+1:02d}.mp4")
                    try:
                        add_text_overlay_to_video(graded, scene_out, scene_text, position="bottom")
                    except Exception:
                        scene_out = graded

            elif higgsfield:
                # ❌ No real footage — generate with Higgsfield
                # Use higgsfield_prompt if defined, otherwise build a cinematic prompt from description
                hf_img_prompt = scene.get(
                    "higgsfield_prompt",
                    f"La Medusa Italian restaurant Montreal, {scene_desc}, warm candlelight, "
                    f"elegant fine dining, gold and black tones, cinematic 9:16 vertical"
                )
                hf_vid_prompt = scene.get(
                    "higgsfield_vid_prompt",
                    f"{scene_desc}, slow cinematic camera movement, warm elegant atmosphere"
                )
                print(f"  🤖 Scene {i+1}: no real footage — generating with Higgsfield")
                print(f"     Prompt: {hf_img_prompt[:80]}…")
                try:
                    img_job = higgsfield.generate_image(
                        prompt=hf_img_prompt,
                        aspect_ratio="9:16"
                    )
                    img_url = higgsfield.get_result_url(img_job)
                    img_path = str(post_dir / f"hf_img_{i+1:02d}.jpg")
                    higgsfield.download_result(img_job, img_path)

                    vid_job = higgsfield.generate_video(
                        prompt=hf_vid_prompt,
                        model="higgsfield-ai/dop/standard",
                        start_image_url=img_url,
                        duration=scene_dur
                    )
                    higgsfield.download_result(vid_job, scene_out)

                    # Color grade the generated clip
                    graded = str(post_dir / f"graded_{i+1:02d}.mp4")
                    grade_video(scene_out, graded, style="warm_gold")
                    scene_out = graded

                    if scene_text:
                        with_text = str(post_dir / f"scene_text_{i+1:02d}.mp4")
                        try:
                            add_text_overlay_to_video(scene_out, with_text, scene_text, "bottom")
                            scene_out = with_text
                        except Exception:
                            pass
                except Exception as e:
                    print(f"  ⚠️ Higgsfield scene {i+1} failed: {e} — skipping")
                    continue
            else:
                print(f"  ⚠️ Scene {i+1}: no footage and Higgsfield not available — skipping")
                continue

            scene_clips.append(scene_out)

        if not scene_clips:
            print(f"  ❌ No scenes produced for post #{post_id}")
            return result

        # ── OUTRO CARD ──────────────────────────────────────────────────────
        outro_card = str(post_dir / "card_outro.mp4")
        try:
            create_brand_card_video(outro_card, "Réservez votre table",
                                    "lamedusarestaurant.ca",
                                    card_type="outro", duration=2.0)
        except Exception as e:
            print(f"  ⚠️ Outro card failed: {e}")
            outro_card = None

        # ── ASSEMBLE: [intro] + scenes + [outro] ────────────────────────────
        all_clips = []
        if intro_card and Path(intro_card).exists():
            all_clips.append(intro_card)
        all_clips.extend(scene_clips)
        if outro_card and Path(outro_card).exists():
            all_clips.append(outro_card)

        if len(all_clips) == 1:
            assembled = all_clips[0]
        else:
            assembled = str(post_dir / "assembled.mp4")
            concat_clips(all_clips, assembled)

        # ── VOICEOVER ───────────────────────────────────────────────────────
        if post.get("voiceover") and post.get("voiceover_text"):
            print(f"  🎙️ Generating French voiceover...")
            audio_path = str(post_dir / "voiceover.mp3")
            tts.generate_voiceover(
                text=post["voiceover_text"],
                output_path=audio_path,
                lang="fr"
            )
            pre_wm = str(post_dir / "pre_wm.mp4")
            merge_video_audio(assembled, audio_path, pre_wm)
        else:
            pre_wm = str(post_dir / "pre_wm.mp4")
            try:
                normalize_audio(assembled, pre_wm)
            except Exception:
                shutil.copy(assembled, pre_wm)

        # ── ENFORCE PLATFORM DURATION LIMIT ────────────────────────────────
        max_dur = get_max_duration_for_post(post)
        actual_dur = get_duration(pre_wm)
        if actual_dur > max_dur:
            print(f"  ✂️  Trimming {actual_dur:.1f}s → {max_dur}s (platform limit: {post.get('platforms')})")
            trimmed = str(post_dir / "pre_wm_trimmed.mp4")
            trim_clip(pre_wm, trimmed, start=0, duration=max_dur)
            shutil.move(trimmed, pre_wm)
        else:
            print(f"  ⏱️  Duration {actual_dur:.1f}s within limit ({max_dur}s) ✅")

        # ── WATERMARK ───────────────────────────────────────────────────────
        final_video = str(post_dir / "final.mp4")
        try:
            add_watermark_to_video(pre_wm, final_video)
        except Exception as e:
            print(f"  ⚠️ Watermark failed: {e}")
            shutil.copy(pre_wm, final_video)

        n_scenes = len(scene_clips)
        result["files"].append(final_video)
        print(f"  ✅ Reel ready: intro + {n_scenes} scenes + outro + watermark → {final_video}")

    return result


def run_cycle(client: str, month: str):
    """Run the full content production cycle for a client/month."""
    print(f"\n{'='*60}")
    print(f"  🚀 FORKY-G — {client.upper()} — {month.upper()}")
    print(f"{'='*60}\n")

    # Load content plan
    plan = CONTENT_PLANS.get(client, {}).get(month)
    if not plan:
        print(f"  ❌ No content plan found for {client}/{month}")
        print(f"  Available: {list(CONTENT_PLANS.keys())}")
        sys.exit(1)

    # Output and media directories
    output_dir = Path("output") / client / month
    media_dir  = Path("media") / client
    output_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Sync media from Drive
    print("📥 Downloading media from Google Drive...\n")
    for folder_key in ["fotos_videos", "fotos_png", "joe"]:
        local = media_dir / folder_key
        try:
            sync_drive_folder(folder_key, str(local))
        except Exception as e:
            print(f"  ⚠️ Could not sync {folder_key}: {e}")

    # Step 2: Look for logo
    logo_path = None
    for ext in ["png", "jpg", "jpeg", "svg"]:
        candidates = list(media_dir.rglob(f"*logo*.{ext}")) + list(media_dir.rglob(f"*Logo*.{ext}"))
        if candidates:
            logo_path = str(candidates[0])
            print(f"  🎨 Logo found: {logo_path}")
            break

    # Step 3: Produce each post
    print("\n📸 Producing content...\n")
    results = []
    success = 0

    for post in plan:
        post_dir = output_dir / f"post_{post['id']:02d}"
        print(f"{'─'*40}")
        print(f"📌 POST #{post['id']} — {post['hook'][:50]}...")

        try:
            result = produce_post(post, media_dir, post_dir, logo_path)
            if result["files"]:
                success += 1
                # Save caption
                caption_file = post_dir / "caption.txt"
                caption_file.write_text(result["caption"], encoding="utf-8")
                # Save post metadata
                meta_file = post_dir / "meta.json"
                meta_file.write_text(json.dumps({
                    "id": post["id"],
                    "date": post["date"],
                    "time": post["time"],
                    "platforms": post["platforms"],
                    "format": post["format"],
                    "hook": post["hook"],
                    "files": result["files"],
                    "caption": result["caption"]
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                results.append(result)
                print(f"  ✅ POST #{post['id']} complete → {post_dir}")
            else:
                print(f"  ❌ POST #{post['id']} failed — no files produced")
        except Exception as e:
            print(f"  ❌ POST #{post['id']} failed: {e}")

    # Summary
    print(f"\n{'='*60}")
    print(f"  ✅ CYCLE COMPLETE — {success}/{len(plan)} posts")
    print(f"  📁 Output: {output_dir}")
    print(f"{'='*60}\n")

    # Save cycle summary
    summary = {
        "client": client,
        "month": month,
        "timestamp": datetime.now().isoformat(),
        "total": len(plan),
        "success": success,
        "posts": results
    }
    summary_file = output_dir / "cycle_summary.json"
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forky-G Content Agent")
    parser.add_argument("--client", default="la_medusa")
    parser.add_argument("--month",  default="junio_2026")
    args = parser.parse_args()

    run_cycle(args.client, args.month)
