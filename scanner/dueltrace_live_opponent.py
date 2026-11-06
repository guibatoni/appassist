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
    PROCESS_QUERY_INFORMATION, PROCESS_VM_READ, HAND_ADDRESS,
    discover_epsxe_pids, _windows_kernel32,
)

OPPONENT_OFFSET = 0x9B361
LP_BASE_OFFSET = 0xEA000
DRAW_HISTORY_OFFSET = 0x1A7E20
DRAW_SAMPLE_SIZE = 6 * 8
RAM_LENGTH = 0x200000
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
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


def _valid_psx_sample(read_at, base: int) -> dict | None:
    """Validate a candidate host mapping without identifying the ISO.

    read_at(address,size) returns bytes or None. Strictly disallows
    partial reads, ambiguous IDs and implausible game-state structures.
    """
    if type(base) is not int or base < 0x10000 or base > 0x7FFF00000000:
        return None
    opponent = read_at(base + OPPONENT_OFFSET, 1)
    duel = read_at(base + LP_BASE_OFFSET, 0x30)
    draw = read_at(base + DRAW_HISTORY_OFFSET, DRAW_SAMPLE_SIZE)
    if (not isinstance(opponent, bytes) or len(opponent) != 1
            or not isinstance(duel, bytes) or len(duel) != 0x30
            or not isinstance(draw, bytes) or len(draw) != DRAW_SAMPLE_SIZE):
        return None
    oid = opponent[0]
    if oid > 39:
        return None
    p1 = int.from_bytes(duel[4:6], "little")
    p2 = int.from_bytes(duel[0x24:0x26], "little")
    hand_indices = duel[0x0A:0x0F]
    if not (0 < p1 <= 32767 and 0 < p2 <= 32767
            and len(set(hand_indices)) >= 3
            and all(x < 60 for x in hand_indices)):
        return None
    # Distinct validated first draws support that this is a PS1 memory
    # mapping, rather than coincidental low numbers in an arbitrary region.
    draws = []
    for i in range(8):
        at = i * 6
        card = int.from_bytes(draw[at:at+2], "little")
        idx_a, idx_b = draw[at+2], draw[at+3]
        if 1 <= card <= 722 and idx_a == idx_b and idx_a < 60:
            draws.append((card, idx_a))
    if len(draws) < 3 or len(set(i for _, i in draws)) < 3:
        return None
    return {
        "runtimeOpponentId": oid,
        "playerLP": p1,
        "opponentLP": p2,
        "drawEntriesPlausible": len(draws),
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
                or base < 0x10000 or size < RAM_LENGTH):
            continue
        # A 2MB PSX mapping may be part of a larger committed reservation.
        # Probe multiple 64KB subpages in the first 1MB, within bounds.
        for delta in range(0, min(size-RAM_LENGTH+1, 0x100000), 0x10000):
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
    readable = []
    while address <= maximum_address and queries < MAX_REGIONS:
        mbi = MEMORY_BASIC_INFORMATION()
        returned = kernel.VirtualQueryEx(
            handle, ctypes.c_void_p(address),
            ctypes.byref(mbi), ctypes.sizeof(mbi))
        queries += 1
        if not returned:
            # Invalid range or inaccessible query: advance one page.
            address += 0x10000
            continue
        base = int(mbi.BaseAddress or 0)
        size = int(mbi.RegionSize)
        next_address = max(address + 0x1000, base + max(size, 0x1000))
        flags = int(mbi.Protect)
        if (mbi.State == MEM_COMMIT
                and size >= RAM_LENGTH
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


def _read_sample_twice(read_at, base):
    first = _valid_psx_sample(read_at, base)
    if first is None:
        return None
    second = _valid_psx_sample(read_at, base)
    if (second is None
            or first["runtimeOpponentId"] != second["runtimeOpponentId"]
            or first["playerLP"] != second["playerLP"]
            or first["opponentLP"] != second["opponentLP"]):
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
                    and type(count) is int and 0 < count <= DRAW_SAMPLE_SIZE):
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
                    "mappingValidatedByIndependentFields":True,
                }
            _PID_BASE_CACHE.pop(pid,None)
        bases, scan_diagnostic = _candidate_bases(kernel,handle)
        found = []
        for base in bases:
            item = _read_sample_twice(read_at_native,base)
            if item:
                found.append(item)
                if len(found) > 1:
                    break
        if len(found) != 1:
            return {**fail, **scan_diagnostic, "status": (
                "ambiguous_ram_mapping" if found else "ram_mapping_not_validated")}
        if len(_PID_BASE_CACHE) > 16:
            _PID_BASE_CACHE.clear()
        _PID_BASE_CACHE[pid] = found[0]["base"]
        return {
            **fail,**scan_diagnostic,"ready":True,"status":"runtime_id_candidate",
            "runtimeOpponentId":found[0]["runtimeOpponentId"],
            "playerLP":found[0]["playerLP"],
            "opponentLP":found[0]["opponentLP"],
            "mappingValidatedByIndependentFields":True,
        }
    finally:
        kernel.CloseHandle(handle)
