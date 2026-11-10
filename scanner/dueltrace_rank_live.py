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
    HAND_ADDRESS, _PID_HAND_ADDRESS_CACHE,
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
    # Mesmos filtros de plausibilidade do Assistente X15 v10.5.
    if not 0<=lp<=32766 or not 0<=cards_used<=40:
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
    # Apenas leituras coerentes com uma estrutura de duelo real.
    # Esses limites filtram RAM não inicializada, mas NÃO validam endereço.
    if fields["turns"]>80 or any(fields[name]>60 for name in (
            "effective_attacks","defense_wins","face_down","spells",
            "traps","fusions","equips")):
        return None
    if lp==0 and not any(fields[name] for name in (
            "turns","fusions","effective_attacks","face_down","cards_used")):
        return None
    return fields


def decode_rank_result_adjustment(raw: bytes) -> int | None:
    """Resultado assinado do X15 v10.5, byte +0 do registro de 32 bytes.

    0x02 = +2 vitória por LP; 0xD8 = -40 vitória por deck-out.
    Zero e quaisquer outros valores NÃO comprovam resultado. O leitor deve
    obter duas amostras estáveis e a ISO deve ser a X15 exata antes de usar.
    """
    if not isinstance(raw,bytes) or len(raw)!=RECORD_BYTES:
        return None
    marker=int.from_bytes(raw[:1],"little",signed=True)
    return marker if marker in (2,-40) else None


def project_spoils_with_adjustment(counters: dict, adjustment: int) -> dict:
    """Aplica o bônus decodificado X15 sem mudar nenhuma das dez tabelas.

    O nome da classificação neste núcleo é X15; a bridge aplica a
    classificação da ISO ativa antes de qualquer exibição na interface.
    """
    if set(counters)!=set(RULES):
        raise ValueError("Contadores do RANK incompletos.")
    if any(type(x) is not int or x<0 for x in counters.values()):
        raise ValueError("Contador inválido.")
    if type(adjustment) is not int or adjustment not in (2,-40,40):
        raise ValueError("Bônus de vitória não comprovado na tabela X15.")
    breakdown={key:_points(counters[key],steps) for key,steps in RULES.items()}
    raw_score=50+adjustment+sum(breakdown.values())
    band="Z-POW" if raw_score>=95 else "S-POW" if raw_score>=50 else "S-TEC"
    return {"score":raw_score,"category":band,"breakdown":breakdown,
            "victory_bonus":adjustment,
            "model":"Remaster X15 — soma por tabela extraída da ISO",
            "final":False}


def project_lp_win_rank(counters: dict) -> dict:
    """Mantém a previsão LP legado; não interpreta resultado não confirmado."""
    result=project_spoils_with_adjustment(counters,2)
    result["model"]="Remaster X15 — projeção se vencer por LP"
    return result


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
        # This is a candidate X15-only record, not a proven generic mod binding.
        # Translate its PS1-relative displacement only after the five-card hand
        # was independently validated in THIS running ePSXe process.
        known_hand=_PID_HAND_ADDRESS_CACHE.get(pid)
        candidate_address=CANDIDATE_RANK_ADDRESS
        if (type(known_hand) is int and known_hand>=HAND_ADDRESS):
            candidate_address=CANDIDATE_RANK_ADDRESS+(known_hand-HAND_ADDRESS)
        elif type(known_hand) is int and known_hand>=0x10000:
            candidate_address=CANDIDATE_RANK_ADDRESS+(known_hand-HAND_ADDRESS)
        if not 0x10000<=candidate_address<0x7FFFFFFEFFFF:
            return {"ready":False,"status":"Endereço de RANK fora da RAM reconhecida",
                    "pid":pid,"counters":None}
        def sample():
            buffer=ctypes.create_string_buffer(RECORD_BYTES)
            read=ctypes.c_size_t()
            ok=kernel.ReadProcessMemory(
                handle,ctypes.c_void_p(candidate_address),
                buffer,RECORD_BYTES,ctypes.byref(read))
            if not ok or read.value!=RECORD_BYTES:
                return None
            counters=decode_rank_record(buffer.raw)
            if counters is None:
                return None
            return counters,decode_rank_result_adjustment(buffer.raw)
        a=sample()
        b=sample()
        if a is None or b!=a:
            return {"ready":False,"status":"RANK não validado ou em transição",
                    "pid":pid,"counters":None}
        return {"ready":True,"status":"Contadores candidatos detectados",
                "pid":pid,"counters":a[0],"result_adjustment":a[1]}
    finally:
        kernel.CloseHandle(handle)


def read_rank_from_verified_binding(binding: dict, *, preferred_pid=None,
                                    kernel=None, pids=None) -> dict:
    """Lê endereço HOST do ePSXe, somente se o binding foi validado por SHA.

    A validação integral do binding deve ser feita pelo chamador com o
    perfil ativo. Não confundir endereços MIPS com endereços do ePSXe.
    """
    from dueltrace_rank_profile_live import read_counters_from_record
    if not isinstance(binding, dict):
        raise ValueError("Binding de mod inválido.")
    addr=binding.get("record_address")
    size=binding.get("record_length")
    if (type(addr) is not int or not 0x10000 <= addr <= 0xFFFFFFFF
            or type(size) is not int or not 28 <= size <= 256):
        raise ValueError("Endereço host ou tamanho de registro inválido.")
    if sys.platform != "win32" and kernel is None:
        return {"ready":False, "status":"RANK exige Windows/ePSXe",
                "pid":None, "counters":None}
    kernel=kernel or _windows_kernel32()
    candidates=discover_epsxe_pids(kernel) if pids is None else list(pids)
    if preferred_pid is not None:
        if preferred_pid not in candidates:
            return {"ready":False,"status":"ePSXe selecionado não encontrado",
                    "pid":None,"counters":None}
        pid=preferred_pid
    elif len(candidates)==1:
        pid=candidates[0]
    else:
        return {"ready":False,
                "status":"ePSXe não encontrado ou múltiplos processos",
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
        return {"ready":False,"status":"Leitura RAM bloqueada",
                "pid":pid,"counters":None}
    try:
        def sample():
            out=ctypes.create_string_buffer(size)
            n=ctypes.c_size_t()
            ok=kernel.ReadProcessMemory(handle,ctypes.c_void_p(addr),out,
                                        size,ctypes.byref(n))
            if not ok or n.value!=size:
                return None
            try:
                return read_counters_from_record(out.raw,binding)
            except (ValueError,KeyError,TypeError):
                return None
        a=sample()
        b=sample()
        if a is None or b!=a:
            return {"ready":False,"status":"Amostras RAM instáveis ou inválidas",
                    "pid":pid,"counters":None}
        return {"ready":True,"status":"Contadores de mod lidos (em calibração)",
                "pid":pid,"counters":a}
    finally:
        kernel.CloseHandle(handle)
