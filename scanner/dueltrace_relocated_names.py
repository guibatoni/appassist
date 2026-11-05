"""Localiza possíveis bases de ponteiros, textos e glifos realocadas.

A descoberta trabalha com o formato de nomes FM já documentado: ponteiros
u16, registros terminados em FF, cabeçalho opcional F8 0A e glifos Shift-JIS
em células de quatro bytes. É um adaptador, não um decoder universal.

Todas as hipóteses permanecem NÃO VERIFICADAS: não habilitar IDs, drops,
efeitos ou perfis com este resultado. A rotina é local, limitada e somente
leitura; não usa nomes canônicos do jogo para presumir identidade.
"""
from __future__ import annotations

from collections import Counter
import struct

from dueltrace_name_boundaries import read_glyphs, read_name_table
from dueltrace_card_opponent_discovery import _plausible_name

MAX_EXE_BYTES = 8 * 1024 * 1024
MAX_SHIFT = 32768
MAX_GLYPH_SHIFT = 16384
MAX_POINTER_LAYOUTS = 6
MAX_GLYPH_LAYOUTS = 8
MAX_TEXT_LAYOUTS = 8
MAX_FINAL_LAYOUTS = 6

_CARD_IDS = tuple(range(1, 723))
_OPP_IDS = tuple(range(0x329, 0x350))
_INDICES = _CARD_IDS + _OPP_IDS
_PTR_SAMPLES = (1, 2, 10, 25, 50, 100, 200, 350, 500, 650, 722,
                0x329, 0x32A, 0x330, 0x340, 0x34F)
_HEADER_SAMPLES = (2, 10, 50, 100, 200, 350, 500, 650, 722,
                   0x32A, 0x330, 0x340)


def _pointer_candidates(sl: bytes, known: int, radius: int) -> tuple[list[int], int]:
    """Encontra sequências completas plausíveis sem decodificar os glifos."""
    found = []
    tested = 0
    lo = max(0, known - radius)
    hi = min(len(sl) - (0x350 * 2), known + radius)
    if hi < lo:
        return found, tested
    for base in range(lo + lo % 2, hi + 1, 2):
        tested += 1
        values = [struct.unpack_from("<H", sl, base + i * 2)[0]
                  for i in _PTR_SAMPLES]
        if not all(values) or max(values) > 0xFF00 or len(set(values)) < 15:
            continue
        # Ponteiros para nomes tendem a progredir em ambos os grupos, mas
        # não pressupor contiguidade entre as cartas e os oponentes.
        card = values[:11]
        opponent = values[11:]
        if any(b <= a for a, b in zip(card, card[1:])):
            continue
        if any(b <= a for a, b in zip(opponent, opponent[1:])):
            continue
        if any(b - a < 2 or b - a > 18000
               for a, b in zip(card, card[1:])):
            continue
        if opponent[-1] - opponent[0] > 0xFFF0:
            continue
        found.append(base)
        if len(found) >= MAX_POINTER_LAYOUTS:
            break
    return found, tested


def _glyph_candidates(sl: bytes, known: int, radius: int) -> tuple[list[int], int]:
    """Reconhece células Shift-JIS intercaladas, não blocos de texto avulsos."""
    candidates = []
    examined = 0
    lo = max(0, known - radius)
    hi = min(len(sl) - 93 * 4, known + radius)
    for base in range(lo + (4 - lo % 4) % 4, hi + 1, 4):
        examined += 1
        # Código de glifo 0 corresponde ao espaço no layout conhecido.
        if sl[base:base + 4] != b"\x00" * 4:
            continue
        # Index 1 deve apontar para um glifo legível; evita candidatos
        # deslocados um glifo para a esquerda/direita.
        if sl[base + 4:base + 6] == b"\x00\x00":
            continue
        # Um bloco esparso/zerado não é uma tabela válida.
        populated = sum(sl[base + i*4:base + i*4+2] != b"\x00\x00"
                        for i in range(1, 93))
        if populated < 24:
            continue
        try:
            glyphs = read_glyphs(sl, base)
        except (ValueError, UnicodeError, struct.error):
            continue
        usable = {g for g in glyphs if (len(g) == 1 and g.isprintable()
                                        and g.isalnum())}
        if len(usable) < 24:
            continue
        candidates.append((base, len(usable)))
    candidates.sort(key=lambda x: (-x[1], abs(x[0] - known), x[0]))
    return [x[0] for x in candidates[:MAX_GLYPH_LAYOUTS]], examined


