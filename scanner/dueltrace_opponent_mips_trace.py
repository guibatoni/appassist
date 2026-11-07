"""Stage 32: conservative, read-only byte-field evidence from an imported MIPS trace.

Not a live debugger. The emulator trace is external, untrusted text and may
contain synthetic instructions. In particular, PS1 RAM 0x8009B361 is the
classic gDuel_bOpponentID location, NOT a universal mod identifier. The
result never verifies opponent identity or authorizes drops/score activation.

Only bounded numeric counts, PS1 virtual addresses and PCs leave this parser.
The original trace is neither copied into the mod profile nor uploaded.
"""
from __future__ import annotations

from collections import defaultdict
import re

MAX_TRACE_BYTES = 8 * 1024 * 1024
MAX_TRACE_LINES = 250_000
MAX_MEMORY_EVENTS = 50_000
MAX_ADDRESSES = 4096
LEGACY_OPPONENT_ADDRESS = 0x8009B361
RAM_START = 0x80000000
RAM_END = 0x80200000

PC = re.compile(r"\bPC\s*[:=]\s*(?:0x)?([0-9A-Fa-f]{8})(?![0-9A-Fa-f])",re.I)
OP = re.compile(r"\bOP\s*[:=]\s*(LBU|LB|SB)(?![A-Za-z])",re.I)
ADDR = re.compile(r"\bADDR\s*[:=]\s*(?:0x)?([0-9A-Fa-f]{8})(?![0-9A-Fa-f])",re.I)
VALUE = re.compile(r"\bVALUE\s*[:=]\s*(?:0x)?([0-9A-Fa-f]{1,8})(?![0-9A-Fa-f])",re.I)


def _empty(status: str) -> dict:
    return {
        "schema": 1, "status": status, "available": False,
        "traceFormatRecognized": False, "instructionSamples": 0,
        "distinctPCs": 0, "byteMemoryEvents": 0,
        "legacyFieldReadEvents": 0, "legacyFieldWriteEvents": 0,
        "legacyObservedValues": [], "candidateAddressCount": 0,
        "candidateAddresses": [],
        "opponentIdentityVerified": False,
        "romIdentityVerified": False,
        "physicalWindowMappingVerified": False,
        "rankRoutineConfirmed": False, "mayActivateDrops": False,
        "note": (
            "Trace externo nao autenticado. Acesso ao endereco classico ou "
            "a um byte candidato nao confirma ID de oponente, associacao "
            "a blocos fisicos nem grupos RANK."
        ),
    }


def inspect_opponent_mips_trace(trace: bytes) -> dict:
    """Find potential byte-field access in a user's MIPS execution trace.

    A plausible trace has >=30 PS1 PC samples and >=8 distinct PCs. Even if
    that threshold passes, it only establishes that the text *resembles* a
    trace; independent in-game identity verification remains necessary.
    A nonclassic candidate needs both loads and a store at the same address,
    at least 3 loads and 2 distinct PCs. Candidates are investigative leads,
    never mapped automatically to the name-table or reward-table indices.
    """
    if not isinstance(trace, bytes) or not 0 < len(trace) <= MAX_TRACE_BYTES:
        return _empty("invalid_trace")

    seen_pcs: set[int] = set()
    instruction_samples = 0
    memory_events = 0
    total_lines = 0
    # Keep only low-value PS1 byte accesses; never preserve original text.
    fields: dict[int, dict] = {}
    for raw in trace.splitlines():
        total_lines += 1
        if total_lines > MAX_TRACE_LINES:
            return _empty("trace_line_limit_exceeded")
        line = raw[:320].decode("ascii", "ignore")
        pc_match = PC.search(line)
        if pc_match is None:
            continue
        pc = int(pc_match.group(1), 16)
        if not RAM_START <= pc < RAM_END:
            continue
        instruction_samples += 1
        if len(seen_pcs) < 5000:
            seen_pcs.add(pc)

        op_match, addr_match, value_match = (
            OP.search(line), ADDR.search(line), VALUE.search(line))
        if op_match is None or addr_match is None or value_match is None:
            continue
        address = int(addr_match.group(1), 16)
        value = int(value_match.group(1), 16)
        if not RAM_START <= address < RAM_END or not 0 <= value <= 39:
            continue
        memory_events += 1
        if memory_events > MAX_MEMORY_EVENTS:
            return _empty("trace_memory_event_limit_exceeded")
        if address not in fields:
            if len(fields) >= MAX_ADDRESSES:
                return _empty("trace_address_limit_exceeded")
            fields[address] = {"reads": 0, "writes": 0,
                               "values": set(), "pcs": set()}
        item = fields[address]
        is_write = op_match.group(1).upper() == "SB"
        item["writes" if is_write else "reads"] += 1
        if len(item["values"]) < 40:
            item["values"].add(value)
        if len(item["pcs"]) < 32:
            item["pcs"].add(pc)

    quality = instruction_samples >= 30 and len(seen_pcs) >= 8
    if not quality:
        return {
            **_empty("insufficient_execution_trace"),
            "instructionSamples": instruction_samples,
            "distinctPCs": len(seen_pcs),
            "byteMemoryEvents": memory_events,
        }
    legacy = fields.get(LEGACY_OPPONENT_ADDRESS, {})
    probable = []
    for address, item in fields.items():
        if address == LEGACY_OPPONENT_ADDRESS:
            continue
        if item["reads"] < 3 or item["writes"] < 1 or len(item["pcs"]) < 2:
            continue
        probable.append({
            "address": f"0x{address:08X}",
            "readEvents": item["reads"],
            "writeEvents": item["writes"],
            "distinctPCs": len(item["pcs"]),
            "observedValues": sorted(item["values"])[:12],
        })
    probable.sort(key=lambda x: (
        -min(x["readEvents"], x["writeEvents"]),
        -x["readEvents"], -x["distinctPCs"], x["address"]))

    legacy_reads = legacy.get("reads", 0)
    legacy_writes = legacy.get("writes", 0)
    state = ("legacy_byte_address_observed" if legacy_reads or legacy_writes
             else "other_byte_field_candidates" if probable
             else "no_opponent_address_evidence")
    return {
        **_empty(state), "available": True,
        "traceFormatRecognized": True,
        "instructionSamples": instruction_samples,
        "distinctPCs": len(seen_pcs),
        "byteMemoryEvents": memory_events,
        "legacyFieldReadEvents": legacy_reads,
        "legacyFieldWriteEvents": legacy_writes,
        "legacyObservedValues": sorted(legacy.get("values", set()))[:12],
        "candidateAddressCount": len(probable),
        "candidateAddresses": probable[:6],
    }
