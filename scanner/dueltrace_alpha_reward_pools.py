"""ALPHA: safe source-bound discovery of the 39 opponent REWARD pools.

Unlike a deck table, the three reward arrays of each duelist record are
indexed by card ID and determine which card CAN drop. The original retail
resource starts with an unused 6144-byte record 0. The three privately supplied
mods show the *same* exact record-zero SHA-256 even when all 39 later records
change. This is a strict format signature, not an in-game MIPS proof.

No ROM content is uploaded, changed, or merged across ISO profiles. Unknown
format/ambiguous layouts fail closed. No runtime RANK or identity binding
becomes verified from these structural observations.
"""
from __future__ import annotations

import hashlib
import struct

from dueltrace_mod_family_probe import decode_matrix, verify_block

CARD_COUNT = 722
DUELISTS = 39
BLOCK_BYTES = 0x1800
GROUP_STRIDE = 0x5B4
TOTAL = 2048
MAX_WA = 96 * 1024 * 1024
# Hash of the full original unused record 0; no copyrighted binary stored.
RETAIL_UNUSED_BLOCK_SHA256 = (
    "1b3925724cfbf58197fc79a8b1166387d9a438ffdf35162c8e863b852bd8b4f7"
)
GROUPS = ("S/A POW", "B/C/D POW/TEC", "S/A TEC")


def _empty(status):
    return {
        "schema": 1, "available": False, "status": status,
        "candidateMode": "structural_only", "source": "own_iso_wa",
        "opponentBlocks": 0, "dropMatrices": 0, "rowCount": 0,
        "base": None, "encoding": None, "rows": [],
        "opponentIdentityVerified": False, "rankGroupLabelsVerified": False,
        "verifiedInGame": False, "mayActivateDrops": False,
        "mayActivateRank": False,
    }


def _valid_matrix(blob, at, codec):
    row = decode_matrix(blob, at, codec)
    if row is None or sum(v > 0 for v in row) < 3:
        return None
    return row


def _read_run(wa, base):
    """Validate 39 complete records after the known unused record-zero."""
    if base < BLOCK_BYTES or base % BLOCK_BYTES not in (0,):
        # The resource may be relocated to an unaligned offset in a future
        # mod; do not silently accept it under this known-layout adapter.
        return None
    if base + DUELISTS * BLOCK_BYTES > len(wa):
        return None
    rows = []
    codecs = set()
    for opponent in range(DUELISTS):
        record = base + opponent * BLOCK_BYTES
        # Group 0 holds the deck distribution: validate it, do NOT export it.
        if _valid_matrix(wa, record, "plain") is None:
            return None
        for group_index, label in enumerate(GROUPS, 1):
            at = record + GROUP_STRIDE * group_index
            weights = _valid_matrix(wa, at, "plain")
            codec = "plain"
            if weights is None:
                weights = _valid_matrix(wa, at, "x15_masked")
                codec = "x15_masked"
            if weights is None:
                return None
            codecs.add(codec)
            for card_id, weight in enumerate(weights, 1):
                if weight:
                    rows.append({
                        "opponent_id": opponent + 1,
                        "card_id": card_id,
                        "group": label, "weight": weight,
                        "source_offset": at + (card_id - 1) * 2,
                    })
    if len(rows) > DUELISTS * 3 * CARD_COUNT:
        return None
    return rows, sorted(codecs)


def discover_alpha_reward_pools(wa: bytes) -> dict:
    """Identify the 39 real-table candidates after retail sentinel block.

    This identification is deterministic across observed Galaxy, Rising and
    Enhance ISOs, including the latter's two overlapping 39-row windows.
    A sentinel can exist at a relocated WA offset: scan 2048-byte pages
    without assuming a fixed byte address. A second valid run is ambiguous
    and therefore not selected. Names are supplied by *that ISO's* catalog.
    """
    if not isinstance(wa, bytes) or not 40 * BLOCK_BYTES <= len(wa) <= MAX_WA:
        return _empty("invalid_resource")
    matches = []
    for start in range(0, len(wa) - 40 * BLOCK_BYTES + 1, 2048):
        if (hashlib.sha256(wa[start:start + BLOCK_BYTES]).hexdigest()
                != RETAIL_UNUSED_BLOCK_SHA256):
            continue
        first = start + BLOCK_BYTES
        decoded = _read_run(wa, first)
        if decoded is None:
            continue
        matches.append((first, decoded))
        if len(matches) > 1:
            return _empty("ambiguous_retail_sentinel_runs")
    if len(matches) != 1:
        return _empty("no_verified_retail_sentinel_run")
    base, (rows, codecs) = matches[0]
    return {
        **_empty("structural_39_reward_tables"),
        "available": True,
        "opponentBlocks": DUELISTS,
        "dropMatrices": DUELISTS * 3,
        "rowCount": len(rows),
        "base": base,
        "encoding": "+".join(codecs),
        "rows": rows,
        "signature": "matching_unused_retail_block0_and_39_complete_reward_records",
        "note": (
            "As cartas e os pesos foram extraidos da ISO ativa. O grupo de "
            "RANK e o vinculo dos indices aos nomes do jogo seguem o formato "
            "original presumido; nao houve verificacao MIPS em duelo."
        ),
    }
