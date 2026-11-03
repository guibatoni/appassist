"""Lê metadados opcionais de efeitos realmente EMBUTIDOS na ISO do mod.

Não procura efeitos às cegas em bytes executáveis. Autores de mods podem
incluir DTEFFECT.JSON no ISO9660 contendo esquema DUELTRACE de efeitos.
Ler um texto declarado não comprova que o efeito é executado pelo jogo.
"""
from __future__ import annotations

import json
from pathlib import Path

from card_catalog import MAX_EFFECT_BYTES, attach_effect_document
from scanner_multiiso import Disc

ALLOWED_NAMES=("DTEFFECT.JSON","DUELTRACE/EFFECTS.JSON","DUELTRACE/CARDS.JSON")


def extract_embedded_effects(rom_path: Path, cards: list[dict], *,
                             rom_sha256: str):
    image=Disc(Path(rom_path))
    try:
        chosen=next((x for x in ALLOWED_NAMES if x in image.files),None)
        if chosen is None:
            return list(cards),{"status":"nao_embutido","count":0}
        length=image.files[chosen][1]
        if length>MAX_EFFECT_BYTES or length<3:
            raise ValueError("Metadados embutidos de tamanho incompatível")
        payload=image.get(chosen,limit_bytes=MAX_EFFECT_BYTES)
        data=json.loads(payload.decode("utf-8-sig"))
        enriched,report=attach_effect_document(
            cards,data,rom_sha256=rom_sha256,
            source=f"declarado_no_iso:{chosen}",
            embedded_in_iso=True)
        report["source_file"]=chosen
        return enriched,report
    finally:
        image.close()
