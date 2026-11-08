"""Extrai notas curtas de versão sem incluir metadados técnicos de publicação.

Somente itens de listas nas seções Novidades, Melhorias e Correções são
apresentados. Corpos antigos de release contendo apenas SHA/CI não recebem
notas inventadas.
"""
from __future__ import annotations

import re

HEADINGS = {
    "novidades": "Novidades",
    "melhorias": "Melhorias",
    "correções": "Correções",
    "correcoes": "Correções",
}
MAX_BODY = 24_000
MAX_ITEMS_PER_SECTION = 5
MAX_ITEM_LENGTH = 160


def summarize_patch_notes(body: str | None) -> list[dict]:
    if not isinstance(body, str) or not body.strip():
        return []
    active = None
    sections: dict[str, list[str]] = {label: [] for label in (
        "Novidades", "Melhorias", "Correções")}
    for line in body[:MAX_BODY].splitlines():
        match = re.fullmatch(r"\s*#{2,3}\s+([^#]+?)\s*#*\s*", line)
        if match:
            active = HEADINGS.get(match.group(1).strip().casefold())
            continue
        if not active or len(sections[active]) >= MAX_ITEMS_PER_SECTION:
            continue
        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        if not bullet:
            continue
        entry = bullet.group(1).strip()
        # Apresentação em texto simples: markdown não é interpretado como HTML.
        entry = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", entry)
        entry = re.sub(r"[\x00-\x1f\x7f]", "", entry)
        entry = entry.replace("**", "").replace("`", "").replace("__", "")
        entry = re.sub(r"\s+", " ", entry).strip()
        if entry and len(entry) <= MAX_ITEM_LENGTH and entry not in sections[active]:
            sections[active].append(entry)
    return [{"title": title, "items": items} for title, items in sections.items()
            if items]
