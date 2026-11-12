"""Projection of opponent deck pools and player deck fusions from the ACTIVE ISO.

Only previously validated identity mappings are published. Weighted NPC
tables are NOT 40-card fixed decks and never presented as one.
"""
from __future__ import annotations

from collections import Counter


def opponent_deck_view(profile, opponent_id, *, cards):
    if type(opponent_id) is not int or not 0 <= opponent_id <= 39:
        raise ValueError("Oponente inválido.")
    if not isinstance(profile,dict):
        return {"available":False,"opponents":[],"opponentId":0,
                "cards":[],"status":"Ative uma ISO para consultar oponentes."}
    roster=[]
    for row in profile.get("opponents",[]):
        if not isinstance(row,dict):
            continue
        cid=row.get("id")
        if type(cid) is int and 1<=cid<=39:
            roster.append({"id":cid,"name":str(row.get("name") or f"Oponente #{cid}")[:100]})
    roster.sort(key=lambda x:x["id"])
    selected=opponent_id or (roster[0]["id"] if roster else 0)
    base={"available":False,"opponents":roster,"opponentId":selected,
          "cards":[],"totalWeight":0,"fixed":False}
    if not roster or selected not in {x["id"] for x in roster}:
        return {**base,"status":"Nenhum oponente validado nesta ISO."}
    # Drops can be available from different evidence. Decks must be tied to
    # opponent identity; never reuse 39 structural names as confirmed IDs.
    if profile.get("verified",{}).get("oponentes")!="verificado":
        return {**base,"status":"IDs dos oponentes ainda não confirmados para este mod."}
    pool=profile.get("decks")
    if not isinstance(pool,list) or not pool:
        return {**base,"status":"Tabela do deck deste oponente ainda não extraída."}
    by_card={}
    for row in pool:
        if not isinstance(row,dict) or row.get("opponent_id")!=selected:
            continue
        cid,w=row.get("card_id"),row.get("weight")
        if type(cid) is not int or not 1<=cid<=722:
            continue
        if type(w) is not int or not 1<=w<=65535:
            continue
        by_card[cid]=by_card.get(cid,0)+w
    total=sum(by_card.values())
    if not by_card:
        return {**base,"status":"Nenhum registro válido encontrado para este oponente."}
    rows=[]
    for cid,weight in sorted(by_card.items(),key=lambda item:(-item[1],item[0])):
        card=cards.get(cid,{})
        rows.append({"id":cid,"name":card.get("name") or f"Carta #{cid}",
                     "type":card.get("type") or card.get("category") or "",
                     "atk":card.get("atk"),"def":card.get("def"),
                     "weight":weight,
                     "chancePercent":round(weight*100/total,4) if total==2048 else None})
    return {**base,"available":True,"cards":rows,"totalWeight":total,
            "status":("Pool ponderado extraído da ISO; cartas possíveis, não deck fixo."
                      if total==2048 else
                      "Pool extraído; soma de pesos diferente de 2048, probabilidades não confirmadas.")}


def fusion_pairs_for_deck(ids,recipes,card_names,*,max_results=80):
    if (not isinstance(ids,list) or len(ids)!=40
            or not all(type(cid) is int and 1<=cid<=722 for cid in ids)):
        return {"total":0,"rows":[]}
    available=Counter(ids)
    rows={}
    conflicts=set()
    for recipe in recipes if isinstance(recipes,list) else []:
        if not isinstance(recipe,dict):
            continue
        a,b,c=(recipe.get(k) for k in ("a","b","result"))
        if not all(type(i) is int and 1<=i<=722 for i in (a,b,c)):
            continue
        if available.get(a,0)<(2 if a==b else 1) or available.get(b,0)<1:
            continue
        key=(min(a,b),max(a,b))
        if key in rows and rows[key]["result"]!=c:
            conflicts.add(key)
            continue
        rows[key]={"a":a,"b":b,"result":c,
                   "nameA":card_names.get(a,{}).get("name") or f"Carta #{a}",
                   "nameB":card_names.get(b,{}).get("name") or f"Carta #{b}",
                   "nameResult":card_names.get(c,{}).get("name") or f"Carta #{c}",
                   "source":str(recipe.get("validation") or "não informado")[:90]}
    ordered=[r for key,r in rows.items() if key not in conflicts]
    ordered.sort(key=lambda r:(r["result"],r["a"],r["b"]))
    return {"total":len(ordered),"rows":ordered[:max_results],
            "conflictsOmitted":len(conflicts)}
