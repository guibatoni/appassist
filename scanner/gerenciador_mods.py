#!/usr/bin/env python3
"""Gerenciador local de mods do Forbidden Memories.

1. Vigia uma pasta por novas ISO/BIN
2. Analisa em segundo plano com o scanner estrutural
3. Exibe os dados validados e os pendentes
4. Salva um perfil isolado por assinatura SHA-256
5. Ativa somente após confirmação explícita

Não altera ROMs, não faz downloads, não envia arquivos para a rede.
"""
from __future__ import annotations

import json
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from auto_mods import DirectoryMonitor, ModCatalog, atomic_json, load_json

COLS = ("arquivo", "estado", "cartas", "oponentes", "drops", "fusoes", "ranks")


def status_label(value):
    return {
        "conhecido_validado": "Reconhecido",
        "parcial_revisar": "Parcial — revisar",
        "desconhecido": "Desconhecido — bloqueado",
    }.get(value, "Não identificado")


class Manager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Forbidden Memories — Analisador Inteligente MultiMod")
        self.geometry("1040x680")
        self.minsize(820, 520)
        self.catalog = ModCatalog()
        self.events = queue.Queue()
        self.monitor = None
        self.settings_path = self.catalog.home / "scanner_settings.json"
        saved = load_json(self.settings_path, {})
        self.folder = tk.StringVar(value=saved.get("watch_folder", ""))
        self.status = tk.StringVar(value="Selecione a pasta de imagens ou um arquivo ISO/BIN")
        self.build_widgets()
        self.refresh()
        self.after(250, self.poll_events)
        self.protocol("WM_DELETE_WINDOW", self.shutdown)
        if self.folder.get() and Path(self.folder.get()).is_dir():
            self.after(400, self.start_watch)

    def build_widgets(self):
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Analisador MultiMod", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Detecta novos mods, extrai apenas dados verificáveis e exige confirmação antes de ativar.",
        ).pack(anchor="w", pady=(3, 12))
        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Label(controls, text="Pasta de ISOs:").pack(side="left")
        ttk.Entry(controls, textvariable=self.folder).pack(side="left", fill="x", expand=True, padx=7)
        ttk.Button(controls, text="Escolher pasta", command=self.choose_folder).pack(side="left", padx=3)
        ttk.Button(controls, text="Monitorar", command=self.start_watch).pack(side="left", padx=3)
        ttk.Button(controls, text="Parar", command=self.stop_watch).pack(side="left", padx=3)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=10)
        ttk.Button(actions, text="Analisar ISO/BIN", command=self.choose_file).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Atualizar lista", command=self.refresh).pack(side="left", padx=6)
        ttk.Button(actions, text="Detalhes da análise", command=self.details).pack(side="left", padx=6)
        ttk.Button(actions, text="Ativar perfil selecionado", command=self.activate).pack(side="right")

        table_box = ttk.Frame(outer)
        table_box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table_box, columns=COLS, show="headings", selectmode="browse", height=12)
        headers = {"arquivo": "Imagem", "estado": "Validação", "cartas": "Cartas", "oponentes": "Adversários",
                   "drops": "Drops", "fusoes": "Fusões", "ranks": "Ranks"}
        for col in COLS:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=115 if col not in ("arquivo", "estado") else (280 if col == "arquivo" else 175), anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_box, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.show_summary())
        ttk.Label(outer, text="Revisão e segurança", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(12, 3))
        self.summary = tk.Text(outer, height=7, wrap="word", state="disabled", font=("Consolas", 10))
        self.summary.pack(fill="x")
        ttk.Label(outer, textvariable=self.status, wraplength=960).pack(anchor="w", pady=(10, 0))

    def selected(self):
        chosen = self.tree.selection()
        if not chosen:
            return None
        return next((e for e in self.catalog.list() if e.get("sha256") == chosen[0]), None)

    def refresh(self):
        chosen = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for entry in sorted(self.catalog.list(), key=lambda e: e.get("analysed_at", ""), reverse=True):
            verified = entry.get("verified", {})
            self.tree.insert("", "end", iid=entry["sha256"], values=(
                entry.get("file_name", ""),
                status_label(entry.get("level")),
                verified.get("cartas", "pendente"),
                verified.get("oponentes", "pendente"),
                verified.get("tabelas_drops", "pendente"),
                verified.get("fusoes", "pendente"),
                verified.get("nomes_dos_ranks", "pendente"),
            ))
        if chosen and self.tree.exists(chosen[0]):
            self.tree.selection_set(chosen[0])
        self.show_summary()

    def show_summary(self):
        entry = self.selected()
        current = self.catalog.current()
        if entry:
            text = (
                "ARQUIVO: " + entry["file_name"] + "\n"
                "SHA-256: " + entry["sha256"] + "\n"
                "STATUS: " + status_label(entry.get("level")) + "\n"
                "ATIVO: " + ("SIM" if current and current["sha256"] == entry["sha256"] else "NÃO") + "\n"
                "FUSÕES: não extraídas automaticamente nesta versão; nunca usar catálogo de outro mod.\n"
                "RANKS: só habilitados para ISO X15 com assinatura verificada.\n"
                "DADOS NÃO CONFIRMADOS: ficam indisponíveis, mesmo após a ativação."
            )
        else:
            text = "Selecione uma ISO para ver o nível de validação e decidir se deseja ativá-la."
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")

    def details(self):
        entry = self.selected()
        if not entry:
            messagebox.showinfo("Seleção", "Selecione um perfil na tabela.", parent=self)
            return
        profile = self.catalog.profile_for(entry)
        if profile is None:
            messagebox.showerror("Erro", "Perfil ausente ou divergente da assinatura.", parent=self)
            return
        detail = tk.Toplevel(self)
        detail.title("Validação — " + entry.get("file_name", ""))
        detail.geometry("820x580")
        box = tk.Text(detail, wrap="none", font=("Consolas", 10))
        box.pack(fill="both", expand=True)
        safe = {
            "arquivo": entry.get("file_name"),
            "hash": entry.get("sha256"),
            "nível": entry.get("level"),
            "validação": profile.get("verified"),
            "recursos_disponíveis": entry.get("features"),
            "quantidades": {k: len(profile.get(k, [])) for k in ("cards", "opponents", "decks", "drops", "fusion_recipes")},
            "observações": profile.get("notes"),
            "pasta_local": entry.get("profile_path"),
        }
        box.insert("1.0", json.dumps(safe, ensure_ascii=False, indent=2))
        box.configure(state="disabled")

    def activate(self):
        entry = self.selected()
        if not entry:
            messagebox.showinfo("Seleção", "Selecione um mod na tabela.", parent=self)
            return
        if entry["level"] == "desconhecido":
            messagebox.showwarning("Mod não identificado",
                "A estrutura não foi reconhecida. O scanner não atribuirá cartas, fusões ou drops de outro mod.\n"
                "A análise está salva e pode ser investigada posteriormente.", parent=self)
            return
        if not messagebox.askyesno("Confirmar ativação",
            "Ativar o perfil desta imagem?\n\n" + entry["file_name"] +
            "\n\n" + status_label(entry["level"]) +
            "\n\nA ativação NÃO modifica a ISO, saves ou Memory Cards.\n"
            "Dados não validados continuarão desativados.\n\n"
            "O overlay precisa estar configurado para ler o perfil ativo.", parent=self):
            return
        try:
            active = self.catalog.activate(entry["sha256"], acknowledge_uncertainty=True)
        except (OSError, ValueError, PermissionError) as exc:
            messagebox.showerror("Falha na ativação", str(exc), parent=self)
            return
        self.status.set("Perfil ativado: " + entry["file_name"] + " — reinicie/recarregue o overlay conectado.")
        self.show_summary()
        messagebox.showinfo("Perfil salvo",
            "Perfil ativo salvo com segurança em:\n" + str(self.catalog.active_file) +
            "\n\nO overlay precisa de integração com este registro para atualizar sua tela.",
            parent=self)

    def choose_folder(self):
        path = filedialog.askdirectory(title="Pasta das ISOs", parent=self)
        if path:
            self.folder.set(path)
            self.start_watch()

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="Analisar imagem de Forbidden Memories",
            filetypes=[("Imagens PS1", "*.bin *.iso"), ("Todos os arquivos", "*.*")], parent=self)
        if not path:
            return
        parent = Path(path).parent
        if self.monitor is None:
            self.monitor = DirectoryMonitor(parent, self.catalog, self.events.put, interval=4, quiet_seconds=3)
            self.monitor.start()
        self.monitor.scan_file(Path(path))
        self.status.set("Arquivo enviado para análise: " + Path(path).name)

    def start_watch(self):
        folder = Path(self.folder.get())
        if not folder.is_dir():
            messagebox.showwarning("Pasta ausente", "Selecione uma pasta existente.", parent=self)
            return
        self.stop_watch()
        self.monitor = DirectoryMonitor(folder, self.catalog, self.events.put, interval=4, quiet_seconds=5)
        self.monitor.start()
        atomic_json(self.settings_path, {"watch_folder": str(folder.resolve())})
        self.status.set("Monitorando pasta: " + str(folder))

    def stop_watch(self):
        if self.monitor is not None:
            self.monitor.stop()
            self.monitor = None

    def poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event.get("event")
                if kind == "concluido":
                    self.status.set("Análise concluída: " + event.get("file", "") + " — " + event.get("level", ""))
                    self.refresh()
                elif kind == "erro":
                    self.status.set("Erro em " + event.get("file", "") + ": " + event.get("message", ""))
                elif kind == "analisando":
                    self.status.set("Analisando ISO (sem modificá-la): " + event.get("file", ""))
                elif kind == "encontrado":
                    self.status.set("Nova imagem detectada: " + event.get("file", ""))
        except queue.Empty:
            pass
        self.after(250, self.poll_events)

    def shutdown(self):
        self.stop_watch()
        self.destroy()


if __name__ == "__main__":
    Manager().mainloop()
