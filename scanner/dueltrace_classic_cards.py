"""Renderização local de cartas clássicas HD inspiradas na composição do anime.

Não copia arquivos de molduras licenciadas: as placas, bordas, estrelas,
badge e tipografia são desenhadas pelo DUELTRACE. Usa exclusivamente a
arte e os atributos realmente extraídos da ISO ativa. A origem permanece
inalterada; o cache é derivado e descartável.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REVISION = 1
SIZE = (360, 520)
CACHE_FILE = "cartas-hd-cache.json"
MAX_CARDS = 722
MAX_IMAGE_BYTES = 4_000_000
MAX_NAME = 150
MAX_DESCRIPTION = 550

GOLD = (207, 156, 55)
INK = (48, 32, 16)
BORDER = (81, 51, 20)
LIGHT = (249, 222, 137)
PANEL = (235, 203, 127)
DARK_FRAME = (29, 43, 49)


def _font(size: int, bold: bool = False):
    # Installed OS fonts only. No fonts shipped with the program.
    options = (["C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
               if bold else
               ["C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for path in options:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text(draw, value, width, size, *, bold=False):
    text = str(value or "").strip().replace("\n", " ")[:MAX_NAME]
    font = _font(size, bold)
    if draw.textbbox((0, 0), text, font=font)[2] <= width:
        return text, font
    while text and draw.textbbox((0, 0), text + "…", font=font)[2] > width:
        text = text[:-1]
    return (text + "…" if text else ""), font


def _read(card, *keys):
    for key in keys:
        value = card.get(key)
        if value is not None and value != "":
            return value
    return None


def _bounded_integer(value, maximum):
    if type(value) is int:
        return value if 0 <= value <= maximum else None
    if isinstance(value, str) and value.isascii() and value.isdigit():
        number = int(value)
        return number if number <= maximum else None
    return None


def _category(card):
    raw = _read(card, "type_id", "tipo")
    if isinstance(raw, str) and raw.isascii() and raw.isdigit():
        raw = int(raw)
    if type(raw) is int:
        from card_catalog import describe_type
        category, label, _evidence = describe_type(raw)
        return category, label
    return (str(card.get("category") or "Não identificado")[:40],
            str(_read(card, "type_label", "type") or "Não identificado")[:40])


def card_fields(card):
    """No guesses for type/level/attribute and no stats for non-monsters."""
    category, kind = _category(card)
    monster = category == "Monstros"
    level = _bounded_integer(_read(card, "level", "nivel"), 99) if monster else None
    attribute = _read(card, "attribute")
    aid = _bounded_integer(_read(card, "attribute_id", "atributo"), 31)
    if not attribute:
        attribute = f"ATR {aid}" if aid is not None and monster else category.upper()[:8]
    description = _read(card, "description_text", "descricao", "description")
    # A description on the scan result is explicitly extracted from this ISO.
    if not isinstance(description, str):
        description = ""
    name = str(_read(card, "name", "nome") or f"Carta #{card.get('id', '?')}")[:MAX_NAME]
    return {
        "name": name,
        "category": category,
        "kind": kind,
        "monster": monster,
        "level": level,
        "attribute": str(attribute)[:14],
        "description": description[:MAX_DESCRIPTION],
        "atk": _bounded_integer(card.get("atk"), 99999) if monster else None,
        "def": _bounded_integer(card.get("def"), 99999) if monster else None,
    }


def _wrap(draw, text, font, max_width, max_lines):
    words = text.replace("\r", " ").replace("\n", " ").split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
            while current and draw.textbbox((0, 0), current, font=font)[2] > max_width:
                lines.append(current[:max(1, len(current) // 2)])
                current = current[max(1, len(current) // 2):]
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return lines


def render_card(card, art: Image.Image) -> Image.Image:
    """360x520: name, attribute, stars, art, info, ATK/DEF and ID footer."""
    if art.width < 16 or art.height < 16 or art.width > 2048 or art.height > 2048:
        raise ValueError("Dimensões da arte inválidas.")
    fields = card_fields(card)
    image = Image.new("RGB", SIZE)
    draw = ImageDraw.Draw(image)
    # Subtle parchment shading, no copied frame image or generated noise.
    for y in range(SIZE[1]):
        edge = abs(y - SIZE[1] // 2) / (SIZE[1] / 2)
        red = int(211 - 22 * edge)
        green = int(162 - 33 * edge)
        blue = int(69 - 17 * edge)
        draw.line((0, y, SIZE[0], y), fill=(red, green, blue))
    draw.rounded_rectangle((4, 4, 355, 515), radius=12,
                           outline=(75, 45, 16), width=5)
    draw.rounded_rectangle((11, 11, 348, 508), radius=9,
                           outline=(246, 209, 121), width=3)
    # Nameplate & attribute are distinctly separated for long names.
    draw.rounded_rectangle((24, 23, 338, 67), radius=5, fill=PANEL,
                           outline=(123, 78, 21), width=3)
    draw.line((28, 28, 332, 28), fill=LIGHT, width=2)
    title, name_font = _text(draw, fields["name"], 263, 22, bold=True)
    draw.text((35, 35), title, font=name_font, fill=INK,
              stroke_width=0)
    draw.ellipse((295, 29, 331, 65), fill=(58, 52, 35),
                 outline=(250, 232, 159), width=3)
    attr, attr_font = _text(draw, fields["attribute"], 31, 9, bold=True)
    tx = (295 + 331 - draw.textbbox((0, 0), attr, font=attr_font)[2]) / 2
    draw.text((tx, 41), attr, font=attr_font, fill=LIGHT)
    # Eight first orbs, then condensed badge for very large mod levels.
    level = fields["level"]
    if level is not None and level > 0:
        count = min(level, 11)
        radius = 9 if count <= 8 else 7
        step = 26 if count <= 8 else 22
        width = count * step
        first = 328 - width
        for i in range(count):
            x = first + i * step + radius
            y = 90
            draw.ellipse((x-radius, y-radius, x+radius, y+radius),
                         fill=(197, 65, 14), outline=(110, 47, 9), width=2)
            draw.ellipse((x-3, y-5, x+1, y-1), fill=(255, 216, 83))
        if level > count:
            draw.text((30, 82), f"NV {level}", font=_font(12, True), fill=INK)

    # The illustration remains unmodified, except a controlled scale.
    draw.rounded_rectangle((33, 109, 327, 378), radius=6,
                           fill=(20, 22, 21), outline=(101, 75, 33), width=5)
    draw.rectangle((39, 115, 321, 371), outline=(242, 203, 105), width=3)
    art_rgb = art.convert("RGB")
    art_rgb.thumbnail((275, 248), Image.Resampling.LANCZOS)
    image.paste(art_rgb, (180 - art_rgb.width // 2, 243 - art_rgb.height // 2))
    draw.rectangle((41, 117, 319, 369), outline=(23, 32, 40), width=2)

    # Description panel and numeric stats occupy separate boxes, per reference.
    draw.rounded_rectangle((23, 389, 220, 489), radius=4,
                           fill=PANEL, outline=BORDER, width=3)
    draw.rounded_rectangle((230, 389, 338, 489), radius=4,
                           fill=PANEL, outline=BORDER, width=3)
    name_kind, kind_font = _text(draw, "[" + fields["kind"] + "]", 181, 13, bold=True)
    draw.text((31, 396), name_kind, font=kind_font, fill=INK)
    description = fields["description"]
    if description:
        body_font = _font(11)
        for j, line in enumerate(_wrap(draw, description, body_font, 180, 5)[:5]):
            draw.text((31, 419 + j * 13), line, font=body_font, fill=INK)
    else:
        draw.text((31, 426), "Texto não disponível",
                  font=_font(11), fill=(102, 76, 42))
    draw.line((237, 439, 331, 439), fill=(129, 89, 32), width=2)
    if fields["monster"]:
        draw.text((238, 404), "ATK", font=_font(14, True), fill=INK)
        draw.text((238, 451), "DEF", font=_font(14, True), fill=INK)
        for number, y in ((fields["atk"], 404), (fields["def"], 451)):
            label = str(number) if number is not None else "—"
            font = _font(18, True)
            right = draw.textbbox((0, 0), label, font=font)[2]
            draw.text((331 - right, y - 1), label, font=font, fill=INK)
    else:
        short, font = _text(draw, fields["category"], 93, 13, bold=True)
        draw.text((237, 431), short, font=font, fill=INK)
    cid = _bounded_integer(card.get("id"), MAX_CARDS)
    draw.text((21, 493), f"DT-{cid:03d}" if cid else "DUELTRACE",
              font=_font(11, True), fill=(70, 47, 25))
    draw.text((260, 495), "LOCAL • MOD", font=_font(9),
              fill=(82, 55, 29))
    return image


def render_card_pack(cards, originals: Path, enhanced: Path, dest: Path):
    """Build once per verified source art + actual card metadata, with cache."""
    originals = Path(originals).resolve(strict=True)
    enhanced = Path(enhanced).resolve()
    dest = Path(dest)
    if dest.is_symlink():
        raise ValueError("Cache de cartas HD não pode ser link simbólico.")
    dest.mkdir(parents=True, exist_ok=True)
    dest = dest.resolve(strict=True)
    if dest == originals or dest.is_relative_to(originals):
        raise ValueError("O renderizador não pode sobrescrever artes originais.")
    manifest_file = dest / CACHE_FILE
    try:
        if manifest_file.is_symlink() or manifest_file.stat().st_size > 512_000:
            raise ValueError("Manifesto inesperado.")
        existing = json.loads(manifest_file.read_text("utf-8"))
        old = existing.get("cards", {}) if existing.get("revision") == REVISION else {}
    except (OSError, ValueError, TypeError):
        old = {}
    if not isinstance(old, dict):
        old = {}
    index = {}
    counts = {"rendered": 0, "cached": 0, "failed": 0}
    for card in cards[:MAX_CARDS]:
        cid = _bounded_integer(card.get("id"), MAX_CARDS)
        if not cid or f"{cid:03d}" in index:
            continue
        filename = f"{cid:03d}.png"
        raw = originals / filename
        hd = enhanced / filename
        source = hd if hd.is_file() and not hd.is_symlink() else raw
        if not source.is_file() or source.is_symlink():
            continue
        try:
            if not 0 < source.stat().st_size <= MAX_IMAGE_BYTES:
                raise ValueError("Imagem fonte inválida.")
            fields = card_fields(card)
            token = hashlib.sha256(source.read_bytes() +
                json.dumps(fields, ensure_ascii=False, sort_keys=True).encode("utf-8") +
                str(REVISION).encode("ascii")).hexdigest()
            target = dest / filename
            if (old.get(filename) == token and target.is_file()
                    and not target.is_symlink()
                    and 0 < target.stat().st_size <= MAX_IMAGE_BYTES):
                with Image.open(target) as test:
                    if test.size == SIZE:
                        counts["cached"] += 1
                        index[filename] = token
                        continue
            if target.is_symlink():
                raise ValueError("Arquivo final não pode ser link simbólico.")
            with Image.open(source) as picture:
                if picture.format != "PNG":
                    raise ValueError("Arte fora do formato PNG.")
                picture.load()
                rendered = render_card(card, picture)
            tmp = dest / (filename + ".tmp")
            try:
                rendered.save(tmp, format="PNG", optimize=True)
                if not 0 < tmp.stat().st_size <= MAX_IMAGE_BYTES:
                    raise ValueError("Carta HD excede o limite.")
                os.replace(tmp, target)
            finally:
                tmp.unlink(missing_ok=True)
            counts["rendered"] += 1
            index[filename] = token
        except (OSError, ValueError, TypeError) as exc:
            counts["failed"] += 1
    pending = dest / (CACHE_FILE + ".tmp")
    try:
        pending.write_text(json.dumps({"revision": REVISION, "cards": index},
                                      separators=(",", ":")), encoding="utf-8")
        os.replace(pending, manifest_file)
    finally:
        pending.unlink(missing_ok=True)
    return {**counts, "available": len(index), "dimensions": list(SIZE),
            "mode": "render_classico_hd_local", "originalsPreserved": True}
