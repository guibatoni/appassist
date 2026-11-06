"""Opt-in DUELTRACE evidence synchronization to a *private* GitHub repository.

Never connects to ChatGPT, never grants inbound remote access to Windows, and
never transmits ROM bytes, art, RAM dumps, host paths, credentials or PID.
The user must explicitly configure the private destination and grant access.
"""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import threading
import urllib.error
import urllib.request

from auto_mods import atomic_json

PRIVATE_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,39}/[A-Za-z0-9_.-]{1,100}$")
FINGERPRINT = re.compile(r"^[a-f0-9]{12}$")
SESSION = re.compile(r"^[a-f0-9]{16}$")
MAX_BYTES = 140000

REPORT_KEYS = frozenset({
    "schema", "subject", "romFingerprint", "running", "startedAtUTC",
    "lastObservedAtUTC", "sampleCount", "changeCount",
    "handReadableChanges", "opponentReadableChanges", "opponentStatuses",
    "events", "verifiedOpponentMapping", "verifiedRankGroups",
    "mayActivateDrops", "mayActivateRank", "networkTransmission", "note",
    "candidateEvents", "candidateIdsObserved",
    "candidateIdStableAcrossReadableChanges", "handAnchorValidatedChanges",
    "distinctLpPairsInReadableChanges", "exportTruncated",
})
EVENT_KEYS = frozenset({"sample", "atUTC", "data"})
HAND_KEYS = frozenset({"ready", "ids"})
OPP_KEYS = frozenset({
    "ready", "status", "candidateId", "mappingMethod", "lpPlayer",
    "lpOpponent", "memoryRegionsExamined", "candidateBasesExamined",
    "rejectionCounts", "knownHandAnchorAtHint", "hintRejectionCounts",
    "handAnchorValidated",
})
RANK_KEYS = frozenset({
    "ready", "state", "scoreCandidate", "categoryCandidate", "modelVerified",
})


class EvidenceSyncError(ValueError):
    """Non-secret user-facing error, never the raw HTTP response."""


def validate_private_repository(repo: str) -> str:
    if not isinstance(repo, str) or not PRIVATE_REPO.fullmatch(repo):
        raise EvidenceSyncError("Use o formato usuario/repositorio-privado.")
    if any(part.startswith(".") or ".." in part or part.endswith(".git")
           for part in repo.split("/")):
        raise EvidenceSyncError("Nome de repositório inválido.")
    return repo


def validate_sanitized_report(raw: str) -> dict:
    """Reject unexpected fields; never upload a raw dump by mistake."""
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_BYTES:
        raise EvidenceSyncError("Relatório não permitido ou muito grande.")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise EvidenceSyncError("JSON de diagnóstico inválido.") from None
    if (not isinstance(data, dict)
            or set(data) - REPORT_KEYS
            or data.get("schema") != 1
            or data.get("subject") != "DUELTRACE Live Diagnostics"
            or data.get("networkTransmission") is not False
            or data.get("verifiedOpponentMapping") is not False
            or data.get("mayActivateDrops") is not False
            or data.get("mayActivateRank") is not False
            or not isinstance(data.get("romFingerprint"), str)
            or not FINGERPRINT.fullmatch(data["romFingerprint"])):
        raise EvidenceSyncError("Relatório fora da lista de campos permitidos.")
    events = data.get("events")
    if not isinstance(events, list) or len(events) > 360:
        raise EvidenceSyncError("Lista de eventos inválida.")
    for item in events:
        if not isinstance(item, dict) or set(item) - EVENT_KEYS:
            raise EvidenceSyncError("Evento não permitido.")
        obj = item.get("data")
        if not isinstance(obj, dict) or set(obj) != {"hand", "opponent", "rank"}:
            raise EvidenceSyncError("Campos de evento inválidos.")
        for key, allowed in (
            ("hand", HAND_KEYS), ("opponent", OPP_KEYS), ("rank", RANK_KEYS)
        ):
            row = obj[key]
            if not isinstance(row, dict) or set(row) - allowed:
                raise EvidenceSyncError("Campo interno não permitido.")
        hand = obj["hand"]
        if (not isinstance(hand.get("ids"), list)
                or len(hand["ids"]) not in (0, 5)
                or any(type(v) is not int or v < 1 or v > 722 for v in hand["ids"])):
            raise EvidenceSyncError("IDs da mão inválidos.")
        for key in ("rejectionCounts", "hintRejectionCounts"):
            counts = obj["opponent"].get(key, {})
            if (not isinstance(counts, dict)
                    or any(type(v) is not int or v < 0 or v > 100000
                           for v in counts.values())
                    or any(not isinstance(k, str) or not re.fullmatch(
                           r"[A-Za-z]{1,40}", k) for k in counts)):
                raise EvidenceSyncError("Contadores inválidos.")
    return data


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise EvidenceSyncError("Redirecionamento remoto recusado.")


