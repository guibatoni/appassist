"""Planejador determinístico de fusões consecutivas da mão do DUELTRACE.

Somente receitas do catálogo ativo são consultadas. O planejador NÃO inventa
combinações, NÃO verifica cartas na mesa e NÃO confirma uma cadeia completa
no emulador. Cada estado consome cartas de slots distintos, sem reutilização.
"""
from __future__ import annotations
from collections import deque

MAX_HAND = 5
MAX_CARD_ID = 722
DEFAULT_MAX_STATES = 20_000


def _valid_hand(hand: object) -> bool:
    return (isinstance(hand, (list, tuple)) and len(hand) == MAX_HAND and
            all(type(cid) is int and 1 <= cid <= MAX_CARD_ID for cid in hand))


def _stat(cards: dict, card_id: int, key: str):
    value = cards.get(card_id, {}).get(key)
    return value if type(value) is int else None


def _manual_count(steps: tuple[dict, ...]) -> int:
    return sum(step["validation"] == "observada_manualmente_no_jogo" for step in steps)


def _path_order(steps: tuple[dict, ...]) -> tuple:
    return tuple((step["slot"], step["material_a"],step["material_b"],
                  step["result"]) for step in steps)


def _prefer(candidate: tuple[dict, ...], existing: tuple[dict, ...]) -> bool:
    """Preferências de proveniência para o MESMO estado e resultado."""
    return (-_manual_count(candidate), _path_order(candidate)) < (
        -_manual_count(existing), _path_order(existing))


def plan_fusion_chains(hand: list[int] | tuple[int, ...] | None,
                       fusion_index: dict, cards: dict[int, dict], *,
                       min_cards: int = 3, max_cards: int = 5,
                       limit: int = 12,
                       max_states: int = DEFAULT_MAX_STATES) -> dict:
    """Explora pares iniciais e continuações com cartas ainda na mão.

    Estado = (máscara de slots consumidos, ID do resultado parcial).
    Cada operação adicional utiliza resultado anterior + uma carta nova.
    Se complete for False, o limite de estados foi alcançado e os resultados
    não podem ser chamados de melhor combinação exaustiva.
    """
    if not all(type(n) is int for n in (min_cards, max_cards, limit, max_states)):
        raise ValueError("Parâmetros de busca inválidos")
    if not 3 <= min_cards <= max_cards <= MAX_HAND:
        raise ValueError("Buscar entre três e cinco cartas da mão")
    if not 1 <= limit <= 100 or not 100 <= max_states <= 200_000:
        raise ValueError("Limite de resultados/estados fora do intervalo")
    empty = {"routes": [], "complete": True,
             "explored_states": 0, "possible_routes": 0, "distinct_results": 0}
    if not _valid_hand(hand) or not isinstance(fusion_index, dict):
        return empty
    cards = cards if isinstance(cards, dict) else {}
    queue = deque()
    visited: dict[tuple[int, int], tuple[dict, ...]] = {}
    truncated = False

    def propose(mask: int, result: int, steps: tuple[dict, ...]):
        nonlocal truncated
        key = (mask, result)
        previous = visited.get(key)
        if previous is not None:
            if _prefer(steps, previous):
                visited[key] = steps
                queue.append((mask, result, steps))
            return
        if len(visited) >= max_states:
            truncated = True
            return
        visited[key] = steps
        queue.append((mask, result, steps))

    for first in range(MAX_HAND):
        for second in range(first+1, MAX_HAND):
            a, b = hand[first], hand[second]
            mask = (1 << first) | (1 << second)
            for result, validation in fusion_index.get(tuple(sorted((a,b))), ()):
                if type(result) is not int or not 1 <= result <= MAX_CARD_ID:
                    continue
                step = {"slot": second+1, "slot_initial": first+1,
                        "material_a": a, "material_b": b,
                        "result": result, "validation": str(validation)}
                propose(mask, result, (step,))

    while queue:
        mask, current, steps = queue.popleft()
        if visited.get((mask, current)) != steps:
            continue
        if len(steps) >= max_cards-1:
            continue
        for slot in range(MAX_HAND):
            if mask & (1 << slot):
                continue
            material = hand[slot]
            for result, validation in fusion_index.get(
                    tuple(sorted((current,material))), ()):
                if type(result) is not int or not 1 <= result <= MAX_CARD_ID:
                    continue
                step = {"slot": slot+1, "material_a": current,
                        "material_b": material, "result": result,
                        "validation": str(validation)}
                propose(mask | (1 << slot), result, steps+(step,))

    best_by_result: dict[int, dict] = {}
    possible = 0
    for (mask, result), steps in visited.items():
        used = [slot+1 for slot in range(MAX_HAND) if mask & (1 << slot)]
        if len(used) < min_cards:
            continue
        possible += 1
        attack = _stat(cards, result, "atk")
        defense = _stat(cards, result, "def")
        all_manual = all(s["validation"]=="observada_manualmente_no_jogo"
                         for s in steps)
        order = [steps[0]["slot_initial"], steps[0]["slot"]]
        order.extend(step["slot"] for step in steps[1:])
        route = {
            "result": result,
            "result_name": str(cards.get(result,{}).get("name") or f"Carta #{result}"),
            "atk": attack, "def": defense,
            "used_slots": used,
            "slot_order": order,
            "cards_consumed": len(used),
            "steps": [dict(s) for s in steps],
            "manual_steps": _manual_count(steps),
            "all_steps_observed_individually": all_manual,
            "route_observed_in_game": False,
        }
        current_best = best_by_result.get(result)
        if current_best is None:
            best_by_result[result] = route
        else:
            old_steps = tuple(current_best["steps"])
            if (len(steps), -_manual_count(steps), _path_order(steps)) < (
                len(old_steps), -_manual_count(old_steps), _path_order(old_steps)):
                best_by_result[result] = route

    routes = sorted(best_by_result.values(),
                    key=lambda r: (
                        r["atk"] is None,
                        -(r["atk"] if r["atk"] is not None else -1),
                        len(r["steps"]), -r["manual_steps"],
                        r["result"], tuple(r["used_slots"])))
    return {"routes":routes[:limit], "complete":not truncated,
            "explored_states":len(visited), "possible_routes":possible,
            "distinct_results":len(routes)}


def describe_route(route: dict, cards: dict[int, dict], *,
                   max_chars: int=280) -> str:
    """Explica cada operação sem atribuir nome a IDs desconhecidos."""
    names = cards if isinstance(cards, dict) else {}
    fragments = []
    def named(card_id):
        return f"#{card_id} {names.get(card_id,{}).get('name') or 'Carta desconhecida'}"
    for n,step in enumerate(route.get("steps",[]),1):
        a,b,result=(step[k] for k in ("material_a","material_b","result"))
        prefix=(f"{named(a)} + {named(b)}" if n==1
                else f"resultado anterior + {named(b)}")
        fragments.append(f"{n}. {prefix} = {named(result)}")
    text="\n".join(fragments)
    return text if len(text) <= max_chars else text[:max_chars-1]+"…"
