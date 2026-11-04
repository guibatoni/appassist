"""Bounded, deterministic validation of extracted FM catalogues and drop IDs.

These checks establish internal consistency, never compatibility verified in a
duel. Inputs come from one scanner result; no names or tables cross ISO hashes.
"""
from __future__ import annotations

from collections import defaultdict
import re

CARD_COUNT = 722
OPPONENT_COUNT = 39
TABLE_COUNT = 117
WEIGHT_TOTAL = 2048
MAX_DROP_ROWS = TABLE_COUNT * CARD_COUNT


def _integer(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and len(value) <= 12 and re.fullmatch(r"[0-9]+", value):
        return int(value)
    return None


def _name(value):
    return (isinstance(value, str) and 0 < len(value.strip()) <= 64
            and not any(ord(ch) < 32 or ch == "\ufffd" for ch in value)
            and sum(ch.isalnum() for ch in value) >= 2)


def validate_identity_catalogs(cards, opponents):
    """Check all IDs/names and the bit widths of the known attribute layout.

    Bit-width checks do not prove that a mod kept the meaning of each field.
    No cleanup of text (including a trailing ``v``) is performed here.
    """
    errors = []
    card_ids = [_integer(row.get("id")) for row in cards]
    opponent_ids = [_integer(row.get("id")) for row in opponents]
    cards_ok = len(cards) == CARD_COUNT and card_ids == list(range(1, CARD_COUNT + 1))
    opponents_ok = (len(opponents) == OPPONENT_COUNT
                    and opponent_ids == list(range(1, OPPONENT_COUNT + 1)))
    if not cards_ok:
        errors.append("card_ids_incomplete_or_duplicated")
    if not opponents_ok:
        errors.append("opponent_ids_incomplete_or_duplicated")
    names_ok = all(_name(row.get("nome")) for row in cards)
    opponent_names_ok = all(_name(row.get("nome")) for row in opponents)
    if not names_ok:
        errors.append("card_names_invalid")
    if not opponent_names_ok:
        errors.append("opponent_names_invalid")
    attribute_bounds = {"tipo": 31, "nivel": 15, "atributo": 15,
                        "estrela_1": 15, "estrela_2": 15}
    attributes_ok = True
    for row in cards:
        for field in ("atk", "def"):
            value = _integer(row.get(field))
            if value is None or not 0 <= value <= 5110 or value % 10:
                attributes_ok = False
        for field, maximum in attribute_bounds.items():
            value = _integer(row.get(field))
            if value is None or not 0 <= value <= maximum:
                attributes_ok = False
    if not attributes_ok:
        errors.append("card_attributes_outside_known_encoding")
    return {"cards_valid": cards_ok and names_ok and attributes_ok,
            "opponents_valid": opponents_ok and opponent_names_ok,
            "card_record_count": len(cards), "opponent_record_count": len(opponents),
            "attributes_encoding_valid": bool(cards) and attributes_ok,
            "in_game_verified": False, "errors": errors}


def validate_drop_associations(checks, drops, *, rom_sha256):
    """Validate every matrix/ID/weight before binding it to a catalogue.

    The scanner's summary of 117 totals is insufficient: rows must reconstruct
    exactly those 117 independent matrices, without duplicates or missing IDs.
    Probability is derived from weights by the caller, not trusted from CSV.
    """
    errors = []
    if not isinstance(rom_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", rom_sha256):
        errors.append("iso_sha256_invalid")
    if len(checks) != TABLE_COUNT or not 0 < len(drops) <= MAX_DROP_ROWS:
        errors.append("drop_cardinality_invalid")
    groups = []
    matrices = set()
    for row in checks[:TABLE_COUNT + 1]:
        oid, group = _integer(row.get("oponente_id")), row.get("rank")
        if (oid is None or not 1 <= oid <= OPPONENT_COUNT
                or not isinstance(group, str) or not group or len(group) > 80
                or _integer(row.get("peso_total")) != WEIGHT_TOTAL):
            errors.append("matrix_identity_or_total_invalid")
            continue
        if group not in groups:
            groups.append(group)
        if (oid, group) in matrices:
            errors.append("matrix_duplicate")
        matrices.add((oid, group))
    expected = {(oid, group) for oid in range(1, OPPONENT_COUNT + 1) for group in groups}
    if len(groups) != 3 or matrices != expected:
        errors.append("matrix_coverage_incomplete")
    totals = defaultdict(int)
    seen = set()
    for row in drops[:MAX_DROP_ROWS + 1]:
        oid = _integer(row.get("oponente_id"))
        cid = _integer(row.get("carta_id"))
        weight = _integer(row.get("peso"))
        group = row.get("rank")
        if (oid is None or cid is None or not 1 <= cid <= CARD_COUNT
                or not isinstance(group, str)
                or (oid, group) not in matrices
                or weight is None or not 1 <= weight <= WEIGHT_TOTAL):
            errors.append("drop_reference_or_weight_invalid")
            continue
        key = (oid, group, cid)
        if key in seen:
            errors.append("drop_duplicate")
        seen.add(key)
        totals[(oid, group)] += weight
    if set(totals) != matrices or any(total != WEIGHT_TOTAL for total in totals.values()):
        errors.append("drop_weights_do_not_match_matrices")
    return {"valid": not errors, "rom_sha256": rom_sha256,
            "matrix_count": len(matrices), "entry_count": len(drops),
            "groups": groups, "in_game_verified": False,
            "errors": sorted(set(errors))}