class GitHubPrivateRepositorySink:
    """Uploads allowlisted report versions to a verified private repository."""

    def __init__(self, opener=None):
        self._opener = opener or urllib.request.build_opener(_NoRedirect())

    def _request(self, method, path, token, payload=None, *, allow_missing=False):
        url = "https://api.github.com" + path
        if not path.startswith("/repos/") or "//" in path:
            raise EvidenceSyncError("Destino remoto inválido.")
        body = (json.dumps(payload, separators=(",", ":")).encode("utf-8")
                if payload is not None else None)
        request = urllib.request.Request(url, data=body, method=method, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "DUELTRACE-Private-Evidence-Sync",
            "Content-Type": "application/json",
        })
        try:
            with self._opener.open(request, timeout=12) as response:
                if getattr(response, "status", 200) not in (200, 201):
                    raise EvidenceSyncError("Resposta GitHub inesperada.")
                content = response.read(512 * 1024 + 1)
                if len(content) > 512 * 1024:
                    raise EvidenceSyncError("Resposta GitHub excedeu o limite.")
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as exc:
            if allow_missing and exc.code == 404:
                return None
            raise EvidenceSyncError(
                "GitHub recusou o acesso. Verifique o token e a permissão Contents.") from None
        except (urllib.error.URLError, OSError, ValueError):
            raise EvidenceSyncError(
                "Não foi possível conectar ao GitHub por HTTPS.") from None

    def verify(self, repo, token):
        repo = validate_private_repository(repo)
        if (not isinstance(token, str) or not 20 <= len(token) <= 256
                or any(ch.isspace() or ord(ch) < 33 or ord(ch) > 126 for ch in token)):
            raise EvidenceSyncError("Token GitHub inválido.")
        meta = self._request("GET", "/repos/" + repo, token)
        if (not isinstance(meta, dict)
                or meta.get("private") is not True
                or str(meta.get("full_name", "")).lower() != repo.lower()):
            raise EvidenceSyncError(
                "Destino recusado: somente repositórios privados são permitidos.")
        permissions = meta.get("permissions")
        if isinstance(permissions, dict) and permissions.get("push") is False:
            raise EvidenceSyncError("Token não pode gravar nesse repositório.")
        return repo

    def upload(self, repo, token, session_id, report_text):
        repo = self.verify(repo, token)
        if not isinstance(session_id, str) or not SESSION.fullmatch(session_id):
            raise EvidenceSyncError("Sessão de diagnóstico inválida.")
        sanitized = validate_sanitized_report(report_text)
        # The only remote target is the configured private repository.
        path = "reports/" + sanitized["romFingerprint"] + "/" + session_id + ".json"
        endpoint = "/repos/" + repo + "/contents/" + path
        current = self._request("GET", endpoint, token, allow_missing=True)
        payload = {
            "message": "DUELTRACE: relatório sanitizado de diagnóstico",
            "content": base64.b64encode(report_text.encode("utf-8")).decode("ascii"),
        }
        if current is not None:
            if (not isinstance(current, dict)
                    or not isinstance(current.get("sha"), str)
                    or not re.fullmatch(r"[a-f0-9]{40}", current["sha"])):
                raise EvidenceSyncError("Arquivo remoto inesperado.")
            payload["sha"] = current["sha"]
        uploaded = self._request("PUT", endpoint, token, payload)
        if not isinstance(uploaded, dict) or not isinstance(
                uploaded.get("commit"), dict):
            raise EvidenceSyncError("GitHub não confirmou a gravação.")
        return {"synced": True, "sessionId": session_id,
                "fingerprint": sanitized["romFingerprint"]}


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _windows_dpapi(data: bytes, *, decrypt: bool) -> bytes:
    if sys.platform != "win32":
        raise EvidenceSyncError("Credenciais seguras exigem Windows.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    func = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    func.argtypes = (
        [ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p, ctypes.POINTER(_DATA_BLOB),
         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
         ctypes.POINTER(_DATA_BLOB)] if decrypt else
        [ctypes.POINTER(_DATA_BLOB), ctypes.c_wchar_p,
         ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
         wintypes.DWORD, ctypes.POINTER(_DATA_BLOB)]
    )
    func.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buf = ctypes.create_string_buffer(data)
    inp = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    output = _DATA_BLOB()
    if decrypt:
        ok = func(ctypes.byref(inp), None, None, None, None, 1,
                  ctypes.byref(output))
    else:
        ok = func(ctypes.byref(inp), "DUELTRACE local-only GitHub credential",
                  None, None, None, 1, ctypes.byref(output))
    if not ok:
        raise EvidenceSyncError("Windows não conseguiu proteger a credencial.")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p))


