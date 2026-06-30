"""
Post Creator — Creates social media posts with text overlays on real photos/videos
Uses PIL/Pillow for image compositing with La Medusa brand colors and fonts
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import textwrap
import subprocess
import tempfile
import os

# Brand colors
GOLD   = "#d6b646"
BLACK  = "#1d1c1a"
WHITE  = "#f5f0e8"
ORANGE = "#f05620"

# Font paths (downloaded in workflow)
FONT_DIR = Path(os.environ.get("FONT_DIR", "/usr/share/fonts/forky"))


def _get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    font_map = {
        "title":    "EdwardianScriptITC.ttf",
        "subtitle": "Marcellus-Regular.ttf",
        "body":     "LibreBaskerville-Regular.ttf",
        "bold":     "LibreBaskerville-Bold.ttf",
    }
    font_file = FONT_DIR / font_map.get(name, "Marcellus-Regular.ttf")
    try:
        return ImageFont.truetype(str(font_file), size)
    except Exception:
        return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _draw_centered_text(draw, text, y, font, color, canvas_w, line_spacing=10, shadow=True):
    """Draw horizontally centered text. Returns the bottom y position."""
    wrapped = textwrap.fill(text, width=20)
    lines = wrapped.split("\n")
    cur_y = y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        x = (canvas_w - lw) // 2
        if shadow:
            draw.text((x + 2, cur_y + 2), line, font=font, fill=(0, 0, 0, 210))
        draw.text((x, cur_y), line, font=font, fill=color)
        cur_y += lh + line_spacing
    return cur_y


# ── BRAND CARD (intro / outro) ────────────────────────────────────────────────

def create_brand_card_image(
    output_path: str,
    main_text: str,
    sub_text: str = "",
    card_type: str = "intro",   # "intro" | "outro"
    size: tuple = (1080, 1920)
) -> str:
    """
    Create a branded text card image for reel intro or outro.
    Black background, La Medusa gold branding, social-media ready.
    """
    w, h = size
    img = Image.new("RGBA", size, (*_hex_to_rgb(BLACK), 255))
    draw = ImageDraw.Draw(img)

    # Gold accent lines top and bottom
    draw.rectangle([(0, 0),    (w, 6)], fill=(*_hex_to_rgb(GOLD), 255))
    draw.rectangle([(0, h-6),  (w, h)], fill=(*_hex_to_rgb(GOLD), 255))

    if card_type == "intro":
        # ── "LA MEDUSA" brand name ─────────────────────────────────────────
        brand_font = _get_font("subtitle", 100)
        brand_y    = h // 3
        brand_end  = _draw_centered_text(draw, "LA MEDUSA", brand_y, brand_font,
                                         _hex_to_rgb(GOLD), w, shadow=True)

        # thin gold divider
        div_y = brand_end + 24
        draw.rectangle([(w//2 - 180, div_y), (w//2 + 180, div_y + 3)],
                       fill=(*_hex_to_rgb(GOLD), 200))

        # Hook text in warm white
        if main_text:
            hook_font = _get_font("body", 54)
            _draw_centered_text(draw, main_text, div_y + 40, hook_font,
                                _hex_to_rgb(WHITE), w, line_spacing=14)

        # Subtle "Depuis 1996" at bottom
        since_font = _get_font("subtitle", 30)
        since_color = tuple(int(c * 0.55) for c in _hex_to_rgb(GOLD))
        _draw_centered_text(draw, "· Depuis 1996 ·", h - 120, since_font,
                            since_color, w, shadow=False)

    else:  # outro
        # ── CTA card ──────────────────────────────────────────────────────
        cta_font = _get_font("subtitle", 68)
        cta_y    = h // 2 - 220
        cta_end  = _draw_centered_text(draw, main_text or "Réservez votre table",
                                       cta_y, cta_font, _hex_to_rgb(GOLD), w)

        # Divider
        div_y = cta_end + 20
        draw.rectangle([(w//2 - 120, div_y), (w//2 + 120, div_y + 2)],
                       fill=(*_hex_to_rgb(GOLD), 180))

        # URL
        url_font = _get_font("body", 42)
        url_end  = _draw_centered_text(draw, sub_text or "lamedusarestaurant.ca",
                                       div_y + 36, url_font, _hex_to_rgb(WHITE), w)

        # Address line
        addr_font  = _get_font("body", 30)
        addr_color = tuple(int(c * 0.65) for c in _hex_to_rgb(WHITE))
        _draw_centered_text(draw, "1218 Rue Drummond, Montréal  ·  (514) 878-4499",
                            url_end + 28, addr_font, addr_color, w, shadow=False)

        # Brand footer
        footer_font = _get_font("subtitle", 32)
        _draw_centered_text(draw, "LA MEDUSA · Depuis 1996",
                            h - 120, footer_font,
                            tuple(int(c * 0.55) for c in _hex_to_rgb(GOLD)),
                            w, shadow=False)

    img = img.convert("RGB")
    img.save(output_path, "JPEG", quality=95)
    return output_path


def create_brand_card_video(
    output_path: str,
    main_text: str,
    sub_text: str = "",
    card_type: str = "intro",
    duration: float = 2.0
) -> str:
    """Convert a brand card image to a short video clip (no animation)."""
    from video_editor import image_to_video

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        card_img = tmp.name

    try:
        create_brand_card_image(card_img, main_text, sub_text, card_type,
                                size=(1080, 1920))
        image_to_video(card_img, output_path, duration=duration, zoom=False)
    finally:
        Path(card_img).unlink(missing_ok=True)

    print(f"  🎴 Brand card ({card_type}) → {output_path}")
    return output_path


# ── TEXT OVERLAY (lower-third style) ─────────────────────────────────────────

def add_text_overlay_to_video(
    video_path: str,
    output_path: str,
    text: str,
    position: str = "bottom",   # top | center | bottom
    color: str = GOLD
) -> str:
    """
    Add a prominent lower-third text overlay to a video.
    Full-width semi-transparent dark band + large centered gold text.
    Optimized for 1080x1920 vertical (reel) format.
    """
    # Render the lower-third (band + gold line + text) as a transparent PNG with
    # PIL, then composite with ffmpeg `overlay`. This avoids the `drawtext` filter,
    # which isn't compiled into every FFmpeg build (e.g. the user's local Mac).
    r, g, b = _hex_to_rgb(color)

    # Probe the real video size so the overlay matches exactly.
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", video_path],
            capture_output=True, text=True)
        W, H = [int(x) for x in probe.stdout.strip().split(",")[:2]]
    except Exception:
        W, H = 1080, 1920

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = 96
    # Prefer the brand font (Marcellus, installed in production); fall back to an
    # elegant system serif locally so text never silently shrinks to PIL's tiny
    # default bitmap font.
    font = None
    for fp in [
        str(FONT_DIR / "Marcellus-Regular.ttf"),
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/System/Library/Fonts/Supplemental/Baskerville.ttc",
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    ]:
        try:
            font = ImageFont.truetype(fp, font_size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    wrapped = textwrap.fill(text, width=20)
    lines = wrapped.split("\n")
    line_h = font_size + 18
    total_h = line_h * len(lines)
    pad = 50                                   # padding above/below the text
    band_h = total_h + pad * 2                 # band sized to actually fit the text

    if position == "bottom":
        band_y = H - band_h - 40               # small margin off the bottom edge
    elif position == "center":
        band_y = (H - band_h) // 2
    else:  # top
        band_y = 60

    # Dark band (0.78 alpha) + gold accent line on its top edge.
    draw.rectangle([0, band_y, W, band_y + band_h], fill=(0x1d, 0x1c, 0x1a, 200))
    draw.rectangle([0, band_y, W, band_y + 5], fill=(0xd6, 0xb6, 0x46, 235))

    ty = band_y + pad
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        tx = (W - lw) // 2
        draw.text((tx + 3, ty + 3), line, font=font, fill=(0, 0, 0, 255))   # shadow
        draw.text((tx, ty), line, font=font, fill=(r, g, b, 255))            # gold text
        ty += line_h

    png_path = output_path + ".overlay.png"
    overlay.save(png_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", png_path,
        "-filter_complex", "[0:v]format=yuv420p[v];[v][1:v]overlay=0:0[out]",
        "-map", "[out]", "-map", "0:a?",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        os.remove(png_path)
    except Exception:
        pass
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg overlay failed:\n{result.stderr[-500:]}")
    print(f"  ✅ Text overlay added (PIL) → {output_path}")
    return output_path


# ── WATERMARK ─────────────────────────────────────────────────────────────────

def add_watermark_to_video(
    video_path: str,
    output_path: str,
    text: str = "LA MEDUSA"
) -> str:
    """Add a subtle brand watermark to the top-right corner of a video."""
    font_path = str(FONT_DIR / "Marcellus-Regular.ttf")
    has_font  = Path(font_path).exists()

    if has_font:
        drawtext = (
            f"drawtext=fontfile={font_path}:"
            f"text='{text}':"
            f"fontcolor=white@0.50:"
            f"fontsize=34:"
            f"x=w-text_w-30:"
            f"y=38:"
            f"shadowcolor=black@0.35:shadowx=1:shadowy=1"
        )
    else:
        drawtext = (
            f"drawtext=text='{text}':"
            f"fontcolor=white@0.50:"
            f"fontsize=34:"
            f"x=w-text_w-30:"
            f"y=38"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"format=yuv420p,{drawtext}",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg watermark failed:\n{result.stderr[-300:]}")
    print(f"  🔖 Watermark added → {output_path}")
    return output_path


# ── STATIC POST ───────────────────────────────────────────────────────────────

def create_static_post(
    photo_path: str,
    output_path: str,
    text_lines: list,
    size: tuple = (1080, 1080),
    overlay_opacity: int = 140,
    logo_path: str = None
) -> str:
    """Create a static post: real photo + dark overlay + brand text."""
    img = Image.open(photo_path).convert("RGBA")
    img = img.resize(size, Image.LANCZOS)

    overlay = Image.new("RGBA", size, (29, 28, 26, overlay_opacity))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)

    y = size[1] // 3
    for line_data in text_lines:
        text  = line_data.get("text", "")
        style = line_data.get("style", "subtitle")
        color = _hex_to_rgb(line_data.get("color", GOLD))

        size_map = {"title": 72, "subtitle": 52, "body": 36}
        font_size = line_data.get("size", size_map.get(style, 52))
        font = _get_font(style, font_size)

        wrapped = textwrap.fill(text, width=26)
        bbox    = draw.textbbox((0, 0), wrapped, font=font)
        text_w  = bbox[2] - bbox[0]
        x = (size[0] - text_w) // 2

        draw.text((x + 2, y + 2), wrapped, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), wrapped, font=font, fill=color)
        y += (bbox[3] - bbox[1]) + 24

    # Gold bottom accent
    draw.rectangle([(0, size[1] - 6), (size[0], size[1])], fill=_hex_to_rgb(GOLD))

    if logo_path and Path(logo_path).exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((120, 120), Image.LANCZOS)
        img.paste(logo, (size[0] - 140, size[1] - 140), logo)

    img = img.convert("RGB")
    img.save(output_path, "JPEG", quality=95)
    print(f"  ✅ Static post → {output_path}")
    return output_path


# ── CAROUSEL SLIDE ────────────────────────────────────────────────────────────

def create_carousel_slide(
    photo_path: str,
    output_path: str,
    main_text: str,
    sub_text: str = "",
    is_cover: bool = False,
    is_cta: bool = False,
    logo_path: str = None
) -> str:
    """Create one carousel slide: photo + brand text overlay."""
    size = (1080, 1080)
    w, h = size

    if is_cta:
        img = Image.new("RGB", size, _hex_to_rgb(BLACK))
    else:
        img = Image.open(photo_path).convert("RGBA")
        img = img.resize(size, Image.LANCZOS)
        opacity = 165 if is_cover else 125
        overlay = Image.new("RGBA", size, (29, 28, 26, opacity))
        img = Image.alpha_composite(img, overlay)
        img = img.convert("RGB")

    draw = ImageDraw.Draw(img)

    # Gold top accent
    draw.rectangle([(0, 0), (w, 5)], fill=_hex_to_rgb(GOLD))

    # Main text
    font_size = 58 if is_cover else 50
    font      = _get_font("subtitle", font_size)
    wrapped   = textwrap.fill(main_text, width=22)
    bbox      = draw.textbbox((0, 0), wrapped, font=font)
    x         = (w - (bbox[2] - bbox[0])) // 2
    y         = h // 3 if is_cover else h // 2 - 70

    draw.text((x + 2, y + 2), wrapped, font=font, fill=(0, 0, 0, 200))
    draw.text((x, y), wrapped, font=font, fill=_hex_to_rgb(GOLD))

    if sub_text:
        sub_font    = _get_font("body", 34)
        sub_wrapped = textwrap.fill(sub_text, width=30)
        sub_bbox    = draw.textbbox((0, 0), sub_wrapped, font=sub_font)
        sub_x       = (w - (sub_bbox[2] - sub_bbox[0])) // 2
        sub_y       = y + (bbox[3] - bbox[1]) + 28
        draw.text((sub_x, sub_y), sub_wrapped, font=sub_font, fill=_hex_to_rgb(WHITE))

    if is_cta and logo_path and Path(logo_path).exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((160, 160), Image.LANCZOS)
        img_rgba = img.convert("RGBA")
        img_rgba.paste(logo, ((w - 160) // 2, h // 2 - 80), logo)
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)

    # Gold bottom accent
    draw.rectangle([(0, h - 6), (w, h)], fill=_hex_to_rgb(GOLD))

    img.save(output_path, "JPEG", quality=95)
    return output_path
