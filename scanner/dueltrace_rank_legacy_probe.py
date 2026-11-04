"""Validação experimental do registro legado de RANK no ePSXe.

Observa apenas a estrutura já usada pelo Assistente X15; não varre memória,
não altera RAM e não declara compatibilidade de outra ISO por nome.
A primeira conferência é de LP; exigimos duas transições de contadores
plausíveis antes de mostrar o score como EXPERIMENTAL.
"""
from __future__ import annotations

from dueltrace_rank_live import RULES

REQUIRED = frozenset(RULES)
ACTION_FIELDS = REQUIRED - {"remaining_lp"}
MAX_ACTION_DELTA = 8


def classify_legacy_transition(previous: dict, current: dict) -> str:
    """Retorna stable/event/invalid. Nunca produz prova de binding RAM.

    Dois polls iguais são estabilidade, NÃO duas ações. Um salto incoerente
    de contador exige nova conferência LP em vez de pontuação enganosa.
    """
    if not isinstance(previous,dict) or not isinstance(current,dict):
        return "invalid"
    if set(previous)!=REQUIRED or set(current)!=REQUIRED:
        return "invalid"
    for key in REQUIRED:
        a,b=previous[key],current[key]
        if type(a) is not int or type(b) is not int or not 0<=a<=32766 or not 0<=b<=32766:
            return "invalid"
    changed=False
    for key in ACTION_FIELDS:
        delta=current[key]-previous[key]
        if delta<0 or delta>MAX_ACTION_DELTA or (
                key=="turns" and delta>2):
            return "invalid"
        if delta:
            changed=True
    lp_delta=current["remaining_lp"]-previous["remaining_lp"]
    if abs(lp_delta)>16000:
        return "invalid"
    if lp_delta:
        changed=True
    return "event" if changed else "stable"


def start_legacy_trial(sha: str, pid: int, counters: dict) -> dict:
    if type(sha) is not str or type(pid) is not int or pid<=0 or set(counters)!=REQUIRED:
        raise ValueError("Amostra experimental de RANK inválida.")
    return {
        "sha":sha,"pid":pid,
        "previous":dict(counters),
        "events":0,
        "confirmed":True,
    }


def update_legacy_trial(trial: dict, sha: str, pid: int, counters: dict) -> tuple[str,int]:
    """Avança somente após alterações reais em leituras sucessivas válidas."""
    if (not isinstance(trial,dict) or trial.get("sha")!=sha
            or trial.get("pid")!=pid or trial.get("confirmed") is not True):
        return "invalid",0
    outcome=classify_legacy_transition(trial.get("previous"),counters)
    if outcome=="invalid":
        return "invalid",0
    if outcome=="event":
        trial["events"]=min(2,trial.get("events",0)+1)
        trial["previous"]=dict(counters)
    return ("candidate" if trial["events"]>=2 else "observing"),trial["events"]
