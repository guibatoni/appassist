"""Extração conservadora de tabelas de pontos RANK do WA_MRG.MRG.

O relatório forense X15 (29/10/2026) localizou 40 cópias de uma tabela de
10 critérios * 5 faixas * (limiar u16 + pontos i16), de 200 bytes cada.
A SHA da tabela é verificável independentemente da identidade da ISO.
Para um mod desconhecido, a TABELA pode ser decodificada, mas a rotina
MIPS que a utiliza, as bonificações, os rótulos e a posição na RAM NÃO
podem ser considerados verificados sem uma auditoria do executável.
"""
from __future__ import annotations

import hashlib
import struct
from collections import Counter

BLOCK_FIRST_SECTOR = 7475
BLOCK_SECTORS = 3
SECTOR = 2048
BLOCK_COUNT = 40
POINT_TABLE_OFFSET = 0x16D0
ROW_COUNT = 10
BANDS_PER_ROW = 5
RECORD_SIZE = 4
TABLE_SIZE = ROW_COUNT * BANDS_PER_ROW * RECORD_SIZE
KNOWN_X15_TABLE_SHA256 = "dffacc55349f6b565d9e9a70db20ce9fe5f5ef5702a5bcc7c35926b764af28e0"
KNOWN_X15_SLUS_SHA256 = "67ef6a3f7999bc4b0e09f773b07ee1c5da829a4d4686f1f2f6c8d4e2d6425bec"

X15_RULE_NAMES = (
    "turns", "effective_attacks", "defense_wins", "face_down",
    "spells", "traps", "cards_used", "remaining_lp", "fusions", "equips",
)
MAX_WA_BYTES = 96 * 1024 * 1024


def _empty(status: str, *, message: str) -> dict:
    return {
        "status": status, "available": False, "rules": {},
        "runtime_verified": False, "table_sha256": None,
        "table_count": 0, "identical_copies": 0,
        "source": "DATA/WA_MRG.MRG", "first_offset": None,
        "criterion_names_verified": False,
        "base_points": None, "lp_victory_bonus": None,
        "slus_sha256": None, "note": message,
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


def extract_rank_table(wa: bytes, *, slus: bytes | None = None,
                       rom_sha256: str | None = None,
                       known_rom_sha256: str | None = None) -> dict:
    """Nunca usa offsets de outras ISOs se as 40 cópias não forem consistentes.

    O teste structural identifica valores de um candidato, não prova que o
    executável tenha a mesma rotina, nem que o rank final seja este modelo.
    """
    if not isinstance(wa, bytes) or not 0 < len(wa) <= MAX_WA_BYTES:
        return _empty("invalid_wa", message="WA indisponível ou acima do limite seguro.")
    last = (BLOCK_FIRST_SECTOR + (BLOCK_COUNT-1)*BLOCK_SECTORS)*SECTOR
    last += POINT_TABLE_OFFSET + TABLE_SIZE
    if len(wa) < last:
        return _empty("layout_unknown", message="WA não contém os 40 registros no layout conhecido.")

    offsets = [
        (BLOCK_FIRST_SECTOR+i*BLOCK_SECTORS)*SECTOR+POINT_TABLE_OFFSET
        for i in range(BLOCK_COUNT)
    ]
    tables = [wa[pos:pos+TABLE_SIZE] for pos in offsets]
    digests = [hashlib.sha256(table).hexdigest() for table in tables]
    counts = Counter(digests)
    most_common, identical = counts.most_common(1)[0]
    if identical != BLOCK_COUNT:
        out = _empty("divergent_rank_tables",
                     message="As 40 cópias não coincidem; não atribuir regras de RANK.")
        out.update(table_count=BLOCK_COUNT, identical_copies=identical)
        return out

    parsed = _decode_table(tables[0])
    if parsed is None:
        return _empty("rank_table_unrecognized",
                      message="Limiar/pontos incompatíveis com o formato documentado.")

    slus_digest = hashlib.sha256(slus).hexdigest() if isinstance(slus, bytes) else None
    known_iso = (isinstance(rom_sha256, str)
                 and isinstance(known_rom_sha256, str)
                 and rom_sha256.lower() == known_rom_sha256.lower())
    known_binary = (known_iso
                    and slus_digest == KNOWN_X15_SLUS_SHA256
                    and most_common == KNOWN_X15_TABLE_SHA256)
    known_content = most_common == KNOWN_X15_TABLE_SHA256

    names = X15_RULE_NAMES if known_binary else tuple(
        f"criterion_{i:02d}" for i in range(1, ROW_COUNT+1))
    return {
        "status": ("known_x15_verified_binary" if known_binary
                   else "candidate_table_repeated_40x"),
        "available": True,
        "rules": {
            name: [{"below": below, "points": points} for below,points in steps]
            for name,steps in zip(names,parsed)
        },
        "runtime_verified": known_binary,
        "table_sha256": most_common,
        "table_count": BLOCK_COUNT,
        "identical_copies": identical,
        "source": "DATA/WA_MRG.MRG",
        "first_offset": offsets[0],
        "first_sector": BLOCK_FIRST_SECTOR,
        "criterion_names_verified": known_binary,
        "known_x15_table_content": known_content,
        "base_points": 50 if known_binary else None,
        "lp_victory_bonus": 2 if known_binary else None,
        "slus_sha256": slus_digest,
        "note": ("40 cópias coincidem, SLUS e SHA da ISO conferidos com o "
                 "relatório forense X15. RAM ainda requer calibração local."
                 if known_binary else
                 "Foram extraídos 10 critérios e 5 faixas por critério de 40 "
                 "cópias idênticas do WA. Não foi comprovado que a rotina "
                 "MIPS desta ISO use essas regras, nem os nomes ou bônus. "
                 "Exibindo apenas os índices e pontos candidatos."),
    }
