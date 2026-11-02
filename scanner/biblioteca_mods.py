"""Biblioteca de Mods integrada via janela Tkinter do próprio Assistente.

Abre como Toplevel da janela do overlay; não depende de serviço externo.
A análise ocorre em segundo plano. Dados incertos não são ativados.
"""
from __future__ import annotations

import json
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from auto_mods import DirectoryMonitor, ModCatalog, atomic_json, load_json
from integracao_overlay import overlay_snapshot
from integracao_overlay import OverlayProfileObserver
from overlay_profile_bridge import apply_overlay_profile
from investigador_iso import investigate
from extrator_fusoes import analyze_fusion_banks, save_fusion_report
from ia_local import analyse_with_local_ai, save_suggestion, DEFAULT_MODEL
from overlay_card_labels import CardLabelSync

VERIFIED_LABELS = {
    "verificado": "✓ Confirmado",
    "verificado_x15": "✓ Confirmado somente X15",
    "extraídas": "✓ Extraído",
    "não_extraídas": "— Não extraído",
    "não_identificado": "? Significado desconhecido",
    "pendente": "— Pendente",
}
TABLE_COLUMNS = ("arquivo", "status", "cartas", "drops", "fusoes")


def preview_model(profile: dict, limit: int | None = None) -> dict:
    """Dados validados para a UI. Sem limite por padrão: 722 cartas ficam acessíveis.

    limit é mantido apenas para consumidores que escolham paginação explícita.
    Nunca importa dados marcados como não verificados.
    """
    features = profile.get("supported_features", {})
    def visible(key, enabled):
        if not enabled:
            return []
        records = list(profile.get(key, []))
        return records[:max(0, limit)] if limit is not None else records
    return {
        "cards": visible("cards", features.get("cards")),
        "opponents": visible("opponents", features.get("opponents")),
        "drops": visible("drops", features.get("drops")),
        "fusions": visible("fusion_recipes", features.get("fusions")),
        "rank_confirmed": bool(features.get("ranks")),
        "scoring_confirmed": bool(features.get("scoring")),
        "profile_name": profile.get("name", ""),
    }


