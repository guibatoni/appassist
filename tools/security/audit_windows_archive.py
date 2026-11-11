"""Auditoria offline do conteúdo exato de um ZIP Windows antes de publicá-lo."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

LIMIT = 1024 * 1024 * 1024
GAME_FILE = re.compile(r"^(?:WA_MRG\.MRG|SLUS_014\.11)$", re.I)
# Executable Windows package must never embed user ROMs, saves or disc images.
GAME_SUFFIXES = {".iso", ".bin", ".img", ".cue", ".chd", ".ccd", ".mcr", ".mcd", ".sav", ".state"}
SECRET_SUFFIXES = {".pfx", ".p12", ".pem", ".key"}
SOURCE_SUFFIXES = {".py", ".pyc", ".pyo", ".ps1", ".cmd", ".sh"}


def _sha256(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def audit_zip(directory: Path, archive: Path) -> dict:
    directory = directory.resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("Pasta de distribuição inválida.")
    expected = {}
    for file in directory.rglob("*"):
        if file.is_symlink():
            raise ValueError("Links simbólicos não são permitidos.")
        if not file.is_file():
            continue
        relative = file.relative_to(directory).as_posix()
        _check_name(relative)
        expected[relative] = file
    if "DUELTRACE-WebUI.exe" not in expected:
        raise ValueError("Executável ausente na pasta.")
    observed = set()
    total = 0
    with zipfile.ZipFile(archive, "r") as z:
        for entry in z.infolist():
            name = entry.filename
            _check_name(name)
            if entry.is_dir():
                continue
            if name in observed:
                raise ValueError("Entrada duplicada no arquivo compactado.")
            observed.add(name)
            file = expected.get(name)
            if file is None:
                raise ValueError("ZIP contém arquivo não examinado.")
            if file.stat().st_size != entry.file_size:
                raise ValueError("ZIP diverge da pasta aprovada em tamanho.")
            total += entry.file_size
            if total > LIMIT:
                raise ValueError("Tamanho descompactado excede limite.")
            with z.open(entry, "r") as src, file.open("rb") as local:
                if _sha256(src) != _sha256(local):
                    raise ValueError("ZIP diverge da pasta aprovada em SHA-256.")
    if observed != set(expected):
        raise ValueError("ZIP não inclui todos os arquivos examinados.")
    with archive.open("rb") as package:
        package_sha256 = _sha256(package)
    return {
        "schema": 1,
        "status": "zip_matches_local_build",
        "files_verified": len(observed),
        "bytes_uncompressed": total,
        "zip_sha256": package_sha256,
        "authenticode_signature_verified": False,
        "note": "Integridade não prova autoria nem ausência de malware.",
    }


def _check_name(name: str) -> None:
    if not name or "\\" in name or ":" in name or name.startswith("/"):
        raise ValueError("Caminho inválido no pacote.")
    parts = name.rstrip("/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Travessia de caminhos no pacote.")
    leaf = parts[-1]
    suffix = PurePosixPath(leaf).suffix.lower()
    if GAME_FILE.fullmatch(leaf) or suffix in GAME_SUFFIXES:
        raise ValueError("Arquivo privado do jogo dentro do pacote.")
    if suffix in SECRET_SUFFIXES or leaf.lower() in (".env", "id_rsa"):
        raise ValueError("Possível chave ou segredo dentro do pacote.")
    if suffix in SOURCE_SUFFIXES:
        raise ValueError("Código-fonte ou script de desenvolvimento no ZIP de clientes.")
    if any(part.casefold() in (".git", "__pycache__", "tests", "user_data",
                               "backups", "private", "analises")
           for part in parts):
        raise ValueError("Diretório privado ou de desenvolvimento no ZIP.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = audit_zip(args.directory, args.archive)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("ZIP validado contra pasta examinada:", result["files_verified"], "arquivos")


if __name__ == "__main__":
    main()
