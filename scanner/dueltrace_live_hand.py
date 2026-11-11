"""Mão ao vivo e fusões mão×mão na tela Início do DUELTRACE.

Somente leitura: a janela RAM da mão é a mesma validada no painel clássico
(0xBFF484, 140 bytes, 5 slots de 28). Nunca detecta automaticamente a ISO
que o emulador abriu: apenas exibe nomes da ROM ativada no DUELTRACE.
"""
from __future__ import annotations

import ctypes
import sys
import re
import time
from ctypes import wintypes

from dueltrace_epsxe_memory import (
    HAND_OFFSET, readable_regions, discover_hand_addresses, choose_stable_hand,
    probe_region_hand_anchors,
)

from fusion_ram_probe import decode_hand

HAND_ADDRESS = 0xBFF484
HAND_BYTES = 140
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
TH32CS_SNAPPROCESS = 0x00000002

# Cache host pointers ONLY while in this process, and revalidate on every read.
# RAM layouts depend on emulator release, plugins and ASLR, not on ISO name.
_PID_HAND_ADDRESS_CACHE: dict[int,int] = {}
_LAST_FAILED_SCAN: dict[int,float] = {}
# Fingerprint of RAM regions plus scan cursor: never store outside this run.
_PID_SCAN_PROGRESS: dict[int,tuple[int,tuple[int,int]]] = {}
# A static five-card buffer is NOT evidence that this is the live hand.
# Candidates remain provisional until the same host address shows a genuine
# change in the five card IDs across separate polling calls.
_PID_PENDING_HANDS: dict[int,dict[int,tuple[tuple[int,...],float]]] = {}
_PID_CONFIRMED_READ_FAILURES: dict[int,int] = {}
MAX_PENDING_HANDS_PER_PID = 64
PENDING_HAND_TTL_SECONDS = 180.0
RESCAN_AFTER_SECONDS = 5.0
EPSXE_IMAGE_PATTERN = re.compile(
    r"epsxe(?:[ ._-]?v?\d+(?:[._-]\d+)*)?(?:[._-](?:x86|x64|win32|win64|32|64))?\.exe\Z",
    re.IGNORECASE,
)


def is_epsxe_process_name(name: str) -> bool:
    """Recognize official image and version-suffixed copies, never arbitrary EXEs."""
    return (type(name) is str and 0 < len(name) <= 90
            and EPSXE_IMAGE_PATTERN.fullmatch(name) is not None)


if sys.platform == "win32":
    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]


def build_fusion_index(recipes: list[dict]) -> dict[tuple[int, int], list[tuple[int, str]]]:
    """Indexação por material, reaproveitável entre atualizações da mão."""
    index = {}
    for row in recipes:
        try:
            a, b, result = (row[k] for k in ("a", "b", "result"))
            if any(type(x) is not int or not 1 <= x <= 722 for x in (a, b, result)):
                continue
            key = tuple(sorted((a,b)))
            value = (result, str(row.get("validation") or "origem não informada"))
            dest = index.setdefault(key, [])
            if value not in dest:
                dest.append(value)
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
    return index


def suggest_hand_pairs(hand: list[int] | None, index: dict,
                       cards: dict[int, dict], *, limit: int=24) -> list[dict]:
    """Compara as 10 combinações possíveis dos cinco slots sem consumir cartas."""
    if (not isinstance(hand,list) or len(hand) != 5
            or any(type(x) is not int or not 1 <= x <= 722 for x in hand)):
        return []
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Limite de sugestões inválido")
    results = []
    seen = set()
    for i in range(5):
        for j in range(i+1,5):
            a,b=hand[i],hand[j]
            for cid, validation in index.get(tuple(sorted((a,b))),()):
                if type(cid) is not int or not 1 <= cid <= 722:
                    continue
                token=(i,j,cid)
                if token in seen:
                    continue
                seen.add(token)
                card=cards.get(cid,{})
                results.append({
                    "slot_a":i+1,"slot_b":j+1,
                    "a":a,"b":b,"result":cid,
                    "result_name":str(card.get("name") or f"Carta #{cid}"),
                    "atk":card.get("atk") if type(card.get("atk")) is int else None,
                    "validation":validation,
                })
    results.sort(key=lambda r:(
        -(r["atk"] if r["atk"] is not None else -1),
        r["slot_a"],r["slot_b"],r["result"]))
    return results[:limit]


def _windows_kernel32():
    if sys.platform != "win32":
        raise OSError("A leitura RAM do ePSXe exige Windows.")
    return ctypes.WinDLL("kernel32", use_last_error=True)


