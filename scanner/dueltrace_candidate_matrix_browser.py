"""Read-only browser for structurally identified deck/drop-like matrices.

Do not equate a physical block with an opponent, or any matrix with a RANK.
This module exposes weights from a *local* ISO only to the local user.
It never mutates the game, the mod profile, or an official drops catalog.
"""
from __future__ import annotations

from dueltrace_mod_family_probe import (
    CARD_COUNT, MATRIX_BYTES, CODECS, TOTAL_WEIGHT,
    decode_matrix, verify_block,
)

MAX_ROWS = 60
MAX_QUERY = 80


def _one_cluster(blob: bytes, family: dict) -> dict | None:
    if (not isinstance(blob, bytes) or len(blob) > 96 * 1024 * 1024
            or not isinstance(family, dict)
            or family.get("scanComplete") is not True
            or family.get("state") not in (
                "single_family_unmapped_windows",
                "unique_structural_candidate",
            )):
        return None
    clusters = family.get("clusters")
    if not isinstance(clusters, list) or len(clusters) != 1:
        return None
    row = clusters[0]
    if not isinstance(row, dict):
        return None
    base, count = row.get("firstBlockOffset"), row.get("consecutiveBlockCount")
    step, stride = row.get("opponentStep"), row.get("matrixStride")
    encoding = row.get("encoding")
    if (not all(type(n) is int for n in (base, count, step, stride))
            or base < 0 or base % 2 or step % 2 or stride % 2
            or count < 39 or count > 128
            or stride < MATRIX_BYTES or step < 3 * stride + MATRIX_BYTES
            or encoding not in CODECS
            or base + (count - 1) * step + 3 * stride + MATRIX_BYTES > len(blob)):
        return None
    # A family report is not sufficient by itself: independently verify 39
    # complete physical blocks before publishing candidate weights.
    if verify_block(blob, base, step, stride, encoding) is None:
        return None
    return row


def _card_catalog(catalog) -> dict[int, dict] | None:
    if not isinstance(catalog, list) or len(catalog) > CARD_COUNT:
        return None
    valid = {}
    for item in catalog:
        if not isinstance(item, dict):
            return None
        cid = item.get("id")
        if type(cid) is not int or not 1 <= cid <= CARD_COUNT or cid in valid:
            return None
        name = item.get("name")
        if not isinstance(name, str) or not name or len(name) > 150:
            return None
        valid[cid] = {
            "name": name,
            "atk": item["atk"] if type(item.get("atk")) is int else None,
            "def": item["def"] if type(item.get("def")) is int else None,
            "type": str(item.get("type") or "")[:60],
        }
    return valid


def browse_candidate_matrices(blob: bytes, family: dict, cards: list,
                              *, physical_block_index: int,
                              matrix_group: int = 1, query: str = "",
                              offset: int = 0, limit: int = 30) -> dict:
    """Return candidate rows from *physical* blocks only.

    physical_block_index is zero-based: it is NOT an opponent ID.
    group 0 is deck-like, groups 1–3 are unlabeled drop-like distributions.
    Values are tentative, never promoted into the official drops feature.
    """
    unavailable = {
        "available": False,
        "status": "unavailable_or_ambiguous_family",
        "mayActivateDrops": False,
        "mayActivateRank": False,
        "opponentIdsVerified": False,
        "rankGroupLabelsVerified": False,
        "rows": [],
    }
    if (type(physical_block_index) is not int
            or type(matrix_group) is not int or not 0 <= matrix_group <= 3
            or type(offset) is not int or not 0 <= offset <= CARD_COUNT
            or type(limit) is not int or not 1 <= limit <= MAX_ROWS
            or not isinstance(query, str) or len(query) > MAX_QUERY):
        return {**unavailable, "status": "invalid_request"}
    cluster = _one_cluster(blob, family)
    valid_cards = _card_catalog(cards)
    if cluster is None or valid_cards is None:
        return unavailable
    count = cluster["consecutiveBlockCount"]
    if not 0 <= physical_block_index < count:
        return {**unavailable, "status": "block_outside_detected_family"}
    codec = cluster["encoding"]
    if codec == "plain_deck_masked_drops":
        codec = "plain" if matrix_group == 0 else "x15_masked"
    address = (cluster["firstBlockOffset"]
               + physical_block_index * cluster["opponentStep"]
               + matrix_group * cluster["matrixStride"])
    weights = decode_matrix(blob, address, codec)
    if weights is None or sum(weights) != TOTAL_WEIGHT:
        return unavailable
    needle = query.casefold().strip()
    visible = []
    for cid, weight in enumerate(weights, 1):
        if not weight:
            continue
        info = valid_cards.get(cid, {})
        name = info.get("name", f"Carta #{cid}")
        if needle and needle not in name.casefold() and needle != str(cid):
            continue
        visible.append({
            "id": cid, "name": name,
            "atk": info.get("atk"), "def": info.get("def"),
            "type": info.get("type", ""),
            "weight": weight,
            "weightDenominator": TOTAL_WEIGHT,
            "chancePercent": round(weight * 100 / TOTAL_WEIGHT, 4),
        })
    visible.sort(key=lambda x: (-x["weight"], x["id"]))
    return {
        "available": True,
        "status": "unverified_structural_matrix",
        "physicalBlockIndex": physical_block_index,
        "blockCount": count,
        "matrixGroup": matrix_group,
        "matrixKind": ("deck_candidate" if matrix_group == 0 else
                       "unlabeled_reward_distribution_candidate"),
        "matrixSlots": CARD_COUNT,
        "totalWeight": TOTAL_WEIGHT,
        "nonzeroCards": sum(v > 0 for v in weights),
        "total": len(visible), "offset": offset,
        "rows": visible[offset:offset + limit],
        "mayActivateDrops": False,
        "mayActivateRank": False,
        "opponentIdsVerified": False,
        "rankGroupLabelsVerified": False,
        "gameplayValidated": False,
        "note": ("Exploracao dos pesos reais do arquivo selecionado. "
                 "O bloco fisico e o grupo nao estao associados "
                 "a adversario ou classificacao de RANK."),
    }
