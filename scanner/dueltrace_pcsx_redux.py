"""PCSX-Redux adapter for DUELTRACE Windows (read-only, version-neutral).

Uses the emulator's documented HTTP GET API instead of Windows host pointers.
Never POST to Redux: its API also exposes RAM writes, state/ISO mutations.
Only 127.0.0.1 is allowed; never route through a proxy or follow redirects.
Versions lacking these endpoints remain unsupported rather than guessed.
"""
from __future__ import annotations

import ctypes
import json
import re
import sys
import time
import urllib.error
import urllib.request
from ctypes import wintypes

from dueltrace_epsxe_memory import HAND_OFFSET, HAND_BYTES
from fusion_ram_probe import decode_hand

DEFAULT_PORT = 8080
RAM_2MB = 2 * 1024 * 1024
RAM_8MB = 8 * 1024 * 1024
MAX_RESPONSE = RAM_8MB
TIMEOUT_SECONDS = 1.8
CONFIRM_TTL_SECONDS = 180.0
_PROCESS_PATTERN = re.compile(
    r"pcsx-redux(?:[._-](?:v?[0-9][0-9a-z._-]{0,50}))?\.(?:exe|main)\Z",
    re.IGNORECASE,
)
# Per-process, in-memory state only. A changing five-card hand confirms the
# live hand, not which user-provided ISO the emulator actually booted.
_PENDING: dict[tuple[int,int], tuple[tuple[int,...],float]] = {}
_CONFIRMED: dict[tuple[int,int], float] = {}


def is_redux_process_name(name: str) -> bool:
    return type(name) is str and len(name) <= 90 and bool(_PROCESS_PATTERN.fullmatch(name))


def valid_port(port: int) -> int:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Porta PCSX-Redux inválida (1024–65535).")
    return port


class _RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(path: str, *, port: int=DEFAULT_PORT, limit: int=MAX_RESPONSE) -> bytes:
    """Read only these two predetermined paths from the loopback emulator."""
    valid_port(port)
    if path not in ("/api/v1/execution-flow", "/api/v1/cpu/ram/raw"):
        raise ValueError("Rota não autorizada do PCSX-Redux.")
    if type(limit) is not int or not 1 <= limit <= MAX_RESPONSE:
        raise ValueError("Tamanho HTTP inválido.")
    url=f"http://127.0.0.1:{port}{path}"
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}), _RejectRedirect())
    request=urllib.request.Request(
        url, headers={"User-Agent":"DUELTRACE-Windows-PCsxRedux/0.19",
                      "Accept":"application/json" if path.endswith("execution-flow")
                      else "application/octet-stream"},
        method="GET")
    with opener.open(request,timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200 or response.geturl()!=url:
            raise ValueError("API PCSX-Redux indisponível na porta selecionada.")
        advertised=response.headers.get("Content-Length")
        if advertised:
            try:
                if int(advertised)>limit:
                    raise ValueError("Resposta do emulador maior que o limite seguro.")
            except (TypeError,OverflowError):
                raise ValueError("Content-Length PCSX-Redux inválido.")
        data=response.read(limit+1)
        if len(data)>limit:
            raise ValueError("Resposta do emulador acima do limite seguro.")
        return data


def _state(port: int, fetch=_fetch) -> dict:
    raw=fetch("/api/v1/execution-flow",port=port,limit=32768)
    try:
        parsed=json.loads(raw)
    except (ValueError,UnicodeError,TypeError):
        raise ValueError("Resposta de status incompatível com a API PCSX-Redux.")
    if not isinstance(parsed,dict) or type(parsed.get("running")) is not bool:
        raise ValueError("API de execução não reconhecida nesta versão do PCSX-Redux.")
    return parsed


def _memory(port: int, fetch=_fetch) -> bytes:
    data=fetch("/api/v1/cpu/ram/raw",port=port,limit=MAX_RESPONSE)
    if type(data) is not bytes or len(data) not in (RAM_2MB,RAM_8MB):
        raise ValueError("Dump de RAM incompatível: esperados 2 MiB ou 8 MiB.")
    return data


def _windows_kernel32():
    if sys.platform!="win32":
        raise OSError("O leitor PCSX-Redux deste DUELTRACE exige Windows.")
    return ctypes.WinDLL("kernel32",use_last_error=True)


if sys.platform == "win32":
    class PROCESSENTRY32W(ctypes.Structure):
        _fields_=[
            ("dwSize",wintypes.DWORD),("cntUsage",wintypes.DWORD),
            ("th32ProcessID",wintypes.DWORD),("th32DefaultHeapID",ctypes.c_void_p),
            ("th32ModuleID",wintypes.DWORD),("cntThreads",wintypes.DWORD),
            ("th32ParentProcessID",wintypes.DWORD),
            ("pcPriClassBase",wintypes.LONG),("dwFlags",wintypes.DWORD),
            ("szExeFile",wintypes.WCHAR*260),
        ]


def discover_redux_pids(kernel=None) -> list[int]:
    """Detect running Redux Windows processes by executable name only.

    It does not open their memory, patch DLLs, or assume an executable version.
    Multiple processes are intentionally rejected until one is selected.
    """
    kernel=kernel or _windows_kernel32()
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(PROCESSENTRY32W)]
    kernel.Process32FirstW.restype=wintypes.BOOL
    kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(PROCESSENTRY32W)]
    kernel.Process32NextW.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.CloseHandle.restype=wintypes.BOOL
    handle=kernel.CreateToolhelp32Snapshot(0x2,0)
    if handle in (None,0,ctypes.c_void_p(-1).value):
        return []
    result=[]
    try:
        item=PROCESSENTRY32W()
        item.dwSize=ctypes.sizeof(PROCESSENTRY32W)
        ok=kernel.Process32FirstW(handle,ctypes.byref(item))
        while ok:
            if is_redux_process_name(item.szExeFile):
                pid=int(item.th32ProcessID)
                if pid>0: result.append(pid)
            ok=kernel.Process32NextW(handle,ctypes.byref(item))
    finally:
        kernel.CloseHandle(handle)
    return sorted(set(result))


