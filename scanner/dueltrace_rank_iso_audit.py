"""Diagnóstico local da ISO (BIN/ISO) para o DUELTRACE v0.7.5.

Ex.: python scanner/dueltrace_rank_iso_audit.py "D:\Jogos\MeuMod.bin"
Não modifica a imagem e não envia ROM, nomes, arte ou códigos para a rede.
Exibe um JSON enxuto com hashes e integridade das tabelas de pontuação.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from scanner_multiiso import process


def inspect_local_iso(path: Path) -> dict:
    path=Path(path).expanduser().resolve(strict=True)
    if path.suffix.casefold() not in (".bin",".iso"):
        raise ValueError("Selecione uma imagem de disco .bin ou .iso.")
    if path.stat().st_size>2*1024*1024*1024:
        raise ValueError("Imagem acima do limite de 2 GiB para análise local.")
    with tempfile.TemporaryDirectory(prefix="dueltrace_rank_audit_") as temp:
        analysis=process(path,Path(temp),with_art=False)
    rank=analysis.get("rank_analysis") or {}
    return {
        "schema":1,
        "rom_sha256":analysis.get("sha256"),
        "slus_sha256":analysis.get("hash_executavel"),
        "wa_prefix_sha256":analysis.get("hash_wa_prefix"),
        "wa_bytes_analyzed":analysis.get("wa_prefix_bytes"),
        "status":analysis.get("status"),
        "opponents_detected":analysis.get("oponentes",0),
        "drops_detected":analysis.get("drops",0),
        "drop_tables":analysis.get("tabelas_drops",0),
        "rank_table":rank,
        "no_iso_content_exported":True,
    }


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("iso",type=Path,help="Imagem local .bin ou .iso")
    ap.add_argument("--report",type=Path,default=None,
                    help="Salvar relatório em JSON (sem arquivos originais)")
    args=ap.parse_args()
    summary=inspect_local_iso(args.iso)
    body=json.dumps(summary,ensure_ascii=False,indent=2)
    print(body)
    if args.report:
        target=args.report.expanduser().resolve()
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(body+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
