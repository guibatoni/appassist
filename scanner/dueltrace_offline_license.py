"""Offline, device-bound Ed25519 licenses for a future DUELTRACE edition.

Preview/Alpha behavior is unaffected: nothing in this module gates startup.
There are no network requests, IP tracking, telemetry or embedded secrets.
This verifier is deliberately fail-closed until a real public key is set.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from dueltrace_commercial_public_key import PUBLIC_KEY_B64

PRODUCT = "DUELTRACE"
EDITION = "commercial-lite"
SCHEMA = 1
MAX_LICENSE_BYTES = 8192
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
BASE64_PATTERN = re.compile(r"[A-Za-z0-9_-]+\Z")
ALLOWED_PAYLOAD = frozenset({
    "schema", "product", "edition", "license_id", "device_hash",
    "issued_on", "expires_on",
})
ALLOWED_DOCUMENT = frozenset({"payload", "signature"})


class LicenseError(ValueError):
    """Invalid, missing, or untrusted license. Never reveal raw license data."""


def canonical_bytes(payload: dict) -> bytes:
    if not isinstance(payload, dict):
        raise LicenseError("Dados da licença inválidos.")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _valid_hash(value: object) -> bool:
    return type(value) is str and HASH_PATTERN.fullmatch(value) is not None


def _valid_day(value: object) -> bool:
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def validate_payload(payload: object) -> dict:
    if not isinstance(payload, dict) or set(payload) != ALLOWED_PAYLOAD:
        raise LicenseError("Campos da licença inválidos.")
    if (type(payload["schema"]) is not int or payload["schema"] != SCHEMA
            or payload["product"] != PRODUCT
            or payload["edition"] != EDITION
            or not _valid_hash(payload["device_hash"])
            or not _valid_day(payload["issued_on"])):
        raise LicenseError("Licença incompatível.")
    if type(payload["license_id"]) is not str:
        raise LicenseError("Identificador de licença inválido.")
    try:
        if str(UUID(payload["license_id"])) != payload["license_id"]:
            raise ValueError()
    except ValueError as exc:
        raise LicenseError("Identificador de licença inválido.") from exc
    end = payload["expires_on"]
    if end is not None and (not _valid_day(end) or end < payload["issued_on"]):
        raise LicenseError("Validade da licença inválida.")
    return payload


def windows_device_hash() -> str:
    """Pseudonymous, product-scoped hash of Windows MachineGuid, not an IP."""
    if os.name != "nt":
        raise LicenseError("Ativação de dispositivo disponível somente no Windows.")
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Cryptography", 0,
                            winreg.KEY_READ) as key:
            guid, kind = winreg.QueryValueEx(key, "MachineGuid")
        if kind != winreg.REG_SZ or not isinstance(guid, str):
            raise ValueError("MachineGuid não é texto.")
        guid = guid.strip().lower()
        if not 8 <= len(guid) <= 100 or not re.fullmatch(r"[0-9a-f-]+", guid):
            raise ValueError("MachineGuid inválido.")
    except (OSError, ValueError) as exc:
        raise LicenseError("Não foi possível identificar este dispositivo.") from exc
    return hashlib.sha256(b"DUELTRACE-COMMERCIAL-LITE-V1\0" +
                          guid.encode("ascii")).hexdigest()


def activation_request(device_hash: str) -> dict:
    if not _valid_hash(device_hash):
        raise LicenseError("Identificação de dispositivo inválida.")
    return {"schema": SCHEMA, "product": PRODUCT, "edition": EDITION,
            "request_id": str(uuid4()), "device_hash": device_hash}


def _decode_public_key(key_b64: str) -> Ed25519PublicKey:
    if not isinstance(key_b64, str) or not key_b64:
        raise LicenseError("A chave pública comercial ainda não foi configurada.")
    try:
        key = base64.b64decode(key_b64, validate=True)
        if len(key) != 32:
            raise ValueError()
        return Ed25519PublicKey.from_public_bytes(key)
    except (ValueError, TypeError) as exc:
        raise LicenseError("Chave pública comercial inválida.") from exc


def verify_license(document: object, device_hash: str,
                   *, public_key_b64: str | None = None,
                   today: date | None = None) -> dict:
    """Verify signature before interpreting rights. Never trust caller payload."""
    if not _valid_hash(device_hash):
        raise LicenseError("Dispositivo inválido.")
    key = _decode_public_key(
        PUBLIC_KEY_B64 if public_key_b64 is None else public_key_b64)
    if not isinstance(document, dict) or set(document) != ALLOWED_DOCUMENT:
        raise LicenseError("Documento de licença inválido.")
    payload = document["payload"]
    signature_text = document["signature"]
    if (not isinstance(signature_text, str) or len(signature_text) != 86
            or not BASE64_PATTERN.fullmatch(signature_text)):
        raise LicenseError("Assinatura de licença inválida.")
    try:
        signature = base64.urlsafe_b64decode(signature_text + "==")
        if len(signature) != 64:
            raise ValueError()
        key.verify(signature, canonical_bytes(payload))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise LicenseError("Assinatura não reconhecida.") from exc
    payload = validate_payload(payload)
    if payload["device_hash"] != device_hash:
        raise LicenseError("Esta licença pertence a outro dispositivo.")
    now = today if today is not None else date.today()
    if payload["issued_on"] > now:
        raise LicenseError("Data de emissão incompatível.")
    if payload["expires_on"] is not None and now > date.fromisoformat(payload["expires_on"]):
        raise LicenseError("Licença expirada.")
    return {"active": True, "edition": EDITION,
            "licenseId": payload["license_id"], "expiresOn": payload["expires_on"]}


def read_license(path: Path, device_hash: str, *,
                 public_key_b64: str | None = None,
                 today: date | None = None) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_LICENSE_BYTES:
        raise LicenseError("Arquivo de licença ausente ou inválido.")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise LicenseError("Não foi possível ler a licença.") from exc
    return verify_license(document, device_hash,
                          public_key_b64=public_key_b64, today=today)


def license_path(data_home: Path) -> Path:
    return Path(data_home) / "commercial" / "license.json"


def install_license(document: object, data_home: Path, device_hash: str,
                    *, public_key_b64: str | None = None) -> dict:
    """Validate before writing; keep it OUTSIDE the install/update directory."""
    status = verify_license(document, device_hash, public_key_b64=public_key_b64)
    encoded = canonical_bytes(document)
    if len(encoded) > MAX_LICENSE_BYTES:
        raise LicenseError("Arquivo de licença excede o limite.")
    destination = license_path(data_home)
    folder = destination.parent
    if folder.is_symlink() or destination.is_symlink():
        raise LicenseError("Caminho de licença inválido.")
    folder.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=".license-", suffix=".tmp", dir=str(folder))
    try:
        with os.fdopen(handle, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, destination)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return status


def local_license_status(data_home: Path, *, device_hash: str | None = None,
                         public_key_b64: str | None = None) -> dict:
    """Nonblocking status for a future commercial UI; never gate Alpha."""
    path = license_path(data_home)
    if not path.exists():
        return {"active": False, "status": "not_activated"}
    try:
        fingerprint = device_hash or windows_device_hash()
        verified = read_license(path, fingerprint, public_key_b64=public_key_b64)
        return {"status": "active", **verified}
    except (LicenseError, OSError):
        return {"active": False, "status": "invalid"}
