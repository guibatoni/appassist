"""DUELTRACE Desktop — novo launcher Windows com navegação animada.

Os números vêm exclusivamente de perfis do ModCatalog; textos de efeitos
sem origem ficam indisponíveis. A janela antiga continua acessível para
ferramentas avançadas. A análise é local e roda fora da thread da interface.
"""
from __future__ import annotations

import os
import queue
import threading
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from auto_mods import ModCatalog, atomic_json, load_json
from card_catalog import CARD_CATEGORIES
from mod_autopilot import ModAutopilot, profile_summary, discover_images
from dueltrace_intelligence import MultiModIntelligence
from ia_local import DEFAULT_MODEL
from integracao_overlay import overlay_snapshot
from dueltrace_brand import apply_window_icon
from dueltrace_visuals import HeroArt, QuickTile, CardArt, CategoryMeters, NAV_SYMBOLS
from dueltrace_theme import (
    BACKGROUND,SIDEBAR,PANEL,PANEL_ALT,BORDER,BLUE,GOLD,GREEN,RED,TEXT,MUTED,
    Panel,NeonButton,setup_theme,text_label,card_stat,
)

PAGES=(
    ("Início","inicio"),("Biblioteca de Mods","mods"),
    ("Biblioteca de Cartas","cartas"),("Fusões","fusoes"),
    ("Overlay","overlay"),("Diagnóstico","diagnostico"),
    ("Configurações","configuracoes"),
)


USER_PAGES=tuple(p for p in PAGES if p[1] in ("inicio","mods","cartas","fusoes"))