def _single_pid(*, preferred_pid=None, pids=None) -> int | None:
    found=discover_redux_pids() if pids is None else list(pids)
    if not found or any(type(x) is not int or x<=0 for x in found):
        return None
    # HTTP port identity cannot be tied reliably to one of two Redux
    # processes. Never associate an arbitrary HTTP server with a PID.
    if len(found)!=1:
        return None
    if preferred_pid is not None and found[0]!=preferred_pid:
        return None
    return found[0]


def connection_status(*, port: int=DEFAULT_PORT, fetch=_fetch, pids=None) -> dict:
    """Sanitized diagnostic safe to show in the desktop Settings screen."""
    valid_port(port)
    try:
        state=_state(port,fetch)
    except (OSError,ValueError,urllib.error.URLError,TimeoutError):
        return {"available":False,"running":False,"port":port,
                "status":"Servidor PCSX-Redux indisponível. Ative Configuration > Emulation > Enable Web Server."}
    found=discover_redux_pids() if pids is None else list(pids)
    if not found:
        return {"available":False,"running":False,"port":port,
                "status":"API acessível, mas processo PCSX-Redux não confirmado neste Windows."}
    if len(found)!=1:
        return {"available":False,"running":False,"port":port,
                "status":"Várias instâncias PCSX-Redux abertas; mantenha apenas uma."}
    return {"available":True,"running":state["running"],"port":port,
            "status":("PCSX-Redux conectado; jogo em execução."
                      if state["running"] else "PCSX-Redux conectado; aguardando jogo em execução.")}


def read_hand_from_redux(*, preferred_pid=None, port: int=DEFAULT_PORT,
                         fetch=_fetch, pids=None, monotonic=time.monotonic) -> dict:
    """Read PS1 hand at the emulated physical RAM offset, never a host address.

    Requiring an inter-poll hand change avoids publishing an unchanged static
    five-card copy as a proven live hand. Status remains provisional until then.
    """
    valid_port(port)
    found=discover_redux_pids() if pids is None else list(pids)
    if not found:
        _PENDING.clear();_CONFIRMED.clear()
        return {"ready":False,"hand_ids":None,"pid":None,
                "status":"PCSX-Redux não encontrado."}
    pid=_single_pid(preferred_pid=preferred_pid,pids=found)
    if pid is None:
        return {"ready":False,"hand_ids":None,"pid":None,
                "status":"Selecione uma única instância PCSX-Redux."}
    key=(pid,port)
    for cache in (_PENDING,_CONFIRMED):
        for old in list(cache):
            if old!=key:cache.pop(old,None)
    try:
        state=_state(port,fetch)
        if not state["running"]:
            _PENDING.pop(key,None);_CONFIRMED.pop(key,None)
            return {"ready":False,"hand_ids":None,"pid":pid,
                    "status":"PCSX-Redux conectado; jogo pausado ou ainda não iniciado."}
        a=_memory(port,fetch)
        first=decode_hand(a[HAND_OFFSET:HAND_OFFSET+HAND_BYTES])
        if first is None:
            _PENDING.pop(key,None);_CONFIRMED.pop(key,None)
            return {"ready":False,"hand_ids":None,"pid":pid,
                    "status":"PCSX-Redux: aguardando mão válida durante o duelo."}
        b=_memory(port,fetch)
        second=decode_hand(b[HAND_OFFSET:HAND_OFFSET+HAND_BYTES])
        if first!=second:
            return {"ready":False,"hand_ids":None,"pid":pid,
                    "status":"PCSX-Redux: mão em transição, aguardando próxima leitura."}
    except (OSError,ValueError,urllib.error.URLError,TimeoutError):
        _PENDING.pop(key,None);_CONFIRMED.pop(key,None)
        return {"ready":False,"hand_ids":None,"pid":pid,
                "status":"PCSX-Redux: servidor ou RAM indisponíveis."}
    now=monotonic()
    ids=tuple(first)
    old=_PENDING.get(key)
    if key not in _CONFIRMED:
        if old and old[0]!=ids and now-old[1]<=CONFIRM_TTL_SECONDS:
            _CONFIRMED[key]=now
        else:
            _PENDING[key]=(ids,now)
            return {"ready":False,"hand_ids":None,"pid":pid,
                    "status":"PCSX-Redux: mão candidata. Jogue ou compre uma carta para confirmar."}
    _PENDING[key]=(ids,now)
    return {"ready":True,"hand_ids":list(ids),"pid":pid,
            "emulator":"pcsx-redux","ramLayout":"ps1-physical",
            "status":"PCSX-Redux: mão ao vivo confirmada por mudança real."}


