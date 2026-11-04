"""Calculadora manual de SPOILS, independente do mapeamento RAM.

Reaproveita integralmente a tabela de dez critérios extraída da ISO Remaster X15
(29/10/2026) e o cálculo legado base 50 + ajuste de vitória + critérios.
Os dados manuais não constituem prova da rotina MIPS do mod selecionado.
"""
from __future__ import annotations

from dueltrace_rank_live import RULES, _points
from dueltrace_rank_system import rank_label_for_existing_score, rank_system

VICTORY_BONUSES = {"lp":2, "deckout":-40, "exodia":40}
BASE_SCORE = 50


def calculate_manual_spoils(counters: dict, victory: str, rom_sha256: str | None) -> dict:
    if not isinstance(counters,dict) or set(counters)!=set(RULES):
        raise ValueError("Informe os dez critérios do SPOILS.")
    if victory not in VICTORY_BONUSES or type(victory) is not str:
        raise ValueError("Resultado do duelo inválido.")
    for name,value in counters.items():
        maximum = 32766 if name=="remaining_lp" else 255
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError("Critério de SPOILS fora do intervalo permitido.")
    breakdown={name:_points(counters[name],limits) for name,limits in RULES.items()}
    victory_bonus=VICTORY_BONUSES[victory]
    score=BASE_SCORE+victory_bonus+sum(breakdown.values())
    return {
        "score":score,
        "category":rank_label_for_existing_score(rom_sha256,score),
        "rankSystem":rank_system(rom_sha256),
        "basePoints":BASE_SCORE,
        "victoryBonus":victory_bonus,
        "victory":victory,
        "breakdown":breakdown,
        "source":"manual_x15_spoils_table",
        "verifiedInEmulator":False,
        "note":(
            "Estimativa manual com a tabela SPOILS extraída do Remaster X15. "
            "A classificação é exibida de acordo com a ISO selecionada. "
            "O uso da mesma tabela numérica em mods diferentes ainda exige "
            "validação contra os resultados reais do ePSXe."
        ),
    }
