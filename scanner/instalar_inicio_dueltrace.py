"""Ativação reversível do DUELTRACE Desktop como entrada principal.

O atualizador antigo instala somente app/tools e scripts permitidos.
Este migrador é executado EXPLICITAMENTE pelo usuário, preserva o
assistente_x15.py existente e não altera launcher.py nem arquivos de jogo.
"""
from __future__ import annotations

import argparse
import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path

START = "# DUELTRACE_MAIN_ENTRY_BEGIN"
END = "# DUELTRACE_MAIN_ENTRY_END"

BRIDGE = """# DUELTRACE_MAIN_ENTRY_BEGIN
if __name__ == "__main__":
    import sys as _dueltrace_sys
    if "--legacy" in _dueltrace_sys.argv:
        _dueltrace_sys.argv.remove("--legacy")
    else:
        from pathlib import Path as _dueltrace_pathlib_Path
        _dueltrace_tools = str(_dueltrace_pathlib_Path(__file__).resolve().parent / "tools")
        if _dueltrace_tools not in _dueltrace_sys.path:
            _dueltrace_sys.path.insert(0, _dueltrace_tools)
        from abrir_biblioteca import main as _dueltrace_main
        _dueltrace_main()
        raise SystemExit(0)
# DUELTRACE_MAIN_ENTRY_END
"""


def _check_legacy(source: str):
    tree = ast.parse(source)
    if not any(isinstance(node, ast.ClassDef) and node.name == "App"
               for node in tree.body):
        raise ValueError("Classe App do assistente antigo não encontrada; integração cancelada.")
    if not any(isinstance(node, ast.If) and "__name__" in ast.unparse(node.test)
               and "__main__" in ast.unparse(node.test) for node in tree.body):
        raise ValueError("Ponto de entrada do assistente antigo não reconhecido.")
    return tree


def patch_source(source: str) -> str:
    if START in source or END in source:
        if START in source and END in source:
            return source
        raise ValueError("Marcadores de integração incompletos; nenhuma alteração aplicada.")
    tree = _check_legacy(source)
    # Depois da docstring e de imports __future__, nunca antes deles.
    anchor = 0
    nodes = tree.body
    n = 0
    if nodes and isinstance(nodes[0], ast.Expr) and isinstance(
            nodes[0].value, (ast.Constant,)) and isinstance(nodes[0].value.value, str):
        anchor = nodes[0].end_lineno
        n = 1
    while n < len(nodes) and isinstance(nodes[n], ast.ImportFrom) and nodes[n].module == "__future__":
        anchor = nodes[n].end_lineno
        n += 1
    lines = source.splitlines(keepends=True)
    before = "".join(lines[:anchor])
    if before and not before.endswith(("\n", "\r")):
        before += "\n"
    after = "".join(lines[anchor:])
    updated = before + "\n" + BRIDGE + "\n" + after
    compile(updated, "assistente_x15.py", "exec")
    return updated


def restore_source(source: str) -> str:
    if START not in source and END not in source:
        return source
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("Marcadores de integração inconsistentes.")
    start = source.index(START)
    end = source.index(END) + len(END)
    # Remover somente a ponte controlada, não os hooks MultiMod preexistentes.
    original = source[:start] + source[end:]
    original = original.replace("\n\n\n\n", "\n\n\n")
    compile(original, "assistente_x15.py", "exec")
    _check_legacy(original)
    return original


def _check_desktop(app_path: Path):
    tools = app_path.parent / "tools"
    for filename in ("abrir_biblioteca.py", "dueltrace_desktop.py", "dueltrace_visuals.py"):
        if not (tools / filename).is_file():
            raise FileNotFoundError(
                f"Arquivo do DUELTRACE não encontrado: {tools / filename}. "
                "Instale primeiro o patch v0.5.2."
            )


def migrate(path: Path, *, restore: bool = False):
    path = Path(path).expanduser().resolve()
    if path.name.lower() != "assistente_x15.py":
        raise ValueError("Selecione somente o assistente_x15.py da sua instalação.")
    if not path.is_file():
        raise FileNotFoundError(f"Assistente antigo não encontrado: {path}")
    if not restore:
        _check_desktop(path)
    raw = path.read_bytes()
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    text = raw[len(bom):].decode("utf-8")
    updated = restore_source(text) if restore else patch_source(text)
    if updated == text:
        return False, None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = path.with_name(f"{path.name}.bak.dueltrace.{timestamp}")
    temp = path.with_name(f".{path.name}.dueltrace-{timestamp}.tmp")
    shutil.copy2(path, backup)
    try:
        temp.write_bytes(bom + updated.encode("utf-8"))
        compile(updated, str(path), "exec")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return True, backup


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ativa/restaura DUELTRACE como interface principal")
    parser.add_argument("--app", type=Path,
                        default=Path(__file__).resolve().parent.parent / "assistente_x15.py")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args(argv)
    try:
        changed, backup = migrate(args.app, restore=args.restore)
    except (OSError, SyntaxError, UnicodeError, ValueError) as exc:
        print("INTEGRACAO CANCELADA — nada foi alterado:", exc, file=sys.stderr)
        return 1
    if changed:
        action = "restaurado" if args.restore else "ativado"
        print(f"DUELTRACE {action} com sucesso. Backup: {backup}")
        print("O botão INICIAR ASSISTENTE abrirá o DUELTRACE moderno.")
        print("Use Abrir Assistente Clássico dentro do novo aplicativo para o modo legado.")
    else:
        print("Nenhuma alteração necessária: configuração já aplicada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
