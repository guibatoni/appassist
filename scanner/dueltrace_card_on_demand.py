"""Render HD sob demanda para as imagens do próprio mod ativo.

É executado pelo servidor HTTP local quando /__card_hd__/... é pedido.
Não reanalisa a ISO, não acessa a rede e não altera arquivos de origem.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path

from PIL import Image
from dueltrace_classic_cards import SIZE, REVISION, card_fields, render_card

_LOCK = threading.RLock()
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def ensure_card_hd(root: Path, card: dict, *, rom_sha256: str) -> Path:
    if type(rom_sha256) is not str or not _SHA.fullmatch(rom_sha256):
        raise ValueError("ISO inválida")
    if not isinstance(card, dict):
        raise ValueError("Carta inválida")
    cid = card.get("id")
    if type(cid) is not int or not 1 <= cid <= 722:
        raise ValueError("ID de carta inválido")
    root = Path(root).resolve(strict=True)
    name = f"{cid:03d}.png"
    raw = root / "artes_722" / name
    upscaled = root / "artes_upscaled" / name
    source = upscaled if upscaled.is_file() and not upscaled.is_symlink() else raw
    if (source.is_symlink() or not source.is_file()
            or not 0 < source.stat().st_size <= 8_000_000
            or not source.resolve(strict=True).is_relative_to(root)):
        raise ValueError("Arte original não disponível")
    out = root / "cartas_classicas_hd"
    if out.is_symlink():
        raise ValueError("Pasta de cache insegura")
    out.mkdir(exist_ok=True)
    out = out.resolve(strict=True)
    if not out.is_relative_to(root) or out == source.parent:
        raise ValueError("Destino de cache inválido")
    target = out / name
    marker = out / (name + ".source-sha256")
    fields = card_fields(card)
    token = hashlib.sha256(
        source.read_bytes()
        + json.dumps(fields, ensure_ascii=False, sort_keys=True).encode("utf-8")
        + f"{rom_sha256}:r{REVISION}:card-on-demand-1".encode("ascii")
    ).hexdigest()
    with _LOCK:
        if (target.is_file() and not target.is_symlink()
                and marker.is_file() and not marker.is_symlink()
                and marker.stat().st_size <= 100):
            if marker.read_text("ascii") == token:
                with Image.open(target) as pic:
                    if pic.size == SIZE:
                        return target
        if target.is_symlink() or marker.is_symlink():
            raise ValueError("Arquivo de cache inseguro")
        with Image.open(source) as art:
            if art.format != "PNG":
                raise ValueError("Arte incompatível")
            art.load()
            generated = render_card(card, art)
        tmp = out / (name + ".on-demand.tmp")
        tag_tmp = out / (name + ".source-sha256.tmp")
        try:
            generated.save(tmp, format="PNG", optimize=True)
            if not 0 < tmp.stat().st_size <= 8_000_000:
                raise ValueError("Carta HD excede o tamanho permitido")
            tag_tmp.write_text(token, encoding="ascii")
            os.replace(tmp, target)
            os.replace(tag_tmp, marker)
        finally:
            tmp.unlink(missing_ok=True)
            tag_tmp.unlink(missing_ok=True)
    return target
