"""Extração conservadora de nomes de tipos a partir do executável da ISO.

Uma string solta (como 'GOD') NÃO é evidência. Só aceitamos um banco
indexado, com registros de largura constante e pelo menos 15 âncoras
coerentes com os 20 tipos de varejo em suas posições conhecidas.
Não executa MIPS nem modifica o disco. Se o mod usar glifos gráficos,
ponteiros realocados ou regras fora do executável, retorna desconhecido.
"""
from __future__ import annotations

import re

RETAIL_EN = (
    "DRAGON", "SPELLCASTER", "ZOMBIE", "WARRIOR", "BEAST-WARRIOR",
    "BEAST", "WINGED BEAST", "FIEND", "FAIRY", "INSECT",
    "DINOSAUR", "REPTILE", "FISH", "SEA SERPENT", "MACHINE",
    "THUNDER", "AQUA", "PYRO", "ROCK", "PLANT",
)
RETAIL_ALIASES = {
    1: ("MAGICIAN",),
    4: ("BEAST WARRIOR",),
    6: ("WINGED-BEAST",),
    12: ("FISH",),
    13: ("SEA-SERPENT",),
    16: ("AQUATIC",),
    17: ("FIRE",),
}
SHA = re.compile(r"[0-9a-f]{64}\Z")
LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _/&'.-]{1,27}\Z")
MIN_MATCHED = 15
MIN_START_MATCHED = 3
MIN_END_MATCHED = 3
MAX_SOURCE = 16_000_000
WIDTHS = (12, 16, 20, 24, 28, 32)
SCAN_REVISION = 1


def _norm(v):
    return re.sub(r"[\s_.-]+", " ", v.upper()).strip()


def _known(index, name):
    return _norm(name) in {_norm(RETAIL_EN[index]), *(
        _norm(a) for a in RETAIL_ALIASES.get(index, ()))}


def _record(blob, offset, width):
    raw = blob[offset:offset + width]
    if len(raw) != width:
        return None
    raw = raw.split(b"\x00", 1)[0].strip(b" \xff\x00")
    try:
        word = raw.decode("ascii")
    except UnicodeDecodeError:
        return None
    return word if LABEL.fullmatch(word) else None


def _scan_fixed_width(exe):
    # Only starts anchored at at least one *correctly indexed* retail name.
    # This avoids scanning the entire executable byte by byte at every width.
    upper = exe.upper()
    candidates = {}
    anchors = ((0, b"DRAGON"), (1, b"SPELLCASTER"),
               (2, b"ZOMBIE"), (8, b"FAIRY"),
               (10, b"DINOSAUR"), (14, b"MACHINE"),
               (17, b"PYRO"), (19, b"PLANT"))
    for code, needle in anchors:
        at = -1
        hits = 0
        while hits < 16:
            at = upper.find(needle, at + 1)
            if at < 0:
                break
            hits += 1
            for width in WIDTHS:
                for pad in range(5):
                    start = at - code * width - pad
                    if start < 0 or start + 20 * width > len(exe):
                        continue
                    key = (start, width)
                    if key in candidates:
                        continue
                    rows = [_record(exe, start + k * width, width)
                            for k in range(20)]
                    if any(x is None for x in rows):
                        continue
                    matched = [i for i, name in enumerate(rows)
                               if _known(i, name)]
                    if (len(matched) < MIN_MATCHED
                            or len([i for i in matched if i < 5]) < MIN_START_MATCHED
                            or len([i for i in matched if i >= 15]) < MIN_END_MATCHED):
                        continue
                    candidates[key] = (rows, len(matched))
    return candidates


def extract_type_names(executable: bytes, *, rom_sha256: str) -> dict:
    if type(rom_sha256) is not str or not SHA.fullmatch(rom_sha256):
        raise ValueError("Identificador da ISO inválido")
    result = {
        "schema": 1, "revision": SCAN_REVISION, "rom_sha256": rom_sha256,
        "status": "tabela_nao_localizada",
        "method": "executable_ascii_fixed_width_structural",
        "typeNameMap": {}, "matchedRetailEntries": 0,
        "tableOffset": None, "tableStride": None,
        "candidates": 0, "inGameVerified": False,
    }
    if not isinstance(executable, bytes) or not 0 < len(executable) <= MAX_SOURCE:
        return result
    candidates = _scan_fixed_width(executable)
    result["candidates"] = min(len(candidates), 1000)
    if not candidates:
        return result
    # Multiple plausible but conflicting banks are ambiguous.
    versions = {}
    for (offset, width), (rows, score) in candidates.items():
        changes = tuple((i, rows[i]) for i in range(20)
                        if not _known(i, rows[i]))
        versions.setdefault(changes, []).append((offset, width, score))
    if len(versions) != 1:
        result["status"] = "tabelas_ambiguas"
        return result
    changes, locations = next(iter(versions.items()))
    loc = max(locations, key=lambda row: (row[2], -row[0]))
    result.update({
        "status": "tabela_textual_coerente",
        "typeNameMap": {str(i): value for i, value in changes},
        "matchedRetailEntries": loc[2],
        "tableOffset": loc[0],
        "tableStride": loc[1],
    })
    return result


def apply_type_names(cards, analysis, *, rom_sha256):
    if (not isinstance(analysis, dict) or
            analysis.get("rom_sha256") != rom_sha256 or
            analysis.get("schema") != 1 or
            analysis.get("status") != "tabela_textual_coerente"):
        return [dict(card) for card in cards]
    mapping = analysis.get("typeNameMap")
    if not isinstance(mapping, dict):
        return [dict(card) for card in cards]
    result = []
    for item in cards:
        card = dict(item)
        raw = card.get("type_id", card.get("tipo"))
        if type(raw) is str and raw.isascii() and raw.isdecimal():
            raw = int(raw)
        if type(raw) is int and 0 <= raw <= 31:
            name = mapping.get(str(raw))
            if type(name) is str and LABEL.fullmatch(name):
                # During art extraction cards still have the raw scanner
                # layout, without the 'category' field created by importer.
                from card_catalog import describe_type
                if not card.get("category"):
                    category, _, _ = describe_type(raw)
                    card["category"] = category
                # A class explicitly named GOD is a monster only when the
                # current card's decoded level/stats corroborate it.
                level = card.get("level", card.get("nivel"))
                atk = card.get("atk")
                defense = card.get("def")
                if (_norm(name) in {"GOD", "DEUS", "DIVINE BEAST"}
                        and type(level) is int and level > 0
                        and ((type(atk) is int and atk > 0)
                             or (type(defense) is int and defense > 0))):
                    card["category"] = "Monstros"
                card["type_label"] = name
                card["category_source"] = "tabela_textual_posicional_iso"
        result.append(card)
    return result
