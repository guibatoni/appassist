"""Auditoria integral e somente leitura dos dois arquivos centrais do Forbidden Memories.

Lê a imagem ISO/BIN local via ISO9660; não distribui nem modifica o jogo.
Não interpreta dados binários desconhecidos como efeitos confirmados.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scanner_multiiso import Disc, decode_names
from effects_audit import find_fm_text_candidates

TARGETS = ("DATA/WA_MRG.MRG", "DATA/SLUS_014.11")
CHUNK = 4 * 1024 * 1024


def read_target(disc: Disc, name: str) -> tuple[bytes, dict]:
    """Lê todos os bytes lógicos do arquivo; não faz amostragem."""
    if name not in disc.files:
        return b"", {"path": name, "status": "ausente"}
    lba, size = disc.files[name]
    if size < 1:
        return b"", {"path": name, "status": "vazio", "size": size}
    # Disc.read aplica a conversão de setores 2352/2048, sem ler o cabeçalho de CD.
    # O limite explícito protege contra tabelas ISO9660 corrompidas.
    if size > 256 * 1024 * 1024:
        return b"", {"path": name, "status": "limite_excedido", "size": size}
    content = bytearray()
    h = hashlib.sha256()
    for offset in range(0, size, CHUNK):
        # O CD é endereçado em setores de 2048 bytes.
        block = disc.read(lba + offset // 2048, min(CHUNK, size - offset))
        if len(block) != min(CHUNK, size - offset):
            raise ValueError(f"Leitura incompleta: {name} em {offset}")
        h.update(block)
        content.extend(block)
    return bytes(content), {
        "path": name, "status": "lido_integralmente", "size": size,
        "bytes_read": len(content), "sha256": h.hexdigest(),
    }


def audit_image(path: Path) -> dict:
    path = Path(path)
    disc = Disc(path)
    try:
        sources = {}
        raw = {}
        for name in TARGETS:
            data, report = read_target(disc, name)
            raw[name], sources[name] = data, report
        executable = raw[TARGETS[1]]
        wa = raw[TARGETS[0]]
        result = {
            "schema": 1,
            "source_image": path.name,
            "targets": sources,
            "card_records": [],
            "opponent_records": [],
            "unmapped_text_candidates": [],
            "art_layout": {"status": "nao_confirmado_para_este_mod"},
            "card_frames": {"status": "localizacao_e_paleta_nao_validadas"},
            "effects": {"status": "sem_mapeamento_confirmado_id_efeito"},
        }
        if executable:
            opponents, cards, diagnostic = decode_names(executable)
            result["executable_diagnostic"] = diagnostic
            result["card_records"] = [
                {"id": c["id"], "name": c["nome"], "atk": c["atk"],
                 "def": c["def"], "type_id": c["tipo"],
                 "source": TARGETS[1], "confidence": "layout_fm_conhecido"}
                for c in cards
            ]
            result["opponent_records"] = opponents
            result["unmapped_text_candidates"] = find_fm_text_candidates(
                executable, max_index=3000
            )
        if wa:
            # O scanner já contém o decodificador de artes com 7 setores por
            # carta, mas a moldura completa NÃO foi validada como parte do
            # mesmo bloco. Não inventamos offsets, paletas ou correspondências.
            expected_end = ((722 - 1) * 7 + 722) * 2048 + 0x2840
            result["art_layout"] = {
                "status": ("intervalo_compativel_com_layout_conhecido"
                           if len(wa) >= expected_end
                           else "intervalo_insuficiente"),
                "cards_expected": 722,
                "pixel_size": [102, 96],
                "source": TARGETS[0],
                "requires_visual_validation": True,
            }
        return result
    finally:
        disc.close()


def main() -> None:
    cli = argparse.ArgumentParser(
        description="Auditoria integral de WA_MRG.MRG e SLUS_014.11"
    )
    cli.add_argument("image", type=Path)
    cli.add_argument("--out", type=Path, default=Path("auditoria_data.json"))
    args = cli.parse_args()
    report = audit_image(args.image)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"Relatório: {args.out.resolve()}")


if __name__ == "__main__":
    main()
