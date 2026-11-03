"""Ordenação/filtro compartilhados pelas bibliotecas por ID do mod ativo.

Não converte categoria desconhecida em monstro. Ordenação determinística
sempre termina no ID, garantindo paginação estável.
"""
from __future__ import annotations

SORT_FIELDS = ("id", "atk", "def", "type", "name")
MAX_TYPE_LENGTH = 100


def validate_sort(sort: str, card_type: str) -> None:
    if type(sort) is not str or sort not in SORT_FIELDS:
        raise ValueError("Ordenação inválida; selecione ID, ATK, DEF, tipo ou nome.")
    if (type(card_type) is not str or len(card_type) > MAX_TYPE_LENGTH
            or any(ord(x) < 32 for x in card_type)):
        raise ValueError("Filtro de tipo inválido.")


def card_type_value(card: dict | None) -> str:
    if not isinstance(card,dict):
        return ""
    return str(card.get("type") or card.get("type_label") or
               card.get("category") or "").strip()


def matches_type(card: dict | None, card_type: str) -> bool:
    if not card_type:
        return True
    return card_type_value(card).casefold() == card_type.casefold()


def sort_key(card: dict | None, card_id: int, name: str, sort: str):
    card=card if isinstance(card,dict) else {}
    typ=card_type_value(card).casefold()
    display=(name or "").casefold()
    if sort in ("atk","def"):
        stat=card.get(sort)
        # Valores ausentes ao final e jamais tratados como 0.
        return (stat is None or type(stat) is not int,
                -stat if type(stat) is int else 0, display, card_id)
    if sort=="type":
        return (not bool(typ),typ,display,card_id)
    if sort=="name":
        return (display,card_id)
    return (card_id,)