# The following is the PS1 physical displacement of the candidate record for
# the EXACT known Remaster X15 SHA only. Never use it for unknown mods.
X15_RANK_OFFSET = 0x2C990


def read_rank_candidate_redux(*, preferred_pid=None,port: int=DEFAULT_PORT,
                              fetch=_fetch,pids=None) -> dict:
    from dueltrace_rank_live import (
        RECORD_BYTES, decode_rank_record, decode_rank_result_adjustment)
    valid_port(port)
    pid=_single_pid(preferred_pid=preferred_pid,pids=pids)
    if pid is None:
        return {"ready":False,"pid":None,"counters":None,
                "status":"PCSX-Redux não encontrado ou múltiplas instâncias."}
    try:
        state=_state(port,fetch)
        if not state["running"]:
            return {"ready":False,"pid":pid,"counters":None,
                    "status":"PCSX-Redux: jogo não está em execução."}
        a=_memory(port,fetch)[X15_RANK_OFFSET:X15_RANK_OFFSET+RECORD_BYTES]
        b=_memory(port,fetch)[X15_RANK_OFFSET:X15_RANK_OFFSET+RECORD_BYTES]
        counters=decode_rank_record(a)
        if a!=b or counters is None:
            raise ValueError("Registro instável ou inválido.")
        return {"ready":True,"pid":pid,"counters":counters,
                "result_adjustment":decode_rank_result_adjustment(a),
                "emulator":"pcsx-redux",
                "status":"PCSX-Redux: contadores X15 candidatos em RAM PS1."}
    except (OSError,ValueError,urllib.error.URLError,TimeoutError):
        return {"ready":False,"pid":pid,"counters":None,
                "status":"PCSX-Redux: RANK X15 não identificado nesta sessão."}


def read_hand_from_redux_host(*, preferred_pid=None, pids=None) -> dict:
    """Fallback for old Redux builds without compatible HTTP GET endpoints.

    Uses the established version-agnostic Windows read-only process scanner
    with STRICT Redux PID enumeration. No static offsets, injection or writes.
    """
    if sys.platform!="win32":
        return {"ready":False,"pid":None,"hand_ids":None,
                "status":"Leitura de RAM local requer Windows."}
    found=discover_redux_pids() if pids is None else list(pids)
    if preferred_pid is not None:
        pid=preferred_pid if preferred_pid in found else None
    else:
        pid=found[0] if len(found)==1 else None
    if pid is None:
        return {"ready":False,"pid":None,"hand_ids":None,
                "status":"PCSX-Redux não encontrado ou múltiplas instâncias."}
    from dueltrace_live_hand import read_hand_from_epsxe
    try:
        result=read_hand_from_epsxe(preferred_pid=pid,pids=[pid])
    except (OSError,ValueError,RuntimeError):
        return {"ready":False,"pid":pid,"hand_ids":None,
                "status":"PCSX-Redux: leitura do processo indisponível."}
    return {**result,"emulator":"pcsx-redux",
            "ramLayout":("windows-ram-dynamic"
                         if result.get("ready") else None),
            "status":str(result.get("status","RAM não identificada")).replace("ePSXe","PCSX-Redux")}


def read_rank_candidate_redux_host(*, preferred_pid=None, pids=None) -> dict:
    """X15-only fallback: reuse ePSXe's candidate reader on a verified Redux PID.

    The caller MUST check the exact X15 ROM SHA. Unknown mods' bindings use
    ePSXe Windows HOST addresses and must never be transported here.
    """
    if sys.platform!="win32":
        return {"ready":False,"pid":None,"counters":None,
                "status":"PCSX-Redux: RANK exige Windows."}
    found=discover_redux_pids() if pids is None else list(pids)
    if preferred_pid is not None:
        pid=preferred_pid if preferred_pid in found else None
    else:
        pid=found[0] if len(found)==1 else None
    if pid is None:
        return {"ready":False,"pid":None,"counters":None,
                "status":"PCSX-Redux não encontrado ou múltiplas instâncias."}
    from dueltrace_rank_live import read_rank_candidate
    try:
        result=read_rank_candidate(preferred_pid=pid,pids=[pid])
    except (OSError,ValueError,RuntimeError):
        return {"ready":False,"pid":pid,"counters":None,
                "status":"PCSX-Redux: contadores X15 não disponíveis."}
    return {**result,"emulator":"pcsx-redux",
            "status":str(result.get("status","RANK indisponível")).replace("ePSXe","PCSX-Redux")}
