"""Planejador de fusões mão + campo; sem leitor de RAM da mesa.

A função só aceita cartas do campo quando a origem de RAM for validada
explicitamente para o perfil SHA corrente. Hoje não há endereços comprovados:
a UI permanece desativada para sugestões de campo até termos evidências.
"""
from __future__ import annotations
import re

SHA = re.compile(r"^[0-9a-f]{64}$")


def suggest_hand_field_fusions(*, rom_sha256: str, hand_ids: list[int],
                               field_snapshot: dict | None,
                               recipes: list[tuple[int,int,int]],
                               cards: dict[int, dict], limit=25) -> dict:
    """Somente sugestões teóricas provenientes do catálogo já aprovado.

    field_snapshot esperado futuramente:
      {"profile_sha256":sha, "ram_verified":True,
       "side":"player", "zone":"monster",
       "slots":[{"slot":0,"card_id":123}, ...]}.
    Sem confirmação de RAM retorna bloqueado (nunca inventa IDs).
    """
    blocked={"ready":False,"reason":"Cartas do campo ainda não identificadas por RAM validada",
             "suggestions":[],"field_cards":[]}
    if not isinstance(rom_sha256,str) or not SHA.fullmatch(rom_sha256):
        return blocked
    if not isinstance(field_snapshot,dict):
        return blocked
    if (field_snapshot.get("profile_sha256")!=rom_sha256
            or field_snapshot.get("ram_verified") is not True
            or field_snapshot.get("side")!="player"
            or field_snapshot.get("zone")!="monster"):
        return blocked
    slots=field_snapshot.get("slots")
    if not isinstance(slots,list) or len(slots)>5:
        return blocked
    seen_slots=set()
    field=[]
    for item in slots:
        if not isinstance(item,dict):
            return blocked
        slot=item.get("slot")
        cid=item.get("card_id")
        if (type(slot) is not int or not 0<=slot<5 or slot in seen_slots
                or type(cid) is not int or not 1<=cid<=722):
            return blocked
        seen_slots.add(slot)
        field.append((slot,cid))
    if not isinstance(hand_ids,list) or len(hand_ids)!=5 or any(
        type(cid) is not int or not 1<=cid<=722 for cid in hand_ids):
        return blocked
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError("Limite inválido")
    # Permutação não importa, mas uma combinação só pode levar ao resultado
    # previsto no catálogo aprovado. Não aprovar receitas nem sobrescrever dados.
    by_pair={}
    for raw in recipes:
        try:
            a,b,result=raw
            if not all(type(v) is int and 1<=v<=722 for v in (a,b,result)):
                continue
            by_pair.setdefault(tuple(sorted((a,b))),set()).add(result)
        except (TypeError,ValueError):
            continue
    suggestions=[]
    for hand_slot,hand_card in enumerate(hand_ids):
        for board_slot,board_card in field:
            pair=tuple(sorted((hand_card,board_card)))
            for result in sorted(by_pair.get(pair,())):
                result_card=cards.get(result,{})
                suggestions.append({
                    "hand_slot":hand_slot,
                    "hand_card_id":hand_card,
                    "field_slot":board_slot,
                    "field_card_id":board_card,
                    "result_id":result,
                    "result_name":result_card.get("name",f"ID {result}"),
                    "result_atk":result_card.get("atk"),
                    "theoretical":True,
                    "confirmation_recorded":False,
                })
    suggestions.sort(key=lambda row:(
        -(row["result_atk"] if type(row["result_atk"]) is int else -1),
        row["hand_slot"],row["field_slot"],row["result_id"]))
    return {
        "ready":True, "reason":"Hipóteses de catálogo — conferir mecânica em jogo",
        "field_cards":[{"slot":slot,"card_id":cid} for slot,cid in field],
        "suggestions":suggestions[:limit],
        "total":len(suggestions),
    }
