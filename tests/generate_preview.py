"""Prévia visual automatizada do DUELTRACE para o CI Windows.

A imagem usa perfis SINTÉTICOS sinalizados como teste. Nenhuma ROM é
lida/distribuída; a prévia não é evidência de compatibilidade com mods.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
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
            fake_cards=([{"id":n,"name":f"CARTA TESTE {n}",
                          "atk":n*400,"def":n*200} for n in range(1,6)]
                        + [{"id":200,"name":"FUSÃO TESTE 1",
                            "atk":1800,"def":1900},
                           {"id":201,"name":"FUSÃO TESTE 2",
                            "atk":2300,"def":1900},
                           {"id":202,"name":"FUSÃO TESTE 3",
                            "atk":2800,"def":1900},
                           {"id":203,"name":"FUSÃO TESTE FINAL",
                            "atk":3200,"def":2000}]) if number==3 else []
            fake_fusions=([
                {"a":1,"b":2,"result":200,
                 "validation":"extraida_sete_bancos_consistentes"},
                {"a":200,"b":3,"result":201,
                 "validation":"extraida_sete_bancos_consistentes"},
                {"a":201,"b":4,"result":202,
                 "validation":"extraida_sete_bancos_consistentes"},
                {"a":202,"b":5,"result":203,
                 "validation":"extraida_sete_bancos_consistentes"},
            ] if number==3 else [])
            atomic_json(p,{
                "rom_sha256":sha,"name":name,
                "supported_features":{"cards":number==3,"effects":False,
                                      "drops":False,"fusions":number==3,"art":False},
                "verified":{"cartas":"TESTE SINTÉTICO"},
                "cards":fake_cards,"opponents":[],"drops":[],
                "fusion_recipes":fake_fusions,
            })
            entries.append({"sha256":sha,"file_name":name,"level":level,
                            "profile_path":str(p),"source_path":str(home/name)})
        atomic_json(catalog.registry_file,{"schema":1,"entries":entries})
        active_sha=f"{3:064x}"
        atomic_json(catalog.active_file,{
            "sha256":active_sha,"features":{"nomes_cartas":True,"fusoes":True},
            "level":"TESTE_SINTETICO",
        })
        app=DueltraceDesktop(catalog=catalog,developer=False)
        gui_errors=[]
        def record_callback_error(error_class,error_value,traceback_object):
            details="".join(traceback.format_exception(
                error_class,error_value,traceback_object))
            gui_errors.append(details)
            print("ERRO NO CALLBACK TKINTER:",details,file=sys.stderr)
        app.report_callback_exception=record_callback_error
        try:
            app.geometry("1360x780+80+80")
            app.update()
            app._render_live_hand({
                "ready":True,"hand_ids":[1,2,3,4,5],
                "pid":None,"status":"SIMULAÇÃO — NÃO CONECTADO À RAM",
            })
            app.update_idletasks()
            x,y=app.winfo_rootx(),app.winfo_rooty()
            w,h=app.winfo_width(),app.winfo_height()
            dest=Path("dist")/"DUELTRACE-PREVIA-INICIO-TESTE.png"
            dest.parent.mkdir(exist_ok=True)
            try:
                ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(dest)
                print("Prévia inicial de dados sintéticos:",dest.resolve())
            except OSError as exc:
                print(f"Prévia Inicial indisponível: {exc}")
            app._set_home_fusion_mode("chains")
            app.update_idletasks()
            dest=Path("dist")/"DUELTRACE-PREVIA-ROTAS-TESTE.png"
            try:
                ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(dest)
                print("Prévia de cadeias sintéticas:",dest.resolve())
            except OSError as exc:
                print(f"Prévia Rotas indisponível: {exc}")
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
            app.update_idletasks()
            app.update()
            if gui_errors:
                raise RuntimeError(
                    "Callback(s) gráficos falharam durante a prévia: "
                    + " | ".join(x.splitlines()[-1] for x in gui_errors))
        finally:
            app.destroy()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
