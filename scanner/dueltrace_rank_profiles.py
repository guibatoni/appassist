"""Registro conservador dos pontos de RANK por ISO verificada.

O modelo X15 foi estabelecido e testado previamente. Sem um decodificador
de instruções MIPS calibrado para cada mod, não atribuímos fórmulas do
Remaster X15 a outro executável SLUS por mera semelhança.
"""
from __future__ import annotations

from dueltrace_rank_live import RULES
from scanner_multiiso import X15_SHA


def rank_profile_for_image(rom_sha256: str) -> dict:
    if not isinstance(rom_sha256, str) or rom_sha256.casefold() != X15_SHA:
        return {
            "available": False,
            "status": "regras_nao_decodificadas_do_executavel",
            "source": "DATA/SLUS_014.11",
            "rules": {},
            "base_points": None,
            "lp_victory_bonus": None,
            "final_rank": False,
            "note": "Este mod precisa de investigação específica das rotinas MIPS. "
                    "Não utilizar os pontos do Remaster X15."
        }
    return {
        "available": True,
        "status": "modelo_validado_para_sha_exato",
        "source": "SLUS_014.11; modelo previamente validado apenas para ISO SHA X15",
        "rules": {
            key: [{"below": threshold, "points": points}
                  for threshold, points in steps]
            for key, steps in RULES.items()
        },
        "base_points": 50,
        "lp_victory_bonus": 2,
        "final_rank": False,
        "note": "Pontuação de referência reconhecida automaticamente pela "
                "assinatura exata da ISO. Não implica extração universal das "
                "instruções MIPS nem confirma a RAM durante o duelo."
    }
