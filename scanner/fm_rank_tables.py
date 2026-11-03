"""Reconhecimento automático (e conservador) de tabelas de pontos RANK.

Busca estruturas de 10 critérios × 5 pares <limiar u16, pontos i16> em
qualquer offset de WA_MRG.MRG, não apenas no endereço X15. Requer 40 blocos
com conteúdos idênticos e espaçamento de três setores PS1. Isso valida a
estrutura dos pontos, NÃO demonstra que o executável MIPS a utilize.
"""
from __future__ import annotations

import hashlib
import struct
from collections import Counter

BLOCK_FIRST_SECTOR = 7475        # Endereço do X15: somente referência forense
BLOCK_SECTORS = 3
SECTOR = 2048
BLOCK_COUNT = 40
POINT_TABLE_OFFSET = 0x16D0
ROW_COUNT = 10
BANDS_PER_ROW = 5
RECORD_SIZE = 4
TABLE_SIZE = ROW_COUNT * BANDS_PER_ROW * RECORD_SIZE
STRIDE = BLOCK_SECTORS * SECTOR
KNOWN_X15_TABLE_SHA256 = "dffacc55349f6b565d9e9a70db20ce9fe5f5ef5702a5bcc7c35926b764af28e0"
KNOWN_X15_SLUS_SHA256 = "67ef6a3f7999bc4b0e09f773b07ee1c5da829a4d4686f1f2f6c8d4e2d6425bec"
X15_RULE_NAMES = (
    "turns", "effective_attacks", "defense_wins", "face_down",
    "spells", "traps", "cards_used", "remaining_lp", "fusions", "equips",
)
MAX_WA_BYTES = 96 * 1024 * 1024
MAX_ANCHORS = 250_000  # limite de CPU para mods malformados
LEGACY_OFFSET = BLOCK_FIRST_SECTOR * SECTOR + POINT_TABLE_OFFSET
LAST_BAND_OFFSET = (BANDS_PER_ROW - 1) * RECORD_SIZE


def _empty(status: str, *, message: str) -> dict:
    return {
        "status": status, "available": False, "rules": {},
        "runtime_verified": False, "binary_verified": False,
        "structure_verified": False, "table_sha256": None,
        "table_count": 0, "identical_copies": 0,
        "source": "DATA/WA_MRG.MRG", "first_offset": None,
        "criterion_names_verified": False,
        "base_points": None, "lp_victory_bonus": None,
        "slus_sha256": None, "note": message,
        "method": "automatic_stride_scan",
    }


def _decode_table(data: bytes) -> list[list[tuple[int, int]]] | None:
    if len(data) != TABLE_SIZE:
        return None
    values = struct.unpack("<" + "Hh" * (ROW_COUNT * BANDS_PER_ROW), data)
    rows = []
    all_points = []
    for r in range(ROW_COUNT):
        steps = []
        previous = -1
        for j in range(BANDS_PER_ROW):
            threshold, score = values[(r * BANDS_PER_ROW + j)*2:
                                      (r * BANDS_PER_ROW + j)*2 + 2]
            if (threshold <= previous or threshold > 32767
                    or not -128 <= score <= 128
                    or (j == BANDS_PER_ROW-1 and threshold != 32767)
                    or (j != BANDS_PER_ROW-1 and threshold == 32767)):
                return None
            previous = threshold
            steps.append((threshold, score))
            all_points.append(score)
        rows.append(steps)
    if len(set(all_points)) < 3:
        return None
    return rows


MAX_BLOCK_STRIDE = 64 * 1024
MAX_STRUCTURAL_CANDIDATES = 10_000
MAX_REPEATS_PER_HASH = 200


def _candidate_positions(wa: bytes):
    """Âncora barata: o último limiar de cada critério vale 0x7FFF."""
    offset = 0
    seen = 0
    while True:
        pos = wa.find(b"\xff\x7f", offset)
        if pos < 0:
            return
        offset = pos + 2
        seen += 1
        if seen > MAX_ANCHORS:
            raise OverflowError("Limite de busca das estruturas RANK excedido")
        start = pos - LAST_BAND_OFFSET
        # Pares de 16 bits podem ser realocados para alinhamento de 2 bytes.
        if start < 0 or start % 2 != 0 or start + TABLE_SIZE > len(wa):
            continue
        if all(wa[start + LAST_BAND_OFFSET + row * BANDS_PER_ROW * RECORD_SIZE:
                  start + LAST_BAND_OFFSET + row * BANDS_PER_ROW * RECORD_SIZE + 2]
               == b"\xff\x7f" for row in range(ROW_COUNT)):
            yield start


