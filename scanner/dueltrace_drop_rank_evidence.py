"""Auditoria de drops por RANK usando resultados observados no jogo.

Os três bancos do WA são verificáveis por pesos, mas sua correspondência a
Z-POW/S-POW/S-TEC varia por mod. Um resultado observado só ajuda a determinar
um grupo quando a carta não aparece nos outros grupos do MESMO oponente.
Observação manual nunca comprova sozinha a execução da rotina MIPS.
"""
from __future__ import annotations

from collections import defaultdict
from dueltrace_rank_drop_solver import solve_rank_drop_labels
from dueltrace_rank_system import (
    available_ranks, drop_pool_labels, pool_index_for_rank,
)

LABELS=("Z-POW","S-POW","S-TEC")
MAX_OBSERVATIONS=500


def rank_drop_report(profile: dict | None, observations: list | None) -> dict:
    empty={"status":"unavailable","observations":0,"usable":0,"ambiguous":0,
           "inconsistent":0,"rankMappings":{},"suspectedMappings":{},"lastDuelId":None,
           "mappingHypotheses":[],"possibleGroups":{},"assignmentCount":0,
           "mappingConsistency":"insufficient_evidence",
           "mismatches":[],"scoreComparisons":{"compared":0,"exact":0,"different":0,
                      "status":"sem_comparacao_independente"},
           "note":"As tabelas e os RANKs ainda não foram correlacionados com duelos reais."}
    if not isinstance(profile,dict):
        return empty
    from dueltrace_drops import get_drop_catalog
    catalog=get_drop_catalog(profile,limit=1)
    if not catalog["available"]:
        return empty
    groups=catalog["groups"]
    sha=profile.get("rom_sha256")
    rank_labels=available_ranks(sha)
    pool_names=drop_pool_labels(sha)
    rank_to_pool={rank:pool_names[pool_index_for_rank(sha,rank)]
                  for rank in rank_labels}
    drops=profile.get("drops",[])
    by_opp=defaultdict(lambda:defaultdict(set))
    for d in drops:
        if isinstance(d,dict) and type(d.get("opponent_id")) is int and type(d.get("card_id")) is int and d.get("group") in groups and type(d.get("weight")) is int and d["weight"]>0:
            by_opp[d["opponent_id"]][d["group"]].add(d["card_id"])
    obs=observations if isinstance(observations,list) else []
    obs=obs[-MAX_OBSERVATIONS:]
    unique=set()
    last_duel_id=None
    candidate=defaultdict(list)
    conflicts=[]
    ambiguous=0
    score_compared=0
    score_exact=0
    known=bool(catalog.get("rankLabelsVerified"))
    for row in obs:
        if not isinstance(row,dict) or row.get("rom_sha256")!=profile.get("rom_sha256"):
            continue
        oid,cid,label,duel=(row.get("opponent_id"),row.get("card_id"),
                            row.get("observed_rank"),row.get("duel_id"))
        if (type(oid) is not int or type(cid) is not int or label not in rank_labels
                or type(duel) is not str or not 8<=len(duel)<=100
                or not 1<=oid<=39 or not 1<=cid<=722):
            continue
        if duel in unique:
            continue
        unique.add(duel)
        last_duel_id=duel
        snap=row.get("rank_snapshot")
        points=row.get("observed_points")
        if (row.get("victory_type")=="lp" and type(points) is int
                and isinstance(snap,dict) and type(snap.get("projected_score")) is int
                and type(snap.get("projected_rank")) is str):
            score_compared+=1
            if snap["projected_score"]==points and snap["projected_rank"]==label:
                score_exact+=1
        possible=[g for g in groups if cid in by_opp[oid][g]]
        pool=rank_to_pool[label]
        if not possible:
            conflicts.append({"duelId":duel,"rank":label,
                              "opponentId":oid,"cardId":cid,
                              "reason":"Carta não consta em nenhuma das três tabelas deste oponente"})
            continue
        if known:
            expected=groups[pool_index_for_rank(sha,label)]
            if expected not in possible:
                conflicts.append({"duelId":duel,"rank":label,
                                  "opponentId":oid,"cardId":cid,
                                  "reason":"Drop não consta da tabela do RANK informado"})
            else:
                candidate[pool].append((duel,oid,pool))
        elif len(possible)==1:
            candidate[pool].append((duel,oid,possible[0]))
        else:
            ambiguous+=1
    solver=solve_rank_drop_labels(
        groups,by_opp,obs,sha,labels=list(pool_names),
        rank_to_label=rank_to_pool)
    inferred={
        rank:{**evidence,
              "groupDisplay":pool_names[groups.index(evidence["group"])]}
        for rank,evidence in solver["supportedMappings"].items()
    }
    # Os três bancos formam uma permutação bijetiva; nunca atribuir dois
    # RANKs ao mesmo banco nem tratar um único drop como prova definitiva.
    known_conflict=bool(conflicts)
    if solver["contradictions"]:
        conflicts.extend(solver["contradictions"])
    if known and known_conflict:
        inferred={}

    return {
        **empty,"status":("mismatch" if conflicts else
                          "manual_corroboration" if inferred else "needs_more_duels"),
        "observations":len(unique),"lastDuelId":last_duel_id,
        "usable":sum(len(x) for x in candidate.values()),
        "ambiguous":ambiguous,"inconsistent":len(conflicts),
        "mappingHypotheses":([{pool_names[i]:groups[i] for i in range(3)}]
                              if known and not conflicts else solver["candidateAssignments"]),
        "possibleGroups":({pool_names[i]:[groups[i]] for i in range(3)}
                          if known and not conflicts else solver["possibleGroups"]),
        "assignmentCount":(1 if known and not conflicts
                           else solver["consistentAssignments"]),
        "mappingConsistency":("identidade_sha_conhecida" if known and not conflicts
                              else "inconsistent_known_mapping" if known and conflicts
                              else solver["status"]),
        "rankMappings":{
            rank:{"group":groups[pool_index_for_rank(sha,rank)],
                  "status":("identidade_iso_conhecida" if known
                            else "layout_original_presumido")}
            for rank in rank_labels
        },
        "suspectedMappings":({} if known else inferred),
        "mismatches":conflicts[:20],
        "scoreComparisons":{
            "compared":score_compared,"exact":score_exact,
            "different":score_compared-score_exact,
            "status":("duelos_coerentes_sem_prova_mips"
                      if score_compared>=2 and score_compared==score_exact else
                      "divergencia_modelo" if score_compared>score_exact else
                      "amostra_insuficiente"),
        },
        "note":("Mapeamentos sugeridos por registros fornecidos pelo jogador "
                "não substituem confirmação por rastros MIPS e resultados "
                "capturados no ePSXe. Pesos WA são verificados independentemente."),
    }