def filter_cards(cards: list, query: str) -> list:
    """Busca local por ID numérico exato ou parte do nome, sem tocar na ISO."""
    value = query.strip().casefold()
    if not value:
        return list(cards)
    if value.isdecimal():
        return [card for card in cards if str(card.get("id", "")) == value]
    return [card for card in cards if value in str(card.get("name", "")).casefold()]


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
        self._manual_pending=set()
        self.progress_var=tk.DoubleVar(value=0.0)
        self._after_id = None
        self.settings_file = self.catalog.home / "biblioteca_settings.json"
        saved_settings=load_json(self.settings_file, {})
        self.folder = tk.StringVar(value=saved_settings.get("folder", ""))
        self.auto_ai=tk.BooleanVar(value=bool(saved_settings.get("auto_ai",False)))
        self.auto_watch=bool(saved_settings.get("auto_watch",False))
        self.ai_model=tk.StringVar(value=saved_settings.get("ai_model",DEFAULT_MODEL))
        self.card_query=tk.StringVar(value="")
        self.card_rows=[]
        self.fusion_rows=[]
        self.fusion_names={}
        self.fusion_source_sha=None
        self.fusion_query=tk.StringVar(value="")
        self.fusion_count=tk.StringVar(value="Nenhuma candidata carregada")
        self._fusion_filter_after=None
        self.card_count=tk.StringVar(value="0 cartas")
        self._card_filter_after=None
        self.status = tk.StringVar(value="Escolha uma pasta ou uma ISO/BIN para iniciar a análise.")
        self._build()
        self.refresh()
        self._poll()
        self.protocol("WM_DELETE_WINDOW", self.close)
        # Só monitorar automaticamente caso o usuário tenha ativado essa opção.
        if self.auto_watch and self.folder.get() and Path(self.folder.get()).is_dir():
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
        ttk.Button(actions, text="Buscar fusões na ISO", command=self.search_fusions).pack(side="left", padx=5)
        ttk.Button(actions, text="IA local: investigar", command=self.ai_selected).pack(side="left", padx=5)
        ttk.Checkbutton(actions,text="IA automática (local)",variable=self.auto_ai,command=self.save_settings).pack(side="left",padx=5)
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
            if name == "Cartas":
                search=ttk.Frame(frame)
                search.pack(fill="x", padx=4, pady=(4,3))
                ttk.Label(search,text="Buscar ID ou nome:").pack(side="left",padx=(0,5))
                ttk.Entry(search,textvariable=self.card_query).pack(side="left",fill="x",expand=True)
                ttk.Label(search,textvariable=self.card_count).pack(side="right",padx=(10,0))
                self.card_query.trace_add("write",lambda *_:self.schedule_card_filter())
            body=ttk.Frame(frame)
            body.pack(fill="both",expand=True)
            table = ttk.Treeview(body, columns=fields, show="headings")
            for c in fields:
                table.heading(c,text=c.title())
                table.column(c,width=110 if c!="nome" else 280,anchor="w")
            table.pack(side="left",fill="both",expand=True)
            scroll = ttk.Scrollbar(body, orient="vertical", command=table.yview)
            scroll.pack(side="right",fill="y")
            table.configure(yscrollcommand=scroll.set)
            self.tabs.add(frame,text=name)
            self.tables[name]=table
        # Os dados desta aba são CANDIDATAS extraídas do WA_MRG;
        # não se confundem com a aba Fusões, que mostra só as confirmadas.
        candidates_frame=ttk.Frame(self.tabs)
        toolbar=ttk.Frame(candidates_frame)
        toolbar.pack(fill="x",padx=4,pady=5)
        ttk.Label(toolbar,text="Candidatas — ID ou nome:").pack(side="left",padx=3)
        ttk.Entry(toolbar,textvariable=self.fusion_query,width=13).pack(side="left",padx=3)
        self.fusion_query.trace_add("write",lambda *_:self.schedule_fusion_filter())
        ttk.Label(toolbar,textvariable=self.fusion_count).pack(side="left",padx=8)
        ttk.Button(toolbar,text="Confirmar receita observada no jogo",
                   command=self.confirm_selected_fusion).pack(side="right",padx=3)
        area=ttk.Frame(candidates_frame)
        area.pack(fill="both",expand=True)
        self.fusion_candidates_table=ttk.Treeview(
            area,columns=("a","b","result","evidencia"),show="headings",selectmode="browse")
        for name,label,width in (
            ("a","Material A",200),("b","Material B",200),
            ("result","Resultado",200),("evidencia","Estado",200)):
            self.fusion_candidates_table.heading(name,text=label)
            self.fusion_candidates_table.column(name,width=width,anchor="w")
        self.fusion_candidates_table.pack(side="left",fill="both",expand=True)
        scroll=ttk.Scrollbar(area,orient="vertical",command=self.fusion_candidates_table.yview)
        scroll.pack(side="right",fill="y")
        self.fusion_candidates_table.configure(yscrollcommand=scroll.set)
        self.tabs.add(candidates_frame,text="Candidatas (fusões)")

        ttk.Label(main, textvariable=self.status, wraplength=1020).pack(fill="x", pady=(8,0))
        ttk.Progressbar(main, variable=self.progress_var, maximum=100,
                        mode="determinate").pack(fill="x", pady=(4,0))

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
        self.card_rows=sorted(model["cards"],key=lambda x: int(x.get("id") or 0))
        self.fusion_names={int(c["id"]):str(c["name"]) for c in model["cards"]}
        self.render_card_rows()
        # Troca de mod NUNCA deve mostrar candidatas do perfil anterior.
        candidate_sha=e["sha256"] if e else None
        if candidate_sha!=self.fusion_source_sha:
            self.fusion_source_sha=candidate_sha
            self.load_fusion_candidates()
        rows={
            "Oponentes":[(c.get("id"),c.get("name")) for c in model["opponents"]],
            "Drops":[(d.get("opponent_id"),d.get("group"),d.get("card_id"),d.get("weight"),
                       d.get("probability_percent")) for d in model["drops"]],
            "Fusões":[(f.get("a"),f.get("b"),f.get("result")) for f in model["fusions"]],
        }
        for key,vals_rows in rows.items():
            table=self.tables[key]
            table.delete(*table.get_children())
            for vals in vals_rows:
                table.insert("","end",values=vals)
        self.status.set((e["file_name"]+": dados disponíveis para revisão.") if e else "Selecione um mod.")

    def schedule_card_filter(self):
        if self._card_filter_after is not None:
            self.after_cancel(self._card_filter_after)
        self._card_filter_after=self.after(150,self.render_card_rows)

    def render_card_rows(self):
        self._card_filter_after=None
        table=self.tables["Cartas"]
        table.delete(*table.get_children())
        matches=filter_cards(self.card_rows,self.card_query.get())
        for row in matches:
            table.insert("","end",values=(row.get("id"),row.get("name"),
                                           row.get("atk"),row.get("def")))
        self.card_count.set(f"{len(matches)} de {len(self.card_rows)} cartas")

    def load_fusion_candidates(self):
        entry=self.selected()
        path=(self.catalog.home/"investigacoes"/(entry["sha256"]+".fusoes.json")) if entry else None
        report=load_json(path,{}) if path else {}
        if not entry or report.get("rom_sha256")!=entry["sha256"]:
            self.fusion_rows=[]
            self.fusion_report={}
        else:
            self.fusion_rows=list(report.get("candidates",[]))
            self.fusion_report=report
        self.render_fusion_candidates()

    def schedule_fusion_filter(self):
        if self._fusion_filter_after is not None:
            self.after_cancel(self._fusion_filter_after)
        self._fusion_filter_after=self.after(180,self.render_fusion_candidates)

    def render_fusion_candidates(self):
        self._fusion_filter_after=None
        table=self.fusion_candidates_table
        table.delete(*table.get_children())
        q=self.fusion_query.get().strip()
        entries=self.fusion_rows
        if q:
            if q.isdecimal():
                num=int(q)
                entries=[r for r in entries if num in (r.get("a"),r.get("b"),r.get("result"))]
            else:
                q=q.casefold()
                entries=[r for r in entries if any(
                    q in self.fusion_names.get(int(r.get(k,0)),"").casefold()
                    for k in ("a","b","result")
                )]
        # Manter a interface responsiva em mods com milhares de receitas.
        # NUNCA ocultar o truncamento: mostrar a contagem completa.
        page=entries[:750]
        for i,r in enumerate(page):
            def label(k):
                cid=int(r[k])
                return f"#{cid:03d} {self.fusion_names.get(cid,'?')}"
            table.insert("","end",iid=str(i),values=(
                label("a"),label("b"),label("result"),
                "CANDIDATA — não validada"))
        self.fusion_display_rows=page
        self.fusion_count.set(
            f"Mostrando {len(page)} de {len(entries)} candidatas; "
            "pesquise um ID para localizar outras. "+
            ("Bancos espelhados: "+str(self.fusion_report.get("matching_banks",0))
             if getattr(self,"fusion_report",None) else "Execute Buscar fusões")
        )

    def search_fusions(self):
        e=self.selected()
        if not e:
            return messagebox.showinfo("Fusões","Selecione uma ISO na lista.",parent=self)
        path=Path(e["source_path"])
        if not path.is_file():
            return messagebox.showerror("ISO não encontrada",str(path),parent=self)
        if getattr(self,"_fusion_busy",False):
            self.status.set("Uma investigação de fusões já está em andamento.")
            return
        self._fusion_busy=True
        self.status.set("Extraindo sete bancos de fusões de "+path.name+"...")
        import threading
        def work():
            try:
                report=analyze_fusion_banks(path,expected_size=e.get("size"),
                    expected_mtime_ns=e.get("mtime_ns"))
                report["rom_sha256"]=e["sha256"]
                output=self.catalog.home/"investigacoes"/(e["sha256"]+".fusoes.json")
                save_fusion_report(output,report)
                self.events.put({"event":"fusoes_encontradas","file":path.name,
                                 "sha256":e["sha256"],"report":report,"path":str(output)})
            except Exception as exc:
                self.events.put({"event":"erro","file":path.name,
                                 "message":"Fusões: "+str(exc)})
            finally:
                self.events.put({"event":"fim_busca_fusoes"})
        threading.Thread(target=work,daemon=True,name="busca-fusoes-rom").start()

    def confirm_selected_fusion(self):
        entry=self.selected()
        selection=self.fusion_candidates_table.selection()
        if not entry or not selection or not getattr(self,"fusion_display_rows",None):
            return messagebox.showinfo("Validação","Selecione uma receita candidata.",parent=self)
        if entry["sha256"]!=self.fusion_source_sha:
            return messagebox.showwarning("Mod incorreto","As candidatas não pertencem ao perfil selecionado.",parent=self)
        recipe=self.fusion_display_rows[int(selection[0])]
        a,b,result=(int(recipe[k]) for k in ("a","b","result"))
        observed=simpledialog.askinteger("Verificar no jogo",
            f"Fusão candidata: #{a} + #{b} = #{result}\n"
            "Execute a fusão na ISO correspondente no emulador.\n"
            "Digite o ID do resultado que você realmente viu no duelo "
            "(Cancelar não altera nada):",
            minvalue=1,maxvalue=722,parent=self)
        if observed is None:
            return
        if observed!=result:
            self.status.set("A fusão observada divergiu da extração; não será ativada.")
            return messagebox.showwarning("Divergência",
                "Resultado observado difere do candidato; nenhuma receita foi ativada.",
                parent=self)
        if not messagebox.askyesno("Confirmar 1 fusão",
            f"Você observou no jogo #{a} + #{b} = #{result}?\n"
            "Essa confirmação habilitará SOMENTE ESTA receita no overlay, "
            "nunca o banco inteiro.",parent=self):
            return
        try:
            number=self.catalog.confirm_fusion(entry["sha256"],a,b,result)
            self.refresh()
        except Exception as exc:
            return messagebox.showerror("Falha de validação",str(exc),parent=self)
        self.status.set(f"{number} fusão(ões) confirmada(s) individualmente para "+entry["file_name"])
        messagebox.showinfo("Receita confirmada",
            "Receita validada pelo usuário e vinculada ao SHA da ISO. "
            "As demais candidatas continuam indisponíveis.",parent=self)

    def _monitor(self, folder=None):
        if self.monitor:
            self.monitor.stop()
        self.monitor=DirectoryMonitor(Path(folder or self.folder.get()),
                                      self.catalog,self.events.put,interval=4,quiet_seconds=5)
        self.monitor.start()

    def save_settings(self):
        atomic_json(self.settings_file,{
            "folder":self.folder.get().strip(),
            "auto_watch":self.auto_watch,
            "auto_ai":bool(self.auto_ai.get()),
            "ai_model":self.ai_model.get().strip() or DEFAULT_MODEL,
        })

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
        self.auto_watch=True
        self.save_settings()
        self.status.set("Monitoramento ativado: "+str(folder))

    def stop_watch(self, *, persist=True):
        if self.monitor:
            self.monitor.stop()
            self.monitor=None
        if persist:
            self.auto_watch=False
            self.save_settings()
        self.status.set("Monitoramento interrompido.")

    def choose_file(self):
        filename=filedialog.askopenfilename(
            title="Importar ISO ou BIN",filetypes=[("Imagens de disco","*.iso *.bin")],parent=self)
        if not filename:return
        image=Path(filename)
        # Importar UM arquivo não ativa a varredura de toda a pasta de ROMs.
        if self.monitor is not None:
            self.monitor.scan_file(image)
            self.status.set("Arquivo colocado na fila de monitoramento: "+image.name)
            return
        key=str(image.resolve())
        if key in self._manual_pending:
            self.status.set("Este arquivo já está sendo analisado: "+image.name)
            return
        self._manual_pending.add(key)
        self.progress_var.set(0.0)
        self.status.set("Análise individual iniciada: "+image.name)
        import threading
        def task():
            try:
                self.events.put({"event":"analisando","file":image.name})
                def progress(stage,done,total):
                    self.events.put({"event":"progresso","file":image.name,
                                     "stage":stage,"percent":round(done*100/total) if total else None})
                entry=self.catalog.analyse(image,progress=progress)
                self.events.put({"event":"concluido","file":image.name,
                                 "level":entry["level"],"sha256":entry["sha256"]})
            except Exception as exc:
                self.events.put({"event":"erro","file":image.name,"message":str(exc)})
            finally:
                self.events.put({"event":"import_done","file":image.name,"key":key})
        threading.Thread(target=task,daemon=True,name="importar-rom").start()

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

    def ai_selected(self):
        e=self.selected()
        if not e:
            return messagebox.showinfo("IA local","Selecione uma ISO já analisada.",parent=self)
        self._launch_local_ai(e)

    def _launch_local_ai(self,e):
        p=self.catalog.profile_for(e)
        if not p:
            self.status.set("IA: perfil ainda não disponível para investigação.")
            return
        iso=Path(e.get("source_path",""))
        if not iso.is_file():
            self.status.set("IA: arquivo ISO não encontrado na pasta original.")
            return
        model=self.ai_model.get().strip() or DEFAULT_MODEL
        self.save_settings()
        self.status.set("IA local: preparando evidências para "+iso.name)
        import threading
        def task():
            try:
                evidence_path=self.catalog.home/"investigacoes"/(e["sha256"]+".json")
                report=investigate(iso,p,evidence_path)
                suggestion=analyse_with_local_ai(report,model=model)
                output=self.catalog.home/"investigacoes"/(e["sha256"]+".ia.json")
                save_suggestion(output,suggestion)
                self.events.put({"event":"ia_concluida","file":iso.name,"path":str(output),
                                 "summary":suggestion.get("resumo","")})
            except Exception as exc:
                self.events.put({"event":"erro","file":iso.name,
                                 "message":"IA local: "+str(exc)})
        threading.Thread(target=task,daemon=True,name="ia-local-investigacao").start()

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
            visual_result=self.on_activate(snapshot) if self.on_activate else {}
        except Exception as exc:
            return messagebox.showerror("Ativação não concluída",str(exc),parent=self)
        self.refresh()
        self.status.set("Perfil confirmado: "+e["file_name"])
        has_cards=len(snapshot.get("cards",{}))
        updated=(visual_result or {}).get("visual_labels_changed")
        visual_status=(f"Rótulos atualizados no momento: {updated}.\n"
                       if isinstance(updated,int) else
                       "A atualização visual depende do painel do Assistente.\n")
        messagebox.showinfo("Perfil ativado",
            "Perfil confirmado:\n"+e["file_name"]+"\n\n"+
            f"{has_cards} cartas disponíveis no catálogo para leitura da mão.\n"+
            visual_status+
            "A identificação automática da ISO ativa no ePSXe ainda não é garantida.\n"+
            "Ranqueamento e fusões não verificados permanecem desativados.",parent=self)

    def _poll(self):
        try:
            while True:
                evt=self.events.get_nowait()
                k=evt.get("event")
                if k=="concluido":
                    self.refresh()
                    self.progress_var.set(100.0)
                    self.status.set("Análise concluída: "+evt.get("file",""))
                    if self.auto_ai.get() and evt.get("level")!="conhecido_validado":
                        entry=next((e for e in self.catalog.list() if e.get("sha256")==evt.get("sha256")),None)
                        if entry:self._launch_local_ai(entry)
                elif k=="erro":
                    self.status.set("Falha em "+evt.get("file","")+": "+evt.get("message",""))
                elif k=="import_done":
                    self._manual_pending.discard(evt["key"])
                elif k=="progresso":
                    pc=evt.get("percent")
                    if isinstance(pc,(int,float)):
                        self.progress_var.set(max(0,min(100,pc)))
                    extra=(" ("+str(pc)+"%)") if isinstance(pc,(int,float)) and pc>0 else ""
                    self.status.set(evt.get("file","")+" — "+evt.get("stage","Lendo ISO")+extra)
                elif k=="analisando":
                    self.status.set("Lendo ISO (somente leitura): "+evt.get("file",""))
                elif k=="encontrado":
                    self.status.set("Nova ISO detectada: "+evt.get("file",""))
                elif k=="ia_concluida":
                    self.load_fusion_candidates()
                    self.status.set("IA local: hipóteses salvas em "+evt["path"])
                    messagebox.showinfo("IA local — não validado",
                        "Sugestões salvas em:\n"+evt["path"]+"\n\n"+
                        evt.get("summary","")[:650]+
                        "\n\nNenhum dado de jogo foi alterado pela IA.",parent=self)
                elif k=="fusoes_encontradas":
                    if self.fusion_source_sha==evt["sha256"]:
                        self.load_fusion_candidates()
                        self.tabs.select(self.fusion_candidates_table.master.master)
                    self.status.set(
                        f"{evt['file']}: {evt['report']['candidate_count']} candidatas, "+
                        f"{evt['report']['matching_banks']} bancos coincidentes. "
                        "Nenhuma foi ativada automaticamente.")
                    if self.auto_ai.get() and evt["report"]["candidate_count"]>0:
                        entry=next((x for x in self.catalog.list()
                                    if x.get("sha256")==evt["sha256"]),None)
                        if entry:self._launch_local_ai(entry)
                elif k=="fim_busca_fusoes":
                    self._fusion_busy=False
                elif k=="investigacao":
                    report=evt["report"]
                    summary=report.get("candidates",{}).get("fusion_bank_summary",{})
                    self.load_fusion_candidates()
                    messagebox.showinfo("Investigação concluída",
                        "Relatório salvo em:\n"+evt["path"]+"\n\n"+
                        f"WA_MRG: {summary.get('candidate_count',0)} receitas candidatas; "+
                        f"{summary.get('matching_banks',0)} bancos coincidentes.\n"+
                        f"Formato: {summary.get('status','não identificado')}\n"+
                        "Abra a aba Candidatas (fusões) para revisar.\n"+
                        "Atenção: candidatas NÃO são fusões validadas.",parent=self)
                    self.status.set("Relatório de investigação salvo.")
        except queue.Empty:
            pass
        self._after_id=self.after(300,self._poll)

    def close(self):
        if self._after_id is not None:
            self.after_cancel(self._after_id)
        if self._card_filter_after is not None:
            self.after_cancel(self._card_filter_after)
        if self._fusion_filter_after is not None:
            self.after_cancel(self._fusion_filter_after)
        self.stop_watch(persist=False)
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

    win_candidates=[]
    for attr in ("win","window","top","root","frame","master"):
        if compact is not None:win_candidates.append(getattr(compact,attr,None))
    win_candidates.extend([compact,root])
    surface=next((w for w in win_candidates if isinstance(w,Misc)
                  and hasattr(w,"winfo_exists") and w.winfo_exists()),root)
    if surface is root:
        for widget in root.winfo_children():
            if isinstance(widget,tk.Toplevel) and "multimod" in widget.title().lower():
                surface=widget
                break

    # Painéis legados podem continuar desenhando o marcador textual
    # "Carta #123 (ID somente)" mesmo após atualização dos dicts.
    # Um sincronizador visual conservador atualiza apenas esses rótulos.
    renderer=CardLabelSync(root,roots=(root,surface,compact))
    def apply_snapshot(snapshot):
        summary=apply_overlay_profile(snapshot,app=app,compact=compact)
        renderer.use_snapshot(snapshot)
        summary["visual_labels_changed"]=renderer.last_changed
        if summary.get("applied"):
            print("MultiMod: perfil carregado no overlay — "+
                  str(summary.get("profile_name",""))+
                  " ("+str(summary.get("card_count",0))+" cartas).",flush=True)
        return summary

    observer=OverlayProfileObserver(root,apply_snapshot)
    observer.start()
    renderer.start()

    # assistente_x15.App.__init__ agenda initialize_profile após criar o
    # hook (root.after(100)). Essa rotina pode substituir de novo self.cards
    # por um perfil "unknown", mesmo com a Biblioteca já ativada. A cada
    # 1,8 s verifique SOMENTE se o catálogo ativo sofreu esse sobrescrito;
    # reaplique quando necessário. Não reinicie a mão todo ciclo.
    def ensure_profile_current():
        try:
            if not root.winfo_exists():
                return
            current_snapshot=overlay_snapshot()
            if current_snapshot.get("ready") and current_snapshot.get("features",{}).get("nomes_cartas"):
                expected=current_snapshot.get("cards",{})
                # Comparar também nomes, não apenas quantidade (mods podem
                # conter as mesmas 722 IDs com nomes diferentes).
                sample_keys=tuple(sorted(expected)[:3])+tuple(sorted(expected)[-3:])
                def catalog_drift(holder):
                    if holder is None:
                        return False
                    actual=getattr(holder,"cards",None)
                    if not isinstance(actual,dict):
                        return True
                    if len(actual)!=len(expected):
                        return True
                    return any(actual.get(cid)!=expected[cid] for cid in sample_keys)
                if catalog_drift(app) or catalog_drift(compact):
                    print("MultiMod: catálogo do overlay alterado pelo perfil legado; restaurando perfil aprovado.",flush=True)
                    apply_snapshot(current_snapshot)
        except Exception as exc:
            print("MultiMod: não foi possível verificar o catálogo ativo:",str(exc),flush=True)
        finally:
            try:
                if root.winfo_exists():
                    root.after(1800,ensure_profile_current)
            except Exception:
                pass

    root.after(400,ensure_profile_current)

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
    return {"open":show,"button":button,"callback":apply_snapshot,
            "observer":observer,"renderer":renderer}
