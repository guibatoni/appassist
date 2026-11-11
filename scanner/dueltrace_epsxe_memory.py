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


def probe_region_hand_anchors(read_at, regions, *, max_probes=512) -> list[int]:
    """Fast, bounded checks of PS1 hand offset near host region boundaries.

    Some ePSXe versions map their 2MB PlayStation RAM directly at the base
    of a readable allocation, others have a small 64KB suballocation offset.
    Read only 140 bytes at each hypothesized hand location. A match must
    still pass two stable strict reads in choose_stable_hand().
    """
    from fusion_ram_probe import decode_hand

    if type(max_probes) is not int or not 1 <= max_probes <= 1024:
        raise ValueError("Limite de sondas ePSXe inválido.")
    found=[]
    seen=set()
    count=0
    # These are probing hints, not evidence of the emulator's RAM location.
    hints=(0,0x10000,0x20000,0x30000,0x40000,0x80000)
    for base,size in regions[:MAX_REGIONS]:
        if type(base) is not int or type(size) is not int or base<MIN_ADDRESS:
            continue
        for delta in hints:
            if HAND_OFFSET+delta+HAND_BYTES>size:
                continue
            address=base+HAND_OFFSET+delta
            if address in seen:
                continue
            seen.add(address)
            count+=1
            value=read_at(address,HAND_BYTES)
            if decode_hand(value) is not None:
                found.append(address)
                if len(found)>=MAX_MATCHES:
                    return found
            if count>=max_probes:
                return found
    return found


def discover_hand_addresses(read_at, regions: list[tuple[int,int]], *,
                            budget: int=MAX_SCAN_BYTES,
                            cursor: tuple[int,int] | None=None,
                            report_progress: bool=False):
    """Bounded scan for strict five-card structures, optionally resumable.

    Old callers get an address list. With report_progress=True, the caller
    receives the next (region index, byte offset) cursor. Each invocation
    scans at most 'budget' bytes; later invocations can continue instead of
    repeating the first 48 MiB forever on larger ePSXe allocations.

    Cursor never becomes a trusted pointer: every candidate still requires
    two fresh, matching reads before any hand IDs are returned.
    """
    if type(budget) is not int or not 0<budget<=MAX_SCAN_BYTES:
        raise ValueError("Limite de leitura da RAM inválido.")
    if not isinstance(regions,list) or len(regions)>MAX_REGIONS:
        raise ValueError("Lista de regiões RAM inválida.")
    if cursor is not None and (
            not isinstance(cursor,tuple) or len(cursor)!=2
            or any(type(item) is not int or item<0 for item in cursor)
            or cursor[0]>=len(regions)
            or cursor[1]>=regions[cursor[0]][1]):
        raise ValueError("Posição de retomada da RAM inválida.")
    start_index,start_offset=cursor if cursor is not None else (0,0)
    found=[]
    seen=set()
    consumed=0
    next_cursor=None
    complete=True
    for index in range(start_index,len(regions)):
        start,size=regions[index]
        if (type(start) is not int or type(size) is not int or
                start<MIN_ADDRESS or size<HAND_BYTES):
            continue
        offset=start_offset if index==start_index else 0
        while offset+HAND_BYTES<=size:
            if budget-consumed<HAND_BYTES:
                next_cursor=(index,offset)
                complete=False
                break
            # 139-byte overlap preserves records crossing any chunk edge.
            remaining=min(size-offset,CHUNK+HAND_BYTES-1,budget-consumed)
            if remaining<HAND_BYTES:
                next_cursor=(index,offset)
                complete=False
                break
            raw=read_at(start+offset,remaining)
            consumed+=remaining
            if isinstance(raw,bytes) and len(raw)==remaining:
                for pos in _candidate_hand_offsets(raw):
                    host=start+offset+pos
                    if host-HAND_OFFSET<MIN_ADDRESS or host in seen:
                        continue
                    seen.add(host)
                    found.append(host)
                    if len(found)>=MAX_MATCHES:
                        complete=False
                        next_cursor=(index,min(size-1,offset+1))
                        break
            if len(found)>=MAX_MATCHES:
                break
            if offset+remaining>=size:
                offset=size
            else:
                offset+=max(1,remaining-(HAND_BYTES-1))
        if not complete:
            break
    outcome={"addresses":found,"cursor":next_cursor,"completed":complete,
             "scanned_bytes":consumed}
    return outcome if report_progress else found


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
