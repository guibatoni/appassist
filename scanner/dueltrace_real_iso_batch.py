"""Batch reproducibility review for local ISO/BIN images and quarantine data.

Input manifest contains PRIVATE local paths. Output contains only hash/status
metadata; no gameplay profile, ROM content or reference evidence is exported.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dueltrace_real_iso_validation import (MAX_EXE_BYTES, MAX_IMAGE_BYTES,
    atomic_report, hash_local_file, safe_json_load,
    validate_real_iso_samples)

MAX_BATCH = 128


def run_batch(manifest: object) -> dict:
    output = {"schema": 1, "format": "dueltrace_iso_evidence_batch",
              "total": 0, "processed": 0, "results": [],
              "validationComplete": False, "anyModUniversallySupported": False,
              "inGameValidationClaimed": False, "mayActivate": False}
    if (not isinstance(manifest, dict) or manifest.get("schema") != 1
            or not isinstance(manifest.get("mods"), list)
            or not 1 <= len(manifest["mods"]) <= MAX_BATCH):
        raise ValueError("Manifesto invalido (1 a 128 mods)")
    output["total"] = len(manifest["mods"])
    seen = set()
    for record in manifest["mods"]:
        if not isinstance(record, dict):
            raise ValueError("Registro de mod invalido")
        image = record.get("image")
        if not isinstance(image, str) or not image or len(image) > 4096:
            raise ValueError("Caminho da imagem local invalido")
        image_path = Path(image).expanduser()
        if image_path.is_symlink():
            raise ValueError("Link simbolico para ISO nao permitido")
        image_sha = hash_local_file(image_path, max_bytes=MAX_IMAGE_BYTES)
        if image_sha in seen:
            raise ValueError("ISO duplicada no manifesto")
        seen.add(image_sha)
        row = {"romSha256": image_sha, "status": "sem_catalogo_candidato",
               "cardSamples": 0, "opponentSamples": 0, "divergences": 0,
               "imageHashChecked": True, "exeHashChecked": False,
               "mayActivate": False, "inGameValidationClaimed": False}
        candidate_file = record.get("candidate")
        observation_file = record.get("observations")
        if candidate_file is not None and observation_file is not None:
            if not all(isinstance(v, str) and 0 < len(v) <= 4096
                       for v in (candidate_file, observation_file)):
                raise ValueError("Caminho de evidencia invalido")
            exe_sha = None
            exe_file = record.get("exe")
            if exe_file is not None:
                if not isinstance(exe_file, str) or not 0 < len(exe_file) <= 4096:
                    raise ValueError("Caminho do executavel invalido")
                exe_sha = hash_local_file(Path(exe_file), max_bytes=MAX_EXE_BYTES)
                row["exeHashChecked"] = True
            candidate = safe_json_load(Path(candidate_file))
            observations = safe_json_load(Path(observation_file))
            evidence = validate_real_iso_samples(
                candidate, observations, image_sha256=image_sha, exe_sha256=exe_sha)
            row.update(status=evidence["status"],
                       cardSamples=evidence["observationsCount"],
                       opponentSamples=evidence["opponentsObserved"],
                       divergences=len(evidence["divergences"]))
        elif candidate_file is None and observation_file is None:
            row["status"] = "sem_catalogo_candidato"
        else:
            row["status"] = "evidencia_incompleta"
        output["results"].append(row)
    output["processed"] = len(output["results"])
    output["sampleCoherentCount"] = sum(
        x["status"] == "amostra_coerente_pendente_prova_completa"
        for x in output["results"])
    output["discrepancyCount"] = sum(
        x["status"] == "divergencias_detectadas" for x in output["results"])
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.manifest.expanduser().resolve() == args.output.expanduser().resolve():
        parser.error("Arquivo de saida deve ser separado do manifesto")
    manifest = safe_json_load(args.manifest)
    target = args.output.expanduser().resolve()
    if isinstance(manifest, dict) and isinstance(manifest.get("mods"), list):
        for item in manifest["mods"]:
            if isinstance(item, dict):
                for field in ("image", "candidate", "observations", "exe"):
                    value = item.get(field)
                    if (isinstance(value, str) and value
                            and target == Path(value).expanduser().resolve()):
                        parser.error("Saida nunca pode sobrescrever ISO ou evidencia")
    report = run_batch(manifest)
    atomic_report(target, report)
    print("ISOs analisadas:", report["processed"])
    print("Amostras coerentes (nao promovidas):", report["sampleCoherentCount"])
    print("Divergencias:", report["discrepancyCount"])
    return 0 if report["discrepancyCount"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
