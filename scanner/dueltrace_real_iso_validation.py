"""Local evidence review for DUELTRACE quarantined card and opponent catalogues.

This is NOT a catalogue importer, a MIPS execution proof or a compatibility
unlocker. A sample comparison never establishes all 722 identities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
CARD_COUNT = 722
OPPONENT_COUNT = 39
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 1_000_000_000
MAX_EXE_BYTES = 8 * 1024 * 1024
MAX_OBSERVATIONS = CARD_COUNT
MIN_SPREAD_SAMPLE = 12


def _sha(value: object) -> bool:
    return isinstance(value, str) and SHA_RE.fullmatch(value) is not None


def _integer(value: object, lo: int, hi: int) -> bool:
    return type(value) is int and lo <= value <= hi


def _same_name(a: object, b: object) -> bool:
    """Ignore case/spacing, never strip odd glyphs or trailing letters."""
    return (isinstance(a, str) and isinstance(b, str) and bool(a.strip())
            and bool(b.strip())
            and " ".join(a.split()).casefold() == " ".join(b.split()).casefold())


def _plausible_name(value: object) -> bool:
    return (isinstance(value, str) and 0 < len(value.strip()) <= 64
            and "\ufffd" not in value
            and not any(ord(c) < 32 for c in value))


def _candidate_valid(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    if (data.get("status") != "catalogo_candidato_reconstruido"
            or not _sha(data.get("romSha256"))
            or not _sha(data.get("exeSha256"))
            or data.get("validated") is not False
            or data.get("inGameVerified") is not False
            or data.get("mayActivate") is not False
            or data.get("cardsCount") != CARD_COUNT
            or data.get("opponentsCount") != OPPONENT_COUNT):
        return False
    cards, opponents = data.get("cards"), data.get("opponents")
    if not isinstance(cards, list) or not isinstance(opponents, list):
        return False
    if len(cards) != CARD_COUNT or len(opponents) != OPPONENT_COUNT:
        return False
    for expected_id, row in enumerate(cards, 1):
        if (not isinstance(row, dict)
                or not _integer(row.get("id"), expected_id, expected_id)
                or not _plausible_name(row.get("nome"))
                or not _integer(row.get("atk"), 0, 5110)
                or not _integer(row.get("def"), 0, 5110)
                or not _integer(row.get("tipo"), 0, 31)):
            return False
    for expected_id, row in enumerate(opponents, 1):
        if (not isinstance(row, dict)
                or not _integer(row.get("id"), expected_id, expected_id)
                or not _plausible_name(row.get("nome"))):
            return False
    return True


def _base_report() -> dict:
    return {"schema": 2, "format": "dueltrace_real_iso_sample_validation",
            "status": "entrada_invalida", "romSha256": None, "exeSha256": None,
            "observationsCount": 0, "matchedCount": 0, "mismatchedCount": 0,
            "typeComparedCount": 0, "quartileCoverage": [0, 0, 0, 0],
            "opponentsObserved": 0, "opponentsMatched": 0,
            "opponentsMismatched": 0, "divergences": [],
            "imageHashChecked": False, "exeHashChecked": False,
            "inGameValidationClaimed": False, "mayActivate": False,
            "promoted": False,
            "note": "Amostras nao provam a identidade dos 722 IDs nem execucao MIPS."}


def validate_real_iso_samples(candidate: object, observations: object,
                              *, image_sha256: str | None = None,
                              exe_sha256: str | None = None) -> dict:
    """Compare two independent reports, strictly tied to this ISO and EXE.

    User-provided 'source' and 'evidenceRef' are declarations, not proof.
    Evidence text and card/opponent names never enter the compact report.
    """
    report = _base_report()
    if not _candidate_valid(candidate):
        report["status"] = "catalogo_candidato_invalido"
        return report
    report["romSha256"] = candidate["romSha256"]
    report["exeSha256"] = candidate["exeSha256"]
    if image_sha256 is not None:
        report["imageHashChecked"] = True
        if image_sha256 != candidate["romSha256"]:
            report["status"] = "iso_arquivo_divergente"
            return report
    if exe_sha256 is not None:
        report["exeHashChecked"] = True
        if exe_sha256 != candidate["exeSha256"]:
            report["status"] = "executavel_arquivo_divergente"
            return report
    if (not isinstance(observations, dict)
            or observations.get("schema") != 1
            or observations.get("source") != "epsxe_observacao_independente"
            or not _sha(observations.get("romSha256"))):
        return report
    if observations["romSha256"] != candidate["romSha256"]:
        report["status"] = "iso_sha_divergente"
        return report
    if ("exeSha256" in observations
            and observations["exeSha256"] != candidate["exeSha256"]):
        report["status"] = "executavel_sha_divergente"
        return report

    rows, opp_rows = observations.get("cards"), observations.get("opponents", [])
    if (not isinstance(rows, list) or not 1 <= len(rows) <= MAX_OBSERVATIONS
            or not isinstance(opp_rows, list) or len(opp_rows) > OPPONENT_COUNT):
        return report
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not _integer(row.get("id"), 1, CARD_COUNT):
            return report
        if row["id"] in seen:
            report["status"] = "observacoes_duplicadas"
            return report
        seen.add(row["id"])
        if (not _plausible_name(row.get("nome"))
                or not all(_integer(row.get(k), 0, 9999) for k in ("atk", "def"))
                or ("tipo" in row and not _integer(row["tipo"], 0, 31))):
            return report
        if (not isinstance(row.get("evidenceRef"), str)
                or not 1 <= len(row["evidenceRef"].strip()) <= 128):
            report["status"] = "referencia_evidencia_ausente"
            return report
    seen_opp = set()
    for row in opp_rows:
        if (not isinstance(row, dict)
                or not _integer(row.get("id"), 1, OPPONENT_COUNT)
                or not _plausible_name(row.get("nome"))
                or not isinstance(row.get("evidenceRef"), str)
                or not 1 <= len(row["evidenceRef"].strip()) <= 128):
            report["status"] = "observacao_oponente_invalida"
            return report
        if row["id"] in seen_opp:
            report["status"] = "oponentes_duplicados"
            return report
        seen_opp.add(row["id"])
    matched = types_compared = opponents_matched = 0
    quartiles = [0, 0, 0, 0]
    divergences = []
    for row in rows:
        cid = row["id"]
        quartiles[min(3, (cid - 1) * 4 // CARD_COUNT)] += 1
        card = candidate["cards"][cid - 1]
        issues = []
        if not _same_name(row["nome"], card["nome"]):
            issues.append("nome")
        for key in ("atk", "def"):
            if row[key] != card[key]:
                issues.append(key)
        if "tipo" in row:
            types_compared += 1
            if row["tipo"] != card["tipo"]:
                issues.append("tipo")
        if issues:
            divergences.append({"id": cid, "fields": issues})
        else:
            matched += 1
    for row in opp_rows:
        opponent = candidate["opponents"][row["id"] - 1]
        if not _same_name(row["nome"], opponent["nome"]):
            divergences.append({"opponentId": row["id"], "fields": ["nome"]})
        else:
            opponents_matched += 1
    mismatch_cards = sum("id" in x for x in divergences)
    report.update(observationsCount=len(rows), matchedCount=matched,
                  mismatchedCount=mismatch_cards,
                  typeComparedCount=types_compared,
                  quartileCoverage=quartiles,
                  opponentsObserved=len(opp_rows),
                  opponentsMatched=opponents_matched,
                  opponentsMismatched=len(opp_rows) - opponents_matched,
                  divergences=sorted(divergences, key=lambda x: ("opponentId" in x,
                              x.get("id", x.get("opponentId")))))
    if divergences:
        report["status"] = "divergencias_detectadas"
    elif len(rows) < MIN_SPREAD_SAMPLE or min(quartiles) < 2:
        report["status"] = "amostra_coerente_mas_insuficiente"
    else:
        report["status"] = "amostra_coerente_pendente_prova_completa"
    return report


def safe_json_load(path: Path) -> object:
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("JSON ausente ou maior que 4 MiB")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def hash_local_file(path: Path, *, max_bytes: int) -> str:
    """Hash full file, read-only, with a basic file-change check."""
    source = Path(path).expanduser()
    if source.is_symlink():
        raise ValueError("Link simbolico nao permitido")
    path = source.resolve(strict=True)
    if not path.is_file():
        raise ValueError("Arquivo local indisponivel")
    before = path.stat()
    if not 0 < before.st_size <= max_bytes:
        raise ValueError("Arquivo fora do limite de tamanho")
    h = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
            count += len(block)
            if count > max_bytes:
                raise ValueError("Arquivo cresceu alem do limite")
    after = path.stat()
    if (count != before.st_size or count != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns):
        raise ValueError("Arquivo alterado durante validacao")
    return h.hexdigest()


def atomic_report(path: Path, data: dict) -> None:
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=path.parent, prefix=".dueltrace-evidence-",
                                         suffix=".tmp", delete=False) as handle:
            tmp_name = handle.name
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def validate_files(candidate: Path, observations: Path,
                   *, iso: Path | None = None, exe: Path | None = None) -> dict:
    digest_iso = hash_local_file(iso, max_bytes=MAX_IMAGE_BYTES) if iso else None
    digest_exe = hash_local_file(exe, max_bytes=MAX_EXE_BYTES) if exe else None
    return validate_real_iso_samples(safe_json_load(candidate),
                                     safe_json_load(observations),
                                     image_sha256=digest_iso, exe_sha256=digest_exe)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iso", type=Path,
                        help="Verifica a SHA-256 do arquivo ISO/BIN local")
    parser.add_argument("--exe", type=Path,
                        help="Verifica a SHA-256 do EXE extraido da mesma ISO")
    args = parser.parse_args(argv)
    paths = [Path(p).expanduser().resolve() for p in
             (args.candidate, args.observations, args.output)]
    if len(set(paths)) != 3 or paths[2] in {Path(p).expanduser().resolve()
                                           for p in (args.iso, args.exe) if p}:
        parser.error("Entradas e saida devem ter caminhos distintos")
    report = validate_files(paths[0], paths[1], iso=args.iso, exe=args.exe)
    atomic_report(paths[2], report)
    print(report["status"])
    print("IDs conferidos:", report["observationsCount"])
    print("Divergencias:", len(report["divergences"]))
    print("Relatorio:", paths[2])
    return 0 if report["status"] == "amostra_coerente_pendente_prova_completa" else 2


if __name__ == "__main__":
    raise SystemExit(main())
