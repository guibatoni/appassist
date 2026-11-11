"""Read-only, opt-in local GitHub CLI access for PRIVATE DUELTRACE releases.

GitHub Releases in a private repository return 404 to unauthenticated
urllib requests. The maintainer may install/authenticate GitHub CLI ONCE,
then use the existing "Atualizar agora" button. No PAT, password or
OAuth client secret is ever embedded in the DUELTRACE binary.

This is a local maintainer/alpha transport, NOT customer distribution.
Do not silently authenticate customers or disclose the private repository.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

REPO = "guibatoni/appassist"
RELEASES_RESOURCE = f"repos/{REPO}/releases?per_page=30"
STABLE_RESOURCE = f"repos/{REPO}/releases/latest"
ZIP_ASSET = "DUELTRACE-WebUI-Windows-Preview.zip"
STABLE_ZIP_ASSET = "DUELTRACE-WebUI-Windows.zip"
MIN_GH_VERSION = (2, 102, 0)
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_ZIP_BYTES = 230 * 1024 * 1024


class PrivateUpdateUnavailable(OSError):
    """Local GitHub CLI is absent, too old or not authorized."""


def _gh_path() -> str:
    """Find an existing authorized GitHub CLI also from Windows Explorer.

    Explorer may run from a PATH snapshot taken before 'gh' was installed.
    Look only in standard locations of the official GitHub CLI installation;
    never download/run arbitrary updater binaries, and never expose tokens.
    """
    path=shutil.which("gh")
    if path:
        return path
    if os.name=="nt":
        roots=(
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramW6432"),
            os.environ.get("LOCALAPPDATA"),
        )
        for index,root in enumerate(roots):
            if not root:
                continue
            candidate=(Path(root)/("Programs" if index==2 else "")/
                       "GitHub CLI"/"gh.exe")
            if candidate.is_file():
                return str(candidate)
    raise PrivateUpdateUnavailable(
        "Atualizações privadas: GitHub CLI não encontrado neste Windows. "
        "Instale em https://cli.github.com/ e execute 'gh auth login' uma vez.")


def _env() -> dict[str, str]:
    # github.com only; do not print environment, tokens or subprocess stderr.
    env = os.environ.copy()
    env.update({"GH_HOST": "github.com", "GH_PROMPT_DISABLED": "1",
                "GIT_TERMINAL_PROMPT": "0", "GH_PAGER": "cat", "NO_COLOR": "1"})
    return env


def _run(args: list[str], *, timeout: int) -> bytes:
    # Resolve the executable before the subprocess try block. Previously
    # PrivateUpdateUnavailable (an OSError subclass) was caught here and
    # replaced by the vague "GitHub privado indisponível" error even when
    # GitHub CLI was simply missing from Windows.
    executable=_gh_path()
    try:
        completed = subprocess.run(
            [executable, *args], capture_output=True, check=False, timeout=timeout,
            env=_env(), shell=False)
    except subprocess.TimeoutExpired as exc:
        raise PrivateUpdateUnavailable(
            "O GitHub CLI não respondeu. Verifique a conexão com a internet."
        ) from exc
    except OSError as exc:
        raise PrivateUpdateUnavailable(
            "O GitHub CLI está instalado, mas não pôde ser executado no Windows."
        ) from exc
    if completed.returncode != 0:
        # Never print stderr: GitHub can echo details from local auth config.
        raise PrivateUpdateUnavailable(
            "GitHub privado: autentique o GitHub CLI com uma conta autorizada.")
    return completed.stdout


def _check_version() -> None:
    """Avoid older gh release download symlink vulnerabilities (GHSA-39wj-f2f4-978v)."""
    version = _run(["version"], timeout=6)[:350].decode("ascii", errors="ignore")
    match = re.search(r"\bgh version (\d+)\.(\d+)\.(\d+)\b", version)
    if not match or tuple(map(int, match.groups())) < MIN_GH_VERSION:
        raise PrivateUpdateUnavailable(
            "Atualize o GitHub CLI para a versão 2.102.0 ou superior.")


def read_private_release_metadata(*, stable: bool = False) -> list | dict:
    """Return only the official repository's authenticated release metadata.

    Do not attempt auto-login and do not expose a token to the app UI.
    """
    _check_version()
    endpoint = STABLE_RESOURCE if stable else RELEASES_RESOURCE
    body = _run(["api", "--method", "GET", endpoint,
                 "-H", "Accept: application/vnd.github+json"], timeout=20)
    if not body or len(body) > MAX_METADATA_BYTES:
        raise PrivateUpdateUnavailable("Metadados de atualizações privadas inválidos.")
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise PrivateUpdateUnavailable(
            "Resposta de atualizações privadas inválida.") from exc
    expected = dict if stable else list
    if not isinstance(data, expected):
        raise PrivateUpdateUnavailable("Lista de atualizações privadas inválida.")
    return data


def download_private_zip(tag: str, asset_name: str, destination: Path,
                         *, sha256: str, expected_size: int) -> Path:
    """Download with user-authenticated gh and verify sha/size before use.

    Content is written only to the fresh updater staging directory; no user
    files, ISO files or existing install files are touched by this routine.
    """
    from hashlib import sha256 as sha256_factory
    import uuid

    if (type(tag) is not str or
            not re.fullmatch(r"preview-v\d{1,4}\.\d{1,4}\.\d{1,4}-r\d{1,15}|v?\d{1,4}\.\d{1,4}\.\d{1,4}", tag)
            or asset_name not in (ZIP_ASSET, STABLE_ZIP_ASSET)
            or type(sha256) is not str or
            not re.fullmatch(r"[a-f0-9]{64}", sha256)
            or type(expected_size) is not int
            or not 0 < expected_size <= MAX_ZIP_BYTES):
        raise PrivateUpdateUnavailable("Identidade do pacote de atualização inválida.")
    destination = Path(destination)
    if (not destination.parent.is_dir() or destination.exists() or
            destination.is_symlink() or destination.parent.is_symlink()):
        raise PrivateUpdateUnavailable("Destino de atualização inseguro.")
    _check_version()
    temporary = destination.parent / (".dueltrace-" + uuid.uuid4().hex + ".zip")
    if temporary.exists() or temporary.is_symlink():
        raise PrivateUpdateUnavailable("Arquivo temporário já existe.")
    try:
        # --output supplies EXACTLY one asset path, not the entire release.
        _run(["release", "download", tag, "--repo", REPO,
              "--pattern", asset_name, "--output", str(temporary)], timeout=240)
        if not temporary.is_file() or temporary.is_symlink():
            raise PrivateUpdateUnavailable("Pacote privado não foi baixado.")
        if temporary.stat().st_size != expected_size:
            raise PrivateUpdateUnavailable("Tamanho do pacote privado divergente.")
        digest = sha256_factory()
        with temporary.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != sha256:
            raise PrivateUpdateUnavailable("SHA-256 do pacote privado divergente.")
        # Atomic move only after integrity check; never touch the installed app.
        temporary.replace(destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
