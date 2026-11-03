"""Relatório portátil, somente de evidências NUMÉRICAS, sem dados da ROM.

O JSON pode ser compartilhado para auditoria: omite ISO/BIN/SLUS/WA,
caminhos locais, nome de usuário, gravações de RAM e logs brutos.
Um hash de conteúdo prova apenas integridade do JSON, NÃO autenticidade
dos resultados manualmente informados pelo jogador.
"""
from __future__ import annotations

import hashlib
import json

MAX_DUELS=500
MAX_TRACES=50


def build_rank_evidence_report(profile: dict, observations: list,
                               trace_records: list, drop_report: dict) -> dict:
    if not isinstance(profile,dict) or not isinstance(drop_report,dict):
        raise ValueError("Perfil de mod inválido")
    sha=profile.get("rom_sha256")
    if not isinstance(sha,str) or len(sha)!=64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise ValueError("SHA da imagem inválido")
    ranks=profile.get("rank_points",{})
    mips=profile.get("rank_mips_evidence",{})
    safe_duels=[]
    for row in observations[-MAX_DUELS:] if isinstance(observations,list) else []:
        if not isinstance(row,dict) or row.get("rom_sha256")!=sha:
            continue
        snap=row.get("rank_snapshot",{})
        safe_duels.append({
            "duel_id":row.get("duel_id") if isinstance(row.get("duel_id"),str) else None,
            "opponent_id":row.get("opponent_id"),
            "card_id":row.get("card_id"),
            "observed_rank":row.get("observed_rank"),
            "observed_points":row.get("observed_points"),
            "victory_type":row.get("victory_type"),
            "projected_score":snap.get("projected_score") if isinstance(snap,dict) else None,
            "projected_rank":snap.get("projected_rank") if isinstance(snap,dict) else None,
            "source":"manual_game_observation",
        })
    safe_traces=[]
    for row in trace_records[-MAX_TRACES:] if isinstance(trace_records,list) else []:
        if not isinstance(row,dict):
            continue
        table=row.get("rankTableEvidence",{})
        safe_traces.append({
            "duel_id":row.get("duel_id"),
            "trace_sha256":row.get("traceSha256"),
            "candidate_pcs_executed":[
                {"pc":x.get("pc"),"hits":x.get("hits")}
                for x in row.get("executedCandidates",[])[:20]
                if isinstance(x,dict)],
            "execution_evidence":row.get("executionEvidence") is True,
            "wa_table_reads_observed":isinstance(table,dict) and table.get("tableReadsObserved") is True,
            "wa_matched_pairs":table.get("matchedPairs",0) if isinstance(table,dict) else 0,
            "rank_routine_confirmed":False,
        })
    safe_rules={}
    if isinstance(ranks,dict) and isinstance(ranks.get("rules"),dict):
        for key,bands in ranks["rules"].items():
            if isinstance(key,str) and len(key)<=64 and isinstance(bands,list):
                safe_rules[key]=[
                    {"below":x.get("below"),"points":x.get("points")}
                    for x in bands[:12] if isinstance(x,dict)
                ]
    report={
        "schema":"DUELTRACE-RANK-EVIDENCE-1",
        "rom_sha256":sha,
        "slus_sha256":profile.get("exe_sha256"),
        "wa_sha256":profile.get("wa_sha256"),
        "drop_tables_validated":profile.get("drops_provenance",{}).get("table_count",0),
        "drop_rank_mappings":{
            "status":drop_report.get("mappingConsistency"),
            "candidate_count":drop_report.get("assignmentCount"),
            "candidate_assignments":drop_report.get("mappingHypotheses",[]),
            "supported_mappings":drop_report.get("suspectedMappings",{}),
            "mismatches":drop_report.get("mismatches",[])[:20],
        },
        "rank_table":{
            "source":"WA_MRG.MRG","sha256":ranks.get("table_sha256") if isinstance(ranks,dict) else None,
            "offset":ranks.get("first_offset") if isinstance(ranks,dict) else None,
            "stride":ranks.get("repeat_stride") if isinstance(ranks,dict) else None,
            "structure_verified":ranks.get("structure_verified") is True if isinstance(ranks,dict) else False,
            "rules":safe_rules,
        },
        "mips":{
            "slus_scan_status":mips.get("status") if isinstance(mips,dict) else None,
            "candidate_pcs":[x.get("pc") for x in mips.get("candidates",[])[:20]
                             if isinstance(x,dict)] if isinstance(mips,dict) else [],
            "rank_routine_confirmed":False,
        },
        "duels":safe_duels,
        "traces":safe_traces,
        "disclaimer":(
            "Relatório offline. Duelo observado manualmente e log de depurador "
            "não têm autenticidade criptográfica de origem. "
            "A correlação entre PCs e valores WA não prova cálculo causal "
            "de RANK até análise dinâmica completa e confirmação no ePSXe."
        ),
    }
    digest=hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,
                                     separators=(",",":")).encode("utf-8")).hexdigest()
    return {**report,"report_sha256":digest}