def _find_repeated_tables(wa: bytes) -> list[tuple[int, int, bytes,
                                                 list[list[tuple[int, int]]]]]:
    """Busca 40 tabelas iguais com stride inferido, sem assumir o offset X15."""
    grouped: dict[str, list[int]] = {}
    decoded: dict[str, tuple[bytes, list[list[tuple[int,int]]]]] = {}
    structural_count = 0
    for start in _candidate_positions(wa):
        table = wa[start:start + TABLE_SIZE]
        rules = _decode_table(table)
        if rules is None:
            continue
        structural_count += 1
        if structural_count > MAX_STRUCTURAL_CANDIDATES:
            raise OverflowError("Candidatos estruturais demais")
        digest = hashlib.sha256(table).hexdigest()
        locations = grouped.setdefault(digest, [])
        locations.append(start)
        if len(locations) > MAX_REPEATS_PER_HASH:
            raise OverflowError("Cópias estruturais em excesso")
        decoded.setdefault(digest, (table, rules))

    results = []
    for digest, offsets in grouped.items():
        if len(offsets) < BLOCK_COUNT:
            continue
        offsets.sort()
        available = set(offsets)
        for i, first in enumerate(offsets):
            if len(offsets)-i < BLOCK_COUNT:
                break
            for second in offsets[i+1:]:
                stride = second-first
                if stride > MAX_BLOCK_STRIDE:
                    break
                if stride < TABLE_SIZE or stride % 2 != 0:
                    continue
                if first+(BLOCK_COUNT-1)*stride not in available:
                    continue
                if all(first+n*stride in available for n in range(BLOCK_COUNT)):
                    table, rules = decoded[digest]
                    results.append((first, stride, table, rules))
                    if len(results) > 1:
                        return results
    return results


def _legacy_diagnostic(wa: bytes) -> dict:
    """Preserva explicação específica para mods parcialmente alterados."""
    last = LEGACY_OFFSET + (BLOCK_COUNT - 1)*STRIDE + TABLE_SIZE
    if len(wa) < last:
        return _empty("layout_unknown", message="WA não contém layout conhecido de 40 blocos.")
    samples = [wa[LEGACY_OFFSET + i*STRIDE:
                  LEGACY_OFFSET + i*STRIDE + TABLE_SIZE]
               for i in range(BLOCK_COUNT)]
    digests = [hashlib.sha256(t).hexdigest() for t in samples]
    unique, identical = Counter(digests).most_common(1)[0]
    if (identical > 1 and identical < BLOCK_COUNT
            and _decode_table(samples[digests.index(unique)]) is not None):
        result = _empty(
            "divergent_rank_tables",
            message="Existem tabelas RANK diferentes entre os 40 duelistas; "
                    "não é seguro usar uma pontuação única para todos.")
        result.update(table_count=BLOCK_COUNT, identical_copies=identical)
        return result
    return _empty("rank_table_unrecognized",
                  message="Nenhuma tabela de RANK completa e repetida foi identificada.")


def extract_rank_table(wa: bytes, *, slus: bytes | None = None,
                       rom_sha256: str | None = None,
                       known_rom_sha256: str | None = None) -> dict:
    """Detecta estrutura por conteúdo; nunca presume pontos de outros mods."""
    if not isinstance(wa, bytes) or not 0 < len(wa) <= MAX_WA_BYTES:
        return _empty("invalid_wa", message="WA indisponível ou acima do limite seguro.")
    try:
        matches = _find_repeated_tables(wa)
        if len(matches) > 1:
            return _empty(
                "ambiguous_rank_tables",
                message="Há mais de uma sequência completa de pontuação. "
                        "É necessária inspeção do SLUS antes de escolher.")
    except OverflowError:
        return _empty("rank_scan_limit",
                      message="ISO apresenta padrões demais; busca interrompida por segurança.")

    if not matches:
        return _legacy_diagnostic(wa)

    first, repeat_stride, table, parsed = matches[0]
    table_sha = hashlib.sha256(table).hexdigest()
    slus_digest = hashlib.sha256(slus).hexdigest() if isinstance(slus,bytes) else None
    known_iso = (isinstance(rom_sha256,str) and isinstance(known_rom_sha256,str)
                 and rom_sha256.lower() == known_rom_sha256.lower())
    known_binary = (
        known_iso and first == LEGACY_OFFSET and repeat_stride == STRIDE
        and slus_digest == KNOWN_X15_SLUS_SHA256
        and table_sha == KNOWN_X15_TABLE_SHA256
    )
    names = X15_RULE_NAMES if known_binary else tuple(
        f"criterion_{i:02d}" for i in range(1, ROW_COUNT + 1))
    return {
        "status": ("known_x15_verified_binary" if known_binary
                   else "candidate_table_repeated_40x"),
        "available": True,
        "rules": {
            name: [{"below": below, "points": points} for below,points in steps]
            for name,steps in zip(names,parsed)
        },
        "structure_verified": True,
        "binary_verified": known_binary,
        # Assinaturas confirmam arquivos, não resultados executados no ePSXe.
        "runtime_verified": False,
        "table_sha256": table_sha,
        "table_count": BLOCK_COUNT,
        "identical_copies": BLOCK_COUNT,
        "source": "DATA/WA_MRG.MRG",
        "first_offset": first,
        "first_sector": first // SECTOR,
        "repeat_stride": repeat_stride,
        "criterion_names_verified": known_binary,
        "known_x15_table_content": table_sha == KNOWN_X15_TABLE_SHA256,
        "base_points": 50 if known_binary else None,
        "lp_victory_bonus": 2 if known_binary else None,
        "slus_sha256": slus_digest,
        "method": "automatic_stride_scan",
        "layout_moved": first != LEGACY_OFFSET or repeat_stride != STRIDE,
        "note": (
            "Tabela WA, executável SLUS e SHA da imagem conferem com a perícia "
            "X15. A leitura de RANK na RAM ainda requer teste em duelo real."
            if known_binary else
            "Foram reconhecidas automaticamente 40 cópias idênticas dos "
            "10 critérios de pontos no WA, mesmo com offset ou espaçamento "
            "entre blocos alterado. O uso da tabela pelo SLUS e os nomes dos "
            "critérios ainda NÃO foram confirmados neste mod."),
    }
