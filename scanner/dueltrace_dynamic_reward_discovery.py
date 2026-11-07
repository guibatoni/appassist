"""Read-only 40-record reward detector for FM mods without retail block hash.

The previous ALPHA parser recognized only an exact sentinel block from three
tested mods. Other mods (e.g. GOG 2.2) can relocate/rewrite that block while
retaining 40 consecutive complete 0x1800 records. This module distinguishes:
- strong known-sentinel layout (already supported elsewhere);
- *retail-convention hypothesis*: record zero reserved, records 1..39 drop
  pools (never decks), to be displayed explicitly as provisional.
Both modes remain unverified in game and may not activate live drops or RANK.
"""
from __future__ import annotations

from dueltrace_alpha_reward_pools import (
    BLOCK_BYTES, GROUP_STRIDE, DUELISTS, GROUPS, MAX_WA,
    _read_run, discover_alpha_reward_pools,
)
from dueltrace_mod_family_probe import decode_matrix, discover_weight_families

SUPPORTED_CODECS = ("plain", "x15_masked", "plain_deck_masked_drops")


def _refuse(status):
    return {
        "schema": 2, "available": False, "status": status,
        "rows": [], "rowCount": 0, "opponentBlocks": 0, "dropMatrices": 0,
        "candidateMode": "unresolved", "possible39Windows": 0,
        "opponentIdentityVerified": False, "rankGroupLabelsVerified": False,
        "verifiedInGame": False, "mayActivateDrops": False,
        "mayActivateRank": False,
    }


def _complete_record(raw: bytes, start: int) -> bool:
    """Verify four independent 722-card weight arrays, not just one anchor."""
    if start < 0 or start + BLOCK_BYTES > len(raw):
        return False
    for group in range(4):
        offset = start + group * GROUP_STRIDE
        if (decode_matrix(raw, offset, "plain") is None
                and decode_matrix(raw, offset, "x15_masked") is None):
            return False
    return True


def discover_dynamic_reward_pools(
    wa: bytes, family: dict | None = None,
) -> dict:
    """Decode 40-block families with the first record treated as reserved.

    The 40-block interpretation is a hypothesis supported by retail format
    sources, not independently proved for every mod. This method never
    changes the underlying family evidence's mayActivate flags.
    """
    if not isinstance(wa,bytes) or not 40 * BLOCK_BYTES <= len(wa) <= MAX_WA:
        return _refuse("invalid_resource")
    known = discover_alpha_reward_pools(wa)
    if known["available"]:
        return {
            **known, "schema": 2, "candidateMode": "retail_sentinel",
            "possible39Windows": 2,
        }
    if known["status"] == "ambiguous_retail_sentinel_runs":
        return _refuse("ambiguous_retail_sentinel_runs")
    if family is None:
        family = discover_weight_families(wa)
    if not isinstance(family, dict) or family.get("scanComplete") is not True:
        return _refuse("insufficient_structural_evidence")
    clusters = family.get("clusters")
    if not isinstance(clusters, list):
        return _refuse("no_complete_family_clusters")
    choices = []
    for item in clusters:
        if not isinstance(item, dict):
            continue
        first = item.get("firstBlockOffset")
        if (type(first) is not int or first < 0 or first % 2048
                or item.get("consecutiveBlockCount") != 40
                or item.get("possible39BlockWindows") != 2
                or item.get("opponentStep") != BLOCK_BYTES
                or item.get("matrixStride") != GROUP_STRIDE
                or item.get("encoding") not in SUPPORTED_CODECS
                or item.get("runCapReached") is True):
            continue
        # Revalidate raw bytes: never trust a stored JSON summary alone.
        if not _complete_record(wa,first):
            continue
        if (first >= BLOCK_BYTES and _complete_record(wa, first - BLOCK_BYTES)):
            continue  # Some other 39-window can precede this run.
        if _complete_record(wa,first + 40 * BLOCK_BYTES):
            continue  # Unknown 41+ block run; never silently truncate.
        decoded = _read_run(wa,first + BLOCK_BYTES)
        if decoded is None:
            continue
        choices.append((first,decoded))
    starts = {first for first, _ in choices}
    if len(starts) != 1:
        return _refuse(
            "ambiguous_40_block_runs" if starts else "no_valid_40_block_run"
        )
    first, (rows, codecs) = choices[0]
    return {
        **_refuse("provisional_40_block_retail_convention"),
        "available": True,
        "rowCount": len(rows),
        "opponentBlocks": DUELISTS,
        "dropMatrices": DUELISTS*3,
        "base": first + BLOCK_BYTES,
        "reservedBlockOffset": first,
        "encoding": "+".join(codecs),
        "rows": rows,
        "candidateMode": "40_block_retail_mapping_hypothesis",
        "possible39Windows": 2,
        "source": "same_iso_40_complete_blocks",
        "structurallyConsistent": True,
        "note": (
            "40 blocos completos; por convencao do jogo original o primeiro "
            "foi tratado como reservado. Hipotese nao confirmada para este "
            "mod: nomes, IDs e grupos RANK podem diferir na execucao."
        ),
    }
