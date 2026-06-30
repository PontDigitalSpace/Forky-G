"""
Brand Designer — Generates 3 visual identity proposals for a new client.
Runs ONCE per client during the onboarding phase (Fase 1).

The agent acts as a creative director (industry-agnostic). It reads ALL
available onboarding materials and proposes 3 distinct, complete visual
identities. The client picks one → it becomes the Production Profile stored
in ClickUp and injected into every content-production prompt thereafter.

Model: claude-opus-4-8 with adaptive thinking — a one-time, high-value
creative/analytical task per client, so Opus-tier is justified.
"""
from __future__ import annotations
import os
import json
import base64
import requests
from pathlib import Path

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-8"


def _encode_image(image_path: str) -> dict:
    """Encode a local image as an Anthropic image content block."""
    with open(image_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    ext = Path(image_path).suffix.lower().lstrip(".")
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                  "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data}
    }


SYSTEM_PROMPT = """\
You are a senior creative director and brand strategist. You work across every \
industry — restaurants, clinics, law firms, fashion, fitness, B2B SaaS, local \
trades — and you adapt your sensibility to whatever the client actually is. You \
do not impose one house style; you read the business and design FOR it.

Your job: study all the onboarding materials provided for ONE client, then \
propose THREE distinct, complete, production-ready visual identities. The client \
will pick one. The chosen one becomes a "Production Profile" that an automated \
content pipeline (image + video generation) will follow for every post — so your \
proposals must be concrete and machine-actionable, not vague mood-words.

PRINCIPLES
- Ground every decision in evidence from the materials. When you choose a color, \
a font, or a mood, it should trace back to something the client said, showed, or \
implied (their words, their references, their audience, their industry norms, \
their competitors).
- The three proposals must be genuinely DIFFERENT strategic directions — not three \
shades of the same idea. Think: e.g. "heritage/artisanal" vs "modern/minimal" vs \
"bold/energetic". Each should be a coherent world a client could say yes to.
- Be specific enough to generate from. "Warm" is not a color. "#C8742A terracotta" is. \
Name actual font families (or close, namable substitutes). Describe lighting, \
composition, and texture a video/image model can act on.
- Respect any hard constraints, dislikes, or non-negotiables the client stated. \
If they said "no pink, never stock-photo smiles", that is law in all 3 proposals.
- If the materials are thin or contradictory, say so honestly in `notes` and make \
reasonable, defensible choices rather than refusing.

Return ONLY valid JSON, no prose before or after, in exactly this shape:
{
  "client_summary": {
    "what_they_are": "one sentence — the business in plain terms",
    "audience": "who they're trying to reach",
    "competitors_or_peers": "named or described, if known",
    "hard_constraints": ["explicit dislikes / must-nots / must-haves from the materials"],
    "evidence_gaps": ["anything important that was missing or unclear in the onboarding"]
  },
  "proposals": [
    {
      "id": 1,
      "name": "short evocative name for this direction",
      "concept": "2-3 sentences: the strategic idea and why it fits THIS client",
      "rationale": "what in the onboarding materials led you here (cite specifics)",
      "color_palette": {
        "primary":   {"hex": "#RRGGBB", "name": "...", "use": "..."},
        "secondary": {"hex": "#RRGGBB", "name": "...", "use": "..."},
        "accent":    {"hex": "#RRGGBB", "name": "...", "use": "..."},
        "neutral_dark":  {"hex": "#RRGGBB", "name": "..."},
        "neutral_light": {"hex": "#RRGGBB", "name": "..."}
      },
      "typography": {
        "headline": {"family": "...", "character": "why it fits"},
        "body":     {"family": "...", "character": "why it fits"}
      },
      "visual_direction": {
        "photography_style": "lighting, color grade, composition, what's in frame",
        "video_style": "pacing, motion, transitions, camera feel",
        "textures_and_graphics": "patterns, grain, frames, iconography, overlays",
        "mood_keywords": ["5-8 concrete adjectives"]
      },
      "do": ["3-5 concrete things content SHOULD always do"],
      "dont": ["3-5 concrete things content should NEVER do"],
      "example_post_idea": "one sample post described in this identity, to make it tangible"
    }
    // ... proposals 2 and 3, same structure, strategically different
  ],
  "recommendation": {
    "pick": 1,
    "why": "which proposal you'd recommend and the honest tradeoff vs the others"
  }
}"""


