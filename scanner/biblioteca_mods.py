"""Biblioteca de Mods integrada via janela Tkinter do próprio Assistente.

Abre como Toplevel da janela do overlay; não depende de serviço externo.
A análise ocorre em segundo plano. Dados incertos não são ativados.
"""
from __future__ import annotations

import json
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from auto_mods import DirectoryMonitor, ModCatalog, atomic_json, load_json
from integracao_overlay import overlay_snapshot
from investigador_iso import investigate

VERIFIED_LABELS = {
    "verificado": "✓ Confirmado",
    "verificado_x15": "✓ Confirmado somente X15",
    "extraídas": "✓ Extraído",
    "não_extraídas": "— Não extraído",
    "não_identificado": "? Significado desconhecido",
    "pendente": "— Pendente",
}
TABLE_COLUMNS = ("arquivo", "status", "cartas", "drops", "fusoes")


def preview_model(profile: dict, limit: int = 180) -> dict:
    """Modelo de prévia limitado — não usar tabelas sem supported_features."""
    features = profile.get("supported_features", {})
    cards = list(profile.get("cards", []))[:limit] if features.get("cards") else []
    opponents = list(profile.get("opponents", [])) if features.get("opponents") else []
    drops = list(profile.get("drops", []))[:limit] if features.get("drops") else []
    fusions = list(profile.get("fusion_recipes", []))[:limit] if features.get("fusions") else []
    return {
        "cards": cards, "opponents": opponents, "drops": drops, "fusions": fusions,
        "rank_confirmed": bool(features.get("ranks")),
        "scoring_confirmed": bool(features.get("scoring")),
        "profile_name": profile.get("name", ""),
    }


