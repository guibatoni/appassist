"""Read-only structural detector for PS1 Forbidden Memories mod weight families.

Works on bytes provided locally by a caller. Finds complete 39x4 blocks
independently of the resource filename and candidate base. Never activates
RANK/drop identities, interprets IDs, or imports data across mods.
"""
from __future__ import annotations

import hashlib
import struct
import sys
from typing import Iterable

CARD_COUNT = 722
OPPONENT_COUNT = 39
MATRICES_PER_OPPONENT = 4   # deck and three unlabeled distributions
CODECS = ("plain", "x15_masked", "plain_deck_masked_drops")
TOTAL_WEIGHT = 2048
MATRIX_BYTES = CARD_COUNT * 2
MAX_BLOB_BYTES = 96 * 1024 * 1024
# Layout hypotheses are format adapters, not assertions about a specific mod.
DEFAULT_LAYOUTS = ((0x1800, 0x5B4), (0x1C00, 0x5C0),
                   (0x2000, 0x600), (0x1400, 0x5B4))
MASK_BASE = 2512
MAX_RESULTS = 8
MAX_RUN_BLOCKS = 128


def decode_matrix(blob: bytes, at: int, codec: str = "plain") -> tuple[int, ...] | None:
    """Decode a 722-word matrix; require positive, sane and normalized weights."""
    if (type(at) is not int or at < 0 or at % 2 or
            at + MATRIX_BYTES > len(blob)):
        return None
    weights = struct.unpack_from('<722H', blob, at)
    if codec == "plain":
        if max(weights) > TOTAL_WEIGHT:
            return None
    elif codec == "x15_masked":
        if min(weights) < MASK_BASE or max(weights) > MASK_BASE + TOTAL_WEIGHT * 8 + 6:
            return None
        if any((w - MASK_BASE) % 8 > 6 for w in weights):
            return None
        weights = tuple((w - MASK_BASE) // 8 for w in weights)
    else:
        return None
    if (sum(weights) != TOTAL_WEIGHT or
            sum(bool(v) for v in weights) < 3):
        return None
    return weights


def verify_block(blob: bytes, base: int, opponent_step: int,
                 matrix_stride: int, codec: str = "plain") -> dict | None:
    """Confirm all 156 matrices without claiming associations with game IDs."""
    if not all(type(i) is int for i in (base, opponent_step, matrix_stride)):
        return None
    if (base < 0 or base % 2 or matrix_stride < MATRIX_BYTES or
            matrix_stride % 2 or opponent_step % 2 or
            opponent_step < matrix_stride * 3 + MATRIX_BYTES or
            base + (OPPONENT_COUNT - 1) * opponent_step +
            3 * matrix_stride + MATRIX_BYTES > len(blob)):
        return None
    minimum = 999
    maximum = 0
    nonzero_totals = [0] * MATRICES_PER_OPPONENT
    individual_digests = set()
    for opponent in range(OPPONENT_COUNT):
        for group in range(MATRICES_PER_OPPONENT):
            offset = base + opponent * opponent_step + group * matrix_stride
            group_codec = ("plain" if group == 0 else "x15_masked") if codec == "plain_deck_masked_drops" else codec
            weights = decode_matrix(blob, offset, group_codec)
            if weights is None:
                return None
            nonzero = sum(x != 0 for x in weights)
            minimum = min(minimum, nonzero)
            maximum = max(maximum, nonzero)
            nonzero_totals[group] += nonzero
            # Distinct distributions discourage accepting constant filler.
            individual_digests.add(hashlib.blake2s(
                struct.pack('<722H', *weights), digest_size=8).digest())
    if len(individual_digests) < OPPONENT_COUNT:
        return None
    return {"base": base, "opponentStep": opponent_step,
            "matrixStride": matrix_stride, "encoding": codec,
            "opponentBlocks": OPPONENT_COUNT,
            "deckMatrices": OPPONENT_COUNT,
            "unlabeledDistributionMatrices": OPPONENT_COUNT * 3,
            "matrixCount": OPPONENT_COUNT * MATRICES_PER_OPPONENT,
            "weightTotalPerMatrix": TOTAL_WEIGHT,
            "cardSlotsPerMatrix": CARD_COUNT,
            "nonzeroEntriesMin": minimum, "nonzeroEntriesMax": maximum,
            "nonzeroEntriesPerGroup": nonzero_totals,
            "distinctMatrices": len(individual_digests),
            "validatedInGame": False,
            "opponentIdsVerified": False,
            "rankGroupLabelsVerified": False,
            "dropsVerified": False,
            "mayActivateDrops": False,
            "mayActivateRank": False}


def _plausible_plain_bases(blob: bytes, *, max_bases: int,
                           alignment: int = 2048) -> list[int]:
    """Linear bounded rolling sum through candidate word-aligned offsets.

    Results are untrusted anchors. Full 156-matrix verification follows.
    """
    if sys.byteorder != "little":
        raise ValueError("A CPU deve usar little-endian")
    words = memoryview(blob)[:len(blob) & ~1].cast('H')
    if len(words) < CARD_COUNT:
        return []
    running = sum(words[:CARD_COUNT])
    nonzero = sum(bool(x) for x in words[:CARD_COUNT])
    found = []
    for index in range(0, len(words) - CARD_COUNT + 1):
        if (not (index % (alignment // 2)) and running == TOTAL_WEIGHT and
                3 <= nonzero <= 300):
            found.append(index * 2)
            if len(found) >= max_bases:
                break
        if index + CARD_COUNT < len(words):
            leaving, arriving = words[index], words[index + CARD_COUNT]
            running += arriving - leaving
            nonzero += bool(arriving) - bool(leaving)
    return found


def discover_weight_families(blob: bytes, *,
                             layout_hypotheses: Iterable[tuple[int, int]] = DEFAULT_LAYOUTS,
                             base_hints: Iterable[int] = (),
                             max_anchors: int = 120000) -> dict:
    """Discover candidates; publish only unique structural evidence.

    Scan finds plain-weight matrices on sector-aligned starts, plus known
    masked matrices at supplied hints/sector-aligned starts. Unaligned mods
    need format-specific base hints to avoid false positives from zero padding. No content bytes
    or per-card probabilities are returned.
    """
    result = {"schema": 1, "state": "not_found",
              "candidateCount": 0, "selected": None, "candidates": [],
              "scanComplete": False, "inGameVerified": False,
              "mayActivateDrops": False, "mayActivateRank": False,
              "universalCompatibilityClaimed": False}
    if (not isinstance(blob, bytes) or len(blob) > MAX_BLOB_BYTES
            or len(blob) < MATRIX_BYTES * 4):
        result["state"] = "invalid_input"
        return result
    layouts = []
    for pair in layout_hypotheses:
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2 or
                not all(type(n) is int for n in pair)):
            result["state"] = "invalid_layout"
            return result
        if pair not in layouts:
            layouts.append(tuple(pair))
    if not 1 <= len(layouts) <= 16 or not 1 <= max_anchors <= 1000000:
        result["state"] = "invalid_layout"
        return result
    hints = set()
    for value in base_hints:
        if type(value) is not int or value < 0 or value % 2:
            result["state"] = "invalid_hints"
            return result
        hints.add(value)
    anchors = _plausible_plain_bases(blob, max_bases=max_anchors)
    result["plainAnchorsExamined"] = len(anchors)
    result["scanComplete"] = len(anchors) < max_anchors
    found = []
    seen = set()
    def try_candidate(base, codec):
        for opponent_step, stride in layouts:
            key = (base, codec, opponent_step, stride)
            if key in seen:
                continue
            seen.add(key)
            # Reject almost everything using only the first two rows.
            deck_codec = "plain" if codec == "plain_deck_masked_drops" else codec
            drops_codec = "x15_masked" if codec == "plain_deck_masked_drops" else codec
            if (decode_matrix(blob, base, deck_codec) is None or
                    decode_matrix(blob, base + stride, drops_codec) is None or
                    decode_matrix(blob, base + 2*stride, drops_codec) is None or
                    decode_matrix(blob, base + 3*stride, drops_codec) is None or
                    decode_matrix(blob, base + opponent_step, deck_codec) is None):
                continue
            report = verify_block(blob, base, opponent_step, stride, codec)
            if report is not None:
                found.append(report)
                if len(found) >= MAX_RESULTS:
                    return
    for base in sorted(hints):
        for codec in CODECS:
            try_candidate(base, codec)
    for base in anchors:
        if len(found) >= MAX_RESULTS: break
        try_candidate(base, 'plain')
        try_candidate(base, 'plain_deck_masked_drops')
    # Masked weights cannot be located by the plain rolling sum. Probe one
    # offset per 2048-byte resource page; other alignments require an adapter
    # supplied via base_hints. Never treat absence as universal rejection.
    for base in range(0, len(blob) - MATRIX_BYTES + 1, 2048):
        if len(found) >= MAX_RESULTS: break
        if base not in hints:
            try_candidate(base, 'x15_masked')
            try_candidate(base, 'plain_deck_masked_drops')
    result["candidates"] = found
    result["candidateCount"] = len(found)
    # Distinguish a unique 39-block window from an uninterrupted 40-block
    # run, where two different 39-block windows are valid. This occurs in
    # observed FM-family resources and must not choose the first window.
    clusters = {}
    for item in found:
        step = item["opponentStep"]
        stride = item["matrixStride"]
        codec = item["encoding"]
        start = item["base"]
        group_codec = lambda group: ("plain" if group == 0 else "x15_masked") if codec == "plain_deck_masked_drops" else codec
        def valid_one(at):
            return (at >= 0 and at + 3*stride + MATRIX_BYTES <= len(blob)
                    and all(decode_matrix(blob,at+g*stride,group_codec(g)) is not None for g in range(4)))
        first = start
        while (start-first)//step < MAX_RUN_BLOCKS-1 and valid_one(first-step):
            first -= step
        end = start + (OPPONENT_COUNT - 1)*step
        while (end-first)//step < MAX_RUN_BLOCKS-1 and valid_one(end+step):
            end += step
        key = (first, end, step, stride, codec)
        full_run = (end-first)//step + 1
        trailer_size = step - 4*stride
        metadata_bytes = 0xC8
        padding_bytes = 0x68
        trailer_verified = False
        rank_rule_uniform = False
        if (full_run <= MAX_RUN_BLOCKS and trailer_size == metadata_bytes + padding_bytes):
            rule_regions = [blob[first+i*step+4*stride:first+i*step+4*stride+metadata_bytes]
                            for i in range(full_run)]
            tail_regions = [blob[first+i*step+4*stride+metadata_bytes:first+(i+1)*step]
                            for i in range(full_run)]
            trailer_verified = all(t == b"\xff" * padding_bytes for t in tail_regions)
            rank_rule_uniform = (bool(rule_regions[0]) and
                                 any(rule_regions[0]) and len(set(rule_regions)) == 1)
        clusters[key] = {"firstBlockOffset":first,
                         "lastBlockOffset":end,
                         "consecutiveBlockCount":full_run,
                         "runCapReached":full_run >= MAX_RUN_BLOCKS,
                         "ffTailVerified":trailer_verified,
                         "ruleBytes":metadata_bytes if rank_rule_uniform else None,
                         "ruleBytesIdenticalAcrossBlocks":rank_rule_uniform,
                         "possible39BlockWindows":max(0,(end-first)//step+2-OPPONENT_COUNT),
                         "encoding":codec,
                         "opponentStep":step,"matrixStride":stride,
                         "inGameVerified":False}
    result["clusters"] = list(clusters.values())
    result["ambiguous39BlockWindows"] = any(x["possible39BlockWindows"] > 1 for x in clusters.values())
    if (not result["scanComplete"] or len(found) >= MAX_RESULTS
            or any(x["runCapReached"] for x in clusters.values())):
        result["state"] = "incomplete_or_ambiguous_scan"
    elif len(found) == 1 and not result["ambiguous39BlockWindows"]:
        result["state"] = "unique_structural_candidate"
        result["selected"] = found[0]
    elif found:
        result["state"] = ("single_family_unmapped_windows" if
                           len(clusters) == 1 else "ambiguous_candidates")
    return result