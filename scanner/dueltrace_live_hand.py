"""Mão ao vivo e fusões mão×mão na tela Início do DUELTRACE.

Somente leitura: a janela RAM da mão é a mesma validada no painel clássico
(0xBFF484, 140 bytes, 5 slots de 28). Nunca detecta automaticamente a ISO
que o emulador abriu: apenas exibe nomes da ROM ativada no DUELTRACE.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from fusion_ram_probe import decode_hand

HAND_ADDRESS = 0xBFF484
HAND_BYTES = 140
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
TH32CS_SNAPPROCESS = 0x00000002

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
            if entry.szExeFile.casefold()=="epsxe.exe":
                found.append(int(entry.th32ProcessID))
            ok=kernel.Process32NextW(handle,ctypes.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    return found


def read_hand_from_epsxe(*, preferred_pid: int | None=None,
                         kernel=None, pids=None) -> dict:
    """Lê estritamente 140 bytes em um ePSXe e valida os cinco slots.

    O PID preferido deve estar presente na lista de processos ePSXe.
    Nunca reaproveita uma mão antiga após falha.
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
    if type(pid) is not int or pid <= 0:
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
        def read_sample():
            buffer=ctypes.create_string_buffer(HAND_BYTES)
            read=ctypes.c_size_t(0)
            ok=kernel.ReadProcessMemory(handle,ctypes.c_void_p(HAND_ADDRESS),
                                        buffer,HAND_BYTES,ctypes.byref(read))
            if not ok or read.value != HAND_BYTES:
                return None
            return decode_hand(buffer.raw)

        # Duas amostras consecutivas evitam mostrar uma mão parcialmente
        # atualizada pelo jogo durante a leitura, sem acessar outras áreas RAM.
        first=read_sample()
        if first is None:
            return {"ready":False,"status":"Mão indisponível ou fora de duelo",
                    "hand_ids":None,"pid":pid}
        second=read_sample()
        if second is None or second != first:
            return {"ready":False,"status":"Mão em transição — aguardando estabilidade",
                    "hand_ids":None,"pid":pid}
        return {"ready":True,"status":"Mão estável: duas leituras válidas",
                "hand_ids":second,"pid":pid}
    finally:
        kernel.CloseHandle(handle)
