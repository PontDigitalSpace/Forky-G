"""
Content Director — the agent's ROLE during content production (Fase 4).

Instead of hardcoded, La-Medusa-specific prompts, the agent acts as a professional
video director / cinematographer and photographer. It is INDUSTRY-AGNOSTIC: the
client's brand context (Production Profile from the ClickUp brand doc) is injected
at call time, so the same role serves every client.

It writes the prompts that drive Higgsfield. Two modes:
  - ANIMATE (default): we already have a REAL client image (photo or video frame)
    that Higgsfield will animate. The prompt must describe only CAMERA MOVEMENT,
    LIGHTING and PACING to apply — it must NOT invent new subjects or change what
    is in the real image. The real product/place stays; we only add cinematic motion.
  - GENERATE: no real footage exists for this scene. The prompt describes a full
    scene to create from scratch, consistent with the brand.

Model: claude-haiku-4-5 (fast/cheap; called per scene). Raw HTTP, matching the
project's other clients (clip_indexer.py, brand_designer.py).
"""
import os
import json
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-haiku-4-5"


SYSTEM_PROMPT = """\
You are a professional video director, cinematographer and photographer producing
short-form social content (Reels / TikTok / vertical 9:16). You work across every
industry and adapt to whatever the client is — you do not impose one house style.

You write prompts for an AI video tool (Higgsfield) that takes a START IMAGE and
adds motion to it. Your prompts are read by that tool, so they must be concrete,
visual, and in English (the tool performs best in English).

ABSOLUTE RULE — ANIMATE, DON'T INVENT:
When a real client image is being animated (the normal case), the real subject in
that image is the hero and must NOT be changed, replaced, or re-imagined. You only
describe HOW to bring it to life: camera movement, lens feel, lighting mood, depth,
pacing, and atmosphere. Never describe new objects, dishes, people, or places that
aren't in the real image. The client's real product/place must remain exactly itself.

KEEP MOTION VERY SUBTLE (critical to avoid warping):
The animator morphs/warps objects when motion is large or fast — glassware, faces,
and text are especially prone to melting or distorting. So describe the SMALLEST
motion that still feels alive: a very slow, gentle push-in OR a slight drift, only a
few percent of zoom over the whole clip. Never ask for fast, large, or sweeping camera
moves. "Almost still, barely breathing" is better than dramatic. Prioritize stability
of the real objects over cinematic flourish.

Always honor the brand context you are given (tone, color mood, do's and don'ts).

Return ONLY valid JSON, no prose, in this exact shape:
{
  "vid_prompt": "camera + lighting + motion + atmosphere to animate the real image (1-2 sentences, English, no new subjects)",
  "img_prompt": "ONLY used when generating from scratch — a full scene to create, brand-consistent (English). When animating a real image, set this to an empty string.",
  "notes": "one short line on the creative choice"
}"""


def _build_user_message(scene_desc, brand_context, mode, platform, duration, scene_text):
    animate = mode == "animate"
    lines = [
        f"MODE: {'ANIMATE a real client image (do NOT invent new content)' if animate else 'GENERATE a new scene from scratch (no real footage exists)'}",
        f"PLATFORM: {platform}  ·  SCENE DURATION: {duration}s",
        f"WHAT THE REAL IMAGE / SCENE SHOWS: {scene_desc or '(unspecified)'}",
    ]
    if scene_text:
        lines.append(f"ON-SCREEN TEXT that will overlay this scene: \"{scene_text}\" "
                     f"(leave headroom in the framing/composition for it)")
    lines.append("\n--- BRAND CONTEXT (Production Profile) ---")
    lines.append(brand_context.strip() if brand_context else "(no brand context provided — keep it neutral and tasteful)")
    if animate:
        lines.append("\nWrite vid_prompt only (camera/light/motion to animate the real image). "
                     "Set img_prompt to \"\".")
    else:
        lines.append("\nWrite BOTH img_prompt (the full scene to create) and vid_prompt "
                     "(how to animate that generated image).")
    return "\n".join(lines)


def generate_scene_prompts(
    scene_desc: str,
    brand_context: str = "",
    mode: str = "animate",
    platform: str = "instagram",
    duration: int = 5,
    scene_text: str = "",
    timeout: int = 60,
) -> dict:
    """
    Ask the director (Claude) to write Higgsfield prompts for one scene.
    `mode`: "animate" (real image is animated — default) or "generate" (from scratch).
    `brand_context`: the client's Production Profile text (industry, tone, colors,
                     do/don'ts). Inject this from the ClickUp brand doc.
    Returns {"vid_prompt", "img_prompt", "notes"}. Raises on API/parse error.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    user_msg = _build_user_message(scene_desc, brand_context, mode, platform, duration, scene_text)

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 500,
            "system": SYSTEM_PROMPT,
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

    data = json.loads(text)
    return {
        "vid_prompt": data.get("vid_prompt", "").strip(),
        "img_prompt": data.get("img_prompt", "").strip(),
        "notes": data.get("notes", "").strip(),
    }


if __name__ == "__main__":
    # Smoke test (consumes a tiny bit of Haiku credit).
    demo_brand = (
        "Cliente: La Medusa — restaurante italiano premium en Montreal. "
        "Tono visual: elegante, cálido, íntimo. Colores: dorado (#d6b646) y negro (#1d1c1a). "
        "Mood: fine dining, luz de vela, herencia. Evitar: estética fast-food, tonos fríos, fotos de stock."
    )
    out = generate_scene_prompts(
        scene_desc="close-up of a handmade pasta dish on an elegant plate",
        brand_context=demo_brand,
        mode="animate",
        platform="instagram",
        duration=4,
        scene_text="Fait à la main.",
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))