def _text_candidates(sl: bytes, pointer_base: int, known_text: int,
                     radius: int) -> list[tuple[int, int]]:
    """Deriva bases pelo cabeçalho opcional F8 0A em IDs independentes.

    Sem cabeçalhos suficientes o parser não tenta adivinhar bases de texto:
    evita buscas quadráticas na ROM e evita aprovar um FF casual.
    """
    pointers = {}
    for index in _HEADER_SAMPLES:
        at = pointer_base + index*2
        if at + 2 > len(sl):
            return []
        pointers[index] = struct.unpack_from("<H", sl, at)[0]
    min_ptr, max_ptr = min(pointers.values()), max(pointers.values())
    lo = max(0, known_text-radius+min_ptr)
    hi = min(len(sl), known_text+radius+max_ptr+3)
    area = sl[lo:hi]
    votes = Counter()
    contributions = {}
    offset = area.find(b"\xf8\x0a")
    while offset >= 0:
        physical = lo + offset
        for idx, ptr in pointers.items():
            base = physical - ptr
            if abs(base-known_text) <= radius and base >= 0:
                votes[base] += 1
                contributions.setdefault(base, set()).add(idx)
        offset = area.find(b"\xf8\x0a", offset+1)
    viable = []
    for base, count in votes.items():
        ids = contributions[base]
        cards = sum(i <= 722 for i in ids)
        opp = sum(i >= 0x329 for i in ids)
        if count >= 4 and cards >= 3 and opp >= 1:
            viable.append((base, count))
    viable.sort(key=lambda item: (-item[1], abs(item[0]-known_text), item[0]))
    return viable[:MAX_TEXT_LAYOUTS]


def discover_relocated_name_layout(
    exe: bytes, *, pointer_base: int, text_base: int, glyph_base: int,
    max_shift: int = MAX_SHIFT, max_glyph_shift: int = MAX_GLYPH_SHIFT
) -> dict:
    """Descobre layouts candidatos, nunca promove tabelas ao perfil do mod."""
    result = {
        "schema": 1, "state": "nao_encontrado",
        "validated": False, "executionConfirmed": False,
        "candidates": [], "pointerBasesExamined": 0,
        "glyphBasesExamined": 0,
        "limits": {}, "note": "Evidência estrutural, não identidade validada."
    }
    if (not isinstance(exe, bytes) or len(exe) > MAX_EXE_BYTES
            or min(pointer_base, text_base, glyph_base) < 0
            or glyph_base + 93*4 > len(exe)):
        result["state"] = "executavel_incompativel"
        return result
    radius = max(0, min(MAX_SHIFT, max_shift)) if type(max_shift) is int else 0
    glyph_radius = (max(0, min(MAX_GLYPH_SHIFT, max_glyph_shift))
                    if type(max_glyph_shift) is int else 0)
    result["limits"] = {"pointerAndTextShift": radius,
                        "glyphShift": glyph_radius}
    pointers, tested = _pointer_candidates(exe, pointer_base, radius)
    result["pointerBasesExamined"] = tested
    glyphs, tested = _glyph_candidates(exe, glyph_base, glyph_radius)
    result["glyphBasesExamined"] = tested
    if not pointers or not glyphs:
        result["state"] = "ponteiros_ou_glifos_nao_localizados"
        return result

    layouts = []
    for pbase in pointers:
        text_positions = _text_candidates(exe, pbase, text_base, radius)
        for tbase, votes in text_positions:
            for gbase in glyphs:
                # Rejeitar a combinação já tratada pelo scanner conhecido.
                if (pbase, tbase, gbase) == (
                        pointer_base, text_base, glyph_base):
                    continue
                try:
                    records = read_name_table(
                        exe, pointer_base=pbase, text_base=tbase,
                        glyph_base=gbase, indices=_INDICES, max_bytes=100)
                except (ValueError, UnicodeError, struct.error):
                    continue
                def verified_format(idx: int) -> bool:
                    row = records[idx]
                    return (row["recordStatus"] == "ff_encontrado"
                            and _plausible_name(row["readablePrefix"]))
                if not all(verified_format(i) for i in (1, 722, 0x329, 0x34F)):
                    continue
                good_cards = [i for i in _CARD_IDS if verified_format(i)]
                good_opp = [i for i in _OPP_IDS if verified_format(i)]
                if len(good_cards) < 720 or len(good_opp) < 38:
                    continue
                names_cards = {records[i]["readablePrefix"]
                               for i in good_cards}
                names_opp = {records[i]["readablePrefix"] for i in good_opp}
                if len(names_cards) < 700 or len(names_opp) < 37:
                    continue
                layouts.append({
                    "pointerBase": pbase, "textBase": tbase,
                    "glyphBase": gbase,
                    "pointerShift": pbase-pointer_base,
                    "textShift": tbase-text_base,
                    "glyphShift": gbase-glyph_base,
                    "headerVotes": votes,
                    "cardNamesTerminated": len(good_cards),
                    "opponentNamesTerminated": len(good_opp),
                    "distinctCardNames": len(names_cards),
                    "distinctOpponentNames": len(names_opp),
                    "cardSamples": [
                        {"id": i, "text": records[i]["readablePrefix"][:52]}
                        for i in (1, 100, 500, 722)],
                    "opponentSamples": [
                        {"id": i-0x328, "text": records[i]["readablePrefix"][:52]}
                        for i in (0x329, 0x33C, 0x34F)],
                    "validated": False,
                })
                if len(layouts) >= MAX_FINAL_LAYOUTS:
                    break
            if len(layouts) >= MAX_FINAL_LAYOUTS:
                break
        if len(layouts) >= MAX_FINAL_LAYOUTS:
            break
    result["candidates"] = layouts
    result["state"] = ("hipoteses_ambiguas" if len(layouts) > 1
                       else "layout_candidato_localizado" if layouts
                       else "nao_encontrado")
    return result
