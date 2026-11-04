"""Diagnóstico sem RAM para entender por que RANK ao vivo está bloqueado.

Este módulo não executa MIPS, não recalcula pontos e não autoriza novos mods.
Uma tabela WA reconhecida e PCs candidatos não bastam para capturar RANK.
"""
from __future__ import annotations

import re

from dueltrace_rank_live import model_available
from dueltrace_rank_profile_live import (
    validate_live_rank_binding, x15_compatible_runtime,
)
from dueltrace_rank_system import rank_system


def diagnose_rank_profile(sha: str | None, profile: dict | None) -> dict:
    valid_sha = type(sha) is str and bool(re.fullmatch("[0-9a-f]{64}",sha))
    info = profile.get("rank_points") if isinstance(profile,dict) else None
    info = info if isinstance(info,dict) else {}
    evidence = profile.get("rank_mips_evidence") if isinstance(profile,dict) else None
    evidence = evidence if isinstance(evidence,dict) else {}
    candidates = evidence.get("candidates")
    candidate_count = min(1000,len(candidates)) if isinstance(candidates,list) else 0
    binding_present = (isinstance(profile,dict)
                       and isinstance(profile.get("rank_runtime_binding"),dict))
    profile_matches = bool(valid_sha and isinstance(profile,dict)
                           and profile.get("rom_sha256") == sha)
    binding_valid = bool(profile_matches and validate_live_rank_binding(profile) is not None)
    x15_exact = bool(profile_matches and model_available(sha))
    binary_match = bool(profile_matches and x15_compatible_runtime(profile))
    ready = x15_exact or binding_valid
    table_detected = info.get("available") is True
    structure_verified = info.get("structure_verified") is True

    if not valid_sha or not isinstance(profile,dict):
        code,reason,action = (
            "no_active_iso",
            "Nenhuma ISO ativa com perfil local foi identificada.",
            "Abra Biblioteca de Mods, importe e selecione uma ISO."
        )
    elif not profile_matches:
        code,reason,action = (
            "profile_sha_mismatch",
            "O perfil não corresponde ao SHA-256 da ISO selecionada.",
            "Reimporte a ISO e selecione o perfil correspondente antes de ler a RAM."
        )
    elif x15_exact:
        code,reason,action = (
            "known_x15_sha",
            "Hash da ISO Remaster X15 reconhecido. O modelo pode ser testado no ePSXe.",
            "Abra um duelo, confirme os LP exibidos no jogo e confira a leitura."
        )
    elif binding_valid:
        code,reason,action = (
            "verified_ram_binding",
            "Esta combinação ISO/SLUS/tabela possui vínculo RAM previamente validado.",
            "Abra um duelo e confirme os LP exatos antes de capturar a previsão."
        )
    elif binary_match:
        code,reason,action = (
            "runtime_binding_required",
            "SLUS e tabela são idênticos ao X15, mas a ISO não possui vínculo RAM validado.",
            "Valide o mapeamento específico desta ISO em duelos independentes; "
            "a igualdade de arquivos não autoriza um endereço RAM presumido."
        )
    elif not table_detected:
        code,reason,action = (
            "rank_table_missing",
            "A tabela de pontos RANK não foi reconhecida no perfil desta ISO.",
            "Extraia as regras e valide o mapeamento RAM específico desta ISO. "
            "Use a calculadora manual enquanto a leitura automática estiver bloqueada."
        )
    elif binding_present:
        code,reason,action = (
            "ram_binding_unverified",
            "Há dados de vínculo RAM, mas eles não passaram as validações da ISO.",
            "Confira os hashes da ISO, SLUS e tabela e as evidências de duelos "
            "independentes. Não reutilize endereços de outros mods."
        )
    elif candidate_count > 0:
        code,reason,action = (
            "mips_candidates_only",
            "A tabela e candidatos MIPS foram localizados, porém não existe "
            "mapeamento RAM validado por duelos reais.",
            "Valide a rotina e os contadores em duelos independentes. "
            "Candidatos estáticos não autorizam leitura automática da RAM."
        )
    else:
        code,reason,action = (
            "ram_binding_missing",
            "A tabela RANK foi encontrada, mas não há mapeamento da RAM "
            "e rotina de execução comprovados para este mod.",
            "Valide o mapeamento específico da ISO em duelos independentes. "
            "Não reutilize endereços de outros mods."
        )
    return {
        "readyForLiveRead":bool(ready),
        "code":code,
        "reason":reason,
        "nextStep":action,
        "isoShaPrefix":sha[:12] if valid_sha else None,
        "rankSystem":rank_system(sha) if valid_sha else None,
        "rankTableDetected":table_detected,
        "rankStructureVerified":structure_verified,
        "mipsCandidates":candidate_count,
        "ramBindingPresent":bool(binding_present),
        "ramBindingVerified":bool(binding_valid),
        "x15Exact":x15_exact,
        "x15CompatibleBinary":binary_match,
        "mipsRuntimeConfirmed":False,
        "legacyProbeAvailable":False,
        "score":None,
        "projectedRank":None,
        "note":"Diagnóstico estático e local, sem leitura RAM ou desbloqueio de projeções.",

    }