class DueltraceDesktop(tk.Tk):
    def __init__(self, *, catalog=None, developer=False):
        super().__init__()
        self.title("DUELTRACE — MultiMod Companion · Alpha 0.6.0")
        self.geometry("1360x780")
        self.minsize(1100,690)
        self.configure(background=BACKGROUND)
        try:apply_window_icon(self)
        except tk.TclError:pass
        setup_theme(self)
        self.catalog=catalog or ModCatalog()
        self.developer=bool(developer)
        self.pages=PAGES if self.developer else USER_PAGES
        self.autopilot=ModAutopilot(self.catalog)
        self.intelligence=MultiModIntelligence(self.catalog)
        self.settings_path=self.catalog.home/"dueltrace_desktop_settings.json"
        settings=load_json(self.settings_path,{})
        older=load_json(self.catalog.home/"biblioteca_settings.json",{})
        self.folder=tk.StringVar(value=settings.get("folder") or older.get("folder",""))
        self.auto_start=tk.BooleanVar(value=settings.get("auto_scan_on_start",True))
        self.ai_enabled=tk.BooleanVar(value=settings.get("ollama_auto",True))
        self.art_enabled=tk.BooleanVar(value=settings.get("extract_local_art",True))
        self.ai_model=tk.StringVar(value=settings.get("ollama_model",DEFAULT_MODEL))
        self.intelligence_note=tk.StringVar(value="Análise de evidências disponível · Ollama opcional")
        self.last_intelligence={}
        self.status=tk.StringVar(value="Pronto — selecione uma ISO/BIN ou uma pasta de mods.")
        self.selected_sha=None
        self.inbox=queue.Queue()
        self.busy=False
        self.active_page=None
        self.page_frame=None
        self._buttons={}
        self._legacy_window=None
        self._legacy_process=None
        self._build_shell()
        self.go("inicio")
        self.after(140,self._poll_events)
        if self.auto_start.get() and self.folder.get() and Path(self.folder.get()).is_dir():
            self.after(650,self.scan_folder)
        for index,(_,key) in enumerate(self.pages,1):
            self.bind_all(f"<Control-Key-{index}>",lambda _e,k=key:self.go(k))
        self.protocol("WM_DELETE_WINDOW",self._close)

    def _build_shell(self):
        top=tk.Frame(self,background=SIDEBAR,height=85,
                     highlightbackground=GOLD,highlightthickness=1)
        top.pack(fill="x",side="top")
        top.pack_propagate(False)
        logo=tk.Frame(top,background=SIDEBAR)
        logo.pack(side="left",padx=26,pady=11)
        text_label(logo,"▽  D U E L T R A C E",color=BLUE,size=22,
                   strong=True,bg=SIDEBAR).pack(anchor="w")
        text_label(logo,"MULTIMOD COMPANION  /  WINDOWS",color=GOLD,size=9,
                   strong=True,bg=SIDEBAR).pack(anchor="w")
        statusbox=tk.Frame(top,background=PANEL_ALT,highlightbackground=BORDER,
                           highlightthickness=1,padx=15,pady=9)
        statusbox.pack(side="right",padx=24,pady=16)
        self.header_status=text_label(statusbox,"●  Pronto para analisar",
                                      color=GREEN,size=10,strong=True,bg=PANEL_ALT)
        self.header_status.pack(anchor="center")
        body=tk.Frame(self,background=BACKGROUND)
        body.pack(fill="both",expand=True)
        sidebar=tk.Frame(body,background=SIDEBAR,width=220,
                         highlightbackground=BORDER,highlightthickness=1)
        sidebar.pack(side="left",fill="y")
        sidebar.pack_propagate(False)
        text_label(sidebar,"EXPLORAR",color=GOLD,size=10,strong=True,
                   bg=SIDEBAR).pack(anchor="w",padx=18,pady=(27,14))
        for name,key in self.pages:
            symbol=NAV_SYMBOLS.get(key,"◇")
            button=NeonButton(sidebar,f"{symbol}  {name}",
                              lambda p=key:self.go(p),width=194,height=47)
            button.pack(pady=5,padx=12)
            self._buttons[key]=button
        tk.Frame(sidebar,background=SIDEBAR).pack(fill="both",expand=True)
        art=HeroArt(sidebar,width=190,height=115)
        art.pack(padx=14,pady=(0,8))
        text_label(sidebar,"✧  Conteúdo do mod processado localmente",
                   color=MUTED,size=8,bg=SIDEBAR).pack(padx=12,pady=(0,16))
        self.stage=tk.Frame(body,background=BACKGROUND)
        self.stage.pack(side="left",fill="both",expand=True)
        footer=tk.Frame(self,background=SIDEBAR,height=34,
                        highlightbackground=BORDER,highlightthickness=1)
        footer.pack(side="bottom",fill="x")
        tk.Label(footer,textvariable=self.status,background=SIDEBAR,
                 foreground=MUTED,anchor="w",font=("Segoe UI",9)).pack(
                     fill="x",padx=20,pady=7)

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
        body.pack(fill="both",expand=True,padx=18,pady=15)
        hero=Panel(body)
        hero.pack(fill="x",pady=(0,11))
        hero_art=HeroArt(hero,width=365,height=173)
        hero_art.pack(side="right",padx=(7,2))
        copy=tk.Frame(hero,background=PANEL)
        copy.pack(side="left",fill="both",expand=True)
        text_label(copy,"A NOVA EXPERIÊNCIA DUELTRACE",color=BLUE,
                   size=10,strong=True,bg=PANEL).pack(anchor="w")
        text_label(copy,"Cada carta. Cada fusão. Cada jogada.",
                   color=GOLD,size=18,strong=True,bg=PANEL).pack(anchor="w",pady=(12,7))
        text_label(copy,"Escolha seu mod e deixe o scanner identificar as estruturas "
                        "que consegue validar. Nenhum efeito ou resultado é inventado.",
                   color=TEXT,size=10,bg=PANEL).pack(anchor="w",pady=(0,13))
        actions=tk.Frame(copy,background=PANEL)
        actions.pack(anchor="w")
        self._action(actions,"Selecionar ISO / BIN",self.choose_file,
                     accent=GOLD,width=190).pack(side="left",padx=(0,10))
        self._action(actions,"Analisar pasta",self.choose_folder,
                     width=155).pack(side="left")
        tiles=tk.Frame(body,background=BACKGROUND)
        tiles.pack(fill="x",pady=(0,12))
        shortcuts=(
            ("Biblioteca de Mods","Detectar e validar","⬡","mods"),
            ("Biblioteca de Cartas","Buscar e filtrar","▣","cartas"),
            ("Fusões","Receitas revisadas","◎","fusoes"),
            ("Overlay","Perfil de duelo","▤","overlay"),
            ("Diagnóstico","Ferramentas RAM","▥","diagnostico"),
            ("Configurações","Preferências locais","⚙","configuracoes"),
        )
        for caption,subtitle,symbol,key in shortcuts:
            if key not in {x[1] for x in self.pages}:
                continue
            item=QuickTile(tiles,caption,subtitle,symbol,
                           lambda k=key:self.go(k),width=192 if not self.developer else 140,height=106,
                           accent=GOLD if key=="fusoes" else BLUE)
            item.pack(side="left",fill="x",expand=True,padx=3)
        lower=tk.Frame(body,background=BACKGROUND)
        lower.pack(fill="both",expand=True)
        left=Panel(lower)
        left.pack(side="left",fill="both",expand=True,padx=(0,6))
        right=Panel(lower)
        right.pack(side="left",fill="both",expand=True,padx=(6,0))
        active=self.catalog.current()
        entries=self.catalog.list()
        profile=None
        if active:
            match=next((x for x in entries if x.get("sha256")==active.get("sha256")),None)
            if match:profile=self.catalog.profile_for(match)
        text_label(left,"⬡   MOD ATIVO",color=BLUE,size=13,strong=True,
                   bg=PANEL).pack(anchor="w")
        if profile:
            text_label(left,str(profile.get("name") or "Mod local"),
                       color=GOLD,size=18,strong=True,bg=PANEL).pack(
                           anchor="w",pady=(12,9))
            text_label(left,"Perfil ativo no DUELTRACE. Ainda não há confirmação "
                            "da ISO executada pelo emulador.",
                       color=MUTED,size=10,bg=PANEL).pack(anchor="w",pady=(0,10))
        else:
            text_label(left,"Nenhum perfil ativo",color=GOLD,size=17,
                       strong=True,bg=PANEL).pack(anchor="w",pady=(12,10))
            text_label(left,"Importe uma ISO/BIN para iniciar. Mods desconhecidos "
                            "exigem investigação antes da ativação.",
                       color=MUTED,size=10,bg=PANEL).pack(anchor="w",pady=(0,10))
        self._action(left,"Ativar ou trocar mod",lambda:self.go("mods"),
                     accent=GOLD,width=198).pack(anchor="w",pady=(2,8))
        if self.developer:
            self._action(left,"Abrir Assistente Clássico",self.open_legacy,
                         width=215).pack(anchor="w",pady=(0,10))
        text_label(left,f"MODS CADASTRADOS  {len(entries)}",color=MUTED,
                   size=10,bg=PANEL).pack(anchor="w",pady=3)
        text_label(left,f"PERFIS VALIDADOS  {sum(e.get('level')=='conhecido_validado' for e in entries)}",
                   color=MUTED,size=10,bg=PANEL).pack(anchor="w",pady=3)
        text_label(right,"▣   BIBLIOTECA INTELIGENTE",color=BLUE,size=13,
                   strong=True,bg=PANEL).pack(anchor="w",pady=(0,10))
        if profile and profile.get("supported_features",{}).get("cards"):
            from card_catalog import category_summary
            counts=category_summary(profile.get("cards",[]))
        else:
            counts={}
        CategoryMeters(right,counts).pack(fill="x",expand=True)
        text_label(right,"Valores extraídos do perfil local; categorias não "
                         "confirmadas não são estimadas.",color=MUTED,
                   size=9,bg=PANEL).pack(anchor="w",pady=(8,0))

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
        automation=Panel(root)
        automation.pack(fill="x",pady=(0,12))
        left=tk.Frame(automation,background=PANEL)
        left.pack(side="left",fill="x",expand=True)
        tk.Checkbutton(left,text="Investigar com Ollama local (quando disponível)",
                       variable=self.ai_enabled,command=self._save_settings,
                       bg=PANEL,fg=TEXT,activebackground=PANEL,
                       activeforeground=TEXT,selectcolor=PANEL_ALT,
                       font=("Segoe UI",10)).pack(anchor="w")
        tk.Checkbutton(left,text="Extrair artes locais dos formatos reconhecidos",
                       variable=self.art_enabled,command=self._save_settings,
                       bg=PANEL,fg=TEXT,activebackground=PANEL,
                       activeforeground=TEXT,selectcolor=PANEL_ALT,
                       font=("Segoe UI",10)).pack(anchor="w")
        tk.Label(automation,textvariable=self.intelligence_note,background=PANEL,
                 foreground=MUTED,wraplength=420,justify="left",
                 font=("Segoe UI",9)).pack(side="right",padx=7)
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
        self.art_root=profile.get("art_root") if profile and profile.get("supported_features",{}).get("art") else None
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
        self.card_sort_var=tk.StringVar(value="ID")
        ttk.Combobox(toolbar,textvariable=self.card_sort_var,state="readonly",
                     values=("ID","ATK ↓","DEF ↓","Nome"),width=11,
                     style="DT.TCombobox").pack(side="right",padx=12)
        self.card_sort_var.trace_add("write",lambda *_:self._refresh_cards())
        sections=tk.Frame(root,background=BACKGROUND)
        sections.pack(fill="both",expand=True)
        main=Panel(sections);main.pack(side="left",fill="both",expand=True,padx=(0,8))
        self.card_tree=self._table(main,("id","name","category","type","atk","def"),
             (("id","ID",55),("name","Nome",225),("category","Categoria",130),
              ("type","Tipo",135),("atk","ATK",70),("def","DEF",70)),height=16)
        self.card_tree.bind("<<TreeviewSelect>>",self._on_select_card)
        detail=Panel(sections,width=300);detail.pack(side="left",fill="y",padx=(8,0))
        detail.pack_propagate(False)
        text_label(detail,"CARTA SELECIONADA",color=BLUE,size=12,strong=True,bg=PANEL).pack(anchor="w")
        self.card_art=CardArt(detail,width=265,height=230)
        self.card_art.pack(fill="x",pady=(8,6))
        text_label(detail,"Arte local quando extraída; prévia simbólica nos demais casos",
                   color=MUTED,size=8,bg=PANEL).pack(anchor="w",pady=(0,7))
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
        order=self.card_sort_var.get() if hasattr(self,"card_sort_var") else "ID"
        if order=="ATK ↓":
            displayed.sort(key=lambda c:(-(int(c.get("atk") or 0)),int(c.get("id") or 0)))
        elif order=="DEF ↓":
            displayed.sort(key=lambda c:(-(int(c.get("def") or 0)),int(c.get("id") or 0)))
        elif order=="Nome":
            displayed.sort(key=lambda c:(str(c.get("name") or "").casefold(),int(c.get("id") or 0)))
        else:
            displayed.sort(key=lambda c:int(c.get("id") or 0))
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
        self.card_art.set_card(card,self.art_root)
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

    def _page_fusoes(self,page):
        root=tk.Frame(page,background=BACKGROUND)
        root.pack(fill="both",expand=True,padx=20,pady=19)
        self._label(root,"Fusões",
                    "Receitas ligadas ao mod selecionado, sem probabilidades inventadas.")
        _,profile=self._profile()
        valid=bool(profile and profile.get("supported_features",{}).get("fusions"))
        recipes=profile.get("fusion_recipes",[]) if valid else []
        panel=Panel(root);panel.pack(fill="both",expand=True)
        text_label(panel,"◎   BANCO DE FUSÕES DO PERFIL",color=BLUE,size=13,strong=True,bg=PANEL).pack(anchor="w")
        text_label(panel,"Somente receitas obtidas e autorizadas pelo mod ativo. Rotas não validadas continuam indisponíveis.",
                   color=MUTED,size=10,bg=PANEL).pack(anchor="w",pady=(7,9))
        tree=self._table(panel,("a","b","result","origin"),
                         (("a","Material A",120),("b","Material B",120),
                          ("result","Resultado",120),("origin","Procedência",300)))
        cards={c["id"]:c.get("name",str(c["id"])) for c in (profile or {}).get("cards",[])}
        for row in recipes:
            try:
                a,b,result=(int(row[k]) for k in ("a","b","result"))
            except (KeyError,TypeError,ValueError):
                continue
            tree.insert("","end",values=(f"#{a} {cards.get(a,'')}",
                                                 f"#{b} {cards.get(b,'')}",
                                                 f"#{result} {cards.get(result,'')}",
                                                 row.get("validation","origem não informada")))
        text_label(panel,f"{len(recipes)} receitas disponíveis no perfil. "
                         "As hipóteses ainda não revisadas não aparecem como válidas.",
                   color=MUTED,size=10,bg=PANEL).pack(anchor="w",pady=(9,7))
        self._action(panel,"Abrir ferramentas avançadas",self.open_advanced,
                     accent=GOLD,width=242).pack(anchor="w")

    def _page_overlay(self,page):
        root=tk.Frame(page,background=BACKGROUND)
        root.pack(fill="both",expand=True,padx=20,pady=19)
        self._label(root,"Overlay de Duelo",
                    "Prévia do perfil ligado ao overlay. A ROM ativa no emulador não é verificada aqui.")
        report=overlay_snapshot(self.catalog)
        left=Panel(root);left.pack(fill="x",pady=9)
        if report.get("ready"):
            text_label(left,"● PERFIL ATIVO",color=GREEN,size=14,strong=True,bg=PANEL).pack(anchor="w")
            text_label(left,report.get("profile_name","Mod"),
                       color=GOLD,size=17,strong=True,bg=PANEL).pack(anchor="w",pady=12)
            flags=report.get("features",{})
            for name,field in (("Cartas e nomes","nomes_cartas"),
                               ("Categorias","categorias"),
                               ("Efeitos com origem","efeitos"),
                               ("Fusões revisadas","fusoes")):
                status="Disponível" if flags.get(field) else "Não validado ou indisponível"
                text_label(left,f"{name}: {status}",color=TEXT,size=11,bg=PANEL).pack(anchor="w",pady=4)
        else:
            text_label(left,"Nenhum perfil pronto para overlay",
                       color=GOLD,size=16,strong=True,bg=PANEL).pack(anchor="w",pady=9)
            text_label(left,"Escolha e ative um perfil na Biblioteca de Mods.",
                       color=MUTED,size=10,bg=PANEL).pack(anchor="w",pady=(0,11))
        self._action(left,"Selecionar perfil",lambda:self.go("mods")).pack(anchor="w",pady=6)
        info=Panel(root);info.pack(fill="x",pady=8)
        text_label(info,"▤  Estado de integração",color=BLUE,size=12,strong=True,
                   bg=PANEL).pack(anchor="w",pady=(0,8))
        text_label(info,"LP e estatísticas só aparecerão quando houver telemetria real e validada.",
                   color=TEXT,size=10,bg=PANEL).pack(anchor="w",pady=(0,10))
        text_label(info,"Leitura de cartas no campo: não validada. "
                        "Fusões envolvendo a mesa continuam desativadas.",
                   color=MUTED,size=11,bg=PANEL).pack(anchor="w")

    def _page_diagnostico(self,page):
        root=tk.Frame(page,background=BACKGROUND)
        root.pack(fill="both",expand=True,padx=20,pady=19)
        self._label(root,"Diagnóstico",
                    "Ferramentas técnicas de investigação, somente leitura e sem acesso presumido ao campo.")
        panel=Panel(root);panel.pack(fill="x",pady=8)
        text_label(panel,"▥   FERRAMENTAS DE DIAGNÓSTICO",color=BLUE,size=14,strong=True,bg=PANEL).pack(anchor="w")
        text_label(panel,"Investigação local  •  somente leitura",color=GOLD,size=10,
                   bg=PANEL).pack(anchor="w",pady=(8,0))
        text_label(panel,"RAM experimental, leitor temporal e revisão de fusões "
                         "permanecem disponíveis na Biblioteca técnica. "
                         "O reconhecimento de cartas no campo não foi validado.",
                   color=TEXT,size=11,bg=PANEL).pack(anchor="w",pady=(10,15))
        self._action(panel,"Abrir diagnóstico avançado",self.open_advanced,
                     accent=GOLD,width=247).pack(anchor="w",pady=(0,8))
        self._action(panel,"Abrir Assistente Clássico",self.open_legacy,
                     width=247).pack(anchor="w")
        text_label(root,"Nenhuma barra de utilização ou porcentagem de confiança "
                        "é exibida sem medição real.",color=MUTED,size=10).pack(anchor="w",pady=18)

    def _page_configuracoes(self,page):
        root=tk.Frame(page,background=BACKGROUND)
        root.pack(fill="both",expand=True,padx=20,pady=19)
        self._label(root,"Configurações",
                    "Preferências locais. Nenhum arquivo de jogo será modificado.")
        panel=Panel(root);panel.pack(fill="x",pady=8)
        text_label(panel,"⚙   PASTA DE MODS",color=BLUE,size=13,strong=True,bg=PANEL).pack(anchor="w")
        ttk.Entry(panel,textvariable=self.folder,width=80,
                  style="DT.TEntry").pack(fill="x",pady=(12,10))
        self._action(panel,"Escolher pasta",self.choose_folder).pack(anchor="w")
        option=Panel(root);option.pack(fill="x",pady=8)
        tk.Checkbutton(option,text="Ao iniciar, analisar automaticamente a pasta salva",
                       variable=self.auto_start,command=self._save_settings,
                       bg=PANEL,fg=TEXT,activebackground=PANEL,
                       activeforeground=TEXT,selectcolor=PANEL_ALT,
                       font=("Segoe UI",11)).pack(anchor="w",pady=5)
        text_label(option,"Análise automática usa parsers locais e cache; "
                          "um modelo Ollama é opcional e não valida dados desconhecidos.",
                   color=MUTED,size=10,bg=PANEL).pack(anchor="w",pady=(2,8))
        self._action(option,"Abrir ajustes avançados",self.open_advanced,
                     width=245).pack(anchor="w")
        text_label(option,"Modelo Ollama local (não envia a ISO):",color=BLUE,
                   bg=PANEL).pack(anchor="w",pady=(12,3))
        ttk.Entry(option,textvariable=self.ai_model,width=40,
                  style="DT.TEntry").pack(anchor="w")
        self.ai_model.trace_add("write",lambda *_:self._save_settings())

    def _save_settings(self):
        atomic_json(self.settings_path,{
            "schema":1,"folder":self.folder.get(),
            "auto_scan_on_start":bool(self.auto_start.get()),
            "ollama_auto":bool(self.ai_enabled.get()),
            "extract_local_art":bool(self.art_enabled.get()),
            "ollama_model":self.ai_model.get().strip() or DEFAULT_MODEL
        })

    def choose_folder(self):
        folder=filedialog.askdirectory(parent=self,title="Selecione a pasta de mods",
                                       initialdir=self.folder.get() or str(Path.home()))
        if not folder:return
        self.folder.set(folder)
        self._save_settings()
        self.go("mods")
        self.scan_folder()

    def choose_file(self):
        filename=filedialog.askopenfilename(
            parent=self,title="Escolha a ISO/BIN do seu mod",
            filetypes=(("Imagens de PS1","*.iso *.bin"),("ISO","*.iso"),
                       ("BIN","*.bin")))
        if not filename:return
        self.go("mods")
        self._start_worker(Path(filename))

    def scan_folder(self):
        if self.busy:return
        folder=Path(self.folder.get())
        if not folder.is_dir():
            self.status.set("Selecione uma pasta de mods nas Configurações.")
            return
        self._save_settings()
        self._start_worker(folder,all_images=True)

    def _start_worker(self,path,*,all_images=False):
        if self.busy:return
        self.busy=True
        use_ollama=bool(self.ai_enabled.get())
        with_art=bool(self.art_enabled.get())
        model=self.ai_model.get().strip() or DEFAULT_MODEL
        self.header_status.configure(text="●  Analisando…",fg=GOLD)
        self.status.set(f"Analisando {path.name} (somente leitura)…")
        def emit(e):self.inbox.put(e)
        def worker():
            try:
                art_available=with_art
                if with_art:
                    try:
                        import PIL  # noqa: F401 — dependência opcional
                    except ImportError:
                        art_available=False
                        emit({"event":"intelligence",
                              "message":"Pillow não instalada; artes não extraídas. Catálogo continua."})
                paths=discover_images(path) if all_images else [Path(path)]
                if not paths:
                    emit({"event":"intelligence","message":"Nenhuma ISO/BIN na pasta selecionada."})
                for index,image in enumerate(paths,1):
                    emit({"event":"found","file":image.name,"index":index,"total":len(paths)})
                    try:
                        result=self.autopilot.analyze_file(
                            image, with_art=art_available,
                            progress=lambda stage,done,total:
                            emit({"event":"progress","stage":stage,"done":done,"total":total}))
                        emit({"event":"done","result":result})
                        try:
                            info=self.intelligence.inspect(
                                image,model=model,use_ollama=use_ollama,emit=emit)
                            emit({"event":"intelligence_done","result":info,
                                  "file":image.name})
                        except (OSError,RuntimeError,ValueError) as exc:
                            emit({"event":"intelligence","message":
                                  "Investigação adicional não concluída: "+str(exc)[:150]})
                    except (OSError,RuntimeError,ValueError) as exc:
                        emit({"event":"error","message":image.name+": "+str(exc)[:220]})
            except (OSError,RuntimeError,ValueError) as exc:
                emit({"event":"error","message":str(exc)[:250]})
            finally:
                emit({"event":"finished"})
        threading.Thread(target=worker,daemon=True,name="dueltrace-autopilot").start()

    def _poll_events(self):
        try:
            while True:
                event=self.inbox.get_nowait()
                kind=event.get("event")
                if kind=="found":
                    self.status.set("Detectado: "+event.get("file",""))
                elif kind=="progress":
                    stage=event.get("stage","Analisando")
                    total=event.get("total") or 0
                    done=event.get("done") or 0
                    percent=f" — {round(done*100/total)}%" if total else ""
                    self.status.set(stage+percent)
                elif kind=="done":
                    summary=event.get("result",{})
                    if summary.get("sha256") and not self.selected_sha:
                        self.selected_sha=summary["sha256"]
                    self.status.set("Perfil analisado: "+summary.get("name","Mod"))
                    self._refresh_mods()
                elif kind=="intelligence":
                    self.intelligence_note.set(event.get("message","Analisando evidências…"))
                    self.status.set(event.get("message","Analisando evidências…"))
                elif kind=="intelligence_done":
                    info=event.get("result",{})
                    self.last_intelligence[event.get("file","")]=info
                    ai=info.get("ai","não_iniciada")
                    overview=info.get("inventory",{})
                    self.intelligence_note.set(
                        f"ISO: {overview.get('iso_files_indexed',0)} arquivos · "
                        f"Artes: {'extraídas' if overview.get('art_extracted') else 'indisponíveis'} · "
                        f"Ollama: {ai}")
                    self.status.set("Investigação local concluída: "+
                                    event.get("file",""))
                elif kind=="error":
                    self.status.set("Análise incompleta: "+event.get("message","Erro"))
                elif kind=="finished":
                    self.busy=False
                    self.header_status.configure(text="●  Sistema local",fg=GREEN)
                    self._refresh_mods()
        except queue.Empty:
            pass
        if self.winfo_exists():self.after(160,self._poll_events)

    def activate_selected(self):
        entry=self._selected_entry()
        if not entry:
            messagebox.showinfo("Ativar perfil",
                "Selecione um mod cadastrado na lista.",parent=self)
            return
        review=entry.get("level")!="conhecido_validado"
        if review:
            if entry.get("level")=="desconhecido":
                messagebox.showwarning("Estrutura não reconhecida",
                    "Não é possível ativar automaticamente este mod. "
                    "Os dados da estrutura precisam ser investigados.",
                    parent=self)
                return
            if not messagebox.askyesno("Perfil parcialmente reconhecido",
                "Este mod possui dados parciais. Somente recursos identificados "
                "serão ativados; ranks, fusões e efeitos desconhecidos ficam "
                "indisponíveis. Deseja ativar este perfil mesmo assim?",
                parent=self):
                return
        try:
            self.catalog.activate(entry["sha256"],
                                  acknowledge_uncertainty=review)
        except (ValueError,PermissionError,OSError) as exc:
            messagebox.showerror("Falha ao ativar perfil",str(exc),parent=self)
            return
        self.status.set("Perfil ativo: "+entry.get("file_name",""))
        self.go("inicio")
        messagebox.showinfo("Perfil ativado",
            "O perfil foi enviado ao DUELTRACE. "
            "Isso não inicia o ePSXe nem confirma qual ISO ele está executando.",
            parent=self)

    def open_legacy(self):
        """Executa o assistente antigo em outro processo, sem alterar seus dados."""
        script=Path(__file__).resolve().parent.parent / "assistente_x15.py"
        if not script.is_file():
            messagebox.showwarning(
                "Assistente clássico indisponível",
                "Não foi possível localizar assistente_x15.py na pasta app.",
                parent=self)
            return
        if self._legacy_process is not None and self._legacy_process.poll() is None:
            self.status.set("O Assistente Clássico já está em execução.")
            return
        try:
            self._legacy_process=subprocess.Popen(
                [sys.executable, str(script), "--legacy"],
                cwd=str(script.parent))
        except OSError as exc:
            messagebox.showerror("Falha ao abrir o Assistente Clássico",
                                 str(exc), parent=self)
            return
        self.status.set("Assistente Clássico iniciado em uma janela separada.")

    def open_advanced(self):
        if self._legacy_window and self._legacy_window.winfo_exists():
            self._legacy_window.lift()
            self._legacy_window.focus_set()
            return
        from biblioteca_mods import BibliotecaMods
        self._legacy_window=BibliotecaMods(self,catalog=self.catalog)
        self._legacy_window.lift()

    def _close(self):
        self._save_settings()
        self.destroy()


def main():
    DueltraceDesktop(developer="--developer" in sys.argv or os.environ.get("DUELTRACE_DEV_MODE")=="1").mainloop()


if __name__=="__main__":
    main()
