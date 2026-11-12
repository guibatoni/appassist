"""Projection of opponent deck pools and player deck fusions from the ACTIVE ISO.

Only previously validated identity mappings are published. Weighted NPC
tables are NOT 40-card fixed decks and never presented as one.
"""
from __future__ import annotations

from collections import Counter


def opponent_deck_view(profile, opponent_id, *, cards, candidate=None):
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
          "cards":[],"totalWeight":0,"fixed":False,
          "opponentMappingVerified":False,"provisional":False}
    if not roster or selected not in {x["id"] for x in roster}:
        return {**base,"status":"Nenhum oponente reconhecido nesta ISO."}

    confirmed=(profile.get("verified",{}).get("oponentes")=="verificado")
    pool=profile.get("decks") if confirmed else None
    provisional=False
    if (not isinstance(pool,list) or not pool) and (
            isinstance(candidate,dict)
            and candidate.get("available") is True
            and candidate.get("rom_sha256")==profile.get("rom_sha256")):
        pool=candidate.get("rows")
        provisional=True
    if not isinstance(pool,list) or not pool:
        return {**base,"status":(
            "A ISO contém nomes estruturais, mas o pool de decks ainda não foi "
            "associado aos adversários. Atualize os dados do mod e tente novamente.")}

    by_card={}
    for row in pool:
        if not isinstance(row,dict) or row.get("opponent_id")!=selected:
            continue
        cid,w=row.get("card_id"),row.get("weight")
        if type(cid) is not int or not 1<=cid<=722:
            continue
        if type(w) is not int or not 1<=w<=2048:
            continue
        by_card[cid]=by_card.get(cid,0)+w
    total=sum(by_card.values())
    if not by_card or total!=2048:
        return {**base,"status":"Pool de deck incompleto ou com pesos inválidos."}
    rows=[]
    for cid,weight in sorted(by_card.items(),key=lambda item:(-item[1],item[0])):
        card=cards.get(cid,{})
        rows.append({"id":cid,"name":card.get("name") or f"Carta #{cid}",
                     "type":card.get("type") or card.get("category") or "",
                     "atk":card.get("atk"),"def":card.get("def"),
                     "weight":weight,
                     "chancePercent":round(weight*100/total,4)})
    return {**base,"available":True,"cards":rows,
            "totalWeight":total,"opponentMappingVerified":confirmed and not provisional,
            "provisional":provisional,
            "status":(
                "CANDIDATO: pool de pesos na posição estrutural #"
                +str(selected)+". A identidade deste adversário não foi "
                "confirmada em duelo; não atribuir estes pesos ao nome acima."
                if provisional else
                "Pool de 2048 pesos associado ao oponente confirmado. "
                "A composição do deck varia a cada duelo, não é fixa.")}


def decode_candidate_deck_pools(wa, reward_evidence, *, rom_sha256):
    """39 structurally validated weighted pools of the active ISO.

    A slot number is NOT proof of the opponent's name or runtime identity.
    The reward detector already validated 40 consecutive 0x1800 blocks.
    Refuse to fabricate a pool if any matrix is missing or fails checksum.
    """
    import re
    from dueltrace_alpha_reward_pools import BLOCK_BYTES, DUELISTS
    from dueltrace_mod_family_probe import decode_matrix
    if (type(rom_sha256) is not str
            or not re.fullmatch(r"[a-f0-9]{64}", rom_sha256)
            or not isinstance(reward_evidence,dict)
            or reward_evidence.get("available") is not True
            or type(reward_evidence.get("base")) is not int
            or reward_evidence.get("opponentBlocks") != DUELISTS
            or reward_evidence.get("candidateMode") not in (
                "retail_sentinel","40_block_retail_mapping_hypothesis")):
        return {"available":False,"rows":[],"verified":False}
    base=reward_evidence["base"]
    if (not isinstance(wa,bytes) or base<0 or
            base+(DUELISTS-1)*BLOCK_BYTES+722*2>len(wa)):
        return {"available":False,"rows":[],"verified":False}
    all_rows=[]
    for slot in range(1,DUELISTS+1):
        weights=decode_matrix(wa,base+(slot-1)*BLOCK_BYTES,"plain")
        if weights is None:
            return {"available":False,"rows":[],"verified":False}
        all_rows.extend(
            {"opponent_id":slot,"card_id":id,"weight":weight}
            for id,weight in enumerate(weights,1) if weight)
    return {"available":True,"rows":all_rows,"verified":False,
            "rom_sha256":rom_sha256,"source":"40_block_weight_family"}



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