class BibliotecaMods(tk.Toplevel):
    def __init__(self, parent, on_activate=None, catalog=None):
        super().__init__(parent)
        self.title("Biblioteca de Mods — Forbidden Memories MultiMod")
        self.geometry("1120x750")
        self.minsize(850, 580)
        self.catalog = catalog or ModCatalog()
        self.on_activate = on_activate
        self.events = queue.Queue()
        self.monitor = None
        self._after_id = None
        self.settings_file = self.catalog.home / "biblioteca_settings.json"
        self.folder = tk.StringVar(value=load_json(self.settings_file, {}).get("folder", ""))
        self.status = tk.StringVar(value="Escolha uma pasta ou uma ISO/BIN para iniciar a análise.")
        self._build()
        self.refresh()
        self._poll()
        self.protocol("WM_DELETE_WINDOW", self.close)
        if self.folder.get() and Path(self.folder.get()).is_dir():
            self.after(350, self.watch)

    def _build(self):
        self.configure(background="#1b132c")
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="BIBLIOTECA DE MODS", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(main, text="Importe, valide, compare e ative perfis de ISOs locais; nada é alterado no jogo.").pack(anchor="w", pady=(2,10))
        top = ttk.Frame(main)
        top.pack(fill="x", pady=(0,8))
        ttk.Label(top, text="Monitorar pasta").pack(side="left")
        ttk.Entry(top, textvariable=self.folder).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Selecionar pasta", command=self.choose_folder).pack(side="left", padx=3)
        ttk.Button(top, text="Monitorar", command=self.watch).pack(side="left", padx=3)
        ttk.Button(top, text="Parar", command=self.stop_watch).pack(side="left", padx=3)
        actions = ttk.Frame(main)
        actions.pack(fill="x", pady=(0,9))
        ttk.Button(actions, text="Importar ISO/BIN", command=self.choose_file).pack(side="left", padx=(0,5))
        ttk.Button(actions, text="Atualizar lista", command=self.refresh).pack(side="left", padx=5)
        ttk.Button(actions, text="Investigar estrutura", command=self.investigate_selected).pack(side="left", padx=5)
        ttk.Button(actions, text="Ativar perfil no overlay", command=self.activate).pack(side="right")

        split = ttk.Panedwindow(main, orient="vertical")
        split.pack(fill="both", expand=True)
        upper = ttk.Frame(split)
        lower = ttk.Frame(split)
        split.add(upper, weight=2)
        split.add(lower, weight=3)
        cols = TABLE_COLUMNS
        self.tree = ttk.Treeview(upper, columns=cols, show="headings", height=7, selectmode="browse")
        for col, label, width in (
            ("arquivo","ISO / mod",310),("status","Validação",185),
            ("cartas","Cartas",95),("drops","Drops",95),("fusoes","Fusões",105)):
            self.tree.heading(col,text=label)
            self.tree.column(col,width=width,anchor="w")
        self.tree.pack(side="left",fill="both",expand=True)
        sb = ttk.Scrollbar(upper, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _evt: self.render())
        self.tabs = ttk.Notebook(lower)
        self.tabs.pack(fill="both",expand=True)
        self.info = tk.Text(self.tabs, wrap="word", font=("Consolas",10), height=10)
        self.tabs.add(self.info,text="Validação")
        self.tables = {}
        specs = {
            "Cartas": ("id","nome","atk","def"),
            "Oponentes": ("id","nome"),
            "Drops": ("oponente","grupo","carta","peso","probabilidade"),
            "Fusões": ("a","b","resultado"),
        }
        for name,fields in specs.items():
            frame = ttk.Frame(self.tabs)
            table = ttk.Treeview(frame, columns=fields, show="headings")
            for c in fields:
                table.heading(c,text=c.title())
                table.column(c,width=110 if c!="nome" else 280,anchor="w")
            table.pack(side="left",fill="both",expand=True)
            scroll = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
            scroll.pack(side="right",fill="y")
            table.configure(yscrollcommand=scroll.set)
            self.tabs.add(frame,text=name)
            self.tables[name]=table
        ttk.Label(main, textvariable=self.status, wraplength=1020).pack(fill="x", pady=(8,0))

    def selected(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return next((e for e in self.catalog.list() if e.get("sha256") == selection[0]), None)

    def refresh(self):
        previous = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for e in sorted(self.catalog.list(),key=lambda r:r.get("analysed_at",""),reverse=True):
            v=e.get("verified",{})
            status={"conhecido_validado":"Confirmado","parcial_revisar":"Parcial — revisar",
                    "desconhecido":"Não identificado"}.get(e.get("level"),"Pendente")
            self.tree.insert("","end",iid=e["sha256"],values=(
                e["file_name"],status,v.get("cartas","pendente"),
                v.get("tabelas_drops","pendente"),v.get("fusoes","pendente")))
        if previous and self.tree.exists(previous[0]):
            self.tree.selection_set(previous[0])
        self.render()

    def render(self):
        e=self.selected()
        p=self.catalog.profile_for(e) if e else None
        active=self.catalog.current()
        lines=[]
        if e and p:
            model=preview_model(p)
            lines.extend([
                "MOD: "+p.get("name",""),
                "ARQUIVO: "+e.get("file_name",""),
                "SHA-256: "+e.get("sha256",""),
                "STATUS: "+e.get("level",""),
                "ATIVO: "+("SIM" if active and active["sha256"]==e["sha256"] else "NÃO"),
                "",
                "VALIDAÇÃO E RASTREABILIDADE:",
            ])
            for k,v in sorted(p.get("verified",{}).items()):
                lines.append("  "+k+": "+VERIFIED_LABELS.get(str(v),str(v)))
            lines.extend(["","Somente dados comprováveis aparecem nas outras abas.",
                          "A seleção do arquivo NÃO comprova qual ISO está ativa no ePSXe.",
                          "Ranks e fusões desconhecidos ficam DESATIVADOS."])
        else:
            model={"cards":[],"opponents":[],"drops":[],"fusions":[]}
            lines=["Selecione um perfil da lista para revisar antes de ativar."]
        self.info.configure(state="normal")
        self.info.delete("1.0","end")
        self.info.insert("1.0","\n".join(lines))
        self.info.configure(state="disabled")
        rows={
            "Cartas":[(c.get("id"),c.get("name"),c.get("atk"),c.get("def")) for c in model["cards"]],
            "Oponentes":[(c.get("id"),c.get("name")) for c in model["opponents"]],
            "Drops":[(d.get("opponent_id"),d.get("group"),d.get("card_id"),d.get("weight"),
                       d.get("probability_percent")) for d in model["drops"]],
            "Fusões":[(f.get("a"),f.get("b"),f.get("result")) for f in model["fusions"]],
        }
        for key,table in self.tables.items():
            table.delete(*table.get_children())
            for vals in rows[key]:
                table.insert("","end",values=vals)
        self.status.set((e["file_name"]+": dados disponíveis para revisão.") if e else "Selecione um mod.")

    def _monitor(self, folder=None):
        if self.monitor:
            self.monitor.stop()
        self.monitor=DirectoryMonitor(Path(folder or self.folder.get()),
                                      self.catalog,self.events.put,interval=4,quiet_seconds=5)
        self.monitor.start()

    def choose_folder(self):
        folder=filedialog.askdirectory(title="Selecionar pasta de ISOs",parent=self)
        if folder:
            self.folder.set(folder)
            self.watch()

    def watch(self):
        folder=Path(self.folder.get())
        if not folder.is_dir():
            messagebox.showwarning("Pasta inválida","Selecione uma pasta existente.",parent=self)
            return
        self._monitor(folder)
        atomic_json(self.settings_file,{"folder":str(folder.resolve())})
        self.status.set("Monitoramento ativado: "+str(folder))

    def stop_watch(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor=None
        self.status.set("Monitoramento interrompido.")

    def choose_file(self):
        filename=filedialog.askopenfilename(
            title="Importar ISO ou BIN",filetypes=[("Imagens de disco","*.iso *.bin")],parent=self)
        if not filename:return
        image=Path(filename)
        if self.monitor is None:
            self._monitor(image.parent)
        self.monitor.scan_file(image)
        self.status.set("Enviado para análise: "+image.name)

    def investigate_selected(self):
        e=self.selected()
        if not e:return messagebox.showinfo("Biblioteca","Selecione uma ISO.",parent=self)
        p=self.catalog.profile_for(e)
        if p is None:return messagebox.showerror("Perfil","Perfil inválido.",parent=self)
        path=Path(e["source_path"])
        # Esta operação acessa apenas metadados internos do disco, e pode
        # ser executada após a análise principal, sem modificar o arquivo.
        if not path.is_file():
            return messagebox.showerror("ISO não encontrada",str(path),parent=self)
        self.status.set("Investigação estrutural em execução: "+path.name)
        import threading
        def work():
            try:
                out=self.catalog.home/"investigacoes"/(e["sha256"]+".json")
                report=investigate(path,p,out)
                self.events.put({"event":"investigacao","file":path.name,
                                 "report":report,"path":str(out)})
            except Exception as exc:
                self.events.put({"event":"erro","file":path.name,"message":str(exc)})
        threading.Thread(target=work,daemon=True,name="investigador-iso").start()

    def activate(self):
        e=self.selected()
        if not e:
            return messagebox.showinfo("Biblioteca","Selecione um perfil.",parent=self)
        if e["level"]=="desconhecido":
            return messagebox.showwarning("Estrutura desconhecida",
                   "O arquivo ainda não tem tabelas confiáveis. Nenhum catálogo será ativado.",parent=self)
        confirmed=messagebox.askyesno(
            "Ativar perfil no overlay",
            "Ativar dados de\n"+e["file_name"]+"?\n\n"
            "Confirme que esta é a MESMA ISO aberta no ePSXe.\n"
            "Dados sem validação (fusões, ranks etc.) serão desativados.\n"
            "A ISO original e os saves NÃO serão modificados.",
            parent=self)
        if not confirmed:return
        try:
            self.catalog.activate(e["sha256"],acknowledge_uncertainty=True)
            snapshot=overlay_snapshot(self.catalog)
            if self.on_activate:
                self.on_activate(snapshot)
        except Exception as exc:
            return messagebox.showerror("Ativação não concluída",str(exc),parent=self)
        self.refresh()
        self.status.set("Perfil confirmado: "+e["file_name"])
        messagebox.showinfo("Perfil ativado",
            "Perfil salvo e notificação enviada ao overlay.\n"
            "Recursos ainda desconhecidos permanecem indisponíveis.\n"
            "Se seu overlay antigo não suportar recarga, reinicie-o.",parent=self)

    def _poll(self):
        try:
            while True:
                evt=self.events.get_nowait()
                k=evt.get("event")
                if k=="concluido":
                    self.refresh()
                    self.status.set("Análise concluída: "+evt.get("file",""))
                elif k=="erro":
                    self.status.set("Falha em "+evt.get("file","")+": "+evt.get("message",""))
                elif k=="analisando":
                    self.status.set("Lendo ISO (somente leitura): "+evt.get("file",""))
                elif k=="encontrado":
                    self.status.set("Nova ISO detectada: "+evt.get("file",""))
                elif k=="investigacao":
                    report=evt["report"]
                    messagebox.showinfo("Investigação concluída",
                        "Relatório salvo em:\n"+evt["path"]+"\n\n"
                        "Candidatas de fusões: "+
                        str(len(report.get("candidates",{}).get("fusion_tables_u16",[])))+
                        "\nAtenção: candidatas NÃO são fusões validadas.",parent=self)
                    self.status.set("Relatório de investigação salvo.")
        except queue.Empty:
            pass
        self._after_id=self.after(300,self._poll)

    def close(self):
        if self._after_id is not None:
            self.after_cancel(self._after_id)
        self.stop_watch()
        self.destroy()


def abrir_biblioteca(parent, on_activate=None, catalog=None):
    """Abre janela dentro do mesmo processo Tkinter do overlay."""
    return BibliotecaMods(parent,on_activate=on_activate,catalog=catalog)


def ligar_ao_overlay(root, app=None, compact=None):
    """Integra Biblioteca ao app legado com tecla Ctrl+Shift+M e botão discreto.

    Recarrega apenas a parte confirmada (nomes, fusões quando houver). O
    overlay anfitrião continua responsável por atualizar visualizações/rank.
    """
    from tkinter import Misc

    def apply_snapshot(snapshot):
        if not snapshot.get("ready"):
            return
        features=snapshot.get("features",{})
        cards=snapshot["cards"] if features.get("nomes_cartas") else {}
        recipes=snapshot["recipes"] if features.get("fusoes") else []
        # Atualiza objetos de domínio sem falsear catálogos não reconhecidos.
        if app is not None:
            if hasattr(app,"apply_mod_profile"):
                app.apply_mod_profile(snapshot)
            else:
                if hasattr(app,"cards"):app.cards=cards
                if hasattr(app,"recipes"):app.recipes=recipes
                if hasattr(app,"index"):
                    idx={}
                    for a,b,c in recipes:
                        idx[(a,b)]=c
                        idx[(b,a)]=c
                    app.index=idx
        if compact is not None:
            if hasattr(compact,"cards"):compact.cards=cards
            if hasattr(compact,"recipes"):compact.recipes=recipes
            try:
                from estrategia_x15 import Strategist
                if hasattr(compact,"strategy"):
                    compact.strategy=Strategist(cards,recipes)
            except (ImportError,TypeError,ValueError):
                pass
            # Nunca reutilizar drops X15 para outro mod.
            if hasattr(compact,"atlas") and not features.get("rank"):
                compact.atlas={"opponents":[],"drops":[],"rankLabels":[]}
            if hasattr(compact,"_active_profile"):
                compact._active_profile=snapshot
            else:
                setattr(compact,"_active_profile",snapshot)
        # A interface legacy pode exigir reinício para reprojetar abas já renderizadas.

    win_candidates=[compact,root]
    for attr in ("win","window","top","root","frame","master"):
        if compact is not None:win_candidates.append(getattr(compact,attr,None))
    surface=next((w for w in win_candidates if isinstance(w,Misc)
                  and hasattr(w,"winfo_exists") and w.winfo_exists()),root)

    current={"window":None}
    def show(_event=None):
        existing=current["window"]
        if existing and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
        else:
            current["window"]=abrir_biblioteca(surface,on_activate=apply_snapshot)
        return "break"
    root.bind_all("<Control-Shift-M>",show,add="+")
    root.bind_all("<Control-Shift-m>",show,add="+")
    try:
        # place() não interfere com o geometry manager já utilizado no overlay.
        button=tk.Button(surface,text="📚 Biblioteca de Mods",command=show,
                         bg="#5b347c",fg="#ffffff",bd=0,cursor="hand2")
        button.place(relx=0.995,rely=0.99,anchor="se")
    except tk.TclError:
        button=None
    return {"open":show,"button":button,"callback":apply_snapshot}
