"""Auditoria de drops por RANK usando resultados observados no jogo.

Os três bancos do WA são verificáveis por pesos, mas sua correspondência a
Z-POW/S-POW/S-TEC varia por mod. Um resultado observado só ajuda a determinar
um grupo quando a carta não aparece nos outros grupos do MESMO oponente.
Observação manual nunca comprova sozinha a execução da rotina MIPS.
"""
from __future__ import annotations

from collections import defaultdict

LABELS=("Z-POW","S-POW","S-TEC")
MAX_OBSERVATIONS=500


def rank_drop_report(profile: dict | None, observations: list | None) -> dict:
    empty={"status":"unavailable","observations":0,"usable":0,"ambiguous":0,
           "inconsistent":0,"rankMappings":{},"suspectedMappings":{},
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
    drops=profile.get("drops",[])
    by_opp=defaultdict(lambda:defaultdict(set))
    for d in drops:
        if isinstance(d,dict) and type(d.get("opponent_id")) is int and type(d.get("card_id")) is int and d.get("group") in groups and type(d.get("weight")) is int and d["weight"]>0:
            by_opp[d["opponent_id"]][d["group"]].add(d["card_id"])
    obs=observations if isinstance(observations,list) else []
    obs=obs[-MAX_OBSERVATIONS:]
    unique=set()
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
        if (type(oid) is not int or type(cid) is not int or label not in LABELS
                or type(duel) is not str or not 8<=len(duel)<=100
                or not 1<=oid<=39 or not 1<=cid<=722):
            continue
        if duel in unique:
            continue
        unique.add(duel)
        snap=row.get("rank_snapshot")
        points=row.get("observed_points")
        if (row.get("victory_type")=="lp" and type(points) is int
                and isinstance(snap,dict) and type(snap.get("projected_score")) is int
                and type(snap.get("projected_rank")) is str):
            score_compared+=1
            if snap["projected_score"]==points and snap["projected_rank"]==label:
                score_exact+=1
        possible=[g for g in groups if cid in by_opp[oid][g]]
        if not possible:
            conflicts.append({"duelId":duel,"rank":label,
                              "opponentId":oid,"cardId":cid,
                              "reason":"Carta não consta em nenhuma das três tabelas deste oponente"})
            continue
        if known:
            if label not in possible:
                conflicts.append({"duelId":duel,"rank":label,
                                  "opponentId":oid,"cardId":cid,
                                  "reason":"Drop não consta da tabela do RANK informado"})
            else:
                candidate[label].append((duel,oid,label))
        elif len(possible)==1:
            candidate[label].append((duel,oid,possible[0]))
        else:
            ambiguous+=1
    inferred={}
    for label,rows in candidate.items():
        distinct={item[2] for item in rows}
        if len(distinct)==1 and len(rows)>=2 and len({r[1] for r in rows})>=2:
            inferred[label]={"group":next(iter(distinct)),
                             "observations":len(rows),
                             "opponents":len({r[1] for r in rows}),
                             "status":"corroborado_manualmente"}
        elif len(distinct)>1:
            conflicts.append({"rank":label,
                              "reason":"Observações discriminantes apontam para bancos incompatíveis"})
    if len({v["group"] for v in inferred.values()}) != len(inferred):
        conflicts.append({"reason":"RANKs diferentes apontam para a mesma tabela"})
        inferred={}
    return {
        **empty,"status":("mismatch" if conflicts else
                          "manual_corroboration" if inferred else "needs_more_duels"),
        "observations":len(unique),
        "usable":sum(len(x) for x in candidate.values()),
        "ambiguous":ambiguous,"inconsistent":len(conflicts),
        "rankMappings":({x:{"group":x,"status":"identidade_iso_conhecida"}
                         for x in LABELS} if known else {}),
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
