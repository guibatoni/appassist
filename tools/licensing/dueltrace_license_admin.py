"""Batoni Dev — Local License Manager UI (owner ONLY, never customer release).

Standalone Tkinter GUI for encrypted key creation, offline issuance,
verification, re-sending the original license, and a minimal sales ledger.
This program never accesses Patreon, the Internet or the customer's ISO.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

# Source entry point needs access to the shared client verifier.
# PyInstaller uses --paths scanner when packaging the admin EXE.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scanner"))

from dueltrace_offline_license import LicenseError
from dueltrace_license_admin_core import (
    admin_paths, check_password, create_keys, default_admin_home,
    export_public_key, has_keys, issue_license, list_issued,
    read_request_file, recover_public_key, resend_issued, verify_issued,
    _public_b64,
)

BG = "#061123"
SURFACE = "#0d1b34"
PANEL = "#102442"
TEXT = "#e9f1ff"
MUTED = "#a5b8d0"
GOLD = "#eac77f"
CYAN = "#7fdcff"
ERROR = "#f3a3a3"


def _downloads() -> Path:
    path = Path.home() / "Downloads"
    return path if path.is_dir() else Path.home()


class LicenseManager(tk.Tk):
    def __init__(self, *, home: Path | None = None):
        super().__init__()
        self.home = home if home is not None else default_admin_home()
        self.current_request: dict | None = None
        self.current_request_path: Path | None = None
        self.order_var = tk.StringVar()
        self.expiry_var = tk.StringVar()
        self.confirmed_var = tk.BooleanVar(value=False)
        self.filter_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Nenhuma operação de ativação iniciada.")
        self.key_status_var = tk.StringVar(value="Verificando chaves...")
        self.request_var = tk.StringVar(value="Nenhum pedido selecionado.")
        self.title("Batoni Dev — Gerenciador de Licenças")
        self.geometry("1010x735")
        self.minsize(870, 650)
        self.configure(background=BG)
        self._configure_theme()
        self._build_widgets()
        self.filter_var.trace_add("write", lambda *_: self.refresh_history())
        self.refresh_keys()
        self.refresh_history()

    def _configure_theme(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", foreground=GOLD, font=("Segoe UI Semibold", 20))
        style.configure("Subtitle.TLabel", foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Heading.TLabel", foreground=CYAN, font=("Segoe UI Semibold", 12))
        style.configure("TButton", background=PANEL, foreground=TEXT, padding=(13, 9),
                        borderwidth=0, focuscolor=PANEL)
        style.map("TButton", background=[("active", "#1b3c64"), ("disabled", "#122238")],
                  foreground=[("disabled", "#66778f")])
        style.configure("Gold.TButton", background="#bc9858", foreground="#071326",
                        font=("Segoe UI Semibold", 10))
        style.map("Gold.TButton", background=[("active", GOLD), ("disabled", "#45516c")])
        style.configure("TEntry", fieldbackground="#0a1830", foreground=TEXT, insertcolor=TEXT)
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 7, 0, 0))
        style.configure("TNotebook.Tab", background=SURFACE, foreground=MUTED,
                        padding=(22, 11))
        style.map("TNotebook.Tab", background=[("selected", PANEL)],
                  foreground=[("selected", GOLD)])
        style.configure("Treeview", background=SURFACE, foreground=TEXT,
                        fieldbackground=SURFACE, borderwidth=0, rowheight=31)
        style.configure("Treeview.Heading", background=PANEL, foreground=CYAN,
                        font=("Segoe UI Semibold", 9))
        style.map("Treeview", background=[("selected", "#255481")])

    def _build_widgets(self):
        header = ttk.Frame(self, padding=(26, 17, 26, 13))
        header.pack(fill="x")
        ttk.Label(header, text="BATONI DEV", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Gerenciador de Licenças • DUELTRACE Commercial Lite",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(2, 1))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=25)
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=23, pady=(10, 0))
        self.issue_tab = ttk.Frame(self.tabs, padding=18)
        self.history_tab = ttk.Frame(self.tabs, padding=18)
        self.security_tab = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(self.issue_tab, text="Emitir licença")
        self.tabs.add(self.history_tab, text="Licenças emitidas")
        self.tabs.add(self.security_tab, text="Chaves e segurança")

        self._build_issue()
        self._build_history()
        self._build_security()
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=24)
        status = ttk.Frame(self, padding=(26, 10, 26, 13))
        status.pack(fill="x")
        ttk.Label(status, textvariable=self.status_var, style="Muted.TLabel",
                  wraplength=920).pack(anchor="w")

    def _build_issue(self):
        container = self.issue_tab
        ttk.Label(container, text="1. Importe o pedido enviado pelo comprador",
                  style="Heading.TLabel").pack(anchor="w", pady=(1, 9))
        row = ttk.Frame(container)
        row.pack(fill="x", pady=(0, 8))
        ttk.Button(row, text="Selecionar pedido (.json)", command=self.select_request).pack(side="left")
        ttk.Label(row, textvariable=self.request_var, style="Muted.TLabel",
                  wraplength=630).pack(side="left", padx=14)
        ttk.Separator(container).pack(fill="x", pady=(14, 18))

        ttk.Label(container, text="2. Identifique a compra e confirme o pagamento",
                  style="Heading.TLabel").pack(anchor="w", pady=(0, 9))
        ttk.Label(container, text="ID da compra (ex.: PATREON-0001), sem nome, e-mail ou senha.",
                  style="Muted.TLabel").pack(anchor="w")
        ttk.Entry(container, textvariable=self.order_var, width=47).pack(anchor="w", pady=(5, 11))
        ttk.Label(container, text="Validade (AAAA-MM-DD). Deixe vazio para licença permanente.",
                  style="Muted.TLabel").pack(anchor="w")
        ttk.Entry(container, textvariable=self.expiry_var, width=25).pack(anchor="w", pady=(5, 10))
        ttk.Checkbutton(container,
                        text="Confirmei o pagamento e os dados do pedido.",
                        variable=self.confirmed_var).pack(anchor="w", pady=(8, 11))

        ttk.Separator(container).pack(fill="x", pady=(9, 18))
        ttk.Label(container, text="3. Emita a licença assinada",
                  style="Heading.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Button(container, text="Emitir licença (.json)", style="Gold.TButton",
                   command=self.emit_license).pack(anchor="w")
        ttk.Label(container,
                  text="Até 2 computadores por compra. A licença original fica guardada localmente para reenvio. "
                       "O arquivo privado de assinatura nunca acompanha a licença do comprador.",
                  style="Muted.TLabel", wraplength=780, justify="left").pack(anchor="w", pady=(14, 0))

    def _build_history(self):
        ttk.Label(self.history_tab, text="Histórico local de licenças",
                  style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self.history_tab,
                  text="Acompanhe o ID da compra e reenvie uma licença já emitida, sem criar outra ativação.",
                  style="Muted.TLabel", wraplength=840).pack(anchor="w", pady=(5, 14))
        controls = ttk.Frame(self.history_tab)
        controls.pack(fill="x", pady=(0, 12))
        ttk.Label(controls, text="Buscar compra ou licença:").pack(side="left")
        ttk.Entry(controls, textvariable=self.filter_var, width=32).pack(side="left", padx=(9, 12))
        ttk.Button(controls, text="Atualizar", command=self.refresh_history).pack(side="left")
        columns = ("order_ref", "license_id", "device", "issued_on", "expires_on")
        self.ledger_tree = ttk.Treeview(self.history_tab, columns=columns,
                                        show="headings", height=12, selectmode="browse")
        for name, label, width in (
            ("order_ref", "Compra", 145),
            ("license_id", "ID da licença", 285),
            ("device", "Dispositivo", 130),
            ("issued_on", "Emissão", 95),
            ("expires_on", "Validade", 110),
        ):
            self.ledger_tree.heading(name, text=label)
            self.ledger_tree.column(name, width=width, minwidth=65, stretch=name=="license_id")
        self.ledger_tree.pack(fill="both", expand=True)
        ttk.Button(self.history_tab, text="Reenviar licença selecionada (.json)",
                   command=self.resend_license).pack(anchor="w", pady=(13, 0))

    def _build_security(self):
        ttk.Label(self.security_tab, text="Proteção de chaves",
                  style="Heading.TLabel").pack(anchor="w", pady=(0, 9))
        ttk.Label(self.security_tab, textvariable=self.key_status_var,
                  style="Muted.TLabel", wraplength=810).pack(anchor="w", pady=(0, 18))
        row = ttk.Frame(self.security_tab)
        row.pack(fill="x", pady=(0, 14))
        ttk.Button(row, text="Criar chaves privadas e públicas",
                   style="Gold.TButton", command=self.setup_keys).pack(side="left")
        ttk.Button(row, text="Exportar chave pública",
                   command=self.export_public).pack(side="left", padx=9)
        ttk.Button(row, text="Recuperar chave pública",
                   command=self.recover_public).pack(side="left")
        ttk.Separator(self.security_tab).pack(fill="x", pady=(15, 18))
        ttk.Label(self.security_tab, text="Verificar arquivo de licença",
                  style="Heading.TLabel").pack(anchor="w")
        ttk.Button(self.security_tab, text="Validar assinatura (.json)",
                   command=self.verify_license).pack(anchor="w", pady=(11, 18))
        ttk.Label(self.security_tab, text="Pasta local protegida pelo perfil do Windows:",
                  style="Muted.TLabel").pack(anchor="w")
        ttk.Label(self.security_tab, text=str(self.home), wraplength=790).pack(anchor="w", pady=(5, 13))
        ttk.Button(self.security_tab, text="Abrir pasta local",
                   command=self.open_local_folder).pack(anchor="w")
        ttk.Separator(self.security_tab).pack(fill="x", pady=(20, 17))
        guidance = (
            "Atenção: a chave privada só deve existir no seu PC. Faça uma cópia "
            "criptografada em mídia segura e guarde a senha separadamente. Nunca "
            "publique o arquivo .pem, nem o envie no GitHub ou ao comprador. "
            "A chave pública pode ser usada no build comercial. Este painel "
            "não recebe pagamentos nem verifica automaticamente o Patreon."
        )
        ttk.Label(self.security_tab, text=guidance, style="Muted.TLabel",
                  wraplength=820, justify="left").pack(anchor="w")

    def _error(self, exc: Exception) -> None:
        detail = str(exc) if isinstance(exc, (LicenseError, OSError, ValueError)) else (
            "Falha inesperada. Verifique os arquivos e permissões locais.")
        self.status_var.set("Operação não realizada: " + detail)
        messagebox.showerror("Batoni Dev — Operação não concluída", detail, parent=self)

    def _password(self, title: str) -> str | None:
        return simpledialog.askstring(title, "Senha da chave privada:", show="*",
                                      parent=self)

    def refresh_keys(self):
        paths = admin_paths(self.home)
        if has_keys(self.home):
            try:
                fingerprint = hashlib.sha256(
                    _public_b64(self.home).encode("ascii")).hexdigest()[:16]
                self.key_status_var.set(
                    "Chaves encontradas neste computador. Identificador público: " +
                    fingerprint + ". Emissão offline disponível.")
            except (LicenseError, OSError) as exc:
                self.key_status_var.set("Chaves não verificáveis: " + str(exc))
        elif paths["private"].exists():
            self.key_status_var.set(
                "Chave privada existente, mas chave pública ausente. "
                "Use Recuperar chave pública com sua senha.")
        else:
            self.key_status_var.set(
                "Nenhuma chave existente. Gere o par uma única vez neste PC; "
                "nunca gere sua chave privada no GitHub Actions.")

    def setup_keys(self):
        if not messagebox.askyesno(
            "Criar chaves offline",
            "A chave privada será criada SOMENTE neste computador, protegida por "
            "senha. Você deverá fazer backup seguro. Continuar?", parent=self):
            return
        first = self._password("Criar senha da Batoni Dev")
        if first is None:
            return
        second = self._password("Confirmar senha da Batoni Dev")
        if second is None:
            return
        try:
            create_keys(self.home, first, second)
            self.refresh_keys()
            self.status_var.set("Chaves criadas localmente e criptografadas. Faça backup seguro.")
            messagebox.showinfo("Chaves criadas",
                "A chave privada foi gerada e armazenada no seu perfil Windows. "
                "Faça backup seguro da pasta secrets e guarde a senha fora do PC. "
                "Exporte apenas a chave PÚBLICA quando preparar o build comercial.",
                parent=self)
        except Exception as exc:
            self._error(exc)

    def recover_public(self):
        pw = self._password("Recuperar chave pública")
        if pw is None:
            return
        try:
            recover_public_key(self.home, pw)
            self.refresh_keys()
            self.status_var.set("Chave pública recuperada a partir da sua chave privada.")
        except Exception as exc:
            self._error(exc)

    def export_public(self):
        destination = filedialog.asksaveasfilename(
            title="Exportar APENAS a chave pública",
            initialdir=str(_downloads()),
            initialfile="BatoniDev-chave-publica.txt",
            defaultextension=".txt",
            filetypes=[("Chave pública de texto", "*.txt")], parent=self)
        if not destination:
            return
        try:
            export_public_key(self.home, Path(destination))
            self.status_var.set("Chave pública exportada. A chave privada permaneceu local.")
            messagebox.showinfo("Chave pública exportada",
                "Você pode usar esse arquivo para preparar o build do cliente. "
                "NUNCA envie o arquivo privado .pem.", parent=self)
        except Exception as exc:
            self._error(exc)

    def select_request(self):
        filename = filedialog.askopenfilename(
            title="Selecionar pedido de ativação do comprador",
            initialdir=str(_downloads()), filetypes=[("Pedido JSON", "*.json")],
            parent=self)
        if not filename:
            return
        try:
            record = read_request_file(Path(filename))
            self.current_request = record
            self.current_request_path = Path(filename)
            self.request_var.set(
                f"Pedido {record['request_id'][:12]}… • dispositivo "
                f"{record['device_hash'][:12]}…")
            self.confirmed_var.set(False)
            self.status_var.set("Pedido válido. Informe o ID da compra e confirme o pagamento.")
        except Exception as exc:
            self.current_request = None
            self.request_var.set("Pedido inválido. Selecione outro arquivo.")
            self._error(exc)

    def emit_license(self):
        if self.current_request is None:
            messagebox.showwarning("Pedido necessário",
                                   "Selecione primeiro o pedido do comprador.", parent=self)
            return
        if not self.confirmed_var.get():
            messagebox.showwarning("Pagamento não confirmado",
                "Confirme manualmente o pagamento antes de emitir a licença.",
                parent=self)
            return
        pw = self._password("Emitir licença — senha Batoni Dev")
        if pw is None:
            return
        destination = filedialog.asksaveasfilename(
            title="Salvar licença assinada para enviar ao comprador",
            initialdir=str(_downloads()), initialfile="DUELTRACE-Licenca.json",
            defaultextension=".json", filetypes=[("Licença DUELTRACE", "*.json")],
            parent=self)
        if not destination:
            return
        if not messagebox.askyesno(
            "Confirmar emissão",
            f"Emitir licença para compra {self.order_var.get().strip().upper()}?\n"
            "Após criada, a licença offline não pode ser revogada remotamente.",
            parent=self):
            return
        try:
            issued = issue_license(
                self.home, pw, self.current_request, self.order_var.get(),
                Path(destination), purchase_confirmed=True,
                expires_on=self.expiry_var.get().strip() or None)
            self.status_var.set(
                f"Licença emitida: {issued['license_id']}. "
                "Envie somente o JSON ao comprador.")
            self.confirmed_var.set(False)
            self.current_request = None
            self.request_var.set("Nenhum pedido selecionado.")
            self.refresh_history()
            messagebox.showinfo("Licença emitida",
                "Arquivo salvo com sucesso. Envie SOMENTE o JSON da licença ao "
                "comprador. A chave privada nunca saiu deste computador.",
                parent=self)
        except Exception as exc:
            self._error(exc)

    def refresh_history(self):
        if not hasattr(self, "ledger_tree"):
            return
        for item in self.ledger_tree.get_children():
            self.ledger_tree.delete(item)
        try:
            records = list_issued(self.home)
            query = self.filter_var.get().strip().lower()
            for row in reversed(records):
                if query and query not in (row["order_ref"] + " " + row["license_id"]).lower():
                    continue
                self.ledger_tree.insert("", "end", iid=row["license_id"], values=(
                    row["order_ref"], row["license_id"],
                    row["device_hash"][:12] + "…", row["issued_on"],
                    row["expires_on"] or "Permanente"))
        except Exception as exc:
            self._error(exc)

    def resend_license(self):
        selected = self.ledger_tree.selection()
        if not selected:
            messagebox.showinfo("Selecione uma licença",
                "Selecione uma licença no histórico para reenviar o mesmo arquivo.",
                parent=self)
            return
        lic = selected[0]
        output = filedialog.asksaveasfilename(
            title="Reexportar licença original", initialdir=str(_downloads()),
            initialfile="DUELTRACE-Licenca-" + lic[:8] + ".json",
            defaultextension=".json", filetypes=[("Licença JSON", "*.json")],
            parent=self)
        if not output:
            return
        try:
            resend_issued(self.home, lic, Path(output))
            self.status_var.set("Licença original reexportada; nenhuma nova ativação criada.")
            messagebox.showinfo("Licença reexportada",
                "Envie este arquivo somente ao comprador correspondente.", parent=self)
        except Exception as exc:
            self._error(exc)

    def verify_license(self):
        filename = filedialog.askopenfilename(
            title="Verificar licença assinada",
            initialdir=str(_downloads()), filetypes=[("Licença JSON", "*.json")],
            parent=self)
        if not filename:
            return
        try:
            result = verify_issued(self.home, Path(filename))
            self.status_var.set("Assinatura válida: " + result["licenseId"])
            messagebox.showinfo("Licença validada",
                "Assinatura Ed25519 válida.\nLicença: " + result["licenseId"] +
                "\nValidade: " + (result["expiresOn"] or "Permanente"),
                parent=self)
        except Exception as exc:
            self._error(exc)

    def open_local_folder(self):
        try:
            self.home.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                raise LicenseError("Disponível apenas no Windows.")
            os.startfile(str(self.home))  # Windows Explorer, not a network URL
        except Exception as exc:
            self._error(exc)


def main() -> int:
    if os.name != "nt":
        print("Batoni Dev License Manager: este aplicativo requer Windows.")
        return 1
    app = LicenseManager()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
