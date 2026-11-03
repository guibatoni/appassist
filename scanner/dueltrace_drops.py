"""Drops extraídos do WA_MRG e nomes vindos do SLUS, sem misturar perfis.

Não inventa grupos Z/S para mods desconhecidos. Recusa tabelas incompletas
ou manipuladas e pagina os resultados sem enviá-los para a rede.
"""
from __future__ import annotations

from collections import defaultdict
from scanner_multiiso import X15_SHA

EXPECTED_OPPONENTS = 39
EXPECTED_TABLES = 117
WEIGHT_TOTAL = 2048
MAX_CARDS = 722
MAX_DROP_ROWS = EXPECTED_TABLES * MAX_CARDS


def _integer(value):
    return value if type(value) is int else None


def get_drop_catalog(profile: dict | None, *, opponent_id: int = 0,
                     group: str = "", query: str = "",
                     offset: int = 0, limit: int = 36) -> dict:
    if type(opponent_id) is not int or not 0 <= opponent_id <= EXPECTED_OPPONENTS:
        raise ValueError("Oponente inválido")
    if type(group) is not str or len(group) > 80:
        raise ValueError("Grupo de drop inválido")
    if type(query) is not str or len(query) > 100:
        raise ValueError("Pesquisa inválida")
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError("Página inválida")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Limite inválido")

    empty = {
        "available": False, "status": "Dados de drops ainda não validados nesta ISO",
        "total": 0, "offset": offset, "rows": [], "opponents": [], "groups": [],
        "rankLabelsVerified": False, "weightTotal": WEIGHT_TOTAL,
        "source": "DATA/WA_MRG.MRG + SLUS_014.11",
        "rankPoints": (profile.get("rank_points", {}) if isinstance(profile,dict) else {}),
    }
    if (not isinstance(profile, dict)
            or profile.get("verified", {}).get("tabelas_drops") != "verificado"
            or profile.get("verified", {}).get("oponentes") != "verificado"
            or not profile.get("supported_features", {}).get("drops")):
        return empty
    raw_opponents = profile.get("opponents")
    raw_groups = profile.get("drop_group_labels")
    drops = profile.get("drops")
    cards = profile.get("cards")
    if (not isinstance(raw_opponents, list)
            or not isinstance(raw_groups, list)
            or not isinstance(drops, list)
            or not isinstance(cards, list)
            or len(raw_opponents) != EXPECTED_OPPONENTS
            or len(raw_groups) != 3
            or len(drops) > MAX_DROP_ROWS):
        return empty
    if any(type(g) is not str or not g or len(g) > 80 for g in raw_groups):
        return empty
    if len(set(raw_groups)) != 3:
        return empty
    opponents = {}
    for opponent in raw_opponents:
        if not isinstance(opponent, dict):
            return empty
        oid = _integer(opponent.get("id"))
        name = opponent.get("name")
        if oid is None or not 1 <= oid <= EXPECTED_OPPONENTS or oid in opponents:
            return empty
        if not isinstance(name, str) or not name.strip() or len(name) > 150:
            return empty
        opponents[oid] = name
    if set(opponents) != set(range(1, EXPECTED_OPPONENTS+1)):
        return empty
    cards_by_id = {
        c["id"]: c for c in cards
        if isinstance(c, dict) and type(c.get("id")) is int
        and 1 <= c["id"] <= MAX_CARDS and isinstance(c.get("name"), str)
    }
    if group and group not in raw_groups:
        raise ValueError("Grupo de drop não pertence ao mod ativo.")

    totals = defaultdict(int)
    seen = set()
    checked = []
    for record in drops:
        if not isinstance(record, dict):
            return empty
        oid = _integer(record.get("opponent_id"))
        cid = _integer(record.get("card_id"))
        rank = record.get("group")
        weight = _integer(record.get("weight"))
        if (oid not in opponents or type(rank) is not str or rank not in raw_groups
                or cid is None or not 1 <= cid <= MAX_CARDS
                or weight is None or not 1 <= weight <= WEIGHT_TOTAL):
            return empty
        key = (oid, rank, cid)
        if key in seen:
            return empty
        seen.add(key)
        totals[(oid, rank)] += weight
        if totals[(oid,rank)] > WEIGHT_TOTAL:
            return empty
        checked.append((oid, rank, cid, weight, record.get("source_offset")))
    if (len(totals) != EXPECTED_TABLES
            or any(totals.get((oid,rank)) != WEIGHT_TOTAL
                   for oid in opponents for rank in raw_groups)):
        return empty

    text = query.strip().casefold()
    matched = []
    for oid, rank, cid, weight, source_offset in checked:
        if opponent_id and oid != opponent_id:
            continue
        if group and rank != group:
            continue
        card=cards_by_id.get(cid,{})
        name = card.get("name") or f"Carta #{cid}"
        if text and text not in name.casefold() and text != str(cid):
            continue
        offset_repr = (f"0x{source_offset:X}"
                       if type(source_offset) is int and 0 <= source_offset <= 96*1024*1024
                       else None)
        matched.append({
            "opponentId": oid, "opponentName": opponents[oid],
            "group": rank, "cardId": cid, "cardName": name,
            "category":card.get("category") or "Não identificada",
            "atk":card.get("atk") if type(card.get("atk")) is int else None,
            "def":card.get("def") if type(card.get("def")) is int else None,
            "weight": weight,
            "chancePercent": round(weight * 100 / WEIGHT_TOTAL, 6),
            "sourceOffset": offset_repr,
        })
    matched.sort(key=lambda row: (
        row["opponentId"], raw_groups.index(row["group"]),
        -row["weight"], row["cardId"]))
    image_sha = profile.get("rom_sha256")
    is_known = (isinstance(image_sha, str) and image_sha.lower() == X15_SHA.lower()
                and profile.get("verified", {}).get("nomes_dos_ranks") == "verificado")
    return {
        **empty, "available": True,
        "status": ("Drops validados: 117 tabelas × 2048 pesos; os grupos de rank "
                   + ("foram identificados." if is_known else
                      "não têm equivalência Z-POW/S-POW/S-TEC confirmada.")),
        "total": len(matched), "rows": matched[offset:offset+limit],
        "opponents": [{"id": key, "name": opponents[key]} for key in sorted(opponents)],
        "groups": list(raw_groups),
        "rankLabelsVerified": is_known,
    }
