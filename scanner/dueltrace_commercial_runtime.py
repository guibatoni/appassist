"""Isolated, fail-closed activation gate for the Commercial Lite executable.

Never used by the Alpha executable. Authentication is enforced in the Python
bridge for every privileged API call, not just by the React modal.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from dueltrace_offline_license import (
    LicenseError, MAX_LICENSE_BYTES, activation_request, install_license,
    local_license_status, windows_device_hash,
)


class CommercialLicenseGate:
    def __init__(self, data_home: Path, *,
                 device_fingerprint: Callable[[], str] = windows_device_hash,
                 public_key_b64: str | None = None):
        self._home = Path(data_home)
        self._fingerprint = device_fingerprint
        self._public_key_b64 = public_key_b64

    def status(self) -> dict:
        try:
            result = local_license_status(
                self._home, device_hash=self._fingerprint(),
                public_key_b64=self._public_key_b64)
        except (LicenseError, OSError):
            result = {"active": False, "status": "device_unavailable"}
        # No hardware identifier, path, or private customer detail returned.
        return {"edition": "commercial-lite", **result}

    def require_active(self) -> None:
        if self.status().get("active") is not True:
            raise PermissionError(
                "DUELTRACE Commercial Lite: ative uma licença válida para continuar.")

    def request(self) -> dict:
        request = activation_request(self._fingerprint())
        return {"fileName": "DUELTRACE-pedido-ativacao.json",
                "content": json.dumps(request, ensure_ascii=True,
                                      sort_keys=True, indent=2)}

    def activate(self, encoded: object) -> dict:
        if type(encoded) is not str or len(encoded.encode("utf-8")) > MAX_LICENSE_BYTES:
            raise LicenseError("Arquivo de licença inválido ou grande demais.")
        try:
            document = json.loads(encoded)
        except (ValueError, UnicodeError) as exc:
            raise LicenseError("O arquivo selecionado não é uma licença JSON válida.") from exc
        installed = install_license(
            document, self._home, self._fingerprint(),
            public_key_b64=self._public_key_b64)
        return {"status": "active", **installed}
