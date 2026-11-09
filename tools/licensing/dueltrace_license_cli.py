#!/usr/bin/env python3
"""Offline-only Batoni Dev license issuer; NEVER include this file in a release.

Commands:
  keygen --private <private.pem> --public <public.txt>
  request --output <request.json>               (customer's Windows machine)
  issue --private <private.pem> --request <request.json> --output <license.json>
  verify --public <public.txt> --license <license.json> --request <request.json>

The Ed25519 private key is encrypted with a passphrase and kept OFFLINE.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import sys
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scanner"))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from dueltrace_offline_license import (
    PRODUCT, EDITION, SCHEMA, HASH_PATTERN, canonical_bytes,
    activation_request, windows_device_hash, verify_license,
    validate_payload, LicenseError,
)


def _new_file(path: Path, content: bytes, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if private else 0o644)
    with os.fdopen(fd, "wb") as output:
        output.write(content)
    if private and os.name != "nt":
        os.chmod(path, 0o600)


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
        raise LicenseError("Arquivo de entrada ausente ou grande demais.")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise LicenseError("Documento JSON inválido.")
    return doc


def _read_request(path: Path) -> dict:
    request = _read_json(path)
    if (set(request) != {"schema", "product", "edition", "request_id", "device_hash"}
            or type(request["schema"]) is not int or request["schema"] != SCHEMA
            or request["product"] != PRODUCT or request["edition"] != EDITION
            or type(request["device_hash"]) is not str
            or not HASH_PATTERN.fullmatch(request["device_hash"])):
        raise LicenseError("Solicitação de ativação inválida.")
    try:
        if str(UUID(request["request_id"])) != request["request_id"]:
            raise ValueError()
    except (ValueError, TypeError, KeyError) as exc:
        raise LicenseError("Identificador de solicitação inválido.") from exc
    return request


def _keygen(private_path: Path, public_path: Path) -> None:
    if private_path.resolve() == public_path.resolve() or private_path.exists() or public_path.exists():
        raise LicenseError("Arquivos já existem; não substitua chaves.")
    password = getpass.getpass("Crie uma senha forte para a chave PRIVADA: ").encode()
    confirm = getpass.getpass("Repita a senha: ").encode()
    if len(password) < 16 or password != confirm:
        raise LicenseError("Use uma senha de pelo menos 16 caracteres, idêntica nas duas entradas.")
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )
    pub_bytes = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    _new_file(private_path, pem, private=True)
    _new_file(public_path, base64.b64encode(pub_bytes) + b"\n")
    print("Chaves geradas offline. O arquivo PRIVADO nunca deve ser enviado ou publicado.")
    print("Copie apenas o conteúdo de", public_path, "para PUBLIC_KEY_B64 na edição comercial.")


def _issue(private_path: Path, request_path: Path, output: Path,
           expires: str | None) -> None:
    request = _read_request(request_path)
    private_bytes = private_path.read_bytes()
    password = getpass.getpass("Senha da chave privada offline: ").encode()
    try:
        private = serialization.load_pem_private_key(private_bytes, password=password)
    except (ValueError, TypeError) as exc:
        raise LicenseError("Chave privada ou senha inválida.") from exc
    if not isinstance(private, Ed25519PrivateKey):
        raise LicenseError("A chave deve usar Ed25519.")
    payload = {
        "schema": SCHEMA, "product": PRODUCT, "edition": EDITION,
        "license_id": str(uuid4()),
        "device_hash": request["device_hash"],
        "issued_on": date.today().isoformat(),
        "expires_on": expires,
    }
    validate_payload(payload)
    signature = private.sign(canonical_bytes(payload))
    token = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    license_doc = {"payload": payload, "signature": token}
    _new_file(output, canonical_bytes(license_doc) + b"\n")
    print("Licença emitida offline; envie somente", output.name, "ao comprador.")
    print("Registre o license_id no seu controle de vendas:", payload["license_id"])


def _verify(public_path: Path, license_file: Path, request_path: Path) -> None:
    request = _read_request(request_path)
    document = _read_json(license_file)
    public_key_b64 = public_path.read_text(encoding="ascii").strip()
    response = verify_license(document, request["device_hash"],
                              public_key_b64=public_key_b64)
    print("Licença válida:", response["licenseId"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Batoni Dev — licenças offline")
    sub = parser.add_subparsers(dest="action", required=True)
    keygen = sub.add_parser("keygen", help="Gerar chave privada e pública offline")
    keygen.add_argument("--private", type=Path, required=True)
    keygen.add_argument("--public", type=Path, required=True)
    request = sub.add_parser("request", help="Gerar solicitação no PC do cliente")
    request.add_argument("--output", type=Path, required=True)
    issue = sub.add_parser("issue", help="Assinar licença a partir de solicitação")
    issue.add_argument("--private", type=Path, required=True)
    issue.add_argument("--request", type=Path, required=True)
    issue.add_argument("--output", type=Path, required=True)
    issue.add_argument("--expires", default=None, help="Data opcional AAAA-MM-DD")
    verify = sub.add_parser("verify", help="Validar licença emitida")
    verify.add_argument("--public", type=Path, required=True)
    verify.add_argument("--license", type=Path, required=True)
    verify.add_argument("--request", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "keygen":
            _keygen(args.private, args.public)
        elif args.action == "request":
            _new_file(args.output, canonical_bytes(
                activation_request(windows_device_hash())) + b"\n")
            print("Solicitação criada:", args.output)
        elif args.action == "issue":
            _issue(args.private, args.request, args.output, args.expires)
        elif args.action == "verify":
            _verify(args.public, args.license, args.request)
    except (LicenseError, OSError, ValueError) as exc:
        print("Falha:", str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
