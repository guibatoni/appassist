"""Anonymous GitHub Releases metadata for installed Windows preview builds.

Customers never access the private source repository or GitHub Actions.
No ROM, ISO, RAM, machine identity, token, or account data is transmitted.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

from dueltrace_public_distribution import PUBLIC_UPDATES_API, PUBLIC_UPDATES_WEB

# Keep legacy names only for callers that import these constants. They point
# EXCLUSIVELY to the public binary distribution repository.
REPO_API = PUBLIC_UPDATES_API
REPO_WEB = PUBLIC_UPDATES_WEB
RELEASES_API = REPO_API + "/releases?per_page=30"
BUILD_INFO_FILE = "dueltrace-build.json"
MAX_BYTES = 768 * 1024
_VERSION_COMPONENT = r"(?:0|[1-9][0-9]{0,3})"
_VERSION_BRANCH = re.compile(
    r"(?:feature|fix|security)/dueltrace-v"
    rf"(?:(?P<compact>[0-9]{{3}})|(?P<semver>{_VERSION_COMPONENT}\."
    rf"{_VERSION_COMPONENT}\.{_VERSION_COMPONENT}))-[a-z0-9][a-z0-9-]*\Z"
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Reject metadata redirects, including those to unrelated hosts."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_json(url: str, expected_type: type = dict) -> dict | list:
    """Request JSON without credentials, redirects, oversize reads, or uploads."""
    if (not isinstance(url,str) or
            not (url == REPO_API or url.startswith(REPO_API + "/"))):
        raise ValueError("Metadados devem vir do repositório público oficial.")
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "DUELTRACE-PublicReleaseChecker/0.9.7",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=8) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("Resposta inesperada da API pública de versões.")
        size = response.headers.get("Content-Length")
        if size and int(size) > MAX_BYTES:
            raise ValueError("Metadados públicos muito grandes.")
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Metadados públicos muito grandes.")
    decoded = json.loads(data.decode("utf-8"))
    if not isinstance(decoded, expected_type):
        raise ValueError("Resposta inválida do repositório de releases.")
    return decoded


def version_for_branch(branch: str | None) -> str | None:
    """Backward-compatible parsing of developer branch names; no network."""
    if not isinstance(branch,str):
        return None
    match=_VERSION_BRANCH.fullmatch(branch)
    if match is None:
        return None
    if match.group("semver") is not None:
        return match.group("semver")
    return ".".join(match.group("compact"))


def fetch_latest_preview() -> dict | None:
    """Compatibility helper, now backed by verified *public ZIP releases*.

    The customer update UI calls the package selector directly. Older callers
    can ask for the latest public Preview here without accessing CI artifacts.
    """
    # Imported lazily to prevent a circular dependency: the package selector
    # imports BUILD_INFO_FILE and _get_json from this module.
    from dueltrace_preview_installer import fetch_latest_preview_package
    release=fetch_latest_preview_package(
        current_version="0.0.0",installed_run_id=0)
    if release is None:
        return None
    return {
        "run_id":release["run_id"],
        "head_sha":release["sha"],
        "version":release["version"],
        "page":release["page"],
    }


def installed_preview_build_id() -> int | None:
    """Read the immutable build identity embedded in the installed app."""
    bundle=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))
    path=bundle/BUILD_INFO_FILE
    try:
        if not path.is_file() or path.stat().st_size>2048:
            return None
        data=json.loads(path.read_text(encoding="utf-8-sig"))
        run_id=data.get("run_id")
        if data.get("schema")!=1 or type(run_id) is not int:
            return None
        if 0 < run_id < 10**15:
            return run_id
    except (OSError,ValueError,TypeError):
        pass
    return None
