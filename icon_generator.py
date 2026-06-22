from PIL import Image, ImageDraw, ImageFont
import math


def _pct_color(pct: float) -> tuple:
    """Green → Yellow → Red based on percentage 0–100."""
    if pct < 50:
        r = int(pct / 50 * 255)
        return (r, 200, 50)
    else:
        g = int((1 - (pct - 50) / 50) * 200)
        return (255, g, 30)


def make_icon(pct: float, size: int = 64) -> Image.Image:
    """Return a PIL Image: pie-chart showing usage percentage."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy, r = size // 2, size // 2, size // 2 - 2
    bg_color = (60, 60, 60, 220)
    fill_color = _pct_color(pct) + (230,)

    # Background circle
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bg_color)

    # Filled arc (usage slice)
    if pct > 0:
        end_angle = -90 + (pct / 100) * 360
        draw.pieslice([cx - r, cy - r, cx + r, cy + r],
                      start=-90, end=end_angle, fill=fill_color)

    # White border
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 outline=(255, 255, 255, 180), width=2)

    # Percentage text
    text = f"{int(pct)}%"
    font_size = max(10, size // 4)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2), text,
              font=font, fill=(255, 255, 255, 255))

    return img
