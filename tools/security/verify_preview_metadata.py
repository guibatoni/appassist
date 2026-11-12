"""Bloqueia Preview com versão, nome da branch ou Patch Notes defasados.

A versão canônica vem de scanner/dueltrace_update_checker.py; não mantenha
número duplicado no workflow. Exit code 1 impede publicar ZIP inconsistente.
"""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scanner/dueltrace_update_checker.py"
NOTES = ROOT / "docs/DUELTRACE_UPDATE_NOTES.md"
VERSION_PATTERN = re.compile(r"(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})\Z")
BRANCH_PATTERN = re.compile(
    r"(?:feature|fix|security)/dueltrace-v"
    r"(?:(?P<compact>[0-9]{3})|(?P<expanded>(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})))-"
    r"[a-z0-9][a-z0-9-]*\Z"
)


def current_version() -> str:
    program = ast.parse(CHECKER.read_text(encoding="utf-8"))
    for node in program.body:
        if (isinstance(node, ast.Assign)
                and any(isinstance(x, ast.Name) and x.id == "CURRENT_VERSION"
                        for x in node.targets)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            version = node.value.value
            if VERSION_PATTERN.fullmatch(version):
                return version
    raise ValueError("CURRENT_VERSION deve ser uma versão semver válida.")


def verify_release_metadata(branch: str | None = None) -> str:
    version = current_version()
    raw = NOTES.read_text(encoding="utf-8-sig")
    if not 0 < len(raw.encode("utf-8")) < 24_000:
        raise ValueError("Patch Notes ausentes ou excedem o limite do aplicativo.")
    first = raw.splitlines()[0].strip() if raw.splitlines() else ""
    if not first.startswith(f"# DUELTRACE v{version} "):
        raise ValueError(
            f"Patch Notes devem declarar a versão canônica v{version}.")
    # Use the SAME formatter as the in-app modal and require nonempty real notes.
    import sys
    sys.path.insert(0, str(ROOT / "scanner"))
    from dueltrace_patch_notes import summarize_patch_notes
    groups = summarize_patch_notes(raw)
    if {x["title"] for x in groups} != {"Novidades", "Melhorias", "Correções"}:
        raise ValueError("Patch Notes exigem Novidades, Melhorias e Correções.")
    if not all(x["items"] for x in groups):
        raise ValueError("Cada seção precisa ter novidades legíveis.")
    if branch and branch not in ("main", "master"):
        matched = BRANCH_PATTERN.fullmatch(branch)
        if not matched:
            raise ValueError("Branch de Preview não reconhecida.")
        label = (matched.group("expanded") if matched.group("expanded")
                 else ".".join(matched.group("compact")))
        if label != version:
            raise ValueError(
                f"Branch v{label} e aplicativo v{version} estão dessincronizados.")
    return version


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--branch", default="")
    cli.add_argument("--print-version", action="store_true")
    opts = cli.parse_args()
    version = verify_release_metadata(opts.branch)
    print(version if opts.print_version
          else f"DUELTRACE v{version}: versão, branch e Patch Notes aprovados.")


if __name__ == "__main__":
    main()
