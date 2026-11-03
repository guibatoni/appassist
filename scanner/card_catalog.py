"""Catálogo de cartas MultiMod: tipos determinísticos e efeitos com procedência.

A tabela de códigos 0..23 corresponde ao formato conhecido de FM PS1.
Mods que alteram essa semântica precisam de adaptador próprio; nunca inventar
texto de efeito, chance de sucesso ou status de carta apenas pelo nome.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CARD_CATEGORIES = ("Monstros", "Mágicas", "Rituais", "Armadilhas", "Equipamentos", "Não identificado")
MONSTER_TYPES = (
    "Dragão", "Mago", "Zumbi", "Guerreiro", "Besta-Guerreira",
    "Besta", "Besta Alada", "Demônio", "Fada", "Inseto", "Dinossauro",
    "Réptil", "Peixe", "Serpente Marinha", "Máquina", "Trovão",
    "Aqua", "Piro", "Rocha", "Planta",
)
SPECIAL_TYPES = {20: ("Mágicas", "Magia"), 21: ("Armadilhas", "Armadilha"),
                 22: ("Rituais", "Ritual"), 23: ("Equipamentos", "Equipamento")}
MAX_EFFECT_BYTES = 1_500_000
MAX_EFFECT_CHARS = 1800
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def describe_type(type_id, *, known_fm_layout=True):
    """Mapa do formato conhecido, sem inferir categorias por textos/ATK."""
    if type(type_id) is not int or not known_fm_layout:
        return "Não identificado", "Não identificado", "estrutura_nao_confirmada"
    if 0 <= type_id < 20:
        return "Monstros", MONSTER_TYPES[type_id], "codigo_fm_padrao"
    if type_id in SPECIAL_TYPES:
        category, name = SPECIAL_TYPES[type_id]
        return category, name, "codigo_fm_padrao"
    return "Não identificado", f"Código {type_id}", "codigo_fm_desconhecido"


def enrich_cards(cards: list[dict], *, known_fm_layout=True) -> list[dict]:
    result = []
    for source in cards:
        c = dict(source)
        category, type_label, evidence = describe_type(
            c.get("type_id"), known_fm_layout=known_fm_layout)
        c.update({
            "category": category, "type_label": type_label,
            "category_source": evidence,
            "effect_text": None, "effect_source": None,
            "effect_status": "nao_identificado",
        })
        result.append(c)
    return result


def category_summary(cards: list[dict]) -> dict[str, int]:
    counts = {category: 0 for category in CARD_CATEGORIES}
    for card in cards:
        category = str(card.get("category", "Não identificado"))
        counts[category if category in counts else "Não identificado"] += 1
    return counts


def effect_sidecar_path(rom_path: Path) -> Path:
    """Ex.: /jogos/MeuMod.iso.dueltrace-effects.json."""
    return Path(str(rom_path) + ".dueltrace-effects.json")


def attach_effect_manifest(cards: list[dict], path: Path, *, rom_sha256: str):
    """Importa texto fornecido explicitamente e ligado ao hash da ISO.

    O arquivo não concede confiança de 'extraído da ISO'. Somente fonte local
    declarada. Rejeita IDs estranhos, SHA divergente, duplicatas e listas enormes.
    """
    path = Path(path)
    if not SHA_RE.fullmatch(rom_sha256.lower()):
        raise ValueError("SHA-256 da ISO inválido")
    if not path.is_file():
        return list(cards), {"status": "nao_fornecido", "count": 0}
    if path.stat().st_size > MAX_EFFECT_BYTES:
        raise ValueError("Manifesto de efeitos excede o limite")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Manifesto de efeitos: schema desconhecido")
    if str(data.get("rom_sha256", "")).lower() != rom_sha256.lower():
        raise ValueError("Manifesto de efeitos não pertence a esta ISO (SHA divergente)")
    records = data.get("effects")
    if not isinstance(records, list) or len(records) > max(4096, len(cards)):
        raise ValueError("Quantidade ou formato de efeitos inválido")
    known = {c.get("id") for c in cards}
    changes = {}
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("Entrada de efeito inválida")
        cid, effect = row.get("id"), row.get("text")
        if type(cid) is not int or cid not in known or cid in changes:
            raise ValueError("ID inválido, ausente ou duplicado no manifesto")
        if (not isinstance(effect, str) or not effect.strip()
                or len(effect) > MAX_EFFECT_CHARS or "\x00" in effect):
            raise ValueError("Texto de efeito inválido")
        changes[cid] = effect.strip()
    enriched = []
    for card in cards:
        c = dict(card)
        if c.get("id") in changes:
            c.update({
                "effect_text": changes[c["id"]],
                "effect_source": "manifesto_local_vinculado_sha256",
                "effect_status": "fornecido_externamente_nao_verificado_na_iso",
            })
        enriched.append(c)
    return enriched, {
        "status": "manifesto_local_nao_validado_na_iso",
        "count": len(changes), "sha256_matches": True,
    }
