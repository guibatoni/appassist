"""Inspeção técnica complementar de ROMs locais do Forbidden Memories.

Não envia dados à rede, nunca modifica a ROM, nunca transforma hipóteses
em tabelas de fusão/rank verificadas. Funciona sem IA externa.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from scanner_multiiso import Disc


def fusion_triplet_hypotheses(data: bytes, *, max_scan_bytes: int = 4_000_000,
                              min_run: int = 24, max_results: int = 8) -> list[dict]:
    """Procura *hipóteses* de tabelas (A,B,resultado) de u16 consecutivos.

    Um conjunto de números plausíveis NÃO comprova fusão; jamais usar como
    catálogo oficial sem confirmar contra o motor do jogo.
    """
    data = data[:max_scan_bytes]
    hypotheses = []
    if len(data) < min_run * 6:
        return hypotheses
    # Alinhamentos distintos; exigir sequências longas reduz coincidências.
    for alignment in (0, 2, 4):
        cursor = alignment
        while cursor + 6 * min_run <= len(data):
            start = cursor
            sample = []
            seen = set()
            while cursor + 6 <= len(data):
                a, b, c = struct.unpack_from("<HHH", data, cursor)
                if not (1 <= a <= 722 and 1 <= b <= 722 and 1 <= c <= 722):
                    break
                sample.append((a, b, c))
                seen.add((a, b, c))
                cursor += 6
                if len(sample) >= 100_000:
                    break
            if len(sample) >= min_run and len(seen) >= min_run:
                hypotheses.append({
                    "offset": start,
                    "entries": len(sample),
                    "unique": len(seen),
                    "examples": [{"a": a, "b": b, "result": c} for a, b, c in sample[:4]],
                    "status": "HIPÓTESE — NÃO VALIDADA / NÃO IMPORTADA",
                })
            # Próxima tentativa por 6 bytes, sem ficar preso à mesma sequência.
            cursor = max(start + 6, cursor + 6)
    # Intervalos podem ser encontrados em mais de um alinhamento: agrupar.
    result = []
    for h in sorted(hypotheses, key=lambda row: -row["entries"]):
        if all(abs(h["offset"] - prev["offset"]) > 10 for prev in result):
            result.append(h)
        if len(result) >= max_results:
            break
    return result


def investigate(rom_path: Path, profile: dict,
                output_path: Path | None = None) -> dict:
    rom_path = Path(rom_path)
    report = {
        "file": rom_path.name,
        "hash_rom": profile.get("rom_sha256"),
        "parser": "estrutura de disco PS1 + validação conservadora de tabelas",
        "internet": False,
        "rom_modified": False,
        "features": profile.get("verified", {}),
        "candidates": {"fusion_tables_u16": []},
        "uncertainties": [],
        "evidence": [],
        "recommendations": [],
    }
    verified = profile.get("verified", {})
    for key, desc in [
        ("cartas", "Tabela de cartas não validada"),
        ("oponentes", "Nomes dos oponentes não validados"),
        ("tabelas_drops", "Pesos de drops não validados"),
        ("nomes_dos_ranks", "Significado dos grupos/ranks não confirmado"),
        ("regras_de_pontuacao", "Fórmula de pontuação não extraída"),
        ("fusoes", "Tabela de fusões não extraída"),
    ]:
        v = str(verified.get(key, "pendente"))
        if not (v.startswith("verificado") or v == "extraídas"):
            report["uncertainties"].append({"field": key, "status": v, "reason": desc})
    disc = None
    try:
        disc = Disc(rom_path)
        report["evidence"].append({
            "type": "iso9660",
            "sector_bytes": disc.sector,
            "offset": disc.offset,
            "files": len(disc.files),
        })
        exes = [x for x in disc.files if x.startswith(("SLUS_", "SLES_", "SLPS_", "SLPM_", "SCUS_"))]
        if not exes:
            exes = [x for x in disc.files if x.endswith(".EXE")]
        for name in exes[:2]:
            executable = disc.get(name)
            report["evidence"].append({"type": "executable", "path": name, "bytes": len(executable)})
            hypotheses = fusion_triplet_hypotheses(executable)
            for h in hypotheses:
                h["source_file"] = name
            report["candidates"]["fusion_tables_u16"].extend(hypotheses)
        report["recommendations"].append(
            "Conferir qualquer candidata a tabela de fusões com casos de teste reais "
            "antes de habilitar fusões. Não importar hipóteses automaticamente."
        )
        if "WA_MRG.MRG" in disc.files:
            wa_lba, wa_size = disc.files["WA_MRG.MRG"]
            report["evidence"].append({
                "type": "data_container", "path": "WA_MRG.MRG",
                "lba": wa_lba, "bytes": wa_size,
            })
        else:
            report["recommendations"].append(
                "Container WA_MRG.MRG não encontrado com o nome esperado. "
                "A estrutura desta ROM requer adaptador específico."
            )
    except Exception as exc:
        report["uncertainties"].append({
            "field": "estrutura_disc",
            "status": "erro",
            "reason": f"{type(exc).__name__}: {exc}",
        })
    finally:
        if disc is not None:
            disc.close()
    report["recommendations"].append(
        "Uma ROM nova gera um perfil distinto por SHA-256. "
        "Dados sem evidências ficam desativados."
    )
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    return report
