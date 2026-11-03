"""Registro conservador dos pontos de RANK por ISO verificada.

O modelo X15 foi estabelecido e testado previamente. Sem um decodificador
de instruções MIPS calibrado para cada mod, não atribuímos fórmulas do
Remaster X15 a outro executável SLUS por mera semelhança.
"""
from __future__ import annotations

from dueltrace_rank_live import RULES
from scanner_multiiso import X15_SHA


def rank_profile_for_image(rom_sha256: str, analysis: dict | None = None) -> dict:
    """Nunca extrapola regras ou rótulos de outro mod.

    Ausência de relatório = compatibilidade com perfis antigos. Um relatório
    novo explicitamente inválido sempre tem precedência e impede fallback.
    """
    if analysis is not None:
        if not isinstance(analysis, dict) or not analysis.get("available"):
            return {
                "available": False,
                "runtime_verified": False,
                "status": (analysis.get("status","invalido")
                           if isinstance(analysis,dict) else "invalido"),
                "source": "DATA/WA_MRG.MRG",
                "rules": {}, "base_points": None,
                "lp_victory_bonus": None, "final_rank": False,
                "note": "Não foi possível validar a tabela do WA nesta ISO."
            }
        verified=(analysis.get("runtime_verified") is True
                  and isinstance(rom_sha256,str)
                  and rom_sha256.casefold()==X15_SHA
                  and analysis.get("status")=="known_x15_verified_binary")
        return {
            "available": True,
            "runtime_verified": verified,
            "status": ("modelo_validado_para_sha_exato" if verified else
                       "tabela_wa_extraida_execucao_nao_confirmada"),
            "source":analysis.get("source","DATA/WA_MRG.MRG"),
            "rules":analysis.get("rules",{}),
            "base_points":analysis.get("base_points") if verified else None,
            "lp_victory_bonus":analysis.get("lp_victory_bonus") if verified else None,
            "criterion_names_verified": verified,
            "table_sha256":analysis.get("table_sha256"),
            "table_count":analysis.get("table_count",0),
            "final_rank": False,
            "note":analysis.get("note","Regras ainda não verificadas no jogo."),
        }
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
