"""
Script Writer — the agent's ROLE for CREATING THE SCRIPT (Fase 4, the foundation).

This is the base of content production: before any prompt or render, the agent acts
as a professional short-form video scriptwriter / creative director and turns a post
BRIEF into a scene-by-scene SCRIPT. The script drives everything downstream
(clip selection → content_director prompts → Higgsfield → edit). A good script makes
everything below it good; a bad one can't be saved by good prompts.

INDUSTRY-AGNOSTIC: the role is generic; the client's brand context (Production
Profile) is injected at call time, so the same scriptwriter serves every client.

ANIMATE, DON'T INVENT: scenes describe REAL client footage to find and animate
(so clip_indexer can match a real clip). The script never asks to invent products,
dishes, people, or places that don't exist.

Output feeds produce_post() directly: a list of scenes
  {"description", "duration", "text"}  (+ optional hints).

Model: claude-haiku-4-5 by default (cheap; once per post). For this foundational
step, claude-sonnet-4-6 is the recommended quality upgrade — see MODEL below.
"""
import os
import json
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Foundational step, called once per post (low volume). Haiku keeps cost minimal;
# set FORKY_SCRIPT_MODEL=claude-sonnet-4-6 for higher script quality.
MODEL = os.environ.get("FORKY_SCRIPT_MODEL", "claude-haiku-4-5")


SYSTEM_PROMPT = """\
You are a professional short-form video scriptwriter and creative director for social
media (Instagram Reels / TikTok / Facebook, vertical 9:16). You have made thousands of
high-retention videos across every industry, and you adapt to whatever the client is —
you never impose one house style.

Your job: turn a POST BRIEF into a tight, scene-by-scene SCRIPT that another system
will produce by animating the client's REAL footage. So your scenes must be shootable
from what a real business actually has on hand.

RULES OF A GOOD SCRIPT (follow all):
1. HOOK FIRST. Scene 1 lands the hook in the first ~3 seconds — visual + on-screen text
   that stops the scroll. No slow intros.
2. 3-5 scenes total. Each scene 3-5 seconds (the AI animator produces ~5s clips — never
   write a single scene longer than 6s; split long beats into two scenes).
3. RESPECT THE PLATFORM MAX. Total duration must fit the most restrictive platform given.
   Trim scene count/length to fit; completion rate beats length.
4. ANIMATE REAL FOOTAGE — BUILD FROM WHAT EXISTS. You are given a list of the REAL
   footage available. EVERY scene's "description" MUST be matchable to something in
   that list (concrete subject + setting + mood, English keywords). This is a HARD
   constraint: do NOT write a scene for a shot that isn't in the available footage.
   If there are no food/dish clips, do NOT write food scenes — tell the story with the
   interiors, ambiance, details and people that DO exist. Never invent footage. If the
   available footage is thin, use fewer scenes rather than describing shots that don't exist.
5. ON-SCREEN TEXT is selective: only 1-3 scenes carry text (short, punchy, in the post's
   publishing language). Leave the rest empty ("") — not every clip needs text. The hook
   scene and the closing CTA scene always have text.
6. CLOSE WITH A CTA scene: brand/logo moment + reservation/website/action line.
7. STAY ON BRAND. Honor the brand context (tone, mood, color feel, do's and don'ts).

Return ONLY valid JSON, no prose, in this exact shape:
{
  "concept": "one line — the creative idea of this video",
  "total_duration": <int seconds, within the platform max>,
  "scenes": [
    {
      "description": "REAL shot to find/animate — concrete English keywords (subject, setting, mood)",
      "duration": <int seconds, 3-6>,
      "text": "on-screen text in the publishing language, or \"\" if none",
      "note": "optional: pacing/camera/music cue for this beat"
    }
  ],
  "music_mood": "short search hint for background music (mood, tempo, no lyrics)"
}"""


