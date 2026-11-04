"""Consulta builds Preview do workflow OFICIAL, sem lista fixa de branches.

Branches com versão compacta (v096) ou explícita (v0.10.0) são reconhecidas.
O conteúdo do GitHub Actions é experimental e nunca é auto-instalado.
Nenhuma ISO, RAM ou informação local é enviada ao GitHub.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

REPO_API = "https://api.github.com/repos/guibatoni/appassist"
REPO_WEB = "https://github.com/guibatoni/appassist"
RUNS_API = REPO_API + "/actions/workflows/validar-webui-desktop.yml/runs?event=push&status=success&per_page=100"
WORKFLOW_NAME = "Validar integração v0 DUELTRACE Windows"
ARTIFACT_NAME = "DUELTRACE-Windows-Preview-Unsigned-Security-Scanned"
BUILD_INFO_FILE = "dueltrace-build.json"
MAX_BYTES = 768 * 1024
_SHA = re.compile(r"[0-9a-f]{40}\Z")
# Os componentes explícitos seguem o limite de quatro dígitos do checker e
# instalador; zeros à esquerda e formas compactas maiores seriam ambíguos.
_VERSION_COMPONENT = r"(?:0|[1-9][0-9]{0,3})"
_VERSION_BRANCH = re.compile(
    r"(?:feature|fix|security)/dueltrace-v"
    rf"(?:(?P<compact>[0-9]{{3}})|(?P<semver>{_VERSION_COMPONENT}\."
    rf"{_VERSION_COMPONENT}\.{_VERSION_COMPONENT}))-[a-z0-9][a-z0-9-]*\Z"
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_json(url: str, expected_type: type = dict) -> dict | list:
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "DUELTRACE-PreviewChecker/0.7.5",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=8) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("Resposta inesperada da API de builds.")
        size = response.headers.get("Content-Length")
        if size and int(size) > MAX_BYTES:
            raise ValueError("Resposta muito grande.")
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Resposta muito grande.")
    decoded = json.loads(data.decode("utf-8"))
    if not isinstance(decoded, expected_type):
        raise ValueError("Resposta inválida do GitHub.")
    return decoded


def version_for_branch(branch: str | None) -> str | None:
    """Extrai uma versão canônica sem interpretar o restante como código/URL."""
    if not isinstance(branch,str):
        return None
    match=_VERSION_BRANCH.fullmatch(branch)
    if match is None:
        return None
    if match.group("semver") is not None:
        return match.group("semver")
    return ".".join(match.group("compact"))


def _accepted_run(item: dict, branch: str | None = None) -> bool:
    run_id = item.get("id")
    sha = item.get("head_sha")
    candidate = item.get("head_branch")
    return (
        type(run_id) is int and 0 < run_id < 10**15
        and (branch is None or candidate == branch)
        and version_for_branch(candidate) is not None
        and item.get("status") == "completed"
        and item.get("conclusion") == "success"
        and item.get("event") == "push"
        and item.get("name") == WORKFLOW_NAME
        and isinstance(item.get("head_repository"),dict)
        and item["head_repository"].get("full_name") == "guibatoni/appassist"
        and isinstance(sha,str) and bool(_SHA.fullmatch(sha))
        and item.get("html_url") == f"{REPO_WEB}/actions/runs/{run_id}"
    )


def fetch_latest_preview() -> dict | None:
    """Seleciona maior versão semanticamente, depois maior build na versão."""
    data=_get_json(RUNS_API)
    runs=data.get("workflow_runs")
    if not isinstance(runs,list):
        raise ValueError("Lista de builds inválida.")
    candidates=[x for x in runs if isinstance(x,dict) and _accepted_run(x)]
    candidates.sort(key=lambda item: (
        tuple(map(int,version_for_branch(item["head_branch"]).split("."))),
        item["id"]), reverse=True)
    for item in candidates[:16]:
        run_id=item["id"]
        artifacts=_get_json(f"{REPO_API}/actions/runs/{run_id}/artifacts?per_page=100").get("artifacts")
        if not isinstance(artifacts,list):
            continue
        found=next((a for a in artifacts if isinstance(a,dict)
                    and a.get("name")==ARTIFACT_NAME
                    and a.get("expired") is False),None)
        if found:
            return {
                "run_id":run_id,
                "head_sha":item["head_sha"],
                "branch":item["head_branch"],
                "version":version_for_branch(item["head_branch"]),
                "page":item["html_url"],
                "artifact_name":ARTIFACT_NAME,
            }
    return None


def installed_preview_build_id() -> int | None:
    """Metadado imutável escrito no executável pelo Actions."""
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
