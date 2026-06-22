from PIL import Image, ImageDraw, ImageFont


def _pct_color(pct: float) -> tuple:
    if pct < 50:
        r = int(pct / 50 * 255)
        return (r, 200, 50)
    else:
        g = int((1 - (pct - 50) / 50) * 200)
        return (255, g, 30)


def make_icon(pct: float, cost_usd: float = 0.0, size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    r = size // 2 - 2
    bg_color = (40, 40, 40, 230)
    fill_color = _pct_color(pct) + (240,)

    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bg_color)

    arc_pct = min(pct, 100)
    if arc_pct > 0:
        end_angle = -90 + (arc_pct / 100) * 360
        draw.pieslice([cx - r, cy - r, cx + r, cy + r],
                      start=-90, end=end_angle, fill=fill_color)

    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 outline=(200, 200, 200, 200), width=2)

    try:
        font_big   = ImageFont.truetype("arial.ttf", max(9, size // 4))
        font_small = ImageFont.truetype("arial.ttf", max(7, size // 5))
    except OSError:
        font_big = font_small = ImageFont.load_default()

    # Top: percentage
    pct_text = f"{min(int(pct), 999)}%"
    bb = draw.textbbox((0, 0), pct_text, font=font_big)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((cx - tw // 2, cy - th - 1), pct_text,
              font=font_big, fill=(255, 255, 255, 255))

    # Bottom: cost in USD
    if cost_usd >= 1.0:
        cost_text = f"${cost_usd:.2f}"
    else:
        cost_text = f"${cost_usd:.3f}"

    bb2 = draw.textbbox((0, 0), cost_text, font=font_small)
    tw2, th2 = bb2[2] - bb2[0], bb2[3] - bb2[1]
    draw.text((cx - tw2 // 2, cy + 2), cost_text,
              font=font_small, fill=(220, 220, 220, 230))

    return img