def _build_user_message(brief, brand_context, available_footage):
    platforms = brief.get("platforms", ["instagram"])
    lines = [
        f"PUBLISHING LANGUAGE: {brief.get('language', 'French')}",
        f"PLATFORMS: {', '.join(platforms)}",
        f"PLATFORM MAX DURATION (seconds, most restrictive wins): {brief.get('max_duration', 35)}",
        f"FORMAT: {brief.get('format', 'reel')}",
        f"PILLAR / THEME: {brief.get('pilar', '(unspecified)')}",
        f"GOAL: {brief.get('goal', '(unspecified)')}",
        f"HOOK (use or sharpen it): {brief.get('hook', '(none given)')}",
    ]
    if brief.get("caption_fr") or brief.get("caption"):
        lines.append(f"CAPTION (for tone reference): {brief.get('caption_fr') or brief.get('caption')}")
    if brief.get("brief_text"):
        lines.append(f"\nEXTRA BRIEF NOTES:\n{brief['brief_text']}")
    lines.append("\n--- BRAND CONTEXT (Production Profile) ---")
    lines.append(brand_context.strip() if brand_context else "(none — keep it neutral and tasteful)")
    if available_footage:
        lines.append("\n--- REAL FOOTAGE AVAILABLE (prefer these; describe scenes you can match) ---")
        lines.append(available_footage if isinstance(available_footage, str)
                     else ", ".join(available_footage))
    else:
        lines.append("\n(No footage inventory provided — describe realistic shots a restaurant/business of this kind would have.)")
    lines.append("\nWrite the scene-by-scene script now.")
    return "\n".join(lines)


def write_script(
    brief: dict,
    brand_context: str = "",
    available_footage=None,
    timeout: int = 90,
) -> dict:
    """
    Act as the scriptwriter: turn a post brief into a scene-by-scene script.
    `brief`: dict with hook, platforms, format, pilar, goal, caption, language,
             max_duration, optional brief_text.
    `brand_context`: the client's Production Profile text (inject from ClickUp brand doc).
    `available_footage`: optional list/str of real clips available (from clip_index) so
                         the scriptwriter only describes shots that can be matched.
    Returns the parsed script dict (concept, total_duration, scenes[], music_mood).
    The `scenes` list is directly usable as post["scenes"] in produce_post().
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    user_msg = _build_user_message(brief, brand_context, available_footage)

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 1500,
            # Self-learning: learned rules/experience from the agent's brain
            # (set by phase_runner via env; empty = behave exactly as before).
            "system": SYSTEM_PROMPT + (
                "\n\n# LEARNED KNOWLEDGE (from your brain — apply when relevant)\n"
                + os.environ["FORKY_BRAIN_CONTEXT"]
                if os.environ.get("FORKY_BRAIN_CONTEXT") else ""
            ),
            "messages": [{"role": "user", "content": user_msg}],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    text = "".join(b["text"] for b in response.json().get("content", [])
                   if b.get("type") == "text").strip()

    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()

    script = json.loads(text)
    # Normalize scenes to exactly what produce_post expects.
    for s in script.get("scenes", []):
        s.setdefault("text", "")
        s["duration"] = int(s.get("duration", 4))
    return script


if __name__ == "__main__":
    demo_brand = (
        "Cliente: La Medusa — restaurante italiano premium en Montreal (desde 1996). "
        "Tono: elegante, cálido, íntimo, herencia. Colores: dorado #d6b646 y negro #1d1c1a. "
        "Mood: luz de vela, fine dining. Evitar: fast-food, tonos fríos, stock."
    )
    demo_brief = {
        "hook": "Le meilleur cadeau pour la fête des pères ?",
        "platforms": ["instagram"],
        "max_duration": 45,
        "format": "reel",
        "pilar": "Experiencias y Celebraciones — Día del Padre",
        "goal": "Reservas + alcance",
        "language": "French",
        "caption_fr": "Le meilleur cadeau pour la fête des pères ? Une vraie soirée italienne.",
    }
    out = write_script(demo_brief, brand_context=demo_brand,
                       available_footage="elegant table with wine and candle, plated dishes, "
                                         "warm restaurant interior, Joe welcoming guests, steak, pasta, risotto")
    print(json.dumps(out, indent=2, ensure_ascii=False))
