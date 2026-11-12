"""DUELTRACE v0.14.0 — high-DPI classic card face.

Only consumes already decoded data from the active ISO; never invents
attributes or modifies source artwork. This file is standalone and importable
by PyInstaller through an ordinary static import.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

SIZE = (540, 780)  # 9:13, native high-resolution render
MAX_CARD_ID = 722


@lru_cache(maxsize=128)
def _font(px: int, bold: bool = False):
    paths = (["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
             if bold else ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for name in paths:
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            pass
    return ImageFont.load_default()


def _bbox_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _fit(draw: ImageDraw.ImageDraw, value: object, max_width: int,
         sizes: tuple[int, ...], bold: bool = False) -> tuple[str, object]:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    for size in sizes:
        font = _font(size, bold)
        if _bbox_width(draw, text, font) <= max_width:
            return text, font
    font = _font(sizes[-1], bold)
    while text and _bbox_width(draw, text + "…", font) > max_width:
        text = text[:-1]
    return text + "…" if text else "", font


def _wrap(draw: ImageDraw.ImageDraw, text: str, width: int,
          font, limit: int) -> list[str]:
    lines = []
    current = ""
    for word in text.replace("\r", " ").replace("\n", " ").split():
        test = f"{current} {word}".strip()
        if _bbox_width(draw, test, font) <= width:
            current = test
            continue
        if current:
            lines.append(current)
            current = ""
        # Split very long unbroken words without overflowing the description.
        while word and _bbox_width(draw, word, font) > width:
            n = len(word)
            while n > 1 and _bbox_width(draw, word[:n], font) > width:
                n -= 1
            lines.append(word[:n])
            word = word[n:]
            if len(lines) >= limit:
                break
        current = word
        if len(lines) >= limit:
            break
    if current and len(lines) < limit:
        lines.append(current)
    return lines[:limit]


def _number(value) -> str:
    # No fabricated zero/9999 when a mod has not exposed an actual stat.
    return str(value) if type(value) is int and 0 <= value <= 99999 else "—"


def render_card_v014(fields: dict, art: Image.Image, card_id) -> Image.Image:
    """Render a readable 540×780 card with ATK/DEF INSIDE the card face.

    The supplied ``fields`` is the output of the existing ``card_fields``
    decoder. Art is taken exclusively from this card's active-ISO cache.
    """
    if not (16 <= art.width <= 2048 and 16 <= art.height <= 2048):
        raise ValueError("Dimensões da arte inválidas")
    if art.width * art.height > 2048 * 2048:
        raise ValueError("Imagem acima do limite permitido")

    category = str(fields.get("category") or "Não identificado")
    monster = fields.get("monster") is True
    if category == "Mágicas":
        palette = ((57, 125, 111), (25, 79, 70), (205, 242, 220))
    elif category == "Armadilhas":
        palette = ((144, 89, 131), (83, 46, 86), (241, 213, 238))
    else:
        palette = ((210, 164, 81), (115, 76, 38), (252, 231, 176))
    parchment, outline, highlight = palette
    ink = (42, 28, 14)

    card = Image.new("RGB", SIZE, parchment)
    draw = ImageDraw.Draw(card)
    # Draw at final output resolution, so borders/glyphs are not post-upscaled.
    for y in range(SIZE[1]):
        border_weight = abs(y - SIZE[1] // 2) / (SIZE[1] / 2)
        shade = int(border_weight * 28)
        draw.line((0, y, SIZE[0] - 1, y),
                  fill=tuple(max(0, c - shade) for c in parchment), width=1)
    draw.rounded_rectangle((6, 6, 533, 773), radius=19, outline=(62, 40, 22), width=8)
    draw.rounded_rectangle((16, 16, 523, 762), radius=14, outline=highlight, width=5)
    draw.rounded_rectangle((30, 30, 510, 101), radius=8,
                           fill=tuple(min(255, c + 18) for c in parchment),
                           outline=outline, width=4)
    draw.line((39, 37, 500, 37), fill=highlight, width=3)

    # Title does not intrude into the right-aligned attribute medallion.
    title, title_font = _fit(draw, fields.get("name") or "Carta", 366,
                             (31, 29, 26, 23, 21), True)
    draw.text((43, 54), title, font=title_font, fill=ink)
    draw.ellipse((443, 41, 498, 95), fill=(39, 43, 46), outline=highlight, width=4)
    attr, attr_font = _fit(draw, fields.get("attribute") or "", 46,
                            (13, 12, 11, 10), True)
    draw.text((470 - _bbox_width(draw, attr, attr_font)//2, 63), attr,
              font=attr_font, fill=highlight)

    # Levels are reported as extracted, never inferred from ATK/DEF.
    level = fields.get("level")
    if monster and type(level) is int and level > 0:
        if level <= 12:
            diameter = 23 if level <= 10 else 19
            spacing = 30 if level <= 10 else 24
            width = level * spacing
            x0 = max(42, 495 - width)
            for n in range(level):
                x = x0 + n * spacing
                draw.ellipse((x, 123, x + diameter, 123 + diameter),
                             fill=(191, 73, 27), outline=(102, 42, 15), width=2)
                draw.ellipse((x + 5, 128, x + 10, 133), fill=(255, 216, 89))
        else:
            label = f"NÍVEL {level}"
            draw.text((400, 124), label, font=_font(18, True), fill=ink)

    # Illustration is fitted *without cropping* into the central art window.
    art_frame = (40, 160, 499, 552)
    draw.rounded_rectangle(art_frame, radius=8, fill=(24, 29, 34),
                           outline=outline, width=7)
    draw.rectangle((49, 168, 490, 544), outline=highlight, width=3)
    original = art.convert("RGB")
    fitted = ImageOps.contain(original, (432, 367), method=Image.Resampling.LANCZOS)
    x = 270 - fitted.width // 2
    y = 356 - fitted.height // 2
    card.paste(fitted, (x, y))
    draw.rectangle((51, 170, 488, 542), outline=(23, 33, 36), width=3)

    # Two distinct areas inside ONE card — description and stats.
    draw.rounded_rectangle((32, 567, 508, 731), radius=7,
                           fill=(239, 215, 165), outline=outline, width=4)
    draw.line((361, 577, 361, 720), fill=outline, width=3)
    kind, kind_font = _fit(draw, "[" + str(fields.get("kind") or category) + "]",
                           302, (20, 18, 16), True)
    draw.text((45, 580), kind, font=kind_font, fill=ink)
    description = str(fields.get("description") or "").strip()
    desc_font = _font(17)
    if description:
        desc_lines = _wrap(draw, description, 299, desc_font, 5)
        for j, line in enumerate(desc_lines):
            draw.text((45, 611 + j * 22), line, font=desc_font, fill=ink)
    else:
        draw.text((45, 619), "Texto indisponível", font=desc_font,
                  fill=(110, 87, 62))

    if monster:
        for tag, val, y in (("ATK", fields.get("atk"), 591),
                            ("DEF", fields.get("def"), 657)):
            draw.text((374, y), tag, font=_font(19, True), fill=ink)
            num = _number(val)
            number_text, number_font = _fit(draw, num, 112, (28, 25, 23, 20, 18), True)
            draw.text((497 - _bbox_width(draw, number_text, number_font), y + 23),
                      number_text, font=number_font, fill=ink)
            if tag == "ATK":
                draw.line((373, 653, 498, 653), fill=outline, width=2)
    else:
        label, label_font = _fit(draw, category, 123, (22, 19, 17), True)
        draw.text((375, 623), label, font=label_font, fill=ink)

    cid = card_id if type(card_id) is int and 1 <= card_id <= MAX_CARD_ID else None
    draw.text((40, 743), f"DT-{cid:03d}" if cid is not None else "DUELTRACE",
              font=_font(15, True), fill=(62, 43, 24))
    draw.text((378, 743), "LOCAL · MOD", font=_font(13), fill=(73, 50, 27))
    return card