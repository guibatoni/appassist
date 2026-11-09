"""Batoni Dev License Manager — offline issuance and minimal local ledger.

No network, no service, no default/example signing keys. Never import this
module into the customer executable. Private key remains password-encrypted
inside the Windows USER profile and is never returned to the UI.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dueltrace_offline_license import (
    PRODUCT, EDITION, SCHEMA, MAX_LICENSE_BYTES, HASH_PATTERN,
    LicenseError, canonical_bytes, validate_payload, verify_license,
)

MAX_REQUEST_BYTES = 8192
MAX_LEDGER_BYTES = 4_000_000
MAX_DEVICES_PER_ORDER = 2
ORDER_RE = re.compile(r"[A-Z0-9][A-Z0-9._-]{2,63}\Z")
REQUEST_FIELDS = frozenset(
    ("schema", "product", "edition", "request_id", "device_hash"))
LEDGER_FIELDS = frozenset(
    ("order_ref", "license_id", "request_id", "device_hash",
     "issued_on", "expires_on"))


def default_admin_home() -> Path:
    """Always keep owner secrets outside source, installers and GitHub."""
    if os.name != "nt":
        raise LicenseError("O Gerenciador Batoni Dev funciona apenas no Windows.")
    root = os.environ.get("LOCALAPPDATA")
    if not root:
        raise LicenseError("Pasta LocalAppData indisponível.")
    return Path(root) / "BatoniDev" / "LicenseManager"


def admin_paths(home: Path) -> dict[str, Path]:
    root = Path(home)
    return {
        "root": root,
        "private": root / "secrets" / "issuer_ed25519_private.pem",
        "public": root / "public" / "issuer_ed25519_public.txt",
        "ledger": root / "ledger.json",
        "issued": root / "issued",
        "lock": root / ".issue.lock",
    }


def _not_link(path: Path) -> None:
    if path.is_symlink():
        raise LicenseError("Caminho com link simbólico não permitido.")


def _ensure_parent(path: Path) -> None:
    parent = path.parent
    _not_link(parent)
    parent.mkdir(parents=True, exist_ok=True)
    _not_link(parent)


def _write_new(path: Path, content: bytes, *, private: bool = False) -> None:
    _not_link(path)
    _ensure_parent(path)
    mode = 0o600 if private else 0o644
    try:
        descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
    except FileExistsError as exc:
        raise LicenseError("Arquivo já existe. Não é permitido substituir.") from exc
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _read_small(path: Path, limit: int) -> bytes:
    _not_link(path)
    try:
        if not path.is_file() or path.stat().st_size > limit:
            raise LicenseError("Arquivo inválido ou excede limite de tamanho.")
        raw = path.read_bytes()
    except OSError as exc:
        raise LicenseError("Arquivo não pode ser lido.") from exc
    if len(raw) > limit:
        raise LicenseError("Arquivo excede o tamanho permitido.")
    return raw


def _public_b64(home: Path) -> str:
    raw = _read_small(admin_paths(home)["public"], 100).strip()
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise LicenseError("Chave pública inválida.") from exc
    if len(decoded) != 32:
        raise LicenseError("Chave pública incompatível.")
    return raw.decode("ascii")


def has_keys(home: Path) -> bool:
    paths = admin_paths(home)
    return paths["private"].is_file() and paths["public"].is_file()


def _private_key(home: Path, password: str) -> Ed25519PrivateKey:
    if type(password) is not str or not password:
        raise LicenseError("Informe a senha da chave privada.")
    raw = _read_small(admin_paths(home)["private"], 8192)
    try:
        loaded = serialization.load_pem_private_key(raw, password=password.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise LicenseError("Senha incorreta ou chave privada inválida.") from exc
    if not isinstance(loaded, Ed25519PrivateKey):
        raise LicenseError("Tipo de chave privada incorreto.")
    return loaded


def _derived_public_b64(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def create_keys(home: Path, password: str, confirmation: str) -> str:
    """Create once; no reset button and no private export through the UI."""
    paths = admin_paths(home)
    if paths["private"].exists() or paths["public"].exists():
        raise LicenseError("Chaves já existentes. Nunca crie outra chave sobre a atual.")
    if (type(password) is not str or type(confirmation) is not str
            or len(password.encode("utf-8")) < 16 or password != confirmation):
        raise LicenseError("Use uma senha de pelo menos 16 bytes e confirme-a.")
    key = Ed25519PrivateKey.generate()
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(
            password.encode("utf-8")))
    public = _derived_public_b64(key)
    _write_new(paths["private"], private_pem, private=True)
    # A crash here intentionally leaves the private key for recovery.
    _write_new(paths["public"], (public + "\n").encode("ascii"), private=True)
    return public


def recover_public_key(home: Path, password: str) -> str:
    paths = admin_paths(home)
    if paths["public"].exists():
        raise LicenseError("A chave pública já existe; recuperação desnecessária.")
    key = _private_key(home, password)
    pub = _derived_public_b64(key)
    _write_new(paths["public"], (pub + "\n").encode("ascii"), private=True)
    return pub


def check_password(home: Path, password: str) -> bool:
    key = _private_key(home, password)
    if _derived_public_b64(key) != _public_b64(home):
        raise LicenseError("Chaves privada e pública não correspondem.")
    return True


def read_request(raw: bytes | str) -> dict:
    if type(raw) is str:
        raw = raw.encode("utf-8")
    if type(raw) is not bytes or len(raw) > MAX_REQUEST_BYTES:
        raise LicenseError("Pedido de ativação inválido ou excede 8 KB.")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise LicenseError("Pedido de ativação não é um JSON válido.") from exc
    if (not isinstance(data, dict) or set(data) != REQUEST_FIELDS
            or type(data["schema"]) is not int or data["schema"] != SCHEMA
            or data["product"] != PRODUCT or data["edition"] != EDITION
            or type(data["device_hash"]) is not str
            or HASH_PATTERN.fullmatch(data["device_hash"]) is None
            or type(data["request_id"]) is not str):
        raise LicenseError("Pedido de ativação não pertence ao DUELTRACE.")
    try:
        if str(UUID(data["request_id"])) != data["request_id"]:
            raise ValueError("UUID não canônico")
    except ValueError as exc:
        raise LicenseError("Identificador do pedido inválido.") from exc
    return data


def read_request_file(path: Path) -> dict:
    return read_request(_read_small(Path(path), MAX_REQUEST_BYTES))


def _read_ledger(home: Path) -> list[dict]:
    path = admin_paths(home)["ledger"]
    if not path.exists():
        return []
    raw = _read_small(path, MAX_LEDGER_BYTES)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise LicenseError("Histórico local danificado. Não emitir novas licenças.") from exc
    if (not isinstance(data, dict) or set(data) != {"schema", "records"}
            or data["schema"] != 1 or not isinstance(data["records"], list)
            or len(data["records"]) > 20000):
        raise LicenseError("Histórico local inválido. Não emitir novas licenças.")
    records = data["records"]
    for entry in records:
        if (not isinstance(entry, dict) or set(entry) != LEDGER_FIELDS
                or any(type(entry[f]) is not str for f in
                       ("order_ref", "license_id", "request_id", "device_hash", "issued_on"))):
            raise LicenseError("Histórico local contém registros inválidos.")
    return records


def list_issued(home: Path) -> list[dict]:
    return list(_read_ledger(home))


def _save_ledger(home: Path, records: list[dict]) -> None:
    path = admin_paths(home)["ledger"]
    body = json.dumps({"schema": 1, "records": records}, ensure_ascii=True,
                      sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(body) > MAX_LEDGER_BYTES:
        raise LicenseError("Histórico atingiu o limite de tamanho.")
    _ensure_parent(path)
    _not_link(path)
    descriptor, temp = tempfile.mkstemp(prefix=".ledger-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextmanager
def _issue_lock(home: Path):
    path = admin_paths(home)["lock"]
    _write_new(path, str(os.getpid()).encode("ascii"), private=True)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def normalize_order_ref(value: str) -> str:
    if type(value) is not str or not ORDER_RE.fullmatch(value.strip().upper()):
        raise LicenseError("Informe o identificador da compra (3 a 64 letras/números).")
    return value.strip().upper()


def issue_license(home: Path, password: str, request: dict,
                  order_ref: str, output_file: Path,
                  *, purchase_confirmed: bool, expires_on: str | None = None) -> dict:
    """Emit only after manual payment confirmation; max two unique PCs/order."""
    if purchase_confirmed is not True:
        raise LicenseError("Confirme o pagamento antes de emitir a licença.")
    order = normalize_order_ref(order_ref)
    request = read_request(canonical_bytes(request))
    if expires_on is not None:
        if not isinstance(expires_on, str):
            raise LicenseError("Data de vencimento inválida.")
        try:
            expiry = date.fromisoformat(expires_on)
        except ValueError as exc:
            raise LicenseError("Use validade no formato AAAA-MM-DD.") from exc
        if expiry < date.today() or expiry.isoformat() != expires_on:
            raise LicenseError("Validade deve ser hoje ou posterior.")
    export = Path(output_file)
    if export.suffix.lower() != ".json" or export.exists() or export.is_symlink():
        raise LicenseError("Escolha um novo arquivo .json, sem sobrescrever existentes.")
    paths = admin_paths(home)
    with _issue_lock(home):
        existing = _read_ledger(home)
        if any(x["request_id"] == request["request_id"] for x in existing):
            raise LicenseError("Este pedido de ativação já foi usado.")
        matching = [x for x in existing if x["order_ref"] == order]
        if any(x["device_hash"] == request["device_hash"] for x in matching):
            raise LicenseError(
                "Esta compra já possui licença para este PC. Reenvie o arquivo original.")
        if len(matching) >= MAX_DEVICES_PER_ORDER:
            raise LicenseError("Limite de dois computadores para esta compra atingido.")
        key = _private_key(home, password)
        pub = _public_b64(home)
        if _derived_public_b64(key) != pub:
            raise LicenseError("Chaves pública e privada não correspondem.")
        payload = {
            "schema": SCHEMA, "product": PRODUCT, "edition": EDITION,
            "license_id": str(uuid4()), "device_hash": request["device_hash"],
            "issued_on": date.today().isoformat(), "expires_on": expires_on,
        }
        validate_payload(payload)
        signature = key.sign(canonical_bytes(payload))
        document = {"payload": payload,
                    "signature": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")}
        verify_license(document, request["device_hash"], public_key_b64=pub)
        blob = canonical_bytes(document) + b"\n"
        if len(blob) > MAX_LICENSE_BYTES:
            raise LicenseError("Licença excede o limite.")
        backup = paths["issued"] / (payload["license_id"] + ".json")
        record = {
            "order_ref": order, "license_id": payload["license_id"],
            "request_id": request["request_id"], "device_hash": request["device_hash"],
            "issued_on": payload["issued_on"], "expires_on": expires_on,
        }
        created_backup = False
        created_export = False
        try:
            _write_new(backup, blob, private=True)
            created_backup = True
            _write_new(export, blob, private=True)
            created_export = True
            _save_ledger(home, [*existing, record])
        except Exception:
            if created_export:
                export.unlink(missing_ok=True)
            if created_backup:
                backup.unlink(missing_ok=True)
            raise
    return {"license_id": payload["license_id"],
            "order_ref": order, "device_hash_prefix": request["device_hash"][:12],
            "output": str(export)}


def verify_issued(home: Path, license_file: Path) -> dict:
    doc = json.loads(_read_small(Path(license_file), MAX_LICENSE_BYTES).decode("utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("payload"), dict):
        raise LicenseError("Licença inválida.")
    device_hash = doc["payload"].get("device_hash")
    if type(device_hash) is not str or HASH_PATTERN.fullmatch(device_hash) is None:
        raise LicenseError("Licença não possui dispositivo válido.")
    result = verify_license(doc, device_hash, public_key_b64=_public_b64(home))
    return result


def resend_issued(home: Path, license_id: str, output_file: Path) -> dict:
    """Re-export the ORIGINAL signed bytes; do not create another activation."""
    try:
        if str(UUID(license_id)) != license_id:
            raise ValueError()
    except ValueError as exc:
        raise LicenseError("Identificador de licença inválido.") from exc
    if not any(x["license_id"] == license_id for x in _read_ledger(home)):
        raise LicenseError("Licença não encontrada no histórico.")
    source = admin_paths(home)["issued"] / (license_id + ".json")
    result = verify_issued(home, source)
    destination = Path(output_file)
    if destination.suffix.lower() != ".json":
        raise LicenseError("Escolha arquivo com extensão .json.")
    _write_new(destination, _read_small(source, MAX_LICENSE_BYTES), private=True)
    return result


def export_public_key(home: Path, output_file: Path) -> Path:
    output = Path(output_file)
    if output.suffix.lower() != ".txt":
        raise LicenseError("Escolha arquivo .txt para a chave pública.")
    content = (_public_b64(home) + "\n").encode("ascii")
    _write_new(output, content)
    return output
