"""Guarded bridge from whole-resource weight-family discovery to drop tables.

The legacy relocated-drop scanner searches only near the retail offset.
This adapter uses a separately found, *unique*, verified 39x4 full-resource
structure. Its three distribution groups have unknown RANK labels, and
opponent ID / game association remains explicitly unverified.
"""
from __future__ import annotations


def use_unique_weight_family(family, decode_at_layout):
    """Return a structural candidate or None; never infer mapping from a name."""
    if not isinstance(family, dict) or not callable(decode_at_layout):
        return None
    if family.get("state") != "unique_structural_candidate":
        return None
    if family.get("candidateCount") != 1:
        return None
    if family.get("ambiguous39BlockWindows") is True:
        return None
    selected = family.get("selected")
    if not isinstance(selected, dict):
        return None
    if (selected.get("opponentBlocks") != 39
            or selected.get("matrixCount") != 156
            or selected.get("deckMatrices") != 39
            or selected.get("unlabeledDistributionMatrices") != 117
            or selected.get("encoding") not in (
                "plain", "x15_masked", "plain_deck_masked_drops")):
        return None
    base = selected.get("base")
    step = selected.get("opponentStep")
    stride = selected.get("matrixStride")
    if (not all(type(x) is int and x >= 0
                for x in (base, step, stride))
            or base % 2 or step % 2 or stride % 2
            or stride < 1444 or step < stride * 3 + 1444):
        return None
    try:
        tables, _status = decode_at_layout(base, step, stride)
    except (ValueError, OverflowError, TypeError):
        return None
    if (not isinstance(tables, dict)
            or len(tables.get("verificacao", [])) != 117
            or not tables.get("drops")
            or any(row.get("peso_total") != 2048
                   for row in tables["verificacao"])):
        return None
    return {
        "schema": 1, "state": "unique_156_matrices_full_resource",
        "selected": {
            "opponentBase": base, "opponentStep": step,
            "rankStride": stride, "encoding": selected["encoding"],
        },
        "candidates": [{
            "opponentBase": base, "opponentStep": step,
            "rankStride": stride, "encoding": selected["encoding"],
        }],
        "selectedSource": "whole_resource_156_matrix_structural_probe",
        "validated": False, "rankLabelsVerified": False,
        "opponentIdsVerified": False, "inGameVerified": False,
        "mayActivateDrops": False, "mayActivateRank": False,
    }
