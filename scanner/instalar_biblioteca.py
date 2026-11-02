"""Integra o botão Biblioteca de Mods no Assistente legado.

Um patch de atualização não deve substituir assistente_x15.py inteiro,
pois ele pode conter ajustes locais. Este instalador injeta somente um hook
mínimo depois da criação do CompactPanel, com backup e validação de sintaxe.
"""
from __future__ import annotations

import argparse
import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path

START = "# MULTIMOD_LIBRARY_HOOK_BEGIN"
END = "# MULTIMOD_LIBRARY_HOOK_END"


def compact_panel_initializer(source: str):
    tree = ast.parse(source)
    app = next((c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == "App"), None)
    if app is None:
        raise ValueError("Classe App não encontrada; versão do Assistente não reconhecida")
    init = next((m for m in app.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and m.name == "__init__"), None)
    if init is None:
        raise ValueError("App.__init__ não encontrado")
    found = []
    for node in ast.walk(init):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                   and t.value.id == "self" and t.attr == "compact" for t in targets):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        name = value.func.id if isinstance(value.func, ast.Name) else getattr(value.func,"attr","")
        if name == "CompactPanel" and value.args:
            found.append((node,ast.unparse(value.args[0])))
    if len(found)!=1:
        raise ValueError("Não foi encontrado exatamente um construtor self.compact=CompactPanel(...)")
    return found[0]


def patch_source(source: str) -> str:
    if START in source:
        return source
    node, root_expression = compact_panel_initializer(source)
    lines=source.splitlines(keepends=True)
    # Usar mesma indentação da expressão original.
    line=lines[node.lineno-1]
    indent=line[:len(line)-len(line.lstrip())]
    end_line=node.end_lineno or node.lineno
    hook=[
        f"{indent}{START}\n",
        f"{indent}try:\n",
        f"{indent}    import sys as _multimod_sys\n",
        f"{indent}    from pathlib import Path as _multimod_Path\n",
        f"{indent}    _multimod_tools = str(_multimod_Path(__file__).resolve().parent / 'tools')\n",
        f"{indent}    if _multimod_tools not in _multimod_sys.path:\n",
        f"{indent}        _multimod_sys.path.insert(0, _multimod_tools)\n",
        f"{indent}    from biblioteca_mods import ligar_ao_overlay as _multimod_library\n",
        f"{indent}    self._multimod_library_bridge = _multimod_library({root_expression}, self, self.compact)\n",
        f"{indent}except Exception as _multimod_exc:\n",
        f"{indent}    print('Biblioteca de Mods: falha ao conectar:', _multimod_exc, flush=True)\n",
        f"{indent}{END}\n",
    ]
    updated="".join(lines[:end_line]+hook+lines[end_line:])
    compile(updated,"assistente_x15.py","exec")
    return updated


def install(path: Path) -> tuple[bool, Path | None]:
    path=Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    data=path.read_bytes()
    # Preserva BOM UTF-8, se houver.
    bom=b"\xef\xbb\xbf" if data.startswith(b"\xef\xbb\xbf") else b""
    source=data[len(bom):].decode("utf-8")
    updated=patch_source(source)
    if updated==source:
        return False,None
    now=datetime.now().strftime("%Y%m%d-%H%M%S")
    backup=path.with_name(path.name+".bak.library."+now)
    shutil.copy2(path,backup)
    tmp=path.with_name(path.name+".library.tmp")
    tmp.write_bytes(bom+updated.encode("utf-8"))
    tmp.replace(path)
    return True,backup


def main():
    p=argparse.ArgumentParser(description="Integra Biblioteca de Mods com backup")
    p.add_argument("--app",type=Path,default=Path(__file__).resolve().parent.parent/"assistente_x15.py")
    args=p.parse_args()
    try:
        updated,backup=install(args.app)
    except (OSError,ValueError,SyntaxError,UnicodeError) as exc:
        print("INTEGRAÇÃO CANCELADA — nenhum arquivo modificado:",exc)
        return 1
    if updated:
        print("Integração concluída; backup em",backup)
        print("Abra o Assistente. Use o botão 'Biblioteca de Mods' ou Ctrl+Shift+M.")
    else:
        print("Biblioteca de Mods já integrada; nenhuma alteração necessária.")
    return 0


if __name__=="__main__":
    sys.exit(main())
