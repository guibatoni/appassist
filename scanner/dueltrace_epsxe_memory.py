"""Conservative read-only RAM discovery across Windows ePSXe releases.

Never assume a process address is portable between versions. Locate the
five-card battle hand *inside the selected ePSXe process*, require exact
slot IDs/indices plus two stable independent reads, and refuse ambiguity.

The scan is bounded and does not dump RAM or send data outside this process.
It does NOT validate the loaded ISO, RANK offsets, opponents or game version.
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

HAND_OFFSET = 0xEA484        # PS1 relative address, not Windows process address
HAND_BYTES = 140
MAX_REGIONS = 32768
MAX_SCAN_BYTES = 48 * 1024 * 1024
CHUNK = 256 * 1024
MAX_MATCHES = 2
MIN_ADDRESS = 0x10000
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
READABLE = {0x02,0x04,0x08,0x20,0x40,0x80}
# A 32-bit Windows process uses a different VirtualQueryEx struct layout.
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
    ] + ([
        ("PartitionId", wintypes.WORD),
    ] if ctypes.sizeof(ctypes.c_void_p)==8 else []) + [
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


def _candidate_hand_offsets(data: bytes):
    """Filter by card-slot 1 index before strict five-card decoding.

    Index 1 is at +40; at ordinary RAM/zero-filled pages most incidental
    4-byte zeros can be rejected without decoding a full record.
    """
    from fusion_ram_probe import decode_hand

    marker=b"\x01\x00\x00\x00"
    at=0
    while (index:=data.find(marker,at))>=0:
        start=index-40
        at=index+1
        if start<0 or start+HAND_BYTES>len(data):
            continue
        if decode_hand(data[start:start+HAND_BYTES]) is not None:
            yield start


def readable_regions(kernel, handle) -> list[tuple[int,int]]:
    """List committed/readable regions, without accessing or modifying content."""
    query=getattr(kernel,"VirtualQueryEx",None)
    if query is None:
        return []
    query.argtypes=[wintypes.HANDLE,ctypes.c_void_p,
                    ctypes.POINTER(MEMORY_BASIC_INFORMATION),ctypes.c_size_t]
    query.restype=ctypes.c_size_t
    maximum=(0x7FFFFFFEFFFF if ctypes.sizeof(ctypes.c_void_p)==8
             else 0x7FFEFFFF)
    address=MIN_ADDRESS
    misses=0
    calls=0
    regions=[]
    while address<=maximum and calls<MAX_REGIONS:
        info=MEMORY_BASIC_INFORMATION()
        returned=query(handle,ctypes.c_void_p(address),ctypes.byref(info),
                       ctypes.sizeof(info))
        calls+=1
        if not returned:
            misses+=1
            if misses>=32:break
            address+=0x10000
            continue
        misses=0
        base=int(info.BaseAddress or 0)
        size=int(info.RegionSize)
        next_address=max(address+0x1000,base+max(0x1000,size))
        flags=int(info.Protect)
        if (info.State==MEM_COMMIT and size>=HAND_BYTES
                and not (flags & (PAGE_GUARD|PAGE_NOACCESS))
                and (flags & 0xFF) in READABLE):
            regions.append((base,size))
        address=next_address
    # Prefer PS1-sized allocations, then larger writable module data.
    # Rank before budget applies so high-address versions aren't starved.
    regions.sort(key=lambda item:(
        0 if 0x180000<=item[1]<=0x400000 else
        1 if 0x400000<item[1]<=0x2000000 else
        2 if 0x20000<=item[1]<0x180000 else 3,
        abs(item[1]-0x200000),item[0]))
    return regions


def discover_hand_addresses(read_at, regions: list[tuple[int,int]], *,
                            budget: int=MAX_SCAN_BYTES) -> list[int]:
    """Scan limited readable regions for structural hand candidates.

    The result contains HOST addresses, never exposed to the frontend/logs.
    The caller must double-read and reject more than one stable candidate.
    """
    if type(budget) is not int or not 0<budget<=MAX_SCAN_BYTES:
        raise ValueError("Limite de leitura da RAM inválido.")
    found=[]
    seen=set()
    consumed=0
    for start,size in regions[:MAX_REGIONS]:
        if (type(start) is not int or type(size) is not int or
                start<MIN_ADDRESS or size<HAND_BYTES):
            continue
        cursor=0
        while cursor<size and consumed<budget:
            # 139-byte overlap preserves records split at chunk boundaries.
            remaining=min(size-cursor,CHUNK+HAND_BYTES-1,budget-consumed)
            if remaining<HAND_BYTES:
                break
            raw=read_at(start+cursor,remaining)
            consumed+=remaining
            if isinstance(raw,bytes) and len(raw)==remaining:
                for off in _candidate_hand_offsets(raw):
                    host=start+cursor+off
                    # Host base must be plausible when translating PSX offsets.
                    if host-HAND_OFFSET<MIN_ADDRESS or host in seen:
                        continue
                    seen.add(host)
                    found.append(host)
                    if len(found)>=MAX_MATCHES:
                        return found
            cursor+=max(1,remaining-(HAND_BYTES-1))
        if consumed>=budget:
            break
    return found


def choose_stable_hand(read_at, addresses, *, max_candidates=128) -> dict:
    """Return one validated hand, otherwise never guess or retain stale data."""
    from fusion_ram_probe import decode_hand

    if not isinstance(addresses,(tuple,list)) or len(addresses)>max_candidates:
        return {"status":"too_many_candidates","address":None,"hand_ids":None}
    matches=[]
    seen=set()
    for address in addresses:
        if (type(address) is not int or address<MIN_ADDRESS
                or address in seen):
            continue
        seen.add(address)
        first=read_at(address,HAND_BYTES)
        decoded=decode_hand(first)
        if decoded is None:
            continue
        second=read_at(address,HAND_BYTES)
        if decoded != decode_hand(second):
            continue
        matches.append((address,decoded))
        if len(matches)>=2:
            return {"status":"ambiguous_ram_mapping",
                    "address":None,"hand_ids":None}
    if len(matches)==1:
        return {"status":"hand_validated","address":matches[0][0],
                "hand_ids":matches[0][1]}
    return {"status":"ram_mapping_not_validated","address":None,"hand_ids":None}
