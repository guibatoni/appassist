"""Drops extraídos do WA_MRG e nomes vindos do SLUS, sem misturar perfis.

Não inventa grupos Z/S para mods desconhecidos. Recusa tabelas incompletas
ou manipuladas e pagina os resultados sem enviá-los para a rede.
"""
from __future__ import annotations

from collections import defaultdict
import re
from scanner_multiiso import X15_SHA
from dueltrace_rank_system import (
    available_ranks, drop_filter_ranks, drop_pool_labels, pool_ranks,
    pool_index_for_drop_filter, rank_system, is_x15_sha,
)
from dueltrace_library_sort import validate_sort,card_type_value,matches_type,sort_key

EXPECTED_OPPONENTS = 39
EXPECTED_TABLES = 117
WEIGHT_TOTAL = 2048
MAX_CARDS = 722
MAX_DROP_ROWS = EXPECTED_TABLES * MAX_CARDS


def _integer(value):
    return value if type(value) is int else None


def get_drop_catalog(profile: dict | None, *, opponent_id: int = 0,
                     group: str = "", query: str = "",
                     offset: int = 0, limit: int = 36,
                     sort: str = "id", card_type: str = "",
                     rank: str = "", card_id: int = 0) -> dict:
    validate_sort(sort,card_type)
    if type(card_id) is not int or not 0 <= card_id <= MAX_CARDS:
        raise ValueError("Carta inválida")
    if type(opponent_id) is not int or not 0 <= opponent_id <= EXPECTED_OPPONENTS:
        raise ValueError("Oponente inválido")
    if type(rank) is not str or len(rank)>32:
        raise ValueError("RANK de recompensa inválido")
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
        "cardTypes": [], "sort": sort, "cardType": card_type,
        "rankOptions": [], "rankSelected": rank,
        "rankSystem": None, "groupOptions": [],
        "source": "DATA/WA_MRG.MRG + SLUS_014.11",
        "rankPoints": (profile.get("rank_points", {}) if isinstance(profile,dict) else {}),
    }
    if not isinstance(profile, dict):
        return empty
    alpha = profile.get("alpha_discovery", {})
    # Only the bridge can construct the opt-in source-bound ALPHA view;
    # never persist these flags in a registered mod profile.
    alpha_candidate = (
        isinstance(alpha, dict)
        and alpha.get("state") == "retail_sentinel_39_reward_records"
        and alpha.get("source") == "local_iso_sha256_matched"
        and alpha.get("rom_sha256") == profile.get("rom_sha256")
        and profile.get("supported_features", {}).get("cards") is True
        and profile.get("verified", {}).get("cartas") == "verificado"
    )
    fully_verified = (
        profile.get("verified", {}).get("tabelas_drops") == "verificado"
        and profile.get("verified", {}).get("oponentes") == "verificado"
        and profile.get("verified", {}).get("cartas") == "verificado"
        and profile.get("supported_features", {}).get("drops") is True
        and profile.get("supported_features", {}).get("cards") is True
    )
    if not fully_verified and not alpha_candidate:
        return empty
    raw_opponents = profile.get("opponents")
    raw_groups = profile.get("drop_group_labels")
    drops = profile.get("drops")
    cards = profile.get("cards")
    if (not isinstance(raw_opponents, list)
            or not isinstance(raw_groups, list)
            or not isinstance(drops, list)
            or not isinstance(cards, list)
            or len(cards) != MAX_CARDS
            or len(raw_opponents) != EXPECTED_OPPONENTS
            or len(raw_groups) != 3
            or len(drops) > MAX_DROP_ROWS):
        return empty
    if any(type(g) is not str or not g or len(g) > 80 for g in raw_groups):
        return empty
    if len(set(raw_groups)) != 3:
        return empty
    iso_sha=profile.get("rom_sha256")
    if not isinstance(iso_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", iso_sha):
        return empty
    provenance = profile.get("drops_provenance", {})
    if not isinstance(provenance, dict):
        return empty
    bound_sha = provenance.get("rom_sha256")
    if bound_sha is not None and (not isinstance(bound_sha, str)
                                  or bound_sha.casefold() != iso_sha.casefold()):
        return empty
    ranks=available_ranks(iso_sha)
    filters=drop_filter_ranks(iso_sha)
    labels=drop_pool_labels(iso_sha)
    grouped_ranks=pool_ranks(iso_sha)
    # Four menu choices cover the original three WA_MRG banks: SA-POW,
    # BCD-POW, BCD-TEC and SA-TEC. Keep old single-rank queries valid.
    if rank and rank not in filters and rank not in ranks:
        raise ValueError("O RANK não pertence ao sistema desta ISO.")
    selected_group=(raw_groups[pool_index_for_drop_filter(iso_sha,rank)]
                    if rank else "")
    if group and selected_group and group!=selected_group:
        raise ValueError("O RANK solicitado pertence a outro banco de drops.")
    labels_by_raw=dict(zip(raw_groups,labels))
    grouped_by_raw=dict(zip(raw_groups,grouped_ranks))
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
    cards_by_id = {}
    for card in cards:
        if (not isinstance(card, dict) or type(card.get("id")) is not int
                or not 1 <= card["id"] <= MAX_CARDS or card["id"] in cards_by_id
                or not isinstance(card.get("name"), str) or not card["name"].strip()):
            return empty
        cards_by_id[card["id"]] = card
    if set(cards_by_id) != set(range(1, MAX_CARDS + 1)):
        return empty
    if group and group not in raw_groups:
        raise ValueError("Grupo de drop não pertence ao mod ativo.")
    card_types=sorted({card_type_value(card) for card in cards_by_id.values()
                       if card_type_value(card)},key=str.casefold)

    totals = defaultdict(int)
    seen = set()
    checked = []
    for record in drops:
        if not isinstance(record, dict):
            return empty
        oid = _integer(record.get("opponent_id"))
        cid = _integer(record.get("card_id"))
        raw_rank = record.get("group")
        weight = _integer(record.get("weight"))
        if (oid not in opponents or type(raw_rank) is not str or raw_rank not in raw_groups
                or cid is None or cid not in cards_by_id
                or weight is None or not 1 <= weight <= WEIGHT_TOTAL):
            return empty
        key = (oid, raw_rank, cid)
        if key in seen:
            return empty
        seen.add(key)
        totals[(oid, raw_rank)] += weight
        if totals[(oid,raw_rank)] > WEIGHT_TOTAL:
            return empty
        checked.append((oid, raw_rank, cid, weight, record.get("source_offset")))
    if (len(totals) != EXPECTED_TABLES
            or any(totals.get((oid,rank)) != WEIGHT_TOTAL
                   for oid in opponents for rank in raw_groups)):
        return empty

    text = query.strip().casefold()
    matched = []
    for oid, raw_rank, cid, weight, source_offset in checked:
        if card_id and cid != card_id:
            continue
        if opponent_id and oid != opponent_id:
            continue
        if group and raw_rank != group:
            continue
        if selected_group and raw_rank != selected_group:
            continue
        card=cards_by_id.get(cid,{})
        if not matches_type(card,card_type):
            continue
        name = card.get("name") or f"Carta #{cid}"
        searchable=[name]
        for key in ("description_text","effect_text","description","effect"):
            value=card.get(key)
            if isinstance(value,str):
                searchable.append(value)
        if text and text != str(cid) and not any(
                text in value.casefold() for value in searchable):
            continue
        offset_repr = (f"0x{source_offset:X}"
                       if type(source_offset) is int and 0 <= source_offset <= 96*1024*1024
                       else None)
        matched.append({
            "opponentId": oid, "opponentName": opponents[oid],
            "group": raw_rank,
            "groupLabel":labels_by_raw[raw_rank],
            "eligibleRanks":list(grouped_by_raw[raw_rank]),
            "cardId": cid, "cardName": name,
            "category":card.get("category") or "Não identificada",
            "cardType":card_type_value(card),
            "atk":card.get("atk") if type(card.get("atk")) is int else None,
            "def":card.get("def") if type(card.get("def")) is int else None,
            "weight": weight,
            "chancePercent": round(weight * 100 / WEIGHT_TOTAL, 6),
            "sourceOffset": offset_repr,
        })
    if sort=="id":
        matched.sort(key=lambda row: (
            row["opponentId"],raw_groups.index(row["group"]),
            row["cardId"]))
    else:
        matched.sort(key=lambda row: (
            sort_key(cards_by_id.get(row["cardId"]),row["cardId"],
                     row["cardName"],sort),
            row["opponentId"],raw_groups.index(row["group"])))
    image_sha = profile.get("rom_sha256")
    is_known = (is_x15_sha(image_sha)
                and profile.get("verified", {}).get("nomes_dos_ranks") == "verificado")
    return {
        **empty, "available": True,
        "provisional": bool(alpha_candidate and not fully_verified),
        "opponentMappingVerified": bool(fully_verified),
        "mayActivateDrops": False,
        "status": (
            "ALPHA — cartas e pesos de drop extraídos desta ISO; 39 índices "
            "provisórios e grupos RANK interpretados pelo formato original. "
            "Associação nome/ID e grupos não confirmada em execução."
            if alpha_candidate and not fully_verified else
            "Drops validados: 117 tabelas × 2048 pesos; "
            + ("RANKs Z-POW, S-POW e S-TEC do Remaster X15 identificados."
               if is_known else
               "padrão original: dez RANKs compartilham três bancos; "
               "mapeamento de mods sem SHA conhecido deve ser conferido em duelo.")),
        "total": len(matched), "rows": matched[offset:offset+limit],
        "opponents": [{"id": key, "name": opponents[key]} for key in sorted(opponents)],
        "groups": list(raw_groups),
        "groupOptions":[
            {"value":raw,"label":labels[i],"ranks":list(grouped_ranks[i])}
            for i,raw in enumerate(raw_groups)
        ],
        "rankOptions":list(filters),"rankSelected":rank,
        "rankSystem":rank_system(iso_sha),
        "cardTypes": card_types,
        "rankLabelsVerified": is_known and not alpha_candidate,
    }

def get_card_drop_sources(profile: dict | None, card_id: int) -> dict:
    """Exibe todos os drops validados da carta na ISO ativa, com paginação interna."""
    if type(card_id) is not int or not 1 <= card_id <= MAX_CARDS:
        raise ValueError("Carta inválida")
    first = get_drop_catalog(profile, card_id=card_id, offset=0, limit=100)
    rom_sha = profile.get("rom_sha256") if isinstance(profile, dict) else None
    result = {
        "romSha": rom_sha if isinstance(rom_sha, str) else None,
        "cardId": card_id,
        "available": first["available"],
        "status": first["status"],
        "total": first["total"],
        "rows": [],
        "rankSystem": first["rankSystem"],
        "rankLabelsVerified": first["rankLabelsVerified"],
        "provisional": first.get("provisional", False),
        "source": first["source"],
    }
    if not first["available"]:
        return result
    rows = list(first["rows"])
    if first["total"] > len(rows):
        second = get_drop_catalog(profile, card_id=card_id, offset=100, limit=100)
        if not second["available"] or second["total"] != first["total"]:
            return {**result, "available": False, "status": "Perfil alterado durante a consulta"}
        rows.extend(second["rows"])
    if len(rows) != first["total"]:
        return {**result, "available": False, "status": "Resultado incompleto"}
    rows.sort(key=lambda row: (
        -row["chancePercent"], row["opponentName"].casefold(), row["opponentId"], row["groupLabel"].casefold()
    ))
    return {**result, "rows": rows}
