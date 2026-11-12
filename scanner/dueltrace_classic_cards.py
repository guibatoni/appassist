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
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont
from dueltrace_card_renderer_v014 import render_card_v014

REVISION = 5
SIZE = (540, 780)
CACHE_FILE = "cartas-hd-cache.json"
MAX_CARDS = 722
MAX_IMAGE_BYTES = 8_000_000
MAX_NAME = 150
MAX_DESCRIPTION = 550

GOLD = (207, 156, 55)
INK = (48, 32, 16)
BORDER = (81, 51, 20)
LIGHT = (249, 222, 137)
PANEL = (235, 203, 127)
DARK_FRAME = (29, 43, 49)


@lru_cache(maxsize=48)
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
    # Respeitar a classificação vinculada ao SHA desta ISO. A versão
    # anterior reinterpretava o código usando a tabela do jogo original.
    if card.get("category_source") == "sondagem_iso_sem_mapeamento_confirmado":
        return (str(card.get("category") or "Não identificado")[:40],
                str(card.get("type_label") or "Tipo a verificar")[:40])
    if card.get("category") and card.get("type_label"):
        return str(card["category"])[:40], str(card["type_label"])[:40]
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
        # Retail nibble mapping. A mod-supplied label always overrides it.
        retail = {0: "LUZ", 1: "TREVAS", 2: "TERRA",
                  3: "ÁGUA", 4: "FOGO", 5: "VENTO"}
        attribute = (retail.get(aid, f"ATR {aid}") if aid is not None and monster
                     else category.upper()[:8])
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
    """High-resolution classic renderer, using only the active ISO's data."""
    return render_card_v014(card_fields(card), art, card.get("id"))

def render_card_pack(cards, originals: Path, enhanced: Path, dest: Path, *,
                     type_analysis=None, type_name_analysis=None):
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
    if isinstance(type_analysis, dict):
        from dueltrace_type_forensics import apply_iso_type_evidence
        cards = apply_iso_type_evidence(
            cards, type_analysis,
            rom_sha256=type_analysis.get("rom_sha256"))
    if isinstance(type_name_analysis, dict):
        from dueltrace_type_names import apply_type_names
        cards = apply_type_names(
            cards, type_name_analysis,
            rom_sha256=type_name_analysis.get("rom_sha256"))
    for card in cards[:MAX_CARDS]:
        cid = _bounded_integer(card.get("id"), MAX_CARDS)
        if not cid or f"{cid:03d}.png" in index:
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