def build_user_content(
    company_info: str = "",
    onboarding_form: str = "",
    transcripts: str = "",
    existing_brand_doc: str = "",
    visual_reference_paths: list[str] | None = None,
) -> list:
    """
    Assemble the multimodal user message from the 5 onboarding inputs.
    Text inputs are concatenated with clear section headers; visual references
    are attached as image blocks so the model can actually see the moodboard.
    """
    sections = []
    if company_info:
        sections.append(f"## COMPANY INFO (industry, audience, competition)\n{company_info}")
    if onboarding_form:
        sections.append(f"## ONBOARDING FORM (client's own answers)\n{onboarding_form}")
    if transcripts:
        sections.append(f"## ONBOARDING CALL TRANSCRIPTS\n{transcripts}")
    if existing_brand_doc:
        sections.append(f"## EXISTING BRAND DOCUMENT (if any)\n{existing_brand_doc}")

    text_blob = (
        "Here are all the onboarding materials for one client. Study them, then "
        "produce the three visual identity proposals as specified.\n\n"
        + "\n\n---\n\n".join(sections)
    )

    content = [{"type": "text", "text": text_blob}]

    # Attach visual references / moodboard images so the model can see them.
    refs = visual_reference_paths or []
    if refs:
        content.append({
            "type": "text",
            "text": f"\n## VISUAL REFERENCES / MOODBOARD ({len(refs)} images follow):"
        })
        for p in refs:
            try:
                content.append(_encode_image(p))
            except Exception as e:
                print(f"  ⚠️ Could not attach reference {p}: {e}")

    return content


def generate_brand_proposals(
    company_info: str = "",
    onboarding_form: str = "",
    transcripts: str = "",
    existing_brand_doc: str = "",
    visual_reference_paths: list[str] | None = None,
    timeout: int = 600,
) -> dict:
    """
    Call Opus 4.8 to generate 3 visual identity proposals from onboarding inputs.
    Returns the parsed JSON dict. Raises on API error or unparseable response.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    user_content = build_user_content(
        company_info=company_info,
        onboarding_form=onboarding_form,
        transcripts=transcripts,
        existing_brand_doc=existing_brand_doc,
        visual_reference_paths=visual_reference_paths,
    )

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 8000,
            # Opus 4.8: adaptive thinking only (no budget_tokens, no temperature).
            # "summarized" so we can watch the reasoning if streaming/debugging.
            "thinking": {"type": "adaptive", "display": "summarized"},
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_content}],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()

    # Pull the final text block (skip thinking blocks).
    text_out = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text_out += block["text"]
    text_out = text_out.strip()

    # Be tolerant of accidental code fences.
    if text_out.startswith("```"):
        text_out = text_out.split("```", 2)[1]
        if text_out.startswith("json"):
            text_out = text_out[4:]
        text_out = text_out.strip().rstrip("`").strip()

    try:
        return json.loads(text_out)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Model did not return valid JSON: {e}\n\n--- raw output ---\n{text_out[:2000]}"
        )


if __name__ == "__main__":
    # Smoke test with a minimal fake client.
    result = generate_brand_proposals(
        company_info="La Bruja de la Montaña — restaurante de cocina de montaña "
                     "asturiana, ticket medio-alto, ubicado en un pueblo de los "
                     "Picos de Europa. Competidores: sidrerías tradicionales y "
                     "restaurantes de autor. Audiencia: comensales 35-60 que buscan "
                     "experiencia gastronómica con producto local.",
        onboarding_form="Quieren transmitir autenticidad, raíz, montaña, sin "
                        "parecer rústicos de bar. Les gusta lo elegante pero cálido. "
                        "No quieren: fotos de stock, tonos fríos, estética 'fast food'.",
        transcripts="(transcripción de llamada de onboarding iría aquí)",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
