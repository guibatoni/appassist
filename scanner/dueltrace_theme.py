"""Identidade visual DUELTRACE: cores, componentes e interações Tkinter.

Implementação nativa para Windows/Tk: sem dependência de tema externo.
Transições discretas de 150-180 ms; visual conceitual inspirado nas telas
aprovadas, sem afirmar que os mockups são componentes executáveis.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

BACKGROUND="#060F20"
SIDEBAR="#07182B"
PANEL="#0B2036"
PANEL_ALT="#102A44"
BORDER="#225874"
BLUE="#26D7FF"
BLUE_DARK="#084868"
GOLD="#EBC176"
GREEN="#36DA9B"
WARNING="#F2AE64"
RED="#FF7985"
TEXT="#ECF7FF"
MUTED="#93B5CC"

def blend(start: str, end: str, ratio: float) -> str:
    ratio=max(0.0,min(1.0,ratio))
    a=tuple(int(start[i:i+2],16) for i in (1,3,5))
    b=tuple(int(end[i:i+2],16) for i in (1,3,5))
    return "#"+"".join(f"{round(x+(y-x)*ratio):02x}" for x,y in zip(a,b))


def setup_theme(root: tk.Misc) -> ttk.Style:
    style=ttk.Style(root)
    style.theme_use("clam")
    style.configure(".",font=("Segoe UI",10),background=BACKGROUND,foreground=TEXT)
    style.configure("DT.TFrame",background=BACKGROUND)
    style.configure("DT.Panel.TFrame",background=PANEL)
    style.configure("DT.TLabel",background=BACKGROUND,foreground=TEXT)
    style.configure("DT.Muted.TLabel",background=BACKGROUND,foreground=MUTED)
    style.configure("DT.Panel.TLabel",background=PANEL,foreground=TEXT)
    style.configure("DT.Heading.TLabel",background=BACKGROUND,foreground=GOLD,
                    font=("Segoe UI Semibold",19))
    style.configure("DT.Treeview",background=PANEL,fieldbackground=PANEL,
                    foreground=TEXT,selectbackground=BLUE_DARK,
                    selectforeground="#FFFFFF",rowheight=30,borderwidth=0)
    style.configure("DT.Treeview.Heading",background=PANEL_ALT,foreground=GOLD,
                    font=("Segoe UI Semibold",10),relief="flat",padding=(9,8))
    style.map("DT.Treeview",background=[("selected",BLUE_DARK)],
              foreground=[("selected",TEXT)])
    style.map("DT.Treeview.Heading",background=[("active",BORDER)])
    style.configure("DT.TEntry",fieldbackground=PANEL_ALT,foreground=TEXT,
                    bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER,padding=7)
    style.configure("DT.TCombobox",fieldbackground=PANEL_ALT,foreground=TEXT,
                    background=PANEL_ALT,arrowcolor=BLUE,padding=6)
    style.map("DT.TCombobox",fieldbackground=[("readonly",PANEL_ALT)],
              foreground=[("readonly",TEXT)])
    style.configure("DT.TCheckbutton",background=PANEL,foreground=TEXT)
    style.map("DT.TCheckbutton",background=[("active",PANEL)])
    style.configure("DT.Horizontal.TProgressbar",background=BLUE,
                    troughcolor=PANEL_ALT,bordercolor=BORDER)
    return style


class NeonButton(tk.Canvas):
    """Botão com hover animado e navegação por teclado."""
    def __init__(self,master,text,command,width=190,height=43,accent=BLUE,
                 active=False,**kwargs):
        super().__init__(master,width=width,height=height,background=SIDEBAR,
                         borderwidth=0,highlightthickness=0,**kwargs)
        self.caption=text
        self.command=command
        self.accent=accent
        self.selected=active
        self.hover=0.0
        self.target=0.0
        self.animation=None
        self.configure(cursor="hand2",takefocus=1)
        self.bind("<Enter>",lambda _e:self._set_target(1.0))
        self.bind("<Leave>",lambda _e:self._set_target(0.0))
        self.bind("<Button-1>",lambda _e:self.command())
        self.bind("<Return>",lambda _e:self.command())
        self.bind("<space>",lambda _e:self.command())
        self.bind("<FocusIn>",lambda _e:self._set_target(1.0))
        self.bind("<FocusOut>",lambda _e:self._set_target(0.0))
        self.bind("<Configure>",lambda _e:self._draw())
        self._draw()

    def set_active(self,value:bool):
        self.selected=bool(value)
        self._draw()

    def _set_target(self,value:float):
        self.target=value
        if self.animation is None:
            self._tick()

    def _tick(self):
        delta=self.target-self.hover
        if abs(delta)<0.025:
            self.hover=self.target
            self.animation=None
        else:
            self.hover+=delta*0.35
            self.animation=self.after(17,self._tick)
        self._draw()

    def _draw(self):
        w=max(60,self.winfo_width());h=max(20,self.winfo_height())
        self.delete("all")
        active=1.0 if self.selected else self.hover*0.65
        bg=blend(SIDEBAR,BLUE_DARK,active)
        stroke=blend(BORDER,self.accent,active)
        self.create_rectangle(2,2,w-3,h-3,fill=bg,outline=stroke,
                              width=2 if self.selected else 1)
        if self.selected:
            self.create_rectangle(4,7,7,h-8,fill=GOLD,outline="")
        self.create_text(w/2,h/2,text=self.caption,fill=TEXT,
                         font=("Segoe UI Semibold",11 if self.selected else 10))


class Panel(tk.Frame):
    def __init__(self,parent,**kwargs):
        super().__init__(parent,background=PANEL,highlightbackground=BORDER,
                         highlightcolor=BLUE,highlightthickness=1,
                         padx=13,pady=12,**kwargs)


def text_label(parent,label,*,color=TEXT,size=10,strong=False,bg=None):
    return tk.Label(parent,text=label,bg=bg or parent.cget("background"),
                    fg=color,font=("Segoe UI Semibold" if strong else "Segoe UI",size),
                    anchor="w",justify="left")


def card_stat(parent,title,value,detail=None):
    panel=Panel(parent)
    text_label(panel,title,color=MUTED,size=10).pack(anchor="w")
    text_label(panel,str(value),color=BLUE,size=21,strong=True).pack(anchor="w",pady=(5,2))
    if detail:text_label(panel,detail,color=MUTED,size=9).pack(anchor="w")
    return panel