class WindowsTokenStore:
    """DPAPI user-scope; no plaintext credential on disk or in diagnostics."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def save(self, token):
        protected = _windows_dpapi(token.encode("ascii"), decrypt=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            with tmp.open("wb") as dest:
                dest.write(protected)
            os.replace(tmp, self.path)
        finally:
            tmp.unlink(missing_ok=True)

    def load(self):
        if not self.path.is_file():
            return None
        if self.path.stat().st_size > 16 * 1024:
            raise EvidenceSyncError("Credencial local inválida.")
        try:
            return _windows_dpapi(self.path.read_bytes(), decrypt=True).decode("ascii")
        except (OSError, ValueError, UnicodeError):
            raise EvidenceSyncError("Credencial local inválida.") from None

    def clear(self):
        self.path.unlink(missing_ok=True)


class PrivateEvidenceSync:
    """User-controlled, per-installation upload of the recorder's safe export."""

    def __init__(self, directory: Path, *, sink=None, token_store=None):
        self._folder = Path(directory)
        self._settings = self._folder / "private_sync_settings.json"
        self._sink = sink or GitHubPrivateRepositorySink()
        self._tokens = token_store or WindowsTokenStore(
            self._folder / "private_sync_credential.bin")
        self._lock = threading.RLock()
        self._last_synced_utc = None
        self._last_error = None

    def _config(self):
        try:
            data = json.loads(self._settings.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def status(self):
        with self._lock:
            data = self._config()
            return {
                "enabled": data.get("enabled") is True,
                "repository": data.get("repo") if data.get("enabled") is True else None,
                "lastSyncedAtUTC": self._last_synced_utc,
                "lastError": self._last_error,
                "remoteIsChatGPTConnection": False,
            }

    def configure(self, repo, token, consent):
        if consent is not True:
            raise EvidenceSyncError("Confirme o envio privado antes de ativar.")
        # Verify private repo *before* saving credentials or enabling uploads.
        repo = self._sink.verify(repo, token)
        with self._lock:
            self._tokens.save(token)
            atomic_json(self._settings, {"schema": 1, "repo": repo,
                                          "enabled": True})
            self._last_error = None
        return self.status()

    def disable(self):
        with self._lock:
            # Existing remote files are not deleted. User controls the repo.
            atomic_json(self._settings, {"schema": 1, "enabled": False})
            self._tokens.clear()
        return self.status()

    def upload(self, recorder):
        with self._lock:
            config = self._config()
            if config.get("enabled") is not True:
                return {"synced": False, "reason": "disabled"}
            repo = config.get("repo")
            token = self._tokens.load()
            if not token:
                raise EvidenceSyncError("Credencial ausente. Reconecte o GitHub.")
        # Recheck locally before network call. Session bytes are sanitized
        # in LiveDiagnosticsRecorder.export_json and validated again here.
        report = recorder.export_json()
        try:
            response = self._sink.upload(repo, token, recorder.session_id, report)
        except EvidenceSyncError as exc:
            with self._lock:
                self._last_error = str(exc)
            raise
        with self._lock:
            self._last_synced_utc = datetime.now(timezone.utc).isoformat(
                timespec="seconds")
            self._last_error = None
        return response
