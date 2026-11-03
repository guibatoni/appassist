"""Prévia visual automatizada do DUELTRACE para o CI Windows.

A imagem usa perfis SINTÉTICOS sinalizados como teste. Nenhuma ROM é
lida/distribuída; a prévia não é evidência de compatibilidade com mods.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "scanner"))

from auto_mods import ModCatalog, atomic_json
from dueltrace_desktop import DueltraceDesktop


def main():
    try:
        from PIL import ImageGrab
    except ImportError:
        print("Sem Pillow: prévia visual indisponível.")
        return 0
    with tempfile.TemporaryDirectory(prefix="dueltrace-preview-") as td:
        home=Path(td)
        catalog=ModCatalog(home)
        entries=[]
        labels=[
            ("TESTE • FM Original.bin","parcial_revisar"),
            ("TESTE • FM13.iso","parcial_revisar"),
            ("TESTE • Remaster X15.bin","conhecido_validado"),
        ]
        for number,(name,level) in enumerate(labels,1):
            sha=f"{number:064x}"
            p=home/"profiles"/sha[:16]/"profile.json"
            atomic_json(p,{
                "rom_sha256":sha,"name":name,
                "supported_features":{"cards":False,"effects":False,
                                      "drops":False,"fusions":False,"art":False},
                "verified":{"cartas":"PENDENTE — SINTÉTICO"},
                "cards":[],"opponents":[],"drops":[],
                "fusion_recipes":[],
            })
            entries.append({"sha256":sha,"file_name":name,"level":level,
                            "profile_path":str(p),"source_path":str(home/name)})
        atomic_json(catalog.registry_file,{"schema":1,"entries":entries})
        app=DueltraceDesktop(catalog=catalog,developer=False)
        try:
            app.geometry("1360x780+80+80")
            app.update()
            app.go("mods")
            # Desenho nativo de componentes e transições após navegação.
            for _ in range(8):
                app.update()
                app.after(20)
            x,y=app.winfo_rootx(),app.winfo_rooty()
            w,h=app.winfo_width(),app.winfo_height()
            if w<100 or h<100:
                raise RuntimeError("Janela Tk não recebeu dimensões válidas")
            dest=Path("dist")/"DUELTRACE-PREVIA-TESTE.png"
            dest.parent.mkdir(exist_ok=True)
            try:
                ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(dest)
                print("Prévia visual de testes:",dest.resolve())
            except OSError as exc:
                print(f"Prévia ImageGrab indisponível neste runner: {exc}")
        finally:
            app.destroy()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
