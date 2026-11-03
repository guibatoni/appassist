"""DUELTRACE Desktop — novo launcher Windows com navegação animada.

Os números vêm exclusivamente de perfis do ModCatalog; textos de efeitos
sem origem ficam indisponíveis. A janela antiga continua acessível para
ferramentas avançadas. A análise é local e roda fora da thread da interface.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from auto_mods import ModCatalog, atomic_json, load_json
from card_catalog import CARD_CATEGORIES
from mod_autopilot import ModAutopilot, profile_summary
from integracao_overlay import overlay_snapshot
from dueltrace_brand import apply_window_icon
from dueltrace_theme import (
    BACKGROUND,SIDEBAR,PANEL,PANEL_ALT,BLUE,GOLD,GREEN,RED,TEXT,MUTED,
    Panel,NeonButton,setup_theme,text_label,card_stat,
)

PAGES=(
    ("Início","inicio"),("Biblioteca de Mods","mods"),
    ("Biblioteca de Cartas","cartas"),("Fusões","fusoes"),
    ("Overlay","overlay"),("Diagnóstico","diagnostico"),
    ("Configurações","configuracoes"),
)


class DueltraceDesktop(tk.Tk):
    def __init__(self, *, catalog=None):
        super().__init__()
        self.title("DUELTRACE — MultiMod Companion")
        self.geometry("1330x830")
        self.minsize(1080,700)
        self.configure(background=BACKGROUND)
        try:apply_window_icon(self)
        except tk.TclError:pass
        setup_theme(self)
        self.catalog=catalog or ModCatalog()
        self.autopilot=ModAutopilot(self.catalog)
        self.settings_path=self.catalog.home/"dueltrace_desktop_settings.json"
        settings=load_json(self.settings_path,{})
        older=load_json(self.catalog.home/"biblioteca_settings.json",{})
        self.folder=tk.StringVar(value=settings.get("folder") or older.get("folder",""))
        self.auto_start=tk.BooleanVar(value=settings.get("auto_scan_on_start",True))
        self.status=tk.StringVar(value="Pronto — selecione uma ISO/BIN ou uma pasta de mods.")
        self.selected_sha=None
        self.inbox=queue.Queue()
        self.busy=False
        self.active_page=None
        self.page_frame=None
        self._buttons={}
        self._legacy_window=None
        self._build_shell()
        self.go("inicio")
        self.after(140,self._poll_events)
        if self.auto_start.get() and self.folder.get() and Path(self.folder.get()).is_dir():
            self.after(650,self.scan_folder)
        self.protocol("WM_DELETE_WINDOW",self._close)

    def _build_shell(self):
        top=tk.Frame(self,background=SIDEBAR,height=78,
                     highlightbackground=BLUE,highlightthickness=1)
        top.pack(fill="x",side="top")
        top.pack_propagate(False)
        brand=tk.Frame(top,background=SIDEBAR)
        brand.pack(side="left",padx=25,pady=9)
        text_label(brand,"▽  DUELTRACE",color=BLUE,size=24,strong=True,bg=SIDEBAR).pack(anchor="w")
        text_label(brand,"MULTIMOD COMPANION  •  WINDOWS",color=GOLD,size=9,bg=SIDEBAR).pack(anchor="w")
        self.header_status=text_label(top,"●  Sistema local",color=GREEN,size=10,bg=SIDEBAR)
        self.header_status.pack(side="right",padx=26)
        body=tk.Frame(self,background=BACKGROUND)
        body.pack(fill="both",expand=True)
        sidebar=tk.Frame(body,background=SIDEBAR,width=240,
                         highlightbackground="#1A4662",highlightthickness=1)
        sidebar.pack(side="left",fill="y")
        sidebar.pack_propagate(False)
        text_label(sidebar,"NAVEGAÇÃO",color=GOLD,size=10,strong=True,bg=SIDEBAR).pack(
            anchor="w",padx=20,pady=(24,10))
        for name,key in PAGES:
            button=NeonButton(sidebar,name,lambda p=key:self.go(p),
                              width=213,height=46)
            button.pack(pady=4,padx=13)
            self._buttons[key]=button
        tk.Frame(sidebar,background=SIDEBAR).pack(fill="both",expand=True)
        text_label(sidebar,"✧  Análise local e segura",color=MUTED,size=9,bg=SIDEBAR).pack(
            anchor="w",padx=20,pady=8)
        self.stage=tk.Frame(body,background=BACKGROUND)
        self.stage.pack(side="left",fill="both",expand=True)
        footer=tk.Frame(self,background=SIDEBAR,height=32)
        footer.pack(side="bottom",fill="x")
        tk.Label(footer,textvariable=self.status,background=SIDEBAR,
                 foreground=MUTED,anchor="w",font=("Segoe UI",9)).pack(
                     fill="x",padx=18,pady=5)

    def _label(self,parent,title,description=None):
        text_label(parent,title,color=GOLD,size=21,strong=True).pack(anchor="w",pady=(3,3))
        if description:
            text_label(parent,description,color=MUTED,size=10).pack(anchor="w",pady=(0,16))

    def _action(self,parent,caption,fn,*,accent=BLUE,width=178):
        button=NeonButton(parent,caption,fn,width=width,height=43,accent=accent)
        return button

    def go(self,key):
        if key==self.active_page and self.page_frame:
            return
        self.active_page=key
        for k,b in self._buttons.items():
            b.set_active(k==key)
        page=tk.Frame(self.stage,background=BACKGROUND)
        page.place(x=30,y=0,relwidth=1,relheight=1)
        render=getattr(self,"_page_"+key)
        render(page)
        previous=self.page_frame
        self.page_frame=page
        for step in range(1,10):
            def move(step=step, target=page, old=previous):
                if not target.winfo_exists():return
                target.place_configure(x=round(30*(1-step/9)))
                if old and old.winfo_exists():
                    old.place_configure(x=-round(step*14/9))
                if step==9 and old and old.winfo_exists():old.destroy()
            self.after(15*step,move)

    def _selected_entry(self):
        entries=self.catalog.list()
        active=self.catalog.current()
        sha=self.selected_sha or (active.get("sha256") if active else None)
        return next((e for e in entries if e.get("sha256")==sha),None)

    def _profile(self):
        entry=self._selected_entry()
        return (entry,self.catalog.profile_for(entry)) if entry else (None,None)

    def _page_inicio(self,page):
        body=tk.Frame(page,background=BACKGROUND)
        body.pack(fill="both",expand=True,padx=22,pady=19)
        hero=Panel(body)
        hero.pack(fill="x",pady=(0,16))
        text_label(hero,"BEM-VINDO AO DUELTRACE",color=GOLD,size=23,strong=True,bg=PANEL).pack(anchor="w")
        text_label(hero,
            "Detecte o mod, identifique cartas e prepare o perfil em poucos cliques. "
            "Dados não reconhecidos permanecem sob revisão.",
            color=TEXT,size=11,bg=PANEL).pack(anchor="w",pady=(7,11))
        buttons=tk.Frame(hero,background=PANEL)
        buttons.pack(anchor="w")
        self._action(buttons,"Selecionar ISO/BIN",self.choose_file,accent=GOLD).pack(side="left",padx=(0,10))
        self._action(buttons,"Biblioteca de Mods",lambda:self.go("mods")).pack(side="left",padx=(0,10))
        self._action(buttons,"Biblioteca de Cartas",lambda:self.go("cartas")).pack(side="left")
        stats=tk.Frame(body,background=BACKGROUND)
        stats.pack(fill="x",pady=(0,15))
        entries=self.catalog.list()
        active=self.catalog.current()
        known=sum(x.get("level")=="conhecido_validado" for x in entries)
        for t,v in (("MODS CADASTRADOS",len(entries)),
                    ("PERFIS CONHECIDOS",known),
                    ("MOD ATIVO","Sim" if active else "Nenhum")):
            card_stat(stats,t,v).pack(side="left",fill="both",expand=True,padx=6)
        panels=tk.Frame(body,background=BACKGROUND)
        panels.pack(fill="both",expand=True)
        left=Panel(panels);left.pack(side="left",fill="both",expand=True,padx=(0,7))
        text_label(left,"MOD ATIVO",color=BLUE,size=13,strong=True,bg=PANEL).pack(anchor="w")
        profile=None
        if active:
            entry=next((x for x in entries if x["sha256"]==active.get("sha256")),None)
            if entry:profile=self.catalog.profile_for(entry)
        if profile:
            text_label(left,profile.get("name","Mod local"),color=GOLD,size=17,strong=True,bg=PANEL).pack(anchor="w",pady=9)
            text_label(left,"Perfil vinculado ao arquivo selecionado. A ISO ativa no emulador não é verificada automaticamente.",
                       color=MUTED,size=10,bg=PANEL).pack(anchor="w",pady=(3,12))
        else:
            text_label(left,"Nenhum perfil ativo",color=MUTED,size=14,bg=PANEL).pack(anchor="w",pady=(15,12))
        self._action(left,"Ativar ou trocar mod",lambda:self.go("mods"),accent=GOLD).pack(anchor="w")
        right=Panel(panels);right.pack(side="left",fill="both",expand=True,padx=(7,0))
        text_label(right,"ANÁLISE AUTOMÁTICA",color=BLUE,size=13,strong=True,bg=PANEL).pack(anchor="w")
        for caption in ("01   Identificar ISO/BIN local","02   Ler estruturas conhecidas",
                        "03   Organizar categorias de cartas","04   Anexar efeitos com fonte identificada",
                        "05   Sinalizar dados que precisam de revisão"):
            text_label(right,caption,color=TEXT,size=11,bg=PANEL).pack(anchor="w",pady=8)
        self._action(right,"Analisar pasta salva",self.scan_folder).pack(anchor="w",pady=(10,0))

    def _table(self,parent,columns,specs,height=14):
        container=tk.Frame(parent,background=PANEL)
        container.pack(fill="both",expand=True,pady=5)
        tree=ttk.Treeview(container,columns=columns,show="headings",
                          height=height,style="DT.Treeview",selectmode="browse")
        for col,label,width in specs:
            tree.heading(col,text=label)
            tree.column(col,width=width,anchor="w")
        tree.pack(side="left",fill="both",expand=True)
        scroll=ttk.Scrollbar(container,orient="vertical",command=tree.yview)
        scroll.pack(side="right",fill="y")
        tree.configure(yscrollcommand=scroll.set)
        return tree

    def _page_mods(self,page):
        root=tk.Frame(page,background=BACKGROUND)
        root.pack(fill="both",expand=True,padx=20,pady=19)
        self._label(root,"Biblioteca de Mods",
                    "Importe uma ISO/BIN ou analise uma pasta. O processamento usa o cache quando possível.")
        toolbar=Panel(root);toolbar.pack(fill="x",pady=(0,13))
        self._action(toolbar,"Importar ISO/BIN",self.choose_file,accent=GOLD).pack(side="left",padx=(0,9))
        self._action(toolbar,"Escanear pasta",self.choose_folder).pack(side="left",padx=(0,9))
        self._action(toolbar,"Reanalisar pasta",self.scan_folder).pack(side="left")
        self._action(toolbar,"Ativar perfil",self.activate_selected,accent=GREEN).pack(side="right")
        box=Panel(root)
        box.pack(fill="both",expand=True)
        text_label(box,"PERFIS ENCONTRADOS",color=BLUE,size=13,strong=True,bg=PANEL).pack(anchor="w")
        self.mod_tree=self._table(box,("name","status","cards","effects","fusions"),
             (("name","Arquivo / mod",250),("status","Validação",165),
              ("cards","Cartas",70),("effects","Efeitos com fonte",120),
              ("fusions","Fusões revisadas",135)))
        self.mod_tree.bind("<<TreeviewSelect>>",self._on_select_mod)
        self.mod_info=text_label(box,"Selecione um mod para revisar a procedência dos dados.",
                                 color=MUTED,size=10,bg=PANEL)
        self.mod_info.pack(anchor="w",pady=(7,2))
        self._refresh_mods()

    def _refresh_mods(self):
        if not hasattr(self,"mod_tree") or not self.mod_tree.winfo_exists():return
        self.mod_tree.delete(*self.mod_tree.get_children())
        for entry in self.catalog.list():
            summary=profile_summary(entry,self.catalog.profile_for(entry))
            sha=entry["sha256"]
            self.mod_tree.insert("","end",iid=sha,
                values=(entry.get("file_name",""),
                        entry.get("level","desconhecido"),
                        summary["cards_total"],summary["effect_count"],
                        summary["fusion_count"]))
        if self.selected_sha and self.mod_tree.exists(self.selected_sha):
            self.mod_tree.selection_set(self.selected_sha)
            self._on_select_mod()

    def _on_select_mod(self,_event=None):
        chosen=self.mod_tree.selection() if hasattr(self,"mod_tree") else ()
        if not chosen:return
        self.selected_sha=chosen[0]
        entry,profile=self._profile()
        if not entry or not profile:return
        summary=profile_summary(entry,profile)
        counts=summary["categories"]
        parts=[f"{k}: {v}" for k,v in counts.items() if v]
        text=(f"SHA: {entry['sha256'][:16]}…  •  "
              f"Categorias: {', '.join(parts) or 'não identificadas'}  •  "
              f"Efeitos: {summary['effect_source']}  •  "
              f"{'REVISÃO NECESSÁRIA' if summary['requires_review'] else 'PERFIL CONHECIDO'}")
        self.mod_info.configure(text=text)

    def _page_cartas(self,page):
        root=tk.Frame(page,background=BACKGROUND)
        root.pack(fill="both",expand=True,padx=20,pady=19)
        self._label(root,"Biblioteca de Cartas",
                    "Monstros, Mágicas, Rituais, Armadilhas e Equipamentos. Efeitos apenas quando houver fonte.")
        entry,profile=self._profile()
        cards=profile.get("cards",[]) if profile and profile.get("supported_features",{}).get("cards") else []
        self.visible_cards=list(cards)
        toolbar=Panel(root);toolbar.pack(fill="x",pady=(0,12))
        self.card_query_var=tk.StringVar()
        self.card_category_var=tk.StringVar(value="Todas")
        text_label(toolbar,"Buscar",color=TEXT,bg=PANEL).pack(side="left",padx=(0,7))
        ttk.Entry(toolbar,textvariable=self.card_query_var,style="DT.TEntry",width=33).pack(
            side="left",padx=(0,12))
        ttk.Combobox(toolbar,textvariable=self.card_category_var,state="readonly",
                     values=("Todas",)+CARD_CATEGORIES,width=18,
                     style="DT.TCombobox").pack(side="left")
        self.card_query_var.trace_add("write",lambda *_:self._refresh_cards())
        self.card_category_var.trace_add("write",lambda *_:self._refresh_cards())
        self.card_counter=text_label(toolbar,"",color=GOLD,size=10,bg=PANEL)
        self.card_counter.pack(side="right")
        sections=tk.Frame(root,background=BACKGROUND)
        sections.pack(fill="both",expand=True)
        main=Panel(sections);main.pack(side="left",fill="both",expand=True,padx=(0,8))
        self.card_tree=self._table(main,("id","name","category","type","atk","def"),
             (("id","ID",55),("name","Nome",225),("category","Categoria",130),
              ("type","Tipo",135),("atk","ATK",70),("def","DEF",70)),height=16)
        self.card_tree.bind("<<TreeviewSelect>>",self._on_select_card)
        detail=Panel(sections,width=300);detail.pack(side="left",fill="y",padx=(8,0))
        detail.pack_propagate(False)
        text_label(detail,"DETALHES DA CARTA",color=BLUE,size=12,strong=True,bg=PANEL).pack(anchor="w")
        self.card_title=text_label(detail,"Selecione uma carta",color=GOLD,size=12,strong=True,bg=PANEL)
        self.card_title.pack(anchor="w",pady=(15,10))
        self.card_details=text_label(detail,"",color=MUTED,size=10,bg=PANEL)
        self.card_details.pack(anchor="w",pady=(0,12))
        text_label(detail,"EFEITO",color=BLUE,strong=True,bg=PANEL).pack(anchor="w")
        self.effect_box=tk.Text(detail,height=10,width=33,wrap="word",background=PANEL_ALT,
                                foreground=TEXT,relief="flat",font=("Segoe UI",10),
                                padx=10,pady=10)
        self.effect_box.pack(fill="x",pady=7)
        self.effect_box.configure(state="disabled")
        self._refresh_cards()

    def _refresh_cards(self):
        if not hasattr(self,"card_tree") or not self.card_tree.winfo_exists():return
        self.card_tree.delete(*self.card_tree.get_children())
        query=self.card_query_var.get().casefold().strip()
        category=self.card_category_var.get()
        displayed=[x for x in self.visible_cards
                   if (category=="Todas" or x.get("category")==category)
                   and (not query or query in str(x.get("name","")).casefold()
                        or query in str(x.get("id",""))
                        or query in str(x.get("effect_text") or "").casefold())]
        for item in displayed:
            self.card_tree.insert("","end",iid=str(item["id"]),
                values=(item["id"],item.get("name",""),item.get("category","Não identificado"),
                        item.get("type_label",""),item.get("atk",""),item.get("def","")))
        self.card_counter.configure(text=f"{len(displayed)} / {len(self.visible_cards)} cartas")

    def _on_select_card(self,_evt=None):
        ids=self.card_tree.selection()
        if not ids:return
        card=next((x for x in self.visible_cards if str(x.get("id"))==ids[0]),None)
        if not card:return
        self.card_title.configure(text=f"#{card['id']}  {card.get('name','')}")
        self.card_details.configure(text=(
            f"Categoria: {card.get('category','Não identificado')}\n"
            f"Tipo: {card.get('type_label','')}\n"
            f"ATK: {card.get('atk','—')}    DEF: {card.get('def','—')}\n"
            f"Origem: {card.get('category_source','desconhecida')}"))
        effect=card.get("effect_text") or "Nenhum efeito foi identificado com fonte rastreável neste mod."
        origin=card.get("effect_source") or "Fonte: não disponível."
        self.effect_box.configure(state="normal")
        self.effect_box.delete("1.0","end")
        self.effect_box.insert("1.0",effect+"\n\n"+origin)
        self.effect_box.configure(state="disabled")
