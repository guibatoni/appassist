"""Biblioteca de Mods integrada via janela Tkinter do próprio Assistente.

Abre como Toplevel da janela do overlay; não depende de serviço externo.
A análise ocorre em segundo plano. Dados incertos não são ativados.
"""
from __future__ import annotations

import csv
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
from fusion_ram_probe import FusionMemoryProbe
from ram_temporal import TemporalRamRecorder, MAX_SECONDS, ALLOWED_MARKERS
from field_ram_probe import FieldMemoryProbe

VERIFIED_LABELS = {
    "verificado": "✓ Confirmado",
    "verificado_x15": "✓ Confirmado somente X15",
    "extraídas": "✓ Extraído",
    "não_extraídas": "— Não extraído",
    "não_identificado": "? Significado desconhecido",
    "revisadas_usuario_lote": "✓ Revisadas pelo usuário (não testadas individualmente)",
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
    def __init__(self, parent, on_activate=None, catalog=None, ram_probe=None):
        super().__init__(parent)
        self.title("Biblioteca de Mods — Forbidden Memories MultiMod")
        self.geometry("1120x750")
        self.minsize(850, 580)
        self.catalog = catalog or ModCatalog()
        self.on_activate = on_activate
        self.ram_probe=ram_probe
        self.temporal=TemporalRamRecorder(ram_probe) if ram_probe is not None else None
        self.field_probe=(FieldMemoryProbe(ram_probe.reader_provider, self.catalog.home)
                          if ram_probe is not None else None)
        self.field_target_id=tk.StringVar(value="291")
        self.field_face=tk.StringVar(value="faceup")
        self.field_slot=tk.StringVar(value="1")
        self.field_expand=tk.BooleanVar(value=False)  # 1 MiB somente por escolha explícita
        self.field_focus=tk.BooleanVar(value=True)  # mais um bloco de 4 KiB se escopo de 96 KiB
        self.field_status=tk.StringVar(value="Campo ainda não mapeado. Inicie com carta na mão e ausente da mesa.")
        self._temporal_after_id=None
        self.temporal_interval=tk.StringVar(value="250")
        self.temporal_duration=tk.StringVar(value="45")
        self.temporal_status=tk.StringVar(value="Monitor inativo; cartas na mesa ainda não mapeadas.")
        self.ram_result_id=tk.StringVar(value="")
        self.ram_diag_status=tk.StringVar(value="Sem capturas. Selecione o perfil ativo no ePSXe.")
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
        ttk.Button(toolbar,text="Aprovar lote revisado",
                   command=self.approve_fusion_batch).pack(side="right",padx=3)
        ttk.Button(toolbar,text="Exportar lista completa CSV",
                   command=self.export_all_fusion_candidates).pack(side="right",padx=3)
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

        diag=ttk.Frame(self.tabs,padding=12)
        ttk.Label(diag,text="Diagnóstico RAM de fusões — SOMENTE LEITURA",
                  font=("Segoe UI",11,"bold")).pack(anchor="w",pady=5)
        ttk.Label(diag,text=(
            "Captura duas amostras curtas da memória do ePSXe. "
            "Não confirma fusões automaticamente; registra apenas diferenças "
            "para descobrir onde o jogo guarda materiais e resultado."
        ),wraplength=990,justify="left").pack(anchor="w",pady=(0,10))
        row=ttk.Frame(diag)
        row.pack(fill="x",pady=(0,10))
        ttk.Button(row,text="1. Capturar ANTES",command=self.capture_ram_before).pack(side="left",padx=4)
        ttk.Button(row,text="2. Capturar DEPOIS",command=self.capture_ram_after).pack(side="left",padx=4)
        ttk.Label(row,text="ID do resultado visto (opcional):").pack(side="left",padx=(20,4))
        ttk.Entry(row,textvariable=self.ram_result_id,width=7).pack(side="left")
        ttk.Label(diag,textvariable=self.ram_diag_status,wraplength=990,
                  justify="left").pack(fill="x",pady=8)
        ttk.Label(diag,text=(
            "Procedimento: durante o duelo, antes da fusão, clique Capturar ANTES; "
            "execute uma fusão real no jogo e, após ela, clique Capturar DEPOIS. "
            "O resultado salvo é experimental; nenhuma receita será aprovada."
        ),wraplength=990,justify="left").pack(anchor="w",pady=(0,8))
        self.tabs.add(diag,text="Diagnóstico RAM")

        temporal_page=ttk.Frame(self.tabs,padding=12)
        ttk.Label(temporal_page,text="Monitor temporal — RAM do ePSXe (somente leitura)",
                  font=("Segoe UI",11,"bold")).pack(anchor="w",pady=5)
        ttk.Label(temporal_page,
                  text="Grava até 90 segundos em 4 regiões pequenas. Marca ações apenas "
                       "por anotação manual; NÃO identifica fusões ou cartas da mesa automaticamente.",
                  wraplength=970,justify="left").pack(anchor="w",pady=(0,12))
        settings=ttk.Frame(temporal_page)
        settings.pack(fill="x",pady=6)
        ttk.Label(settings,text="Intervalo (ms):").pack(side="left")
        ttk.Combobox(settings,values=("200","250","500","1000"),
                     textvariable=self.temporal_interval,state="readonly",
                     width=7).pack(side="left",padx=(5,18))
        ttk.Label(settings,text="Duração máxima (s):").pack(side="left")
        ttk.Combobox(settings,values=("15","30","45","60","90"),
                     textvariable=self.temporal_duration,state="readonly",
                     width=7).pack(side="left",padx=5)
        controls=ttk.Frame(temporal_page)
        controls.pack(fill="x",pady=12)
        ttk.Button(controls,text="Iniciar gravação",command=self.start_temporal).pack(side="left",padx=4)
        ttk.Button(controls,text="Parar e exportar JSON/CSV",
                   command=self.stop_temporal).pack(side="left",padx=4)
        ttk.Label(temporal_page,text="Marque a ação após executá-la no jogo. "
                  "O horário do clique NÃO é o instante exato do evento.",
                  wraplength=970,justify="left").pack(anchor="w",pady=(3,8))
        marks=ttk.Frame(temporal_page)
        marks.pack(fill="x",pady=5)
        for marker,caption in (("fusao","Fusão"),("invocacao","Invocação"),
                               ("ataque","Ataque"),("cancelamento","Cancelamento"),
                               ("controle","Controle")):
            ttk.Button(marks,text="Marcar "+caption,
                       command=lambda m=marker:self.mark_temporal(m)
                       ).pack(side="left",padx=3)
        ttk.Label(temporal_page,textvariable=self.temporal_status,
                  wraplength=980,justify="left").pack(fill="x",pady=14)
        ttk.Label(temporal_page,text="Os arquivos são salvos em "
                  "%LOCALAPPDATA%\\ForbiddenMemoriesMultiMod\\diagnosticos_temporais\\<SHA>. "
                  "Use uma gravação por ação e envie o JSON para investigação.",
                  wraplength=980,justify="left").pack(anchor="w")
        self.tabs.add(temporal_page,text="Monitor temporal")

        field_page=ttk.Frame(self.tabs,padding=12)
        ttk.Label(field_page,text="Cartas no campo — investigação em preparação",
                  font=("Segoe UI",11,"bold")).pack(anchor="w",pady=5)
        ttk.Label(field_page,text=(
            "Hoje validamos apenas os cinco IDs da mão em 0xBFF484. "
            "Nenhum endereço de cartas no campo (monstros/magias, aliados/adversário) "
            "foi comprovado para esta ISO. A leitura do campo permanece DESATIVADA."
        ),wraplength=940,justify="left").pack(anchor="w",pady=(0,12))
        ttk.Label(field_page,text=(
            "Próximo procedimento: gravar uma sessão com o campo vazio, marcar "
            "uma invocação, gravar o mesmo monstro no campo e, depois, "
            "marcar sua remoção. Repetir com cartas diferentes e controles sem "
            "alteração. Procuraremos IDs, posições, lado do jogador e estabilidade "
            "dos endereços antes de sugerir fusões mão + campo."
        ),wraplength=940,justify="left").pack(anchor="w",pady=(0,12))
        ttk.Label(field_page,text=(
            "Critério futuro: identificar ID e posição de forma independente, "
            "conferir o perfil da ISO, usar somente receitas aprovadas e "
            "separar sugestões envolvendo cartas da mesa das combinações da mão. "
            "NENHUMA carta da mesa é inventada por heurística."
        ),wraplength=940,justify="left").pack(anchor="w")
        ttk.Separator(field_page,orient="horizontal").pack(fill="x",pady=12)
        ttk.Label(field_page,text="Diagnóstico por fases — preparação, mesa e atualização da mão",
                  font=("Segoe UI",10,"bold")).pack(anchor="w",pady=5)
        ttk.Label(field_page,text=(
            "v0.4.12: avaliação especial dos endereços C393FA e C39822, "
            "incluindo o controle SEM AÇÃO. São hipóteses, não slots identificados."
        ),wraplength=940,justify="left",foreground="#4A6785").pack(anchor="w",pady=(0,7))
        ttk.Label(field_page,text=(
            "Monitor de ocupação experimental: compara slot VAZIO → OCUPADO → REMOVIDO. "
            "Pode usar controles opcionais para excluir bytes voláteis. "
            "Nenhuma ocorrência valida automaticamente o campo ou libera fusões."
        ),wraplength=940,justify="left").pack(anchor="w",pady=(0,8))
        target_row=ttk.Frame(field_page)
        target_row.pack(fill="x",pady=(0,7))
        ttk.Label(target_row,text="ID da carta que será invocada:").pack(side="left")
        ttk.Entry(target_row,textvariable=self.field_target_id,width=8).pack(side="left",padx=8)
        ttk.Label(target_row,text="A carta precisa estar na mão na fase ANTES.").pack(side="left")
        options=ttk.Frame(field_page)
        options.pack(fill="x",pady=(0,8))
        ttk.Label(options,text="Face escolhida:").pack(side="left")
        ttk.Combobox(options,values=("faceup","facedown"),state="readonly",
                     textvariable=self.field_face,width=11).pack(side="left",padx=(5,16))
        ttk.Label(options,text="Slot observado (1 a 5):").pack(side="left")
        ttk.Combobox(options,values=("1","2","3","4","5"),state="readonly",
                     textvariable=self.field_slot,width=4).pack(side="left",padx=5)
        ttk.Checkbutton(options,text="Ampliar 96 KiB → 1 MiB (experimental)",
                        variable=self.field_expand).pack(side="left",padx=12)
        ttk.Checkbutton(field_page,text=(
            "Monitor direcionado: IDs de 28 B e candidatos C39000–C39A00 "
            "(+4 KiB se escolher 96 KiB)"),
            variable=self.field_focus).pack(anchor="w",pady=(0,7))
        controls=ttk.Frame(field_page)
        controls.pack(fill="x",pady=(0,6))
        ttk.Button(controls,text="1. ANTES (slot vazio)",
                   command=self.capture_field_before).pack(side="left",padx=(0,6))
        ttk.Button(controls,text="2. PREPARADA (opcional)",
                   command=self.capture_field_prepared).pack(side="left",padx=5)
        ttk.Button(controls,text="3. NA MESA",
                   command=self.capture_field_after).pack(side="left",padx=5)
        ttk.Button(controls,text="4. OCUPADA (controle)",
                   command=self.capture_field_occupied_control).pack(side="left",padx=5)
        controls2=ttk.Frame(field_page)
        controls2.pack(fill="x",pady=(0,9))
        ttk.Button(controls2,text="5. REMOVIDA (slot vazio)",
                   command=self.capture_field_removed).pack(side="left",padx=(0,6))
        ttk.Button(controls2,text="6. VAZIA (controle)",
                   command=self.capture_field_vacant_control).pack(side="left",padx=5)
        ttk.Button(controls2,text="7. MÃO ATUALIZADA (opcional)",
                   command=self.capture_field_refresh).pack(side="left",padx=5)
        negative=ttk.Frame(field_page)
        negative.pack(fill="x",pady=(0,7))
        ttk.Label(negative,text="Teste de controle SEM JOGADA (alternativa a PREPARADA):").pack(
            side="left",padx=(0,8))
        ttk.Button(negative,text="2X. SEM AÇÃO (slot vazio)",
                   command=self.capture_field_no_action).pack(side="left")
        ttk.Label(field_page,textvariable=self.field_status,
                  wraplength=960,justify="left").pack(fill="x",pady=(5,8))
        ttk.Label(field_page,text=(
            "Faça uma captura ANTES somente com a posição escolhida VAZIA. "
            "PREPARADA (opcional) após escolher FaceUp/FaceDown e Guardian Star. "
            "NA MESA assim que colocar a carta, antes do turno. "
            "OCUPADA (controle): sem retirar nem alterar a carta, repita a leitura. "
            "REMOVIDA: depois que a carta realmente sair do campo. "
            "VAZIA (controle): capture novamente sem alterar o slot vazio. "
            "MÃO ATUALIZADA pode ocorrer quando o turno mudar, em qualquer ordem "
            "posterior à captura NA MESA. "
            "Na região ampliada, somente o mesmo ePSXe é lido, sem dump bruto. "
            "IMPORTANTE: no jogo, a escolha FaceUp/FaceDown pode ser irreversivel. "
            "Nao tente cancelar depois de escolher a face. "
            "Controle SEM AÇÃO: clique 1. ANTES, nao interaja com o jogo "
            "nem com a selecao de cartas/turno e clique 2X. SEM AÇÃO. "
            "Isso salva um JSON separado, sem invocacao e sem PREPARADA. "
            "Para testar a invocacao real, comece novamente por 1. ANTES. "
            "Monitor direcionado e escopo so mudam no proximo ANTES. "
            "Todos os enderecos seguem NAO VALIDADOS."
        ),wraplength=960,justify="left").pack(anchor="w")
        self.tabs.add(field_page,text="Campo de duelo")



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

    def _active_rom_for_ram(self):
        entry=self.selected()
        if not entry:
            raise ValueError("Selecione uma ISO na Biblioteca primeiro")
        active=self.catalog.current()
        if not active or active.get("sha256")!=entry.get("sha256"):
            raise ValueError("Ative este perfil no overlay antes do diagnóstico")
        if self.ram_probe is None:
            raise RuntimeError("Diagnóstico requer Biblioteca integrada ao Assistente, não janela independente")
        return entry

    def capture_ram_before(self):
        try:
            entry=self._active_rom_for_ram()
            snap=self.ram_probe.capture_before(entry["sha256"])
            ids=", ".join(f"#{i:03d}" for i in snap["hand_ids"])
            self.ram_diag_status.set(
                "Captura ANTES concluída (somente leitura). "+
                f"ePSXe PID {snap['pid']}; mão: {ids}. "+
                "Agora realize uma fusão no jogo e clique Capturar DEPOIS.")
            self.status.set("Diagnóstico RAM: captura ANTES armazenada apenas em memória.")
        except Exception as exc:
            messagebox.showwarning("Diagnóstico RAM",str(exc),parent=self)

    def capture_ram_after(self):
        try:
            entry=self._active_rom_for_ram()
            observed=self.ram_result_id.get().strip()
            if observed and (not observed.isdecimal() or not 1<=int(observed)<=722):
                raise ValueError("Resultado observado deve ser um ID entre 1 e 722")
            result,path=self.ram_probe.capture_after(
                entry["sha256"],
                observed_result_id=int(observed) if observed else None)
            changes=", ".join(
                f"{name}: {data['changed_bytes']} bytes"
                for name,data in result["diff"].items()
                if data.get("changed_bytes") is not None)
            self.ram_diag_status.set(
                "CAPTURA EXPERIMENTAL SALVA — não comprova fusão. "+
                f"PID {result['pid']}; alterações: {changes or 'nenhuma região comparável'}. "+
                f"Arquivo: {path}")
            self.status.set("Comparação de RAM salva em: "+str(path))
        except Exception as exc:
            messagebox.showwarning("Diagnóstico RAM",str(exc),parent=self)

    def _field_selected_sha(self):
        entry=self._active_rom_for_ram()
        if self.field_probe is None:
            raise RuntimeError("Leitor de campo experimental indisponível")
        return entry["sha256"]

    def capture_field_before(self):
        try:
            sha=self._field_selected_sha()
            typed=self.field_target_id.get().strip()
            if not typed.isdecimal() or not 1<=int(typed)<=722:
                raise ValueError("Informe um ID válido entre 1 e 722")
            target=int(typed)
            confirmed=messagebox.askyesno(
                "Captura experimental do campo",
                f"A carta #{target:03d} está na MÃO e o slot {self.field_slot.get()} "
                "está VAZIO na mesa?\\n\\n"
                "Não avance se houver outro monstro no mesmo slot. "
                "A varredura usa 96 KiB ou 1 MiB, conforme sua seleção, "
                "mas nenhum byte será tratado como slot comprovado.",
                parent=self)
            if not confirmed:return
            if self.field_probe is None:
                raise RuntimeError("Leitor RAM não disponível")
            self.field_probe=FieldMemoryProbe(
                self.field_probe.reader_provider,self.catalog.home,
                expanded=bool(self.field_expand.get()),
                focused=bool(self.field_focus.get()))
            snap=self.field_probe.capture_before(
                sha,target,user_slot=int(self.field_slot.get()))
            self.field_status.set(
                f"ANTES registrada: PID {snap['pid']}; carta #{target:03d} na mão. "
                f"{snap['readable_chunks']} blocos legíveis; "
                f"{len(snap['unreadable_chunks'])} indisponíveis. "
                "Para controle sem jogada, nao toque no jogo e clique 2X. SEM AÇÃO. "
                "Para invocação real, prepare a carta e prossiga a 3. NA MESA.")
        except Exception as exc:
            messagebox.showwarning("Investigação do campo",str(exc),parent=self)

    def capture_field_prepared(self):
        try:
            sha=self._field_selected_sha()
            if not messagebox.askyesno(
                "Carta preparada, ainda fora do slot",
                "Você já selecionou a carta, FaceUp/FaceDown e Guardian Star, "
                "mas AINDA NÃO a posicionou no campo? Esta etapa é opcional.",
                parent=self):
                return
            prepared=self.field_probe.capture_prepared(
                sha,face_state=self.field_face.get())
            diff=prepared["changes_since_before"]
            self.field_status.set(
                f"PREPARADA registrada: {diff['changed_bytes']} bytes alterados "
                f"na região experimental. Agora POSICIONE a carta no slot e "
                "avance para 3. NA MESA quando ela estiver realmente no campo. "
                "Nao tente cancelar apos escolher FaceUp/FaceDown.")
        except Exception as exc:
            messagebox.showwarning("Investigação do campo",str(exc),parent=self)

    def capture_field_no_action(self):
        """Controle negativo: o jogo permanece intacto entre as leituras."""
        try:
            sha=self._field_selected_sha()
            if not messagebox.askyesno(
                "Controle SEM AÇÃO — nenhuma jogada",
                "Você já registrou 1. ANTES com a carta na mão e o slot vazio? "
                "DESDE ENTÃO, manteve o jogo no mesmo estado, sem selecionar "
                "cartas, clicar em FaceUp/FaceDown, passar o turno, atacar "
                "ou mover nada? O slot continua vazio? "
                "Este procedimento não envolve cancelar uma jogada. "
                "Depois deste controle, clique novamente 1. ANTES para "
                "uma invocação real.",
                parent=self):
                return
            report,path=self.field_probe.capture_no_action(
                sha,user_slot=int(self.field_slot.get()))
            changes=report["no_action_analysis"]
            summary=changes["before_to_no_action"]
            focus=changes["focus_before_to_no_action"]
            priority=report["priority_address_review"]["candidates"]
            summary_candidates="; ".join(
                f"{x['address'][-6:]}: {x['status']}"
                for x in priority)
            self.field_status.set(
                f"SEM AÇÃO registrado: {summary['changed_bytes']} bytes mudaram "
                f"na leitura de controle; na região direcionada, "
                f"{focus['changed_bytes']} bytes. "
                f"Prioritários: {summary_candidates}. "
                f"JSON: {path}. Inicie 1. ANTES para invocar de verdade. "
                "Nenhum slot foi validado.")
            self.status.set("Controle negativo sem jogada salvo: "+str(path))
        except Exception as exc:
            messagebox.showwarning(
                "Controle de leitura sem jogada",str(exc),parent=self)

    def capture_field_after(self):
        try:
            sha=self._field_selected_sha()
            if not messagebox.askyesno(
                "Carta SETADA no slot",
                "A carta já está VISÍVEL no slot da sua mesa? "
                "Capture AGORA, antes de passar o turno. "
                "Ela pode continuar aparecendo na RAM da mão e isso NÃO é erro. "
                "Confirme apenas se realmente a colocou no campo.",
                parent=self):
                return
            report,path=self.field_probe.capture_after(
                sha,face_state=self.field_face.get(),
                user_slot=int(self.field_slot.get()))
            analysis=report["analysis"]
            still=report["hand_state_at_set"]["target_still_visible_in_hand_ram"]
            # Leitura de uint16 apenas; nao confundir com card ID do slot real.
            observed=report["observed_by_user"]["slot_position_1_to_5"]
            raw=report["hypothetical_slot_probe"]["set"][observed-1]
            suspect=(f"Candidato {raw['address']} = {raw['u16_le']} (NÃO validado). "
                     if raw["u16_le"] is not None
                     else "Candidato indisponível nesta captura. ")
            self.field_status.set(
                f"NA MESA registrada: {analysis['candidate_count_total']} ocorrências "
                f"novas do ID #{report['reference_card_id']:03d}. "
                +suspect+
                f"ID continua na RAM da mão: {'SIM (esperado neste estágio)' if still else 'NÃO'}. "
                f"Arquivo: {path}. "
                "Opcional: OCUPADA (controle), depois REMOVIDA e VAZIA (controle).")
            self.status.set("Hipóteses de campo salvas em: "+str(path))
        except Exception as exc:
            messagebox.showwarning("Investigação do campo",str(exc),parent=self)

    def capture_field_occupied_control(self):
        try:
            sha=self._field_selected_sha()
            if not messagebox.askyesno(
                "Controle com a carta ainda na mesa",
                "A mesma carta continua fisicamente no mesmo slot? "
                "Capture sem invocar, atacar, mover, destruir ou passar o turno "
                "entre NA MESA e este controle sempre que possível.",
                parent=self):
                return
            report,path=self.field_probe.capture_occupied_control(sha)
            self.field_status.set(
                f"OCUPADA (controle) registrada. "
                f"Arquivo atualizado: {path}. Agora capture REMOVIDA "
                "quando o monstro efetivamente sair da mesa.")
            self.status.set("Controle de ocupação salvo: "+str(path))
        except Exception as exc:
            messagebox.showwarning("Investigação da ocupação",str(exc),parent=self)

    def capture_field_vacant_control(self):
        try:
            sha=self._field_selected_sha()
            if not messagebox.askyesno(
                "Controle de slot vazio",
                "O slot da carta permanece VAZIO desde a última REMOVIDA? "
                "Evite outras ações entre as capturas. "
                "O controle pode eliminar candidatos instáveis.",
                parent=self):
                return
            report,path=self.field_probe.capture_vacant_control(sha)
            analysis=report["occupancy_analysis"]
            priority=report["priority_address_review"]["candidates"]
            summary_candidates="; ".join(
                f"{x['address'][-6:]}: {x['status']}"
                for x in priority)
            self.field_status.set(
                f"VAZIA (controle) registrada: {analysis['matched_total']} "
                "bytes correlacionados restantes, "
                f"{analysis['reversible_total']} reversíveis; "
                f"{analysis['discarded_due_to_unstable_controls']} descartados "
                f"por controles instáveis. "
                f"Prioritários: {summary_candidates}. "
                f"Não comprova nenhum slot. JSON: {path}")
            self.status.set("Controle de slot vazio salvo: "+str(path))
        except Exception as exc:
            messagebox.showwarning("Investigação da ocupação",str(exc),parent=self)

    def capture_field_refresh(self):
        try:
            sha=self._field_selected_sha()
            if not messagebox.askyesno(
                "Confirmar nova mão no turno",
                "O turno já foi passado e a mão do ePSXe atualizou? "
                "A carta pode permanecer na mesa; esta fase é opcional.",
                parent=self):
                return
            report,path=self.field_probe.capture_hand_refresh(sha)
            analysis=report["hand_refresh_analysis"]
            self.field_status.set(
                f"MÃO ATUALIZADA registrada: ID diminuiu na mão: "
                f"{'SIM' if analysis['target_count_decreased'] else 'NÃO'}. "
                f"Relatório atualizado: {path}. "
                "Este dado NÃO comprova slot de mesa.")
            self.status.set("Diagnóstico do campo atualizado: "+str(path))
        except Exception as exc:
            messagebox.showwarning("Investigação do campo",str(exc),parent=self)

    def capture_field_removed(self):
        try:
            sha=self._field_selected_sha()
            if not messagebox.askyesno(
                "Confirmar remoção",
                "A carta investigada NÃO está mais no SEU campo? "
                "Registrar somente se ela realmente saiu da mesa.",
                parent=self):
                return
            report,path=self.field_probe.capture_removed(sha)
            candidates=report["analysis"]["candidates"]
            cleared=sum(x["disappeared_after_removal"] is True for x in candidates)
            occupancy=report["occupancy_analysis"]
            self.field_status.set(
                f"REMOVIDA: {cleared}/{len(candidates)} IDs novos desapareceram; "
                f"{occupancy.get('matched_total',0)} bytes correlacionados com "
                f"entrada/saída, dos quais {occupancy.get('reversible_total',0)} "
                f"retornaram ao valor anterior. "
                f"Arquivo: {path}. Opcional: 6. VAZIA (controle). "
                "Nenhum slot foi validado.")
            self.status.set("Hipóteses com remoção salvas em: "+str(path))
        except Exception as exc:
            messagebox.showwarning("Investigação do campo",str(exc),parent=self)

    def start_temporal(self):
        try:
            entry=self._active_rom_for_ram()
            if self.temporal is None:
                raise RuntimeError("Monitor temporal indisponível neste modo")
            initial=self.temporal.start(
                entry["sha256"],interval_ms=int(self.temporal_interval.get()),
                duration_seconds=int(self.temporal_duration.get()))
            self.temporal_status.set(
                f"Gravando. PID {initial['pid']}; 1 amostra. "
                "Realize UMA ação no ePSXe, volte e marque o tipo de ação. "
                "Depois clique Parar e exportar.")
            self._temporal_schedule()
        except Exception as exc:
            messagebox.showwarning("Monitor temporal",str(exc),parent=self)

    def _temporal_schedule(self):
        if self.temporal is not None and self.temporal.active and self.winfo_exists():
            self._temporal_after_id=self.after(
                self.temporal.interval_ms,self._temporal_tick)

    def _temporal_tick(self):
        self._temporal_after_id=None
        if self.temporal is None or not self.temporal.active:
            return
        try:
            state=self.temporal.sample()
            self.temporal_status.set(
                f"Gravando: {state['samples']} amostras · "
                f"{state['elapsed_ms']/1000:.1f}s · "
                f"{len(self.temporal.markers)} marcações. "
                "O monitor não confirma fusões nem identifica cartas da mesa.")
            if state["finished_by_duration"] or state["finished_by_limit"]:
                self.stop_temporal(
                    reason="duracao" if state["finished_by_duration"] else "limite")
            else:
                self._temporal_schedule()
        except Exception as exc:
            self.stop_temporal(reason="erro",detail=str(exc))

    def mark_temporal(self, label):
        try:
            if self.temporal is None:
                raise RuntimeError("Monitor não está integrado ao Assistente")
            marker=self.temporal.mark(label)
            self.temporal_status.set(
                f"Marcador '{marker['caption']}' adicionado em "
                f"{marker['elapsed_ms']/1000:.1f}s (clique do usuário). "
                f"Amostras: {len(self.temporal.samples)}.")
        except Exception as exc:
            messagebox.showwarning("Monitor temporal",str(exc),parent=self)

    def stop_temporal(self, reason="manual", detail=""):
        if self._temporal_after_id is not None:
            try:self.after_cancel(self._temporal_after_id)
            except tk.TclError:pass
            self._temporal_after_id=None
        if self.temporal is None or not self.temporal.active:
            if reason=="manual":
                messagebox.showinfo("Monitor temporal",
                                    "Nenhuma gravação em andamento.",parent=self)
            return
        try:
            report,json_path,csv_path=self.temporal.stop(reason=reason)
            self.temporal_status.set(
                f"Gravação finalizada ({reason}): {report['sample_count']} amostras, "
                f"{len(report['markers'])} marcações. "
                f"JSON: {json_path} | CSV: {csv_path}. "
                "Nenhuma fusão confirmada automaticamente."
                +(f" Erro durante leitura: {detail}" if detail else ""))
            self.status.set("Relatórios temporais exportados para: "+str(json_path.parent))
        except Exception as exc:
            messagebox.showerror("Monitor temporal","Falha na exportação: "+str(exc),parent=self)

    def load_fusion_candidates(self):
        entry=self.selected()
        path=(self.catalog.home/"investigacoes"/(entry["sha256"]+".fusoes.json")) if entry else None
        report=load_json(path,{}) if path else {}
        if not entry or report.get("rom_sha256")!=entry["sha256"]:
            self.fusion_rows=[]
            self.fusion_report={}
            self.fusion_review_status=None
        else:
            self.fusion_rows=list(report.get("candidates",[]))
            self.fusion_report=report
            profile=self.catalog.profile_for(entry) or {}
            review=profile.get("fusion_review",{})
            self.fusion_review_status=(
                review.get("status") if review.get("candidate_fingerprint")==
                report.get("candidate_fingerprint") else None
            )
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
        review_label=("REVISADA PELO USUÁRIO · não testada individualmente"
                      if self.fusion_review_status else
                      "CANDIDATA — não validada")
        for i,r in enumerate(page):
            def label(k):
                cid=int(r[k])
                return f"#{cid:03d} {self.fusion_names.get(cid,'?')}"
            table.insert("","end",iid=str(i),values=(
                label("a"),label("b"),label("result"),review_label))
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

    def export_all_fusion_candidates(self):
        """Exporta TODAS as candidatas, inclusive as ocultas pela prévia de 750."""
        entry=self.selected()
        if (not entry or entry["sha256"]!=self.fusion_source_sha
                or not getattr(self,"fusion_rows",None)):
            return messagebox.showwarning("Exportação",
                "Selecione uma ISO e execute Buscar fusões na ISO.",parent=self)
        destination=filedialog.asksaveasfilename(
            parent=self,title="Exportar todas as fusões candidatas",
            initialfile="fusoes_candidatas_"+entry["sha256"][:12]+".csv",
            defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not destination:return
        try:
            with Path(destination).open("w",newline="",encoding="utf-8-sig") as handle:
                writer=csv.writer(handle)
                writer.writerow(["SHA256_ISO","Material_A_ID","Material_A_Nome",
                                 "Material_B_ID","Material_B_Nome",
                                 "Resultado_ID","Resultado_Nome","Evidencia"])
                for row in self.fusion_rows:
                    a,b,c=(int(row[k]) for k in ("a","b","result"))
                    writer.writerow([
                        entry["sha256"],a,self.fusion_names.get(a,""),
                        b,self.fusion_names.get(b,""),c,self.fusion_names.get(c,""),
                        "revisada_usuario_lote" if self.fusion_review_status else
                        "candidata_nao_validada"])
        except OSError as exc:
            return messagebox.showerror("Exportação falhou",str(exc),parent=self)
        self.status.set(
            f"Exportadas {len(self.fusion_rows)} candidatas para revisão completa: "+
            str(destination))

    def approve_fusion_batch(self):
        """Confirma em duas etapas antes de expor receitas ao overlay."""
        entry=self.selected()
        if not entry or entry.get("sha256")!=self.fusion_source_sha:
            return messagebox.showwarning("Fusões","Selecione o mod correto.",parent=self)
        report=getattr(self,"fusion_report",{})
        count=len(getattr(self,"fusion_rows",[]))
        fingerprint=report.get("candidate_fingerprint")
        if count<50 or not fingerprint:
            return messagebox.showwarning("Sem receitas revisáveis",
                "Execute Buscar fusões na ISO e confira as candidatas primeiro.",
                parent=self)
        if not messagebox.askyesno("Aprovação de catálogo completo",
            "ISO: "+entry.get("file_name","")+"\n"+
            f"Fusões candidatas: {count}\n"+
            f"Bancos coincidentes: {report.get('matching_banks',0)}/7\n"+
            "SHA-256 da ISO: "+entry["sha256"]+"\n\n"+
            "A tela mostra no máximo 750 linhas por vez. Confirme que revisou "
            "também as demais (use Exportar lista completa CSV).\n\n"
            "Este procedimento permite usar TODAS essas receitas no overlay, "
            "mas NÃO prova que cada "
            "uma foi reproduzida no ePSXe.\n\n"
            "Deseja continuar? Nenhuma ROM ou save será alterado.",
            parent=self):
            return
        typed=simpledialog.askstring("Confirmação explícita",
            "Para ativar o catálogo revisado, digite exatamente:\n"
            "CATALOGO REVISADO\n\n"
            "Essa ação aprova as candidatas para uso no overlay, "
            "sem marcá-las como verificadas individualmente no jogo.",
            parent=self)
        if typed!="CATALOGO REVISADO":
            self.status.set("Aprovação cancelada: expressão de confirmação incorreta.")
            return
        try:
            result=self.catalog.review_fusion_batch(
                entry["sha256"],expected_fingerprint=fingerprint,
                acknowledgement=typed)
            self.refresh()
            self.load_fusion_candidates()
            # Atualiza imediatamente o overlay somente se o perfil está
            # efetivamente ativo; o observador também vê o registro atualizado.
            current=self.catalog.current()
            if current and current.get("sha256")==entry["sha256"] and self.on_activate:
                self.on_activate(overlay_snapshot(self.catalog))
        except Exception as exc:
            return messagebox.showerror("Lote não aprovado",str(exc),parent=self)
        total=result["count"]
        self.status.set(f"{total} fusões revisadas do mod "+entry["file_name"]+
                        " disponíveis no overlay. Não verificadas individualmente.")
        messagebox.showinfo("Catálogo revisado",
            f"{total} receitas vinculadas somente a esta ISO.\n"
            "Status: revisadas pelo usuário; não testadas individualmente.\n"
            "As ISOs, saves e Memory Cards não foram alterados.\n"
            "Abra o overlay e confira as rotas da mão detectada.",parent=self)

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
            "Fusões não revisadas permanecem desativadas; "
            "fusões revisadas podem ser usadas com indicação de sua origem.",parent=self)

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
        # Encerrar a aquisição antes de destruir widgets; salvar diagnóstico parcial.
        if self.temporal is not None and self.temporal.active:
            self.stop_temporal(reason="fechar_janela")
        if self._temporal_after_id is not None:
            try:self.after_cancel(self._temporal_after_id)
            except tk.TclError:pass
            self._temporal_after_id=None
        if self._after_id is not None:
            self.after_cancel(self._after_id)
        if self._card_filter_after is not None:
            self.after_cancel(self._card_filter_after)
        if self._fusion_filter_after is not None:
            self.after_cancel(self._fusion_filter_after)
        self.stop_watch(persist=False)
        self.destroy()


def abrir_biblioteca(parent, on_activate=None, catalog=None, ram_probe=None):
    """Abre janela dentro do mesmo processo Tkinter do overlay."""
    return BibliotecaMods(parent,on_activate=on_activate,catalog=catalog,ram_probe=ram_probe)


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

    # Rastreio de RAM sem hooks adicionais no app legado.
    catalog=ModCatalog()
    ram_probe=FusionMemoryProbe(
        (lambda: compact.get_reader()) if compact is not None
        and callable(getattr(compact,"get_reader",None)) else (lambda: None),
        catalog.home)
    current={"window":None}
    def show(_event=None):
        existing=current["window"]
        if existing and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
        else:
            current["window"]=abrir_biblioteca(surface,on_activate=apply_snapshot,
                                               catalog=catalog,ram_probe=ram_probe)
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
            "observer":observer,"renderer":renderer,"ram_probe":ram_probe}