def discover_epsxe_pids(kernel=None) -> list[int]:
    """Enumeração restrita ao processo ePSXe.exe; não modifica processos."""
    kernel = kernel or _windows_kernel32()
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(PROCESSENTRY32W)]
    kernel.Process32FirstW.restype=wintypes.BOOL
    kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(PROCESSENTRY32W)]
    kernel.Process32NextW.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.CloseHandle.restype=wintypes.BOOL
    handle=kernel.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0)
    if handle in (None,0,ctypes.c_void_p(-1).value):
        raise OSError("Windows não permitiu enumerar processos.")
    found=[]
    try:
        entry=PROCESSENTRY32W()
        entry.dwSize=ctypes.sizeof(PROCESSENTRY32W)
        ok=kernel.Process32FirstW(handle,ctypes.byref(entry))
        while ok:
            if is_epsxe_process_name(entry.szExeFile):
                found.append(int(entry.th32ProcessID))
            ok=kernel.Process32NextW(handle,ctypes.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    return found


def read_hand_from_epsxe(*, preferred_pid: int | None=None,
                         kernel=None, pids=None,
                         candidate_addresses=None, monotonic=time.monotonic) -> dict:
    """Read 5 battle cards from old or new Windows ePSXe memory layouts.

    Legacy host address is fast path; if unreadable, scan ONLY the selected
    emulator's readable memory for the strict 5×28-byte structure, twice.
    Never infer emulator version or ROM identity from an arbitrary PID.
    """
    kernel=kernel or _windows_kernel32()
    candidates=discover_epsxe_pids(kernel) if pids is None else list(pids)
    if not candidates:
        for cache in (_PID_HAND_ADDRESS_CACHE,_LAST_FAILED_SCAN,
                      _PID_SCAN_PROGRESS,_PID_PENDING_HANDS,
                      _PID_CONFIRMED_READ_FAILURES):
            cache.clear()
        return {"ready":False,"status":"ePSXe não encontrado",
                "hand_ids":None,"pid":None}
    active_pids=set(candidates)
    for cache in (_PID_HAND_ADDRESS_CACHE,_LAST_FAILED_SCAN,
                  _PID_SCAN_PROGRESS,_PID_PENDING_HANDS,
                  _PID_CONFIRMED_READ_FAILURES):
        for old_pid in tuple(cache):
            if old_pid not in active_pids:
                cache.pop(old_pid,None)
    if preferred_pid is not None:
        if preferred_pid not in candidates:
            return {"ready":False,"status":"Processo ePSXe iniciado não encontrado",
                    "hand_ids":None,"pid":None}
        pid=preferred_pid
    elif len(candidates)==1:
        pid=candidates[0]
    else:
        return {"ready":False,"status":"Há vários processos ePSXe; feche os extras",
                "hand_ids":None,"pid":None}
    if type(pid) is not int or pid<=0:
        return {"ready":False,"status":"PID de emulador inválido",
                "hand_ids":None,"pid":None}
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.ReadProcessMemory.argtypes=[
        wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,
        ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
    kernel.ReadProcessMemory.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.CloseHandle.restype=wintypes.BOOL
    handle=kernel.OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ,False,pid)
    if not handle:
        return {"ready":False,"status":"Acesso de leitura negado ao ePSXe",
                "hand_ids":None,"pid":pid}
    try:
        def read_at(address,size):
            if (type(address) is not int or address<0x10000
                    or type(size) is not int or not 0<size<=256*1024+140):
                return None
            buffer=ctypes.create_string_buffer(size)
            read=ctypes.c_size_t(0)
            ok=kernel.ReadProcessMemory(handle,ctypes.c_void_p(address),
                                        buffer,size,ctypes.byref(read))
            return buffer.raw if ok and read.value==size else None

        # ONLY a candidate that already demonstrated actual card changes in
        # previous polls may be treated as the live RAM pointer. Two immediate
        # identical reads alone are insufficient: they accept static buffers.
        cached=_PID_HAND_ADDRESS_CACHE.get(pid)
        if cached is not None:
            validated=choose_stable_hand(read_at,[cached])
            if validated["hand_ids"] is not None:
                _PID_CONFIRMED_READ_FAILURES.pop(pid,None)
                return {"ready":True,"status":"Mão ao vivo confirmada",
                        "hand_ids":validated["hand_ids"],"pid":pid,
                        "ramLayout":"legacy" if cached==HAND_ADDRESS else "dynamic"}
            misses=_PID_CONFIRMED_READ_FAILURES.get(pid,0)+1
            if misses<2:
                _PID_CONFIRMED_READ_FAILURES[pid]=misses
                return {"ready":False,
                        "status":"RAM em transição — verificando endereço conhecido",
                        "hand_ids":None,"pid":pid}
            # Old pointer is invalid twice; resume discovery, never show a
            # previous hand and never accept a stale cache as positive proof.
            _PID_HAND_ADDRESS_CACHE.pop(pid,None)
            _PID_CONFIRMED_READ_FAILURES.pop(pid,None)
            _PID_PENDING_HANDS.pop(pid,None)
            _LAST_FAILED_SCAN.pop(pid,None)
            _PID_SCAN_PROGRESS.pop(pid,None)

        now=monotonic()
        pending=_PID_PENDING_HANDS.setdefault(pid,{})
        for address,(old_ids,first_seen) in tuple(pending.items()):
            if now-first_seen>PENDING_HAND_TTL_SECONDS:
                pending.pop(address,None)

        changed=[]
        checked=set()

        def observe(address):
            if type(address) is not int or address<0x10000 or address in checked:
                return
            checked.add(address)
            pair=choose_stable_hand(read_at,[address])
            ids=pair["hand_ids"]
            if ids is None:
                return
            new_ids=tuple(ids)
            previous=pending.get(address)
            if previous is not None and previous[0]!=new_ids:
                # A genuine inter-poll change. Do not confuse two consecutive
                # reads of an UNCHANGED stale hand with proof of activity.
                changed.append((address,ids))
            elif previous is None and len(pending)<MAX_PENDING_HANDS_PER_PID:
                pending[address]=(new_ids,now)

        # Revisit EVERY provisional address before looking for more. Static
        # copies stay provisional and do NOT prevent discovery of the real RAM.
        for address in tuple(pending):
            observe(address)

        # Legacy address remains an inexpensive candidate, not a privileged
        # auto-confirmation. Explicit candidate_addresses is a test seam.
        if candidate_addresses is None:
            observe(HAND_ADDRESS)
            last=_LAST_FAILED_SCAN.get(pid)
            if last is None or now-last>=RESCAN_AFTER_SECONDS:
                regions=readable_regions(kernel,handle)
                if regions:
                    for address in probe_region_hand_anchors(read_at,regions):
                        observe(address)
                    fingerprint=hash(tuple(regions))
                    saved=_PID_SCAN_PROGRESS.get(pid)
                    cursor=(saved[1] if saved is not None
                            and saved[0]==fingerprint else None)
                    page=discover_hand_addresses(
                        read_at,regions,cursor=cursor,report_progress=True)
                    for address in page["addresses"]:
                        observe(address)
                    if page["cursor"] is None:
                        _PID_SCAN_PROGRESS.pop(pid,None)
                    else:
                        _PID_SCAN_PROGRESS[pid]=(fingerprint,page["cursor"])
                else:
                    _PID_SCAN_PROGRESS.pop(pid,None)
                _LAST_FAILED_SCAN[pid]=now
        else:
            for address in candidate_addresses:
                observe(address)

        if len(changed)>1:
            # Mirrored/changeable copies cannot be distinguished without a
            # separate in-game signal. Never choose one arbitrarily.
            return {"ready":False,
                    "status":"Mais de uma mão muda na RAM; mapeamento ambíguo",
                    "hand_ids":None,"pid":pid}
        if len(changed)==1:
            address,ids=changed[0]
            _PID_HAND_ADDRESS_CACHE[pid]=address
            _PID_CONFIRMED_READ_FAILURES.pop(pid,None)
            _PID_PENDING_HANDS.pop(pid,None)
            _PID_SCAN_PROGRESS.pop(pid,None)
            _LAST_FAILED_SCAN.pop(pid,None)
            if len(_PID_HAND_ADDRESS_CACHE)>32:
                keep=_PID_HAND_ADDRESS_CACHE[pid]
                _PID_HAND_ADDRESS_CACHE.clear()
                _PID_HAND_ADDRESS_CACHE[pid]=keep
            return {"ready":True,
                    "status":"RAM confirmada após mudança real da mão",
                    "hand_ids":ids,"pid":pid,
                    "ramLayout":"legacy" if address==HAND_ADDRESS else "dynamic"}

        if len(pending)>1:
            status="Múltiplos candidatos de RAM; aguardando mudança real da mão"
        elif pending:
            status="RAM candidata localizada; jogue uma carta para confirmar a mão"
        elif pid in _PID_SCAN_PROGRESS:
            status="ePSXe detectado; buscando estrutura da mão em outros blocos"
        else:
            status="ePSXe detectado; mão real ainda não localizada"
        return {"ready":False,"status":status,"hand_ids":None,"pid":pid}
    finally:
        kernel.CloseHandle(handle)
