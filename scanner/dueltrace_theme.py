"""Identidade visual DUELTRACE: cores, componentes e interações Tkinter.

Implementação nativa para Windows/Tk: sem dependência de tema externo.
Transições discretas de 150-180 ms; visual conceitual inspirado nas telas
aprovadas, sem afirmar que os mockups são componentes executáveis.
"""
from __future__ import annotations

import tkinter as tk
import math
from tkinter import ttk

BACKGROUND="#040B18"
SIDEBAR="#071427"
PANEL="#09213A"
PANEL_ALT="#123856"
BORDER="#1A5C7F"
BLUE="#20D8FF"
BLUE_DARK="#075679"
GOLD="#F3C373"
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
                    selectforeground="#FFFFFF",rowheight=34,borderwidth=0)
    style.configure("DT.Treeview.Heading",background=PANEL_ALT,foreground=GOLD,
                    font=("Segoe UI Semibold",10),relief="flat",padding=(11,10))
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
    """Botão premium com gradiente, bordas luminosas, hover e foco acessível.

    Tk nativo mantém toda a navegação por teclado. Os desenhos são estáticos
    entre transições e não criam threads ou timers periódicos.
    """
    def __init__(self, master, text, command, width=190, height=43, accent=BLUE,
                 active=False, **kwargs):
        bg = master.cget("background")
        super().__init__(master, width=width, height=height, background=bg,
                         borderwidth=0, highlightthickness=0, **kwargs)
        self.caption = text
        self.command = command
        self.accent = accent
        self.selected = bool(active)
        self.hover = 0.0
        self.target = 0.0
        self.animation = None
        self.focused = False
        self.configure(cursor="hand2", takefocus=1)
        self.bind("<Enter>", lambda _: self._set_target(1.0))
        self.bind("<Leave>", lambda _: self._set_target(0.0))
        self.bind("<FocusIn>", self._focus_in)
        self.bind("<FocusOut>", self._focus_out)
        self.bind("<Button-1>", lambda _: self.command())
        self.bind("<Return>", lambda _: self.command())
        self.bind("<space>", lambda _: self.command())
        self.bind("<Configure>", lambda _: self._draw())
        self.bind("<Destroy>", self._cleanup)
        self._draw()

    def _cleanup(self, _event):
        if self.animation is not None:
            try:
                self.after_cancel(self.animation)
            except tk.TclError:
                pass
            self.animation = None

    def _focus_in(self, _event):
        self.focused = True
        self._set_target(1.0)

    def _focus_out(self, _event):
        self.focused = False
        self._set_target(0.0)

    def set_active(self, value: bool):
        self.selected = bool(value)
        self._draw()

    def _set_target(self, value: float):
        self.target = value
        if self.animation is None:
            self._tick()

    def _tick(self):
        delta = self.target - self.hover
        if abs(delta) < 0.025:
            self.hover = self.target
            self.animation = None
        else:
            self.hover += delta * 0.35
            self.animation = self.after(17, self._tick)
        self._draw()

    def _draw(self):
        self.delete("all")
        w = max(60, self.winfo_width())
        h = max(20, self.winfo_height())
        illuminated = max(self.hover, 0.9 if self.selected else 0.0)
        border = blend(BORDER, self.accent, 0.5 + illuminated * 0.5)
        # Bordas realmente arredondadas por raio em cada linha do gradiente.
        radius=min(12,h//3)
        x0,y0,x1,y1=4,4,w-5,h-5
        for y in range(y0,y1+1,2):
            t=(y-y0)/max(1,y1-y0)
            dist=min(y-y0,y1-y)
            inset=0 if dist>=radius else radius-math.sqrt(max(0,radius*radius-(radius-dist)**2))
            tone=blend(blend(PANEL_ALT,BLUE_DARK,illuminated*.75),
                       blend("#071326",PANEL,illuminated*.20),t)
            self.create_line(x0+inset,y,x1-inset,y,fill=tone,width=2)
        self.create_line(x0+radius,y0,x1-radius,y0,
                         fill=blend(BLUE,self.accent,illuminated),width=2)
        self.create_line(x0+radius,y1,x1-radius,y1,fill=border,width=2)
        self.create_line(x0,y0+radius,x0,y1-radius,fill=border,width=2)
        self.create_line(x1,y0+radius,x1,y1-radius,fill=border,width=2)
        for box,start in (
            ((x0,y0,x0+2*radius,y0+2*radius),90),
            ((x1-2*radius,y0,x1,y0+2*radius),0),
            ((x0,y1-2*radius,x0+2*radius,y1),180),
            ((x1-2*radius,y1-2*radius,x1,y1),270),
        ):
            self.create_arc(*box,start=start,extent=90,style="arc",outline=border,width=2)
        self.create_line(13,y0+4,w-13,y0+4,
                         fill=blend(BLUE,self.accent,illuminated*.8),width=1)
        if self.selected:
            self.create_rectangle(5, 12, 8, h-13,fill=GOLD,outline="")
        if illuminated>0.05:
            self.create_line(16,7,w-16,7,
                             fill=blend(BORDER,self.accent,illuminated),width=1)
        self.create_text(w/2,h/2,text=self.caption,fill=TEXT,
                         width=w-20,
                         font=("Segoe UI Semibold",10 if not self.selected else 11))
        if self.focused:
            self.create_rectangle(10,8,w-11,h-9,outline=GOLD,dash=(2,3))


class Panel(tk.Frame):
    """Painel com textura gradiente e acabamento metálico, preservando a API pack.

    O Canvas é apenas um plano de fundo abaixo dos widgets: todos os controles
    existentes permanecem Tk nativos, acessíveis e funcionais.
    """
    def __init__(self,parent,**kwargs):
        parent_bg=parent.cget("background")
        super().__init__(parent,background=parent_bg,highlightthickness=0,
                         padx=13,pady=12,**kwargs)
        self._skin = tk.Canvas(self, background=parent_bg, highlightthickness=0,
                               borderwidth=0, takefocus=0)
        self._skin.place(x=0,y=0,relwidth=1,relheight=1)
        # Canvas.lower() manipula itens internos; chamar 'lower' do Tk
        # diretamente mantém a decoração atrás dos controles.
        self.tk.call("lower", str(self._skin))
        self._skin.bind("<Configure>", self._paint)

    def _paint(self, event):
        c = self._skin
        w, h = event.width, event.height
        if w < 5 or h < 5:
            return
        c.delete("all")
        radius=min(17,h//5,w//6)
        x0,y0,x1,y1=2,2,w-3,h-3
        for y in range(y0,y1+1,3):
            t=y/max(h-1,1)
            color=blend(blend(PANEL_ALT,PANEL,.48),PANEL,min(1,t*.85))
            dist=min(y-y0,y1-y)
            inset=0 if dist>=radius else radius-math.sqrt(max(0,radius*radius-(radius-dist)**2))
            c.create_line(x0+inset,y,x1-inset,y,fill=color,width=3)
        c.create_line(x0+radius,y0,x1-radius,y0,fill=blend(GOLD,BLUE,.55),width=2)
        c.create_line(x0+radius,y1,x1-radius,y1,fill=GOLD,width=2)
        c.create_line(x0,y0+radius,x0,y1-radius,fill=blend(GOLD,BLUE,.35),width=1)
        c.create_line(x1,y0+radius,x1,y1-radius,fill=BLUE_DARK,width=1)
        for box,start in (
            ((x0,y0,x0+2*radius,y0+2*radius),90),
            ((x1-2*radius,y0,x1,y0+2*radius),0),
            ((x0,y1-2*radius,x0+2*radius,y1),180),
            ((x1-2*radius,y1-2*radius,x1,y1),270),
        ):
            c.create_arc(*box,start=start,extent=90,style="arc",outline=GOLD,width=1)
        c.create_line(8,5,30,5,fill=GOLD,width=2)
        c.create_line(w-30,5,w-8,5,fill=BLUE,width=2)


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
