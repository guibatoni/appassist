"""Conservative live opponent-ID probe for ePSXe (read-only, Windows).

PS1 NTSC-U reference: gDuel_bOpponentID at 0x8009B361.
A virtual host RAM base is NOT a fixed ePSXe address. Find a 2MB PSX
RAM mapping and validate independent duel-state fields before returning
the raw runtime ID. Mods may move the game fields; never claim universal
mapping, never equate the ID with a structural name position or drop block.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from dueltrace_live_hand import (
    PROCESS_QUERY_INFORMATION, PROCESS_VM_READ, HAND_ADDRESS, HAND_BYTES,
    discover_epsxe_pids, _windows_kernel32, decode_hand,
)

OPPONENT_OFFSET = 0x9B361
HAND_OFFSET = 0xEA484
LP_BASE_OFFSET = 0xEA000
DRAW_HISTORY_OFFSET = 0x1A7E20
DRAW_SAMPLE_SIZE = 6 * 8
MAX_LIVE_READ_BYTES = max(DRAW_SAMPLE_SIZE, HAND_BYTES)
RAM_LENGTH = 0x200000
# A PSX mapping can be split by VirtualQueryEx; only offsets that must
# be read for independent validation are required to be accessible.
MIN_REQUIRED_SPAN = DRAW_HISTORY_OFFSET + DRAW_SAMPLE_SIZE
MAX_REGIONS = 32768
MAX_CANDIDATE_BASES = 128
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
READABLE = {0x02,0x04,0x08,0x20,0x40,0x80}
# Legacy ePSXe memory host base, estimated from the existing hand
# mapping. Not accepted without independent LP/history/hand checks.
LEGACY_HOST_BASE_HINT = HAND_ADDRESS - 0xEA484
# Only bounded in-memory caching; never writes host addresses or RAM dumps.
_PID_BASE_CACHE: dict[int,int] = {}


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    # Win32 MEMORY_BASIC_INFORMATION does not contain PartitionId.
    # Using the 64-bit layout in a 32-bit app corrupts RegionSize and
    # prevents the scanner from discovering any readable PS1 RAM.
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
    ] + ([("PartitionId", wintypes.WORD)] if ctypes.sizeof(ctypes.c_void_p) == 8 else []) + [
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


def _note_validation(stats, reason):
    if isinstance(stats, dict):
        stats[reason] = stats.get(reason, 0) + 1


def _hand_anchor(read_at, base):
    """Correlate PSX hand bytes with the ALREADY proven ePSXe hand reader.

    This requires a valid five-card layout at both addresses and exact
    equality, so a low-value byte in unrelated process memory cannot
    become an opponent ID merely because the history layout changed.
    """
    candidate = read_at(base + HAND_OFFSET, HAND_BYTES)
    known = read_at(HAND_ADDRESS, HAND_BYTES)
    if (not isinstance(candidate, bytes) or len(candidate) != HAND_BYTES
            or not isinstance(known, bytes) or len(known) != HAND_BYTES
            or candidate != known):
        return None
    decoded = decode_hand(candidate)
    return decoded if decoded is not None and len(decoded) == 5 else None


def _valid_psx_sample(read_at, base: int, stats=None) -> dict | None:
    """Validate a candidate host mapping without identifying the ISO.

    read_at(address,size) returns bytes or None. Strictly disallows
    partial reads, ambiguous IDs and implausible game-state structures.
    """
    if type(base) is not int or base < 0x10000 or base > 0x7FFF00000000:
        _note_validation(stats, "invalidCandidateBase")
        return None
    opponent = read_at(base + OPPONENT_OFFSET, 1)
    duel = read_at(base + LP_BASE_OFFSET, 0x30)
    verified_hand = _hand_anchor(read_at, base)
    # Record the known-good hand match EVEN when the presumed opponent or
    # LP offsets fail. This distinguishes a good RAM anchor from a bad
    # game-specific field layout without endorsing any opponent ID.
    if verified_hand is not None:
        _note_validation(stats, "validatedHandAnchors")
    draw = read_at(base + DRAW_HISTORY_OFFSET, DRAW_SAMPLE_SIZE)
    if (not isinstance(opponent, bytes) or len(opponent) != 1
            or not isinstance(duel, bytes) or len(duel) != 0x30):
        _note_validation(stats, "unreadableFields")
        return None
    oid = opponent[0]
    if oid > 39:
        _note_validation(stats, "opponentIdOutOfRange")
        return None
    p1 = int.from_bytes(duel[4:6], "little")
    p2 = int.from_bytes(duel[0x24:0x26], "little")
    hand_indices = duel[0x0A:0x0F]
    if not (0 < p1 <= 32767 and 0 < p2 <= 32767):
        _note_validation(stats, "implausibleLifePoints")
        return None
    if (verified_hand is None
            and not (len(set(hand_indices)) >= 3
                     and all(x < 60 for x in hand_indices))):
        _note_validation(stats, "implausibleHandIndices")
        return None
    # Distinct validated first draws support that this is a PS1 memory
    # mapping, rather than coincidental low numbers in an arbitrary region.
    draws = []
    if not isinstance(draw, bytes) or len(draw) != DRAW_SAMPLE_SIZE:
        draw = bytes(DRAW_SAMPLE_SIZE)
    for i in range(8):
        at = i * 6
        card = int.from_bytes(draw[at:at+2], "little")
        idx_a, idx_b = draw[at+2], draw[at+3]
        if 1 <= card <= 722 and idx_a == idx_b and idx_a < 60:
            draws.append((card, idx_a))
    history_valid = (
        len(draws) >= 3 and len(set(i for _, i in draws)) >= 3)
    if verified_hand is None and not history_valid:
        _note_validation(stats, "implausibleDrawHistory")
        return None
    _note_validation(stats, "validatedSamples")
    return {
        "runtimeOpponentId": oid,
        "playerLP": p1,
        "opponentLP": p2,
        "drawEntriesPlausible": len(draws),
        "validationMethod": (
            "known_hand_anchor" if verified_hand is not None
            else "legacy_draw_history"),
        "base": base,
    }


def _select_region_candidates(regions, *, hint=LEGACY_HOST_BASE_HINT,
                              max_candidates=MAX_CANDIDATE_BASES):
    """Prefer PSX-sized readable mappings in low *or* high host memory.

    Regions are untrusted kernel metadata. We rank the full list before
    applying the cap so an early 2GB scan cannot starve higher mappings.
    Returned offsets are only probe candidates, not proof of RAM location.
    """
    candidates = [hint] if type(hint) is int and hint >= 0x10000 else []
    ordered = []
    for base, size in regions:
        if (type(base) is not int or type(size) is not int
                or base < 0x10000 or size < MIN_REQUIRED_SPAN):
            continue
        # A 2MB PSX mapping may be part of a larger committed reservation.
        # Probe multiple 64KB subpages in the first 1MB, within bounds.
        for delta in range(0, min(size-MIN_REQUIRED_SPAN+1, 0x100000), 0x10000):
            candidate = base + delta
            # Exact-size regions precede unrelated large allocations.
            ordered.append((0 if size == RAM_LENGTH else 1,
                            abs(size-RAM_LENGTH), candidate))
    ordered.sort()
    seen = set(candidates)
    for _, _, base in ordered:
        if base in seen:
            continue
        seen.add(base)
        candidates.append(base)
        if len(candidates) >= max_candidates:
            break
    return candidates[:max_candidates]


def _candidate_bases(kernel, handle) -> tuple[list[int], dict]:
    """Inspect all readable committed regions, including Win64 high memory.

    The old 0x80000000 bound omitted high host addresses entirely.
    The legacy low-address guess remains a candidate, never a proof.
    """
    kernel.VirtualQueryEx.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p,
        ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
    kernel.VirtualQueryEx.restype = ctypes.c_size_t
    maximum_address = (
        0x7FFFFFFEFFFF if ctypes.sizeof(ctypes.c_void_p) == 8
        else 0x7FFEFFFF)
    address = 0x10000
    queries = 0
    consecutive_query_failures = 0
    readable = []
    while address <= maximum_address and queries < MAX_REGIONS:
        mbi = MEMORY_BASIC_INFORMATION()
        returned = kernel.VirtualQueryEx(
            handle, ctypes.c_void_p(address),
            ctypes.byref(mbi), ctypes.sizeof(mbi))
        queries += 1
        if not returned:
            consecutive_query_failures += 1
            if consecutive_query_failures >= 32:
                break
            address += 0x10000
            continue
        consecutive_query_failures = 0
        base = int(mbi.BaseAddress or 0)
        size = int(mbi.RegionSize)
        next_address = max(address + 0x1000, base + max(size, 0x1000))
        flags = int(mbi.Protect)
        if (mbi.State == MEM_COMMIT
                and size >= MIN_REQUIRED_SPAN
                and not (flags & (PAGE_GUARD | PAGE_NOACCESS))
                and (flags & 0xFF) in READABLE):
            readable.append((base, size))
        address = next_address
    bases = _select_region_candidates(readable)
    return bases, {
        "memoryRegionsExamined": queries,
        "readableLargeRegions": len(readable),
        "candidateBasesExamined": len(bases),
        "scanReachedLimit": queries >= MAX_REGIONS,
        "searchedHighMemory": ctypes.sizeof(ctypes.c_void_p) == 8,
    }


def _read_sample_twice(read_at, base, stats=None):
    first = _valid_psx_sample(read_at, base, stats)
    if first is None:
        return None
    second = _valid_psx_sample(read_at, base, stats)
    if (second is None
            or first["runtimeOpponentId"] != second["runtimeOpponentId"]
            or first["playerLP"] != second["playerLP"]
            or first["opponentLP"] != second["opponentLP"]):
        _note_validation(stats, "unstableSamples")
        return None
    return first


def probe_live_opponent(*, preferred_pid: int | None = None,
                        kernel=None, pids=None,
                        read_at=None, candidate_bases=None) -> dict:
    """Return a provisional opponent byte, never a verified opponent name.

    Dependency injection permits fully offline tests without process access.
    Native mode opens ePSXe.exe with READ+QUERY only and closes all handles.
    """
    fail = {
        "ready": False, "status": "unavailable",
        "runtimeOpponentId": None,
        "runtimeIdVerifiedForMod": False,
        "romIdentityVerified": False,
        "opponentNameVerified": False,
        "rankGroupsVerified": False,
        "mayActivateDrops": False,
        "mayActivateRank": False,
    }
    if read_at is not None and candidate_bases is not None:
        bases = list(candidate_bases)
        if len(bases) > MAX_CANDIDATE_BASES:
            return {**fail, "status": "too_many_candidates"}
        found = [_read_sample_twice(read_at, base) for base in bases]
        found = [v for v in found if v is not None]
        if len(found) != 1:
            return {**fail, "status": (
                "ambiguous_ram_mapping" if found else "ram_mapping_not_validated")}
        return {**fail, "ready": True, "status": "runtime_id_candidate",
                "runtimeOpponentId": found[0]["runtimeOpponentId"],
                "playerLP": found[0]["playerLP"],
                "opponentLP": found[0]["opponentLP"],
                "validationMethod": found[0]["validationMethod"],
                "mappingValidatedByIndependentFields": True}

    if sys.platform != "win32" and kernel is None:
        return {**fail, "status": "windows_only"}
    kernel = kernel or _windows_kernel32()
    candidates = discover_epsxe_pids(kernel) if pids is None else list(pids)
    if preferred_pid is not None:
        if preferred_pid not in candidates:
            return {**fail, "status": "preferred_epsxe_missing"}
        pid = preferred_pid
    elif len(candidates) == 1:
        pid = candidates[0]
    else:
        return {**fail, "status": (
            "no_epsxe" if not candidates else "multiple_epsxe_processes")}
    if type(pid) is not int or pid <= 0:
        return {**fail, "status": "invalid_pid"}

    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.ReadProcessMemory.argtypes=[
        wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,
        ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
    kernel.ReadProcessMemory.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.CloseHandle.restype=wintypes.BOOL
    handle = kernel.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,False,pid)
    if not handle:
        return {**fail, "status": "read_access_denied"}
    try:
        def read_at_native(addr, count):
            if not (type(addr) is int and 0 <= addr < 0x800000000000
                    and type(count) is int and 0 < count <= MAX_LIVE_READ_BYTES):
                return None
            buffer = ctypes.create_string_buffer(count)
            n = ctypes.c_size_t()
            ok = kernel.ReadProcessMemory(
                handle, ctypes.c_void_p(addr),buffer,count,ctypes.byref(n))
            return buffer.raw if ok and n.value == count else None
        cached_base = _PID_BASE_CACHE.get(pid)
        if cached_base is not None:
            observed = _read_sample_twice(read_at_native, cached_base)
            if observed:
                return {
                    **fail,"ready":True,"status":"runtime_id_candidate",
                    "runtimeOpponentId":observed["runtimeOpponentId"],
                    "playerLP":observed["playerLP"],
                    "opponentLP":observed["opponentLP"],
                    "validationMethod":observed["validationMethod"],
                    "mappingValidatedByIndependentFields":True,
                }
            _PID_BASE_CACHE.pop(pid,None)
        # Reuse the known working hand address before scanning thousands
        # of unrelated host allocations. It can shortcut the scan ONLY
        # when the full five-card hand decodes identically at both offsets.
        hint_stats = {}
        hinted = _read_sample_twice(
            read_at_native, LEGACY_HOST_BASE_HINT, hint_stats)
        if hinted is not None and hinted["validationMethod"] == "known_hand_anchor":
            _PID_BASE_CACHE[pid] = LEGACY_HOST_BASE_HINT
            return {
                **fail,"ready":True,"status":"runtime_id_candidate",
                "runtimeOpponentId":hinted["runtimeOpponentId"],
                "playerLP":hinted["playerLP"],
                "opponentLP":hinted["opponentLP"],
                "validationMethod":"known_hand_anchor",
                "mappingValidatedByIndependentFields":True,
                "memoryScanSkippedByKnownHand":True,
            }
        bases, scan_diagnostic = _candidate_bases(kernel,handle)
        failure_counts = {}
        found = []
        for base in bases:
            item = _read_sample_twice(read_at_native,base,failure_counts)
            if item:
                found.append(item)
                if len(found) > 1:
                    break
        if len(found) != 1:
            # Preserve separate stage diagnostics for the hand-derived base.
            # This never exports the host base or RAM bytes; it shows whether
            # the stable hand matched while legacy LP/ID offsets failed.
            return {**fail, **scan_diagnostic,
                    "knownHandAnchorAtHint":hint_stats.get("validatedHandAnchors",0)>0,
                    "hintValidationBreakdown":hint_stats,
                    "validationBreakdown":failure_counts, "status": (
                "ambiguous_ram_mapping" if found else "ram_mapping_not_validated")}
        if len(_PID_BASE_CACHE) > 16:
            _PID_BASE_CACHE.clear()
        _PID_BASE_CACHE[pid] = found[0]["base"]
        return {
            **fail,**scan_diagnostic,"ready":True,"status":"runtime_id_candidate",
            "runtimeOpponentId":found[0]["runtimeOpponentId"],
            "playerLP":found[0]["playerLP"],
            "opponentLP":found[0]["opponentLP"],
            "validationMethod":found[0]["validationMethod"],
            "mappingValidatedByIndependentFields":True,
        }
    finally:
        kernel.CloseHandle(handle)
