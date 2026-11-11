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
        return {"ready":False,"status":"ePSXe não encontrado","hand_ids":None,"pid":None}
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

        # Prefer the original known 2.0.x address and recheck twice.
        first=decode_hand(read_at(HAND_ADDRESS,HAND_BYTES))
        if first is not None:
            second=decode_hand(read_at(HAND_ADDRESS,HAND_BYTES))
            if second is None or second!=first:
                return {"ready":False,
                        "status":"Mão em transição — aguardando estabilidade",
                        "hand_ids":None,"pid":pid}
            _PID_HAND_ADDRESS_CACHE[pid]=HAND_ADDRESS
            _LAST_FAILED_SCAN.pop(pid,None)
            _PID_SCAN_PROGRESS.pop(pid,None)
            return {"ready":True,"status":"Mão estável: duas leituras válidas",
                    "hand_ids":second,"pid":pid,"ramLayout":"legacy"}

        cached=_PID_HAND_ADDRESS_CACHE.get(pid)
        if cached is not None and cached!=HAND_ADDRESS:
            result=choose_stable_hand(read_at,[cached])
            if result["hand_ids"] is not None:
                _PID_SCAN_PROGRESS.pop(pid,None)
                return {"ready":True,
                        "status":"Mão estável em layout ePSXe alternativo",
                        "hand_ids":result["hand_ids"],"pid":pid,
                        "ramLayout":"dynamic"}
        _PID_HAND_ADDRESS_CACHE.pop(pid,None)
        scan_detail=None
        if candidate_addresses is not None:
            addresses=list(candidate_addresses)
        else:
            now=monotonic()
            last=_LAST_FAILED_SCAN.get(pid)
            if last is not None and now-last<RESCAN_AFTER_SECONDS:
                return {"ready":False,
                        "status":"ePSXe detectado; procurando outras regiões da RAM",
                        "hand_ids":None,"pid":pid}
            regions=readable_regions(kernel,handle)
            if not regions:
                _LAST_FAILED_SCAN[pid]=monotonic()
                _PID_SCAN_PROGRESS.pop(pid,None)
                return {"ready":False,
                        "status":"ePSXe detectado, mas nenhuma região RAM acessível",
                        "hand_ids":None,"pid":pid}
            # Shortcut: candidate PlayStation RAM at committed region start.
            # This is a heuristic only: choose_stable_hand still double-reads.
            fast=probe_region_hand_anchors(read_at,regions)
            fast_check=choose_stable_hand(read_at,fast)
            if fast_check["status"]=="ambiguous_ram_mapping":
                return {"ready":False,
                        "status":"Várias mãos plausíveis na RAM; identificação ambígua",
                        "hand_ids":None,"pid":pid}
            if fast_check["hand_ids"] is not None:
                addresses=fast
            else:
                # Continue a large process's memory scan across polls instead
                # of starting from byte 0 after every 48 MiB budget.
                fingerprint=hash(tuple(regions))
                saved=_PID_SCAN_PROGRESS.get(pid)
                cursor=saved[1] if saved is not None and saved[0]==fingerprint else None
                scan_detail=discover_hand_addresses(
                    read_at,regions,cursor=cursor,report_progress=True)
                addresses=scan_detail["addresses"]
                if scan_detail["cursor"] is None:
                    _PID_SCAN_PROGRESS.pop(pid,None)
                else:
                    _PID_SCAN_PROGRESS[pid]=(fingerprint,scan_detail["cursor"])
                    if len(_PID_SCAN_PROGRESS)>32:
                        # Avoid unbounded state on machines with many ePSXe PIDs.
                        keep=_PID_SCAN_PROGRESS[pid]
                        _PID_SCAN_PROGRESS.clear()
                        _PID_SCAN_PROGRESS[pid]=keep
        result=choose_stable_hand(read_at,addresses)
        if result["hand_ids"] is not None:
            _PID_HAND_ADDRESS_CACHE[pid]=result["address"]
            _LAST_FAILED_SCAN.pop(pid,None)
            _PID_SCAN_PROGRESS.pop(pid,None)
            if len(_PID_HAND_ADDRESS_CACHE)>32:
                _PID_HAND_ADDRESS_CACHE.clear()
                _PID_HAND_ADDRESS_CACHE[pid]=result["address"]
            return {"ready":True,"status":"Mão reconhecida nesta versão do ePSXe",
                    "hand_ids":result["hand_ids"],"pid":pid,"ramLayout":"dynamic"}
        if candidate_addresses is None:
            _LAST_FAILED_SCAN[pid]=monotonic()
            if len(_LAST_FAILED_SCAN)>32:
                _LAST_FAILED_SCAN.clear()
        if result["status"]=="ambiguous_ram_mapping":
            return {"ready":False,
                    "status":"RAM ambígua; não é seguro selecionar um endereço",
                    "hand_ids":None,"pid":pid}
        if scan_detail is not None and scan_detail["cursor"] is not None:
            status="ePSXe detectado; busca de RAM continua em outros blocos"
        else:
            status="ePSXe detectado; estrutura de cinco cartas não validada"
        return {"ready":False,"status":status,
                "hand_ids":None,"pid":pid}
    finally:
        kernel.CloseHandle(handle)
