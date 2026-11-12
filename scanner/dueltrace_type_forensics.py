"""Análise automática e conservadora dos códigos de tipo da ISO ativa.

Lê exclusivamente os 5 bits de tipo já decodificados da tabela de atributos
do executável PS1. Detectar um código ou padrão divergente NÃO demonstra que
o jogo usa uma nova classe específica; rótulos continuam provisórios.
Nenhuma ISO é alterada e nenhum dado de outro mod é reutilizado.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import re

REVISION = 1
CARD_COUNT = 722
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
CLASSIC_MAX_TYPE = 23
MAX_TYPE = 31


def _value(card, *names):
    for name in names:
        v = card.get(name)
        if v is not None:
            return v
    return None


def _integer(raw, maximum):
    if type(raw) is int:
        return raw if 0 <= raw <= maximum else None
    if isinstance(raw, str) and raw.isascii() and raw.isdigit() and len(raw) <= 6:
        value = int(raw)
        return value if value <= maximum else None
    return None


def _monster_signals(card):
    level = _integer(_value(card, "nivel", "level"), 15)
    attack = _integer(_value(card, "atk"), 5110)
    defense = _integer(_value(card, "def"), 5110)
    return (level is not None and level > 0 and
            ((attack is not None and attack > 0) or
             (defense is not None and defense > 0)))


def _empty_monster_fields(card):
    level = _integer(_value(card, "nivel", "level"), 15)
    attack = _integer(_value(card, "atk"), 5110)
    defense = _integer(_value(card, "def"), 5110)
    return level == 0 and attack == 0 and defense == 0


def analyze_iso_types(cards, *, rom_sha256):
    """Audita os 722 registros e retorna evidências restritas à ISO indicada.

    A análise não consegue reconhecer uma troca 1:1 de nomes mantendo os mesmos
    números e atributos; tal semântica depende de prova adicional do mod.
    """
    if not isinstance(rom_sha256, str) or not SHA256_PATTERN.fullmatch(rom_sha256):
        raise ValueError("SHA-256 da ISO inválido")
    if not isinstance(cards, list) or len(cards) != CARD_COUNT:
        return {"schema": 1, "revision": REVISION, "rom_sha256": rom_sha256,
                "status": "catalogo_incompleto", "analyzed": 0,
                "unresolvedCodes": [], "monsterLikeCodes": [],
                "observedCodes": [], "mappingVerified": False,
                "inGameVerified": False}
    groups = defaultdict(list)
    valid = True
    for index, card in enumerate(cards, start=1):
        if not isinstance(card, dict) or _integer(card.get("id"), CARD_COUNT) != index:
            valid = False
            break
        raw = _integer(_value(card, "tipo", "type_id"), MAX_TYPE)
        if raw is None:
            valid = False
            break
        groups[raw].append(card)
    if not valid:
        return {"schema": 1, "revision": REVISION, "rom_sha256": rom_sha256,
                "status": "campos_incompativeis", "analyzed": 0,
                "unresolvedCodes": [], "monsterLikeCodes": [],
                "observedCodes": [], "mappingVerified": False,
                "inGameVerified": False}

    unresolved = set()
    suspected = set()
    monster_like = set()
    isolated = set()
    reasons = {}
    for code, group in sorted(groups.items()):
        monster_count = sum(_monster_signals(c) for c in group)
        empty_count = sum(_empty_monster_fields(c) for c in group)
        if code > CLASSIC_MAX_TYPE:
            unresolved.add(code)
            reasons[str(code)] = "codigo_fora_da_tabela_fm"
        elif code >= 20 and monster_count:
            # Valores de uma carta anômala não podem mudar a classificação
            # de todas as mágicas/armadilhas do mesmo código.
            if monster_count * 2 >= len(group):
                unresolved.add(code)
                suspected.add(code)
                reasons[str(code)] = "tipo_especial_majoritariamente_monstro"
            else:
                isolated.update(c["id"] for c in group if _monster_signals(c))
                reasons[str(code)] = "cartas_isoladas_com_atributos_de_monstro"
        if code in unresolved and monster_count * 100 >= len(group) * 80:
            monster_like.add(code)

    return {
        "schema": 1,
        "revision": REVISION,
        "rom_sha256": rom_sha256,
        "status": ("tipos_alterados_ou_desconhecidos" if unresolved or isolated
                   else "codigos_compativeis_com_fm_nao_confirmados_em_jogo"),
        "analyzed": CARD_COUNT,
        "observedCodes": sorted(groups),
        "counts": {str(k): len(v) for k, v in sorted(groups.items())},
        "unresolvedCodes": sorted(unresolved),
        "suspectedRemaps": sorted(suspected),
        "isolatedCardIds": sorted(isolated),
        "monsterLikeCodes": sorted(monster_like),
        "reasons": reasons,
        "mappingVerified": False,
        "inGameVerified": False,
        "method": "campos_tipo_5bits_e_coerencia_nivel_atk_def_da_propria_iso",
    }


def apply_iso_type_evidence(cards, report, *, rom_sha256):
    """Produz cartas anotadas sem modificar lista ou dados de origem."""
    if (not isinstance(report, dict)
            or report.get("rom_sha256") != rom_sha256
            or report.get("schema") != 1
            or report.get("revision") != REVISION
            or report.get("analyzed") != CARD_COUNT):
        return [dict(c) for c in cards]
    unresolved = set(report.get("unresolvedCodes", []))
    monsters = set(report.get("monsterLikeCodes", []))
    isolated = set(report.get("isolatedCardIds", []))
    result = []
    for card in cards:
        copy = dict(card)
        code = _integer(_value(copy, "type_id", "tipo"), MAX_TYPE)
        if code in unresolved or copy.get("id") in isolated:
            copy["type_semantics_unresolved"] = True
            copy["category"] = ("Monstros"
                                if code in monsters or copy.get("id") in isolated
                                else "Não identificado")
            copy["type_label"] = f"Tipo #{code} (a verificar)"
            copy["category_source"] = "sondagem_iso_sem_mapeamento_confirmado"
        result.append(copy)
    return result
