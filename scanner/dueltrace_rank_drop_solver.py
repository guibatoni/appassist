"""Inferência exaustiva e conservadora da correspondência RANK ↔ banco WA.

Três bancos, três classes: no máximo 3! = 6 permutações. Cada resultado
observado elimina apenas bancos que NÃO poderiam produzir sua carta.
Nenhum duelo observado permite afirmar o algoritmo MIPS do emulador.
"""
from __future__ import annotations

from itertools import permutations

LABELS = ("Z-POW", "S-POW", "S-TEC")
MAX_DUELS = 500


def solve_rank_drop_labels(groups, by_opponent, observations, iso_sha,
                           *, min_distinct_opponents=2, labels=LABELS,
                           rank_to_label=None):
    result={
        "status":"insufficient_evidence",
        "consistentAssignments":0,
        "candidateAssignments":[],
        "possibleGroups":{},
        "supportedMappings":{},
        "contradictions":[],
        "ambiguousDrops":0,
        "distinctDuels":0,
        "evidenceByRank":{},
        "method":"exact_exhaustive_assignment",
        "executionVerified":False,
    }
    if (not isinstance(labels,(tuple,list)) or len(labels)!=3
            or len(set(labels))!=3
            or not all(type(x) is str and x for x in labels)
            or (rank_to_label is not None and
                (not isinstance(rank_to_label,dict)
                 or not all(v in labels for v in rank_to_label.values())))
            or not isinstance(groups,list) or len(groups)!=3
            or len(set(groups))!=3
            or not all(type(x) is str and x for x in groups)
            or not isinstance(by_opponent,dict)
            or type(iso_sha) is not str or len(iso_sha)!=64):
        return result
    obs=observations if isinstance(observations,list) else []
    possibilities={label:set(groups) for label in labels}
    by_rank={label:{"duels":set(),"opponents":set()} for label in labels}
    seen={}
    contradictions=[]
    ambiguous=0
    for item in obs[-MAX_DUELS:]:
        if not isinstance(item,dict) or item.get("rom_sha256")!=iso_sha:
            continue
        duel=item.get("duel_id")
        oid=item.get("opponent_id")
        cid=item.get("card_id")
        rank=item.get("observed_rank")
        label=(rank_to_label.get(rank) if rank_to_label is not None else rank)
        if (type(duel) is not str or not 8<=len(duel)<=100
                or type(oid) is not int or not 1<=oid<=39
                or type(cid) is not int or not 1<=cid<=722
                or label not in labels):
            continue
        identity=(oid,cid,rank)
        if duel in seen:
            if seen[duel]!=identity:
                contradictions.append({"duelId":duel,"reason":"Mesmo duelo possui resultados conflitantes"})
            continue
        seen[duel]=identity
        present={group for group in groups if cid in by_opponent.get(oid,{}).get(group,set())}
        by_rank[label]["duels"].add(duel)
        by_rank[label]["opponents"].add(oid)
        if not present:
            contradictions.append({"duelId":duel,"opponentId":oid,
                                   "cardId":cid,"rank":rank,
                                   "reason":"Carta ausente dos três bancos WA deste oponente"})
            continue
        if len(present)>1:
            ambiguous+=1
        possibilities[label].intersection_update(present)
    valid=[]
    for permutation in permutations(groups):
        candidate=dict(zip(labels,permutation))
        if all(candidate[rank] in possibilities[rank] for rank in labels):
            valid.append(candidate)
    inferred={}
    for rank in labels:
        possible={item[rank] for item in valid}
        if (len(possible)==1 and len(by_rank[rank]["duels"])>=2
                and len(by_rank[rank]["opponents"])>=min_distinct_opponents
                and not contradictions):
            inferred[rank]={
                "group":next(iter(possible)),
                "observations":len(by_rank[rank]["duels"]),
                "opponents":len(by_rank[rank]["opponents"]),
                "status":"corroborado_manualmente",
            }
    if not valid and seen:
        contradictions.append({"reason":"Nenhuma associação bijetiva entre os 3 RANKs e os 3 bancos é compatível com os duelos registrados"})
    return {
        **result,
        "status":("inconsistent" if contradictions else
                  "corroborated" if inferred else
                  "underdetermined"),
        "consistentAssignments":len(valid),
        "candidateAssignments":valid[:6],
        "possibleGroups":{rank:sorted({p[rank] for p in valid})
                          for rank in labels},
        "supportedMappings":inferred,
        "contradictions":contradictions[:20],
        "ambiguousDrops":ambiguous,
        "distinctDuels":len(seen),
        "evidenceByRank":{k:{"duels":len(v["duels"]),
                            "opponents":len(v["opponents"])}
                          for k,v in by_rank.items()},
        "executionVerified":False,
    }
