from PIL import Image, ImageDraw, ImageFont


def _bg_color(pct: float) -> tuple:
    if pct < 50:
        return (30, 140, 30, 255)
    elif pct < 80:
        return (200, 140, 0, 255)
    else:
        return (180, 30, 30, 255)


def make_icon(pct: float, cost_usd: float = 0.0, size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Solid colored background square (rounded look via ellipse)
    bg = _bg_color(pct)
    draw.rectangle([0, 0, size - 1, size - 1], fill=bg)

    # Big bold number centered
    text = str(min(int(pct), 999))
    font_size = size - 10 if len(text) <= 2 else size - 18
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = (size - tw) // 2 - bb[0]
    y = (size - th) // 2 - bb[1]
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    return img
