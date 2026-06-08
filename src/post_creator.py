"""
Post Creator — Creates social media posts with text overlays on real photos/videos
Uses PIL/Pillow for image compositing with La Medusa brand colors and fonts
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from pathlib import Path
import textwrap
import subprocess
import os

# Brand colors
GOLD   = "#d6b646"
BLACK  = "#1d1c1a"
WHITE  = "#f5f0e8"
ORANGE = "#f05620"

# Font paths (downloaded in workflow)
FONT_DIR = Path(os.environ.get("FONT_DIR", "/usr/share/fonts/forky"))


def _get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a font by name, fallback to default if not found."""
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


def create_static_post(
    photo_path: str,
    output_path: str,
    text_lines: list,         # [{"text": "...", "style": "title|subtitle|body", "color": "#hex"}]
    size: tuple = (1080, 1080),
    overlay_opacity: int = 140,
    logo_path: str = None
) -> str:
    """
    Create a static post: real photo + dark overlay + text in brand colors.
    """
    img = Image.open(photo_path).convert("RGBA")
    img = img.resize(size, Image.LANCZOS)

    # Dark overlay for text readability
    overlay = Image.new("RGBA", size, (29, 28, 26, overlay_opacity))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)

    # Draw text lines centered
    y = size[1] // 3
    for line_data in text_lines:
        text  = line_data.get("text", "")
        style = line_data.get("style", "subtitle")
        color = _hex_to_rgb(line_data.get("color", GOLD))

        size_map = {"title": 72, "subtitle": 48, "body": 36}
        font_size = line_data.get("size", size_map.get(style, 48))
        font = _get_font(style, font_size)

        # Word wrap
        wrapped = textwrap.fill(text, width=28)
        bbox = draw.textbbox((0, 0), wrapped, font=font)
        text_w = bbox[2] - bbox[0]
        x = (size[0] - text_w) // 2

        # Shadow
        draw.text((x + 2, y + 2), wrapped, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), wrapped, font=font, fill=color)

        y += (bbox[3] - bbox[1]) + 20

    # Gold bottom line
    draw.rectangle([(0, size[1] - 6), (size[0], size[1])], fill=_hex_to_rgb(GOLD))

    # Logo if available
    if logo_path and Path(logo_path).exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo_size = (120, 120)
        logo = logo.resize(logo_size, Image.LANCZOS)
        img.paste(logo, (size[0] - 140, size[1] - 140), logo)

    img = img.convert("RGB")
    img.save(output_path, "JPEG", quality=95)
    print(f"  ✅ Static post → {output_path}")
    return output_path


def create_carousel_slide(
    photo_path: str,
    output_path: str,
    main_text: str,
    sub_text: str = "",
    is_cover: bool = False,
    is_cta: bool = False,
    logo_path: str = None
) -> str:
    """Create one carousel slide with photo + text overlay."""
    size = (1080, 1080)

    if is_cta:
        # CTA slide: dark background, gold text, logo
        img = Image.new("RGB", size, _hex_to_rgb(BLACK))
    else:
        img = Image.open(photo_path).convert("RGBA")
        img = img.resize(size, Image.LANCZOS)
        opacity = 160 if is_cover else 120
        overlay = Image.new("RGBA", size, (29, 28, 26, opacity))
        img = Image.alpha_composite(img, overlay)
        img = img.convert("RGB")

    draw = ImageDraw.Draw(img)

    # Gold top accent line
    draw.rectangle([(0, 0), (size[0], 5)], fill=_hex_to_rgb(GOLD))

    # Main text
    font_size = 54 if is_cover else 48
    font = _get_font("subtitle", font_size)
    wrapped = textwrap.fill(main_text, width=24)
    bbox = draw.textbbox((0, 0), wrapped, font=font)
    x = (size[0] - (bbox[2] - bbox[0])) // 2
    y = size[1] // 3 if is_cover else size[1] // 2 - 60

    draw.text((x + 2, y + 2), wrapped, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), wrapped, font=font, fill=_hex_to_rgb(GOLD))

    # Sub text
    if sub_text:
        sub_font = _get_font("body", 32)
        sub_wrapped = textwrap.fill(sub_text, width=32)
        sub_bbox = draw.textbbox((0, 0), sub_wrapped, font=sub_font)
        sub_x = (size[0] - (sub_bbox[2] - sub_bbox[0])) // 2
        sub_y = y + (bbox[3] - bbox[1]) + 24
        draw.text((sub_x, sub_y), sub_wrapped, font=sub_font, fill=_hex_to_rgb(WHITE))

    # Logo on CTA slide
    if is_cta and logo_path and Path(logo_path).exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((160, 160), Image.LANCZOS)
        img_rgba = img.convert("RGBA")
        img_rgba.paste(logo, ((size[0] - 160) // 2, size[1] // 2 - 80), logo)
        img = img_rgba.convert("RGB")

    # Gold bottom line
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, size[1] - 6), (size[0], size[1])], fill=_hex_to_rgb(GOLD))

    img.save(output_path, "JPEG", quality=95)
    return output_path


def add_text_overlay_to_video(
    video_path: str,
    output_path: str,
    text: str,
    position: str = "bottom",  # top, center, bottom
    color: str = GOLD
) -> str:
    """Add text overlay to a video using FFmpeg drawtext filter."""
    r, g, b = _hex_to_rgb(color)
    hex_ffmpeg = f"{r:02x}{g:02x}{b:02x}"

    y_pos = {
        "top":    "50",
        "center": "(h-text_h)/2",
        "bottom": "h-text_h-80"
    }.get(position, "h-text_h-80")

    font_path = str(FONT_DIR / "Marcellus-Regular.ttf")
    escaped_text = text.replace("'", "\\'").replace(":", "\\:")

    # Check if font exists
    if Path(font_path).exists():
        drawtext = (
            f"drawtext=fontfile={font_path}:"
            f"text='{escaped_text}':"
            f"fontcolor=0x{hex_ffmpeg}:"
            f"fontsize=56:"
            f"x=(w-text_w)/2:"
            f"y={y_pos}:"
            f"shadowcolor=black:shadowx=2:shadowy=2:"
            f"box=1:boxcolor=black@0.4:boxborderw=12"
        )
    else:
        drawtext = (
            f"drawtext=text='{escaped_text}':"
            f"fontcolor=0x{hex_ffmpeg}:"
            f"fontsize=56:"
            f"x=(w-text_w)/2:"
            f"y={y_pos}:"
            f"shadowcolor=black:shadowx=2:shadowy=2"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", drawtext,
        "-c:v", "libx264", "-crf", "18",
        "-c:a", "copy",
        "-preset", "fast",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg drawtext failed:\n{result.stderr[-500:]}")
    print(f"  ✅ Text overlay added → {output_path}")
    return output_path
