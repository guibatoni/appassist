"""Upscaling conservador das artes extraídas da ISO, sem IA generativa.

Não reconstrói conteúdo inexistente e nunca altera os PNGs extraídos do mod.
Interpolação Lanczos 3x apenas das ilustrações 102x96, não dos textos/molduras
pixel-art do PS1. Cache SHA por arquivo e resultado atômico, sem rede.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

UPSCALE_REVISION = 1
UPSCALE_FACTOR = 3
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_ARTWORKS = 722
MANIFEST_FILE = "upscale-cache.json"
ART_ID = re.compile(r"[0-9]{3}\.png\Z")


def upscale_extracted_arts(originals: Path, output: Path) -> dict:
    """Idempotent processing for 722 exact PS1 artworks. Fails soft per card."""
    from PIL import Image, ImageFile
    originals = Path(originals).resolve(strict=True)
    output = Path(output)
    if not originals.is_dir() or output.is_symlink():
        raise ValueError("Diretório de artes original inválido.")
    output.mkdir(parents=True, exist_ok=True)
    output = output.resolve(strict=True)
    if output == originals or output.is_relative_to(originals):
        raise ValueError("Upscaling nunca deve substituir as artes originais.")
    if originals.is_relative_to(output):
        raise ValueError("Diretório de saída inválido.")
    manifest_path = output / MANIFEST_FILE
    try:
        if manifest_path.is_symlink() or manifest_path.stat().st_size > 512 * 1024:
            raise ValueError("Manifesto inválido.")
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        old = {}
    cache = (old.get("files", {}) if isinstance(old, dict)
             and old.get("revision") == UPSCALE_REVISION
             and old.get("factor") == UPSCALE_FACTOR else {})
    if not isinstance(cache, dict):
        cache = {}
    updated = {}
    counts = {"generated": 0, "cached": 0, "failed": 0, "available": 0}
    warnings = []
    for cid in range(1, MAX_ARTWORKS + 1):
        name = f"{cid:03d}.png"
        original = originals / name
        if not original.is_file() or original.is_symlink():
            continue
        try:
            if not 0 < original.stat().st_size <= MAX_INPUT_BYTES:
                raise ValueError("Arte de tamanho inválido.")
            content_hash = hashlib.sha256(original.read_bytes()).hexdigest()
            result = output / name
            token = str(UPSCALE_REVISION) + ":" + str(UPSCALE_FACTOR) + ":" + content_hash
            if (cache.get(name) == token and result.is_file()
                    and not result.is_symlink()
                    and 0 < result.stat().st_size <= MAX_OUTPUT_BYTES):
                # Detect damaged cache entries without decoding every asset.
                with Image.open(result) as test:
                    if test.size == (102 * UPSCALE_FACTOR, 96 * UPSCALE_FACTOR):
                        updated[name] = token
                        counts["cached"] += 1
                        counts["available"] += 1
                        continue
            if result.is_symlink():
                raise ValueError("Arte melhorada contém link simbólico.")
            # Verified original dimensions prevent images from other mods
            # being silently interpreted as this ISO's PS1 artwork.
            with Image.open(original) as image:
                if image.format != "PNG" or image.size != (102, 96):
                    raise ValueError("Arte não corresponde ao formato original.")
                image.load()
                # Palette artwork -> RGB. Lanczos preserves outlines and
                # color changes; no hallucinating model or aggressive sharpen.
                resized = image.convert("RGB").resize(
                    (102 * UPSCALE_FACTOR, 96 * UPSCALE_FACTOR),
                    resample=Image.Resampling.LANCZOS)
            temporary = output / (name + ".tmp")
            try:
                resized.save(temporary, format="PNG", optimize=True)
                if not 0 < temporary.stat().st_size <= MAX_OUTPUT_BYTES:
                    raise ValueError("Saída excedeu o limite de arte.")
                os.replace(temporary, result)
            finally:
                temporary.unlink(missing_ok=True)
            updated[name] = token
            counts["generated"] += 1
            counts["available"] += 1
        except (OSError, ValueError, SyntaxError) as exc:
            counts["failed"] += 1
            if len(warnings) < 12:
                warnings.append(f"ID {cid}: {str(exc)[:100]}")
    manifest = {
        "schema": 1, "revision": UPSCALE_REVISION,
        "factor": UPSCALE_FACTOR, "algorithm": "Pillow Lanczos 3x",
        "files": updated,
    }
    pending = output / (MANIFEST_FILE + ".tmp")
    try:
        pending.write_text(json.dumps(manifest, separators=(",", ":")),
                           encoding="utf-8")
        os.replace(pending, manifest_path)
    finally:
        pending.unlink(missing_ok=True)
    return {"factor": UPSCALE_FACTOR, **counts, "warnings": warnings,
            "mode": "upscale_local_sem_ia", "originalsPreserved": True}
