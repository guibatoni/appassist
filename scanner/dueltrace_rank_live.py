"""Estimativa de RANK do Remaster X15, sem modificar o ePSXe.

A fórmula das dez categorias foi inspecionada na ISO X15 conhecida;
o endereço virtual do primeiro registro (0xB41990) é HIPÓTESE e requer
calibração manual por LP visível no jogo em cada duelo. Nenhuma informação
é importada de outra ISO por nome ou suposição.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from dueltrace_live_hand import (
    PROCESS_QUERY_INFORMATION, PROCESS_VM_READ,
    discover_epsxe_pids, _windows_kernel32,
)
from scanner_multiiso import X15_SHA

CANDIDATE_RANK_ADDRESS = 0xB41990
RECORD_BYTES = 32

# (limiar exclusivo, pontos). Extraídos da ISO Remaster X15.
RULES = {
    "turns": [(5,12),(9,8),(29,0),(33,-8),(32767,-12)],
    "effective_attacks": [(2,4),(4,2),(10,0),(20,-2),(32767,-4)],
    "defense_wins": [(2,0),(6,-10),(10,-20),(15,-30),(32767,-40)],
    "face_down": [(1,0),(11,-2),(21,-4),(31,-6),(32767,-8)],
    "spells": [(1,2),(4,-4),(7,-8),(10,-12),(32767,-16)],
    "traps": [(1,2),(3,-8),(5,-16),(7,-24),(32767,-32)],
    "cards_used": [(9,15),(13,12),(33,0),(37,-5),(32767,-7)],
    "remaining_lp": [(100,-7),(1000,-5),(7000,0),(8000,4),(32767,6)],
    "fusions": [(1,4),(5,0),(10,-4),(15,-8),(32767,-12)],
    "equips": [(1,4),(5,0),(10,-4),(15,-8),(32767,-12)],
}


def model_available(sha256: str | None) -> bool:
    return isinstance(sha256,str) and sha256.casefold()==X15_SHA.casefold()


def _points(value: int, steps: list[tuple[int,int]]) -> int:
    for threshold,score in steps:
        if value < threshold:
            return score
    return steps[-1][1]


def decode_rank_record(raw: bytes) -> dict | None:
    """Valida registro hipotético; valores plausíveis NÃO provam mapeamento."""
    if not isinstance(raw,bytes) or len(raw)!=RECORD_BYTES:
        return None
    lp=int.from_bytes(raw[20:22],"little",signed=True)
    cards_used=int.from_bytes(raw[24:25],"little",signed=True)
    if not 0<=lp<=32766 or not 0<=cards_used<=80:
        return None
    fields={
        "turns":raw[1],
        "effective_attacks":raw[2],
        "defense_wins":raw[3],
        "face_down":raw[4],
        "spells":raw[5],
        "traps":raw[6],
        "fusions":raw[8],
        "equips":raw[9],
        "remaining_lp":lp,
        "cards_used":cards_used,
    }
    # Mod desconhecido e bytes incoerentes não devem virar pontuação.
    if fields["turns"]>100:
        return None
    return fields


def project_lp_win_rank(counters: dict) -> dict:
    """Projeção APENAS para vitória futura por LP, não nota final do duelo."""
    if set(counters)!=set(RULES):
        raise ValueError("Contadores do RANK incompletos.")
    if any(type(x) is not int or x<0 for x in counters.values()):
        raise ValueError("Contador inválido.")
    breakdown={key:_points(counters[key],steps) for key,steps in RULES.items()}
    raw_score=50+2+sum(breakdown.values())  # 2 = vitória futura por LP
    # Para drops Remaster X15: agrupamento das três bolsas confirmadas na ISO.
    band="Z-POW" if raw_score>=95 else "S-POW" if raw_score>=50 else "S-TEC"
    return {"score":raw_score,"category":band,"breakdown":breakdown,
            "model":"Remaster X15 — projeção se vencer por LP",
            "final":False}


def read_rank_candidate(*, preferred_pid=None, kernel=None, pids=None) -> dict:
    """Lê 2×32 bytes em processo ePSXe conhecido, sem modificar a memória."""
    if sys.platform!="win32" and kernel is None:
        return {"ready":False,"status":"RANK exige Windows/ePSXe","pid":None,"counters":None}
    kernel=kernel or _windows_kernel32()
    candidates=discover_epsxe_pids(kernel) if pids is None else list(pids)
    if not candidates:
        return {"ready":False,"status":"ePSXe não encontrado","pid":None,"counters":None}
    if preferred_pid is not None:
        if preferred_pid not in candidates:
            return {"ready":False,"status":"Processo ePSXe selecionado não encontrado",
                    "pid":None,"counters":None}
        pid=preferred_pid
    elif len(candidates)==1:
        pid=candidates[0]
    else:
        return {"ready":False,"status":"Há vários processos ePSXe abertos",
                "pid":None,"counters":None}
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
        return {"ready":False,"status":"Acesso de leitura à RAM negado",
                "pid":pid,"counters":None}
    try:
        def sample():
            buffer=ctypes.create_string_buffer(RECORD_BYTES)
            read=ctypes.c_size_t()
            ok=kernel.ReadProcessMemory(
                handle,ctypes.c_void_p(CANDIDATE_RANK_ADDRESS),
                buffer,RECORD_BYTES,ctypes.byref(read))
            if not ok or read.value!=RECORD_BYTES:
                return None
            return decode_rank_record(buffer.raw)
        a=sample()
        b=sample()
        if a is None or b!=a:
            return {"ready":False,"status":"RANK não validado ou em transição",
                    "pid":pid,"counters":None}
        return {"ready":True,"status":"Contadores candidatos detectados",
                "pid":pid,"counters":a}
    finally:
        kernel.CloseHandle(handle)
