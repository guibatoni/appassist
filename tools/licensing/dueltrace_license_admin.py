"""Batoni Dev — DUELTRACE-style offline License Manager, owner-only.

Modern CustomTkinter shell matches the DUELTRACE palette and navigation.
All signing, purchase checks and file protections remain in admin_core.
No remote calls or customer-facing administration endpoints.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
import customtkinter as ctk

if not getattr(sys,"frozen",False):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scanner"))

from dueltrace_offline_license import LicenseError
from dueltrace_license_admin_core import (
    admin_paths, check_password, create_keys, default_admin_home,
    export_public_key, has_keys, issue_license, list_issued,
    read_request_file, recover_public_key, resend_issued, verify_issued,
    _public_b64,
)

# Exact DUELTRACE theme tokens from web/app/globals.css.
BG="#040a1a"
SURFACE="#081530"
PANEL="#0b1c3d"
BORDER="#1b3f78"
TEXT="#e6f0ff"
MUTED="#8ea3c7"
GOLD="#f5b83d"
CYAN="#38c8ff"
ERROR="#f0444f"
SUCCESS="#2fd27a"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def _downloads() -> Path:
    path=Path.home()/"Downloads"
    return path if path.is_dir() else Path.home()


def _text(parent, value, *, size=13, color=TEXT, bold=False, wrap=None,
          textvariable=None, **kwargs):
    font=ctk.CTkFont(family="Segoe UI",size=size,
                     weight="bold" if bold else "normal")
    options={"text_color":color,"font":font,"anchor":"w","justify":"left"}
    if wrap is not None:
        options["wraplength"]=wrap
    if textvariable is not None:
        options["textvariable"]=textvariable
    else:
        options["text"]=value
    options.update(kwargs)
    return ctk.CTkLabel(parent,**options)


def _btn(parent, label, callback, *, primary=False, width=None):
    options=dict(text=label,command=callback,height=39,corner_radius=9,
                 font=ctk.CTkFont(family="Segoe UI",size=12,weight="bold"),
                 border_width=1)
    if primary:
        options.update(fg_color="#372c1a",hover_color="#55431e",
                       text_color=GOLD,border_color=GOLD)
    else:
        options.update(fg_color=PANEL,hover_color="#12365b",
                       text_color=TEXT,border_color=BORDER)
    if width is not None:
        options["width"]=width
    return ctk.CTkButton(parent,**options)


def _modal(parent, title: str, body: str, kind="info") -> str | bool | None:
    """DUELTRACE-styled native modal; no passwords written to disk/logs."""
    window=ctk.CTkToplevel(parent)
    window.title(title)
    window.configure(fg_color=BG)
    window.resizable(False,False)
    window.transient(parent)
    window.overrideredirect(True)
    width,height=(490,300) if kind=="password" else (500,260)
    px=parent.winfo_rootx()+max(0,(parent.winfo_width()-width)//2)
    py=parent.winfo_rooty()+max(0,(parent.winfo_height()-height)//2)
    window.geometry(f"{width}x{height}+{px}+{py}")
    result={"value":None}
    outer=ctk.CTkFrame(window,fg_color=SURFACE,corner_radius=16,
                       border_width=2,border_color=GOLD if kind=="confirm" else BORDER)
    outer.pack(fill="both",expand=True,padx=2,pady=2)
    heading=ctk.CTkFrame(outer,fg_color="transparent")
    heading.pack(fill="x",padx=22,pady=(19,8))
    _text(heading,"◆",size=17,color=GOLD).pack(side="left",padx=(0,10))
    _text(heading,title,size=17,color=TEXT,bold=True).pack(side="left")
    _text(outer,body,size=12,color=MUTED,wrap=438).pack(
        fill="x",padx=23,pady=(5,13))
    secret=None
    if kind=="password":
        secret=ctk.CTkEntry(outer,show="*",height=41,corner_radius=9,
                            fg_color=BG,border_color=BORDER,text_color=TEXT,
                            font=ctk.CTkFont(family="Segoe UI",size=14))
        secret.pack(fill="x",padx=23,pady=(1,14))
    bar=ctk.CTkFrame(outer,fg_color="transparent")
    bar.pack(side="bottom",fill="x",padx=22,pady=(3,19))
    def finish(value):
        result["value"]=value
        window.grab_release()
        window.destroy()
    if kind in ("confirm","password"):
        _btn(bar,"Cancelar",lambda:finish(None if kind=="password" else False),
             width=115).pack(side="right",padx=(8,0))
        _btn(bar,"Confirmar",lambda:finish(secret.get() if secret else True),
             primary=True,width=130).pack(side="right")
        window.bind("<Return>",lambda _e:finish(secret.get() if secret else True))
    else:
        _btn(bar,"Entendido",lambda:finish(True),primary=True,width=140).pack(side="right")
        window.bind("<Return>",lambda _e:finish(True))
    window.bind("<Escape>",lambda _e:finish(None if kind=="password" else False))
    window.after(50,lambda:secret.focus_set() if secret else window.focus_force())
    window.grab_set()
    parent.wait_window(window)
    return result["value"]


class _BrandDialogs:
    """Drop-in wrappers keep the original core operations untouched."""
    @staticmethod
    def showerror(title,body,*,parent):
        return _modal(parent,title,body,"error")

    @staticmethod
    def showinfo(title,body,*,parent):
        return _modal(parent,title,body,"info")

    @staticmethod
    def showwarning(title,body,*,parent):
        return _modal(parent,title,body,"warning")

    @staticmethod
    def askyesno(title,body,*,parent):
        return _modal(parent,title,body,"confirm") is True


messagebox=_BrandDialogs()


class LicenseManager(ctk.CTk):
    """Frameless desktop shell with DUELTRACE visual identity."""
    def __init__(self, *, home: Path | None = None):
        super().__init__()
        self.home=home if home is not None else default_admin_home()
        self.current_request: dict | None=None
        self.current_request_path: Path | None=None
        self.order_var=tk.StringVar()
        self.expiry_var=tk.StringVar()
        self.confirmed_var=tk.BooleanVar(value=False)
        self.filter_var=tk.StringVar()
        self.status_var=tk.StringVar(value="Pronto para gerenciar licenças offline.")
        self.key_status_var=tk.StringVar(value="Verificando chaves...")
        self.request_var=tk.StringVar(value="Nenhum pedido selecionado.")
        self.total_var=tk.StringVar(value="0")
        self.device_total_var=tk.StringVar(value="0")
        self.title("Batoni Dev — DUELTRACE License Manager")
        self.geometry("1180x780")
        self.minsize(950,670)
        self.configure(fg_color=BG)
        self._maximized=False
        self._minimizing=False
        self._prior_geometry=None
        self._drag_anchor=None
        self._current_page=None
        self._build_widgets()
        self._style_tree()
        self.filter_var.trace_add("write",lambda *_:self.refresh_history())
        self.refresh_keys()
        self.refresh_history()
        if os.name=="nt":
            self.after(100,self._activate_frameless)

    def _activate_frameless(self):
        try:
            self.overrideredirect(True)
        except tk.TclError:
            pass

    def _restore_caption_after_minimize(self,event=None):
        if self._minimizing and os.name=="nt":
            self._minimizing=False
            self.after(70,self._activate_frameless)

    def _minimize_window(self):
        if os.name=="nt":
            self._minimizing=True
            self.overrideredirect(False)
            self.iconify()
            self.bind("<Map>",self._restore_caption_after_minimize,add="+")
        else:
            self.iconify()

    def _work_area(self):
        if os.name=="nt":
            try:
                import ctypes
                class RECT(ctypes.Structure):
                    _fields_=[("left",ctypes.c_long),("top",ctypes.c_long),
                              ("right",ctypes.c_long),("bottom",ctypes.c_long)]
                rect=RECT()
                if ctypes.windll.user32.SystemParametersInfoW(48,0,
                        ctypes.byref(rect),0):
                    return (rect.left,rect.top,
                            rect.right-rect.left,rect.bottom-rect.top)
            except (OSError,AttributeError):
                pass
        return (0,0,self.winfo_screenwidth(),self.winfo_screenheight())

    def _toggle_maximize(self):
        if self._maximized:
            if self._prior_geometry:
                self.geometry(self._prior_geometry)
            self._maximized=False
            self.max_button.configure(text="□")
        else:
            self._prior_geometry=self.geometry()
            x,y,w,h=self._work_area()
            self.geometry(f"{w}x{h}+{x}+{y}")
            self._maximized=True
            self.max_button.configure(text="❐")

    def _drag_begin(self,event):
        if not self._maximized:
            self._drag_anchor=(event.x_root-self.winfo_x(),
                               event.y_root-self.winfo_y())

    def _drag_move(self,event):
        if self._drag_anchor is not None and not self._maximized:
            x=event.x_root-self._drag_anchor[0]
            y=event.y_root-self._drag_anchor[1]
            self.geometry(f"+{x}+{y}")

    def _drag_end(self,event=None):
        self._drag_anchor=None

    def _bind_drag(self,widget):
        for item in (widget,):
            item.bind("<ButtonPress-1>",self._drag_begin)
            item.bind("<B1-Motion>",self._drag_move)
            item.bind("<ButtonRelease-1>",self._drag_end)
            item.bind("<Double-Button-1>",lambda _e:self._toggle_maximize())

    def _style_tree(self):
        style=ttk.Style(self)
        style.theme_use("clam")
        style.configure("Admin.Treeview",background=SURFACE,
                        foreground=TEXT,fieldbackground=SURFACE,
                        borderwidth=0,relief="flat",rowheight=33,
                        font=("Segoe UI",10))
        style.configure("Admin.Treeview.Heading",background=PANEL,
                        foreground=CYAN,borderwidth=0,
                        font=("Segoe UI Semibold",10))
        style.map("Admin.Treeview",
                  background=[("selected","#164b72")],
                  foreground=[("selected",TEXT)])
        style.map("Admin.Treeview.Heading",
                  background=[("active","#112d4f")])
        self.ledger_tree.configure(style="Admin.Treeview")

    def _build_widgets(self):
        shell=ctk.CTkFrame(self,fg_color=BG,corner_radius=18,
                           border_width=1,border_color=GOLD)
        shell.pack(fill="both",expand=True,padx=13,pady=13)
        self.shell=shell
        self._build_titlebar(shell)
        body=ctk.CTkFrame(shell,fg_color="transparent")
        body.pack(fill="both",expand=True,padx=13,pady=(13,8))
        body.grid_columnconfigure(1,weight=1)
        body.grid_rowconfigure(0,weight=1)
        self.sidebar=ctk.CTkFrame(body,width=235,fg_color=SURFACE,
                                  border_color=BORDER,border_width=1,
                                  corner_radius=14)
        self.sidebar.grid(row=0,column=0,sticky="ns",padx=(0,13))
        self.sidebar.grid_propagate(False)
        self._build_sidebar(self.sidebar)
        self.content=ctk.CTkFrame(body,fg_color="#061129",
                                  border_color=BORDER,border_width=1,
                                  corner_radius=14)
        self.content.grid(row=0,column=1,sticky="nsew")
        self.content.grid_rowconfigure(0,weight=1)
        self.content.grid_columnconfigure(0,weight=1)
        self.issue_tab=ctk.CTkScrollableFrame(self.content,fg_color="transparent",
                         scrollbar_button_color="#315f89",
                         scrollbar_button_hover_color=CYAN)
        self.history_tab=ctk.CTkFrame(self.content,fg_color="transparent")
        self.security_tab=ctk.CTkScrollableFrame(self.content,fg_color="transparent",
                         scrollbar_button_color="#315f89",
                         scrollbar_button_hover_color=CYAN)
        self.pages={"issue":self.issue_tab,"history":self.history_tab,
                    "security":self.security_tab}
        self.nav_buttons={}
        # Sidebar buttons are added after page definitions for reliable selection.
        self._create_navigation()
        self._build_issue()
        self._build_history()
        self._build_security()
        self._show_page("issue")
        status=ctk.CTkFrame(shell,fg_color=SURFACE,corner_radius=9,height=35)
        status.pack(fill="x",padx=14,pady=(0,12))
        _text(status,"●",size=12,color=SUCCESS).pack(side="left",padx=(11,7))
        _text(status,"LOCAL / OFFLINE",size=10,color=CYAN,bold=True).pack(side="left")
        _text(status,"  •  ",size=12,color=MUTED).pack(side="left")
        _text(status,"",size=11,color=MUTED,textvariable=self.status_var,
              wrap=810).pack(side="left",fill="x",expand=True,padx=(0,10))

    def _build_titlebar(self,shell):
        header=ctk.CTkFrame(shell,fg_color="#040b1f",corner_radius=13,height=88)
        header.pack(fill="x",padx=2,pady=2)
        header.pack_propagate(False)
        canvas=tk.Canvas(header,width=67,height=65,bg="#040b1f",
                         highlightthickness=0,borderwidth=0)
        canvas.pack(side="left",padx=(23,11),pady=10)
        canvas.create_polygon(5,7,61,7,33,57,outline=CYAN,fill="",
                              width=3,smooth=False)
        canvas.create_polygon(17,15,49,15,33,43,outline="#1a8fe0",fill="",
                              width=2,smooth=False)
        branding=ctk.CTkFrame(header,fg_color="transparent")
        branding.pack(side="left",fill="y",pady=10)
        name=_text(branding,"DUELTRACE",size=26,color=TEXT,bold=True)
        name.pack(anchor="w")
        _text(branding,"BATONI DEV  ·  LICENSE MANAGER",size=11,
              color=GOLD,bold=True).pack(anchor="w",pady=(0,2))
        self._bind_drag(header)
        self._bind_drag(canvas)
        self._bind_drag(branding)
        self._bind_drag(name)
        controls=ctk.CTkFrame(header,fg_color="transparent")
        controls.pack(side="right",padx=(10,15),pady=12)
        for label,callback,hover in (
            ("—",self._minimize_window,"#13365b"),
            ("□",self._toggle_maximize,"#13365b"),
            ("×",self.destroy,"#6b2031"),
        ):
            button=ctk.CTkButton(controls,text=label,command=callback,
                        width=37,height=34,corner_radius=8,
                        fg_color="transparent",hover_color=hover,
                        text_color=TEXT,font=ctk.CTkFont(size=20))
            button.pack(side="left",padx=2)
            if label=="□":self.max_button=button
        badge=ctk.CTkFrame(header,fg_color="#0c2b31",border_color="#255f65",
                           border_width=1,corner_radius=11)
        badge.pack(side="right",padx=12,pady=19)
        _text(badge,"●  GERENCIADOR OFFLINE",size=11,color=SUCCESS,
              bold=True).pack(padx=12,pady=8)
        sep=ctk.CTkFrame(shell,height=2,fg_color="#22415d",corner_radius=0)
        sep.pack(fill="x",padx=15)

    def _build_sidebar(self,side):
        _text(side,"PAINEL BATONI DEV",size=11,color=MUTED,bold=True).pack(
            anchor="w",padx=18,pady=(23,11))
        _text(side,"Licenciamento",size=17,color=TEXT,bold=True).pack(
            anchor="w",padx=18)
        _text(side,"DUELTRACE Commercial Lite",size=10,color=MUTED).pack(
            anchor="w",padx=18,pady=(2,20))
        self.nav_holder=ctk.CTkFrame(side,fg_color="transparent")
        self.nav_holder.pack(fill="x",padx=10)
        filler=ctk.CTkFrame(side,fg_color="transparent")
        filler.pack(fill="both",expand=True)
        notice=ctk.CTkFrame(side,fg_color="#081f35",
                            border_color="#1b4164",border_width=1,corner_radius=11)
        notice.pack(fill="x",padx=12,pady=(0,15))
        _text(notice,"◆  ASSINATURA ED25519",size=11,color=CYAN,
              bold=True).pack(anchor="w",padx=13,pady=(13,5))
        _text(notice,"Chaves guardadas somente no seu computador. "
              "Nenhuma validação por IP.",size=11,color=MUTED,
              wrap=180).pack(anchor="w",padx=13,pady=(0,13))

    def _create_navigation(self):
        for name,label in (
            ("issue","◇   Emitir licença"),
            ("history","▤   Licenças emitidas"),
            ("security","♢   Chaves e segurança"),
        ):
            button=ctk.CTkButton(self.nav_holder,text=label,
                     height=43,corner_radius=9,
                     font=ctk.CTkFont(family="Segoe UI",size=13,weight="bold"),
                     anchor="w",command=lambda item=name:self._show_page(item))
            button.pack(fill="x",pady=4)
            self.nav_buttons[name]=button

    def _show_page(self,name):
        if name not in self.pages:return
        for key,page in self.pages.items():
            page.grid_forget()
            button=self.nav_buttons[key]
            selected=key==name
            button.configure(
                fg_color="#15365b" if selected else "transparent",
                hover_color="#15365b",text_color=CYAN if selected else MUTED,
                border_width=1 if selected else 0,
                border_color=CYAN if selected else BORDER)
        self.pages[name].grid(row=0,column=0,sticky="nsew",padx=14,pady=14)
        self._current_page=name

    def _page_intro(self,frame,title,subtitle):
        _text(frame,title,size=24,color=TEXT,bold=True).pack(
            anchor="w",padx=8,pady=(10,2))
        _text(frame,subtitle,size=12,color=MUTED,wrap=720).pack(
            anchor="w",padx=8,pady=(0,18))

    def _card(self,parent,*,title,description):
        card=ctk.CTkFrame(parent,fg_color=SURFACE,corner_radius=13,
                          border_width=1,border_color=BORDER)
        card.pack(fill="x",padx=8,pady=(0,14))
        head=ctk.CTkFrame(card,fg_color="transparent")
        head.pack(fill="x",padx=20,pady=(16,4))
        _text(head,title,size=15,color=GOLD,bold=True).pack(anchor="w")
        _text(card,description,size=12,color=MUTED,wrap=710).pack(
            anchor="w",fill="x",padx=20,pady=(0,15))
        return card

    def _build_issue(self):
        parent=self.issue_tab
        self._page_intro(parent,"Emitir licença","Processo seguro em três etapas, "
                         "sem servidores ou configurações técnicas.")
        c=self._card(parent,title="01  ·  Importar pedido",
                     description="Selecione o pedido JSON recebido do comprador.")
        row=ctk.CTkFrame(c,fg_color="transparent")
        row.pack(fill="x",padx=20,pady=(0,19))
        _btn(row,"Selecionar pedido (.json)",self.select_request).pack(side="left")
        _text(row,"",size=11,color=CYAN,textvariable=self.request_var,
              wrap=325).pack(side="left",fill="x",expand=True,padx=(14,0))
        c=self._card(parent,title="02  ·  Confirmar compra",
                     description="Informe o identificador de venda. "
                     "O aplicativo não consulta Patreon automaticamente.")
        fields=ctk.CTkFrame(c,fg_color="transparent")
        fields.pack(fill="x",padx=20,pady=(0,7))
        left=ctk.CTkFrame(fields,fg_color="transparent")
        left.pack(side="left",fill="x",expand=True,padx=(0,12))
        right=ctk.CTkFrame(fields,fg_color="transparent")
        right.pack(side="left",fill="x",expand=True)
        _text(left,"ID DA COMPRA",size=10,color=CYAN,bold=True).pack(anchor="w")
        ctk.CTkEntry(left,textvariable=self.order_var,height=40,corner_radius=8,
                     placeholder_text="PATREON-0001",fg_color=BG,
                     border_color=BORDER,text_color=TEXT).pack(fill="x",pady=(6,0))
        _text(right,"VALIDADE (OPCIONAL)",size=10,color=CYAN,bold=True).pack(anchor="w")
        ctk.CTkEntry(right,textvariable=self.expiry_var,height=40,
                     corner_radius=8,placeholder_text="AAAA-MM-DD",
                     fg_color=BG,border_color=BORDER,text_color=TEXT).pack(
                     fill="x",pady=(6,0))
        ctk.CTkCheckBox(c,text="Pagamento conferido e confirmado",
                variable=self.confirmed_var,fg_color="#a47d31",
                hover_color=GOLD,border_color=BORDER,text_color=TEXT,
                font=ctk.CTkFont(size=12)).pack(anchor="w",padx=20,pady=(8,19))
        c=self._card(parent,title="03  ·  Assinar e emitir",
                     description="A assinatura é criada com a sua chave privada "
                     "criptografada. Envie ao comprador apenas o arquivo JSON.")
        _btn(c,"◆   Emitir licença assinada",self.emit_license,
             primary=True).pack(anchor="w",padx=20,pady=(0,17))
        _text(parent,"Máximo de dois computadores por compra. "
              "O histórico e a chave privada permanecem locais.",
              size=11,color=MUTED,wrap=720).pack(anchor="w",padx=15,pady=(0,16))

    def _build_history(self):
        parent=self.history_tab
        self._page_intro(parent,"Licenças emitidas",
            "Pesquise compras e reenvie licenças existentes sem gastar outra ativação.")
        metrics=ctk.CTkFrame(parent,fg_color="transparent")
        metrics.pack(fill="x",padx=8,pady=(0,15))
        for label,var in (("LICENÇAS EMITIDAS",self.total_var),
                          ("COMPUTADORES",self.device_total_var)):
            card=ctk.CTkFrame(metrics,fg_color=SURFACE,
                corner_radius=11,border_color=BORDER,border_width=1)
            card.pack(side="left",fill="x",expand=True,padx=(0,12))
            _text(card,label,size=11,color=MUTED,bold=True).pack(
                anchor="w",padx=18,pady=(15,3))
            _text(card,"",size=25,color=GOLD,bold=True,
                  textvariable=var).pack(anchor="w",padx=18,pady=(0,16))
        search=ctk.CTkFrame(parent,fg_color=SURFACE,
                            corner_radius=11,border_width=1,border_color=BORDER)
        search.pack(fill="x",padx=8,pady=(0,14))
        _text(search,"PESQUISAR POR COMPRA OU LICENÇA",size=10,
              color=CYAN,bold=True).pack(anchor="w",padx=15,pady=(12,5))
        searchline=ctk.CTkFrame(search,fg_color="transparent")
        searchline.pack(fill="x",padx=15,pady=(0,13))
        ctk.CTkEntry(searchline,textvariable=self.filter_var,height=40,
                corner_radius=8,placeholder_text="Nome da compra ou ID",
                fg_color=BG,border_color=BORDER,
                text_color=TEXT).pack(side="left",fill="x",expand=True,padx=(0,9))
        _btn(searchline,"Atualizar",self.refresh_history,width=105).pack(side="right")
        table_frame=ctk.CTkFrame(parent,fg_color=SURFACE,corner_radius=12,
                border_width=1,border_color=BORDER)
        table_frame.pack(fill="both",expand=True,padx=8,pady=(0,12))
        columns=("order_ref","license_id","device","issued_on","expires_on")
        self.ledger_tree=ttk.Treeview(table_frame,columns=columns,show="headings",
                           height=11,selectmode="browse")
        for name,label,width in (
            ("order_ref","Compra",128),
            ("license_id","ID da licença",265),
            ("device","Dispositivo",122),
            ("issued_on","Emissão",96),
            ("expires_on","Validade",107),
        ):
            self.ledger_tree.heading(name,text=label)
            self.ledger_tree.column(name,width=width,minwidth=70,
                                    stretch=name=="license_id")
        self.ledger_tree.pack(side="left",fill="both",expand=True,padx=(12,0),pady=13)
        scroll=ctk.CTkScrollbar(table_frame,orientation="vertical",
                command=self.ledger_tree.yview,
                button_color="#315f89",button_hover_color=CYAN)
        scroll.pack(side="right",fill="y",padx=(1,9),pady=14)
        self.ledger_tree.configure(yscrollcommand=scroll.set)
        _btn(parent,"◇   Reenviar licença selecionada",self.resend_license,
             primary=True).pack(anchor="w",padx=8,pady=(0,15))

    def _build_security(self):
        parent=self.security_tab
        self._page_intro(parent,"Chaves e segurança",
             "Gerencie sua assinatura digital sem expor a chave privada.")
        card=self._card(parent,title="◆  Identidade de assinatura",
               description="Sua chave privada Ed25519 fica criptografada e "
               "armazenada somente neste computador.")
        _text(card,"",size=12,color=CYAN,wrap=680,
              textvariable=self.key_status_var).pack(
              fill="x",anchor="w",padx=20,pady=(0,12))
        row=ctk.CTkFrame(card,fg_color="transparent")
        row.pack(fill="x",padx=19,pady=(0,18))
        _btn(row,"Criar chaves",self.setup_keys,primary=True).pack(
             side="left",padx=(0,9))
        _btn(row,"Exportar chave pública",self.export_public).pack(
             side="left",padx=(0,9))
        _btn(row,"Recuperar chave pública",self.recover_public).pack(side="left")
        card=self._card(parent,title="◇  Verificar autenticidade",
               description="Confira localmente se uma licença foi realmente "
               "assinada com a chave correspondente.")
        _btn(card,"Validar licença (.json)",self.verify_license).pack(
             anchor="w",padx=19,pady=(0,17))
        card=self._card(parent,title="▣  Dados armazenados no Windows",
               description="A pasta contém seu histórico, chave privada "
               "criptografada e arquivos emitidos. Nunca a envie ao GitHub.")
        _text(card,str(self.home),size=11,color=CYAN,wrap=680).pack(
              anchor="w",padx=19,pady=(0,12))
        _btn(card,"Abrir pasta local",self.open_local_folder).pack(
             anchor="w",padx=19,pady=(0,17))
        note=ctk.CTkFrame(parent,fg_color="#211c19",corner_radius=11,
                          border_width=1,border_color="#775d30")
        note.pack(fill="x",padx=8,pady=(0,13))
        _text(note,"◆  IMPORTANTE PARA A BATONI DEV",size=12,
              color=GOLD,bold=True).pack(anchor="w",padx=17,pady=(14,6))
        _text(note,"Faça backup criptografado da chave privada e guarde a "
              "senha separadamente. Só a chave pública é exportável. "
              "Este gerenciador não se conecta ao Patreon nem cria "
              "licenças automaticamente após uma venda.",
              size=12,color=MUTED,wrap=700).pack(
              anchor="w",padx=17,pady=(0,16))

    def _error(self, exc: Exception) -> None:
        detail = str(exc) if isinstance(exc, (LicenseError, OSError, ValueError)) else (
            "Falha inesperada. Verifique os arquivos e permissões locais.")
        self.status_var.set("Operação não realizada: " + detail)
        messagebox.showerror("Batoni Dev — Operação não concluída", detail, parent=self)

    def _password(self, title: str) -> str | None:
        result=_modal(self,title,"Informe sua senha privada da Batoni Dev.",
                      kind="password")
        return result if isinstance(result,str) else None

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
            self.total_var.set(str(len(records)))
            self.device_total_var.set(str(len(
                {row["device_hash"] for row in records})))
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
