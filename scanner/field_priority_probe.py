"""Revisão de dois endereços de RAM, sem validar ocupação do campo.

Avalia somente valores pontuais em capturas já feitas, nunca identifica cartas.
"""
from __future__ import annotations

from field_cancel_probe import _get_byte

PRIORITY_ADDRESSES = (0xC393FA, 0xC39822)
REAL_PHASES = ("before", "prepared", "set", "occupied_control", "removed", "vacant_control")


def analyze_priority(phases: dict) -> dict:
    """Classifica comportamento observável, não prova identidade de um slot."""
    is_no_action = "no_action" in phases
    names = ("before", "no_action") if is_no_action else REAL_PHASES
    results = []
    for address in PRIORITY_ADDRESSES:
        values = {
            name: _get_byte(phases[name], address)
            if isinstance(phases.get(name), dict) else None
            for name in names
        }
        b = values["before"]
        if is_no_action:
            n = values["no_action"]
            state = ("LEITURA_INCOMPLETA" if b is None or n is None
                     else "MUDOU_SEM_ACAO" if b != n else "ESTAVEL_SEM_ACAO")
        else:
            p, s, o, r, v = (values[k] for k in REAL_PHASES[1:])
            if b is None or s is None:
                state = "LEITURA_INCOMPLETA"
            elif p is not None and p != b:
                state = "MUDOU_NA_PREPARACAO"
            elif s == b:
                state = "SEM_MUDANCA_NA_COLOCACAO"
            elif o is not None and o != s:
                state = "INSTAVEL_DURANTE_OCUPADA"
            elif r is not None and r == s:
                state = "PERSISTE_APOS_REMOVIDA"
            elif r is not None and r != b:
                state = "NAO_RETORNOU_AO_INICIO"
            elif r is not None and v is not None and v != r:
                state = "INSTAVEL_DURANTE_VAZIA"
            elif p is None or o is None or r is None or v is None:
                state = "FALTAM_CONTROLES"
            else:
                state = "PADRAO_REVERSIVEL_PARA_RETESTE"
        results.append({
            "address": f"0x{address:08X}",
            "values_u8": values,
            "status": state,
            "field_slot_verified": False,
            "occupancy_verified": False,
        })
    return {
        "scope": "DOIS_CANDIDATOS_HISTORICOS_NAO_VALIDADOS",
        "experiment": "SEM_ACAO" if is_no_action else "INVOCACAO_OBSERVADA",
        "candidates": results,
        "field_slot_verified": False,
        "occupancy_verified": False,
    }
