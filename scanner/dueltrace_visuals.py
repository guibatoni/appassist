"""Componentes visuais originais para o DUELTRACE Desktop.

Arte vetorial desenhada em Tk Canvas: sem cartas/ilustrações comerciais,
sem dados fictícios, arquivos externos ou dependências adicionais.
Os contadores e estados vêm exclusivamente do perfil real do scanner.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from dueltrace_theme import (
    BACKGROUND, SIDEBAR, PANEL, PANEL_ALT, BORDER,
    BLUE, GOLD, GREEN, RED, TEXT, MUTED, blend, text_label,
)

CATEGORY_COLORS = {
    "Monstros": BLUE,
    "Mágicas": "#38D8AE",
    "Rituais": "#9289FF",
    "Armadilhas": "#F087D5",
    "Equipamentos": GOLD,
    "Não identificado": MUTED,
}

CATEGORY_SYMBOLS = {
    "Monstros": "◇", "Mágicas": "✦", "Rituais": "◎",
    "Armadilhas": "⌑", "Equipamentos": "⬡", "Não identificado": "?",
}

NAV_SYMBOLS = {
    "inicio": "⌂", "mods": "⬡", "cartas": "▣",
    "fusoes": "◎", "overlay": "▤", "diagnostico": "▥", "configuracoes": "⚙",
}


def category_color(category: str) -> str:
    return CATEGORY_COLORS.get(category, MUTED)


def mini_label(parent, caption: str, *, color=BLUE):
    return text_label(parent, caption, color=color, size=10, strong=True)


class QuickTile(tk.Canvas):
    """Atalho acessível por clique e teclado, com realce progressivo."""
    def __init__(self, parent, caption, subtitle, symbol, action, *,
                 accent=BLUE, width=165, height=108):
        super().__init__(parent, width=width, height=height, bd=0,
                         highlightthickness=0, bg=BACKGROUND, cursor="hand2",
                         takefocus=1)
        self.caption, self.subtitle, self.symbol = caption, subtitle, symbol
        self.action, self.accent = action, accent
        self._hover = 0.0
        self._target = 0.0
        self._after = None
        self.bind("<Enter>", lambda _: self._target_hover(1.0))
        self.bind("<Leave>", lambda _: self._target_hover(0.0))
        self.bind("<FocusIn>", lambda _: self._target_hover(1.0))
        self.bind("<FocusOut>", lambda _: self._target_hover(0.0))
        self.bind("<Button-1>", lambda _: self.action())
        self.bind("<Return>", lambda _: self.action())
        self.bind("<space>", lambda _: self.action())
        self.bind("<Configure>", lambda _: self._draw())
        self._draw()

    def _target_hover(self, target):
        self._target = target
        if self._after is None:
            self._animate()

    def _animate(self):
        self._hover += (self._target - self._hover) * 0.38
        self._draw()
        if abs(self._target - self._hover) > 0.025:
            self._after = self.after(17, self._animate)
        else:
            self._hover = self._target
            self._after = None

    def _draw(self):
        self.delete("all")
        w,h = max(self.winfo_width(),80),max(self.winfo_height(),80)
        accent = self.accent
        hover = self._hover
        self.create_rectangle(1,1,w-2,h-2,
                              outline=blend(BORDER,accent,.4+hover*.55),width=2)
        for y in range(4,h-4,3):
            t=(y-4)/max(1,h-8)
            base=blend(blend(PANEL_ALT,accent,hover*.13),BACKGROUND,t*.80)
            self.create_line(4,y,w-5,y,fill=base,width=3)
        self.create_line(12,5,w-12,5,fill=blend(BLUE,accent,.5+hover*.5),width=2)
        self.create_line(11,h-7,w-11,h-7,fill=blend(BORDER,accent,.6+hover*.4),width=2)
        self.create_line(6,13,6,h-12,fill=blend(BORDER,accent,hover),width=1)
        self.create_line(w-7,13,w-7,h-12,fill=blend(BORDER,accent,hover),width=1)
        self.create_text(w/2,26,text=self.symbol,fill=accent,
                         font=("Segoe UI Symbol",26))
        self.create_text(w/2,62,text=self.caption,fill=TEXT,
                         width=w-12,font=("Segoe UI Semibold",10))
        self.create_text(w/2,87,text=self.subtitle,fill=MUTED,
                         width=w-12,font=("Segoe UI",8))


class HeroArt(tk.Canvas):
    """Cena premium original: pirâmide, horizonte, órbitas e cartas holográficas.

    Arte independente das ilustrações do jogo; não representa cartas reais.
    Ajusta-se de 190 px (lateral) até o banner da página inicial.
    """
    def __init__(self,parent,*,width=350,height=190):
        super().__init__(parent,width=width,height=height,bd=0,
                         highlightthickness=0,bg=PANEL)
        self.bind("<Configure>",lambda _:self._draw())
        self._draw()

    def _draw(self):
        self.delete("all")
        w=max(110,self.winfo_width())
        h=max(105,self.winfo_height())
        scale=min(w/350,h/190)
        accent_top="#0A3154"
        for y in range(0,h,3):
            t=y/max(1,h-1)
            shade=blend(accent_top,"#031224",min(1,t*.94))
            self.create_rectangle(0,y,w,y+3,outline=shade,fill=shade)
        cx=w*.52
        horizon=h*.76
        # Arquitetura antiga abstrata no horizonte.
        for side in (-1,1):
            x=cx+side*w*.36
            self.create_polygon(x-30*scale,horizon,x,h*.27,
                                x+30*scale,horizon,
                                fill=blend(PANEL,GOLD,.12),
                                outline=blend(BORDER,GOLD,.32),width=1)
        # Pirâmide e linhas luminosas.
        self.create_polygon(cx-100*scale,horizon,cx,h*.05,
                            cx+100*scale,horizon,fill="#0C2441",
                            outline=GOLD,width=max(1,int(2*scale)))
        self.create_polygon(cx,h*.05,cx+100*scale,horizon,cx,horizon,
                            fill="#0D3753",outline="")
        self.create_line(cx,h*.05,cx,horizon,fill=blend(GOLD,BLUE,.55),width=2)
        for depth in (1,.79,.58):
            dy=(horizon-h*.05)*depth+h*.05
            side=100*scale*depth
            self.create_line(cx-side,dy,cx+side,dy,
                             fill=blend(BORDER,GOLD,.27),width=1)
        # Energia circular na base, anéis em perspectiva.
        for i in range(6):
            rw=(w*.38)-i*7*scale
            rh=(h*.20)-i*3*scale
            if rw>3 and rh>3:
                self.create_oval(cx-rw,h*.60-rh,cx+rw,h*.60+rh,
                                 outline=blend(BLUE,GOLD,i*.14),width=1+int(i==0))
        # Fachos orbitais assimétricos em composição cinematográfica.
        for j in range(6):
            yy=h*.17+j*h*.12
            self.create_line(0,yy,w,yy-6*scale,
                             fill=blend(PANEL_ALT,BLUE,.07+(j%2)*.04))
        colors=(BLUE,"#45DAB5","#9885FF","#F78BD3",GOLD)
        symbols=("◇","✧","◎","⌑","⬡")
        large=w>=260
        offsets=(-2,-1,0,1,2) if large else (-1,0,1)
        spread=55*scale if large else 46*scale
        for idx,k in enumerate(offsets):
            x=cx+k*spread
            center=(k==0)
            cw=(55 if center else 45)*scale
            ch=(93 if center else 77)*scale
            top=h*(.14 if center else .27)
            # Pequeno brilho antes da borda de cada carta.
            color=colors[(k+2)%5]
            self.create_rectangle(x-cw/2-2,top-2,x+cw/2+2,top+ch+2,
                                  outline=blend(color,GOLD,.22),width=2)
            self.create_rectangle(x-cw/2,top,x+cw/2,top+ch,
                                  fill="#041629",outline=color,width=2)
            self.create_rectangle(x-cw/2+5*scale,top+7*scale,
                                  x+cw/2-5*scale,top+ch-12*scale,
                                  fill="#0B2E4C",outline=blend(color,BLUE,.42))
            # Ícone original, evita imagens e nomes de cartas falsos.
            self.create_text(x,top+ch*.46,text=symbols[(k+2)%5],
                             fill=color,font=("Segoe UI Symbol",max(9,int(27*scale))))
            self.create_line(x-cw/2+8*scale,top+ch-7*scale,
                             x+cw/2-8*scale,top+ch-7*scale,fill=GOLD,width=1)
        # Estrelas de luz estáticas e linhas de acabamento.
        for fx,fy in ((.1,.17),(.84,.18),(.73,.75),(.21,.67),(.54,.07),(.93,.60)):
            sx,sy=w*fx,h*fy
            self.create_line(sx-4*scale,sy,sx+4*scale,sy,fill=GOLD,width=1)
            self.create_line(sx,sy-4*scale,sx,sy+4*scale,fill=GOLD,width=1)
        self.create_line(0,h-4,w,h-4,fill=GOLD,width=2)
        self.create_line(0,h-8,w,h-8,fill=BLUE,width=1)
        if large:
            self.create_text(cx,h-15,text="DUELTRACE  •  MULTIMOD COMPANION",
                             fill=GOLD,font=("Segoe UI Semibold",max(8,int(9*scale))))


class CardArt(tk.Canvas):
    """Prévia da arte local extraída quando disponível; senão usa símbolo."""
    def __init__(self, parent, *, width=244, height=235):
        super().__init__(parent, width=width, height=height, bg=PANEL,
                         bd=0, highlightthickness=0)
        self.card = None
        self.art_root = None
        self._card_photo = None
        self.bind("<Configure>", lambda _: self._draw())
        self._draw()

    def set_card(self, card: dict | None, art_root: str | None = None):
        self.card = card
        self.art_root = art_root
        self._card_photo = None
        if card is not None and art_root:
            try:
                cid = int(card.get("id", 0))
                directory = Path(art_root).resolve(strict=True)
                artwork = (directory / f"{cid:03d}.png").resolve(strict=True)
                if (1 <= cid <= 722 and artwork.is_relative_to(directory)
                        and artwork.stat().st_size <= 1_000_000):
                    raw = tk.PhotoImage(file=str(artwork))
                    self._card_photo = raw.zoom(2, 2) if raw.width() <= 110 else raw
            except (OSError, ValueError, tk.TclError):
                self._card_photo = None
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = max(self.winfo_width(), 150), max(self.winfo_height(), 170)
        self.create_rectangle(3,3,w-4,h-4,fill=SIDEBAR,outline=GOLD,width=2)
        for y in range(6,h-7,4):
            t=y/max(1,h)
            color=blend(PANEL_ALT,"#041224",t)
            self.create_line(7,y,w-8,y,fill=color,width=4)
        self.create_rectangle(11,11,w-12,h-12,outline=BLUE,width=1)
        self.create_line(16,15,w-16,15,fill=GOLD,width=2)
        self.create_line(16,h-15,w-16,h-15,fill=GOLD,width=2)
        card = self.card
        if not card:
            self.create_text(w/2, h*.43, text="◇", fill=BLUE,
                             font=("Segoe UI Symbol", 52))
            self.create_text(w/2, h*.72, text="NENHUMA CARTA", fill=MUTED,
                             font=("Segoe UI Semibold", 10))
            return
        category = str(card.get("category") or "Não identificado")
        accent = category_color(category)
        symbol = CATEGORY_SYMBOLS.get(category, "?")
        if self._card_photo is not None:
            self.create_rectangle(w/2-108, h*.42-102, w/2+108, h*.42+102,
                                  outline=accent, width=2)
            self.create_image(w/2, h*.42, image=self._card_photo)
        else:
            for i in range(5):
                inset = 20+i*9
                self.create_oval(inset, h*.15+inset*.25, w-inset,
                                 h*.73-inset*.25,
                                 outline=blend(accent, PANEL_ALT, i*.18), width=2)
            self.create_text(w/2, h*.42, text=symbol, fill=accent,
                             font=("Segoe UI Symbol", 62))
        self.create_text(w/2, 26, text=f"ID #{card.get('id','?')}",
                         fill=GOLD, font=("Segoe UI Semibold", 10))
        self.create_text(w/2, h*.77, text=str(card.get("name") or "Sem nome"),
                         width=w-38, fill=TEXT,
                         font=("Segoe UI Semibold", 11))
        self.create_text(w/2, h*.91, text=f"{category} · {'arte local' if self._card_photo else 'símbolo'}",
                         width=w-20, fill=MUTED, font=("Segoe UI", 9))


class HandCardTile(tk.Canvas):
    """Uma das cinco cartas da mão, com arte da ISO quando disponível.

    A prévia permanece simbólica se a extração de artes não for suportada.
    Não redesenha informações não validadas da RAM.
    """
    def __init__(self, parent, slot: int, *, height=142):
        super().__init__(parent, height=height, width=145, bg=PANEL, bd=0,
                         highlightthickness=0)
        self.slot=slot
        self.card=None
        self._picture=None
        self.bind("<Configure>",lambda _:self._draw())
        self._draw()

    def show(self, card: dict | None, *, art_root: str | None=None):
        self.card=card
        self._picture=None
        if card and art_root:
            try:
                cid=int(card["id"])
                directory=Path(art_root).resolve(strict=True)
                path=(directory/f"{cid:03d}.png").resolve(strict=True)
                if (1<=cid<=722 and path.is_relative_to(directory)
                        and path.stat().st_size<1_000_000):
                    raw=tk.PhotoImage(file=str(path))
                    self._picture=raw.subsample(2,2) if raw.width()>70 else raw
            except (OSError,ValueError,TypeError,tk.TclError):
                self._picture=None
        self._draw()

    def _draw(self):
        self.delete("all")
        w=max(115,self.winfo_width())
        h=max(120,self.winfo_height())
        active=self.card is not None
        edge=BLUE if active else BORDER
        for y in range(2,h-3,3):
            mix=y/max(h-1,1)
            color=blend(PANEL_ALT,"#06172A",mix)
            self.create_line(5,y,w-6,y,fill=color,width=3)
        self.create_rectangle(3,3,w-4,h-4,outline=edge,width=2)
        self.create_line(11,5,w-12,5,fill=GOLD,width=2)
        self.create_text(12,15,anchor="w",
                         text=f"SLOT {self.slot:02d}",fill=GOLD,
                         font=("Segoe UI Semibold",9))
        if not active:
            self.create_text(w/2,h*.49,text="◇",fill=BORDER,
                             font=("Segoe UI Symbol",30))
            self.create_text(w/2,h-18,text="Aguardando carta",fill=MUTED,
                             font=("Segoe UI",8))
            return
        card=self.card
        if self._picture:
            self.create_image(w/2,57,image=self._picture)
        else:
            self.create_text(w/2,56,text="▣",fill=BLUE,
                             font=("Segoe UI Symbol",30))
        cid=card.get("id","?")
        self.create_text(w/2,93,text=f"#{cid}  {card.get('name',f'Carta {cid}')}",
                         width=w-13,anchor="center",fill=TEXT,
                         font=("Segoe UI Semibold",9))
        attack=card.get("atk")
        defense=card.get("def")
        if type(attack) is int and type(defense) is int:
            stats=f"ATK {attack:,}  •  DEF {defense:,}"
        else:
            stats="Atributos indisponíveis"
        self.create_text(w/2,h-13,text=stats,fill=GOLD,
                         font=("Segoe UI",8))


class CategoryMeters(tk.Frame):
    """Distribuição real do catálogo sem inventar percentuais ou totais."""
    def __init__(self, parent, counts: dict, *, background=PANEL):
        super().__init__(parent, background=background)
        total = sum(max(0, int(counts.get(category, 0) or 0))
                    for category in CATEGORY_COLORS)
        self.total = total
        for category in CATEGORY_COLORS:
            count = max(0, int(counts.get(category, 0) or 0))
            if count == 0 and category == "Não identificado":
                continue
            row = tk.Frame(self, background=background)
            row.pack(fill="x", pady=3)
            text_label(row, category, color=TEXT, size=10,
                       bg=background).pack(side="left")
            text_label(row, str(count), color=GOLD, size=10,
                       strong=True, bg=background).pack(side="right")
            track = tk.Canvas(self, height=7, bg=PANEL_ALT, bd=0,
                              highlightthickness=0)
            track.pack(fill="x", pady=(0, 3))
            ratio = (count / total) if total else 0
            accent = category_color(category)
            def update(_e, c=track, r=ratio, color=accent):
                c.delete("all")
                width = c.winfo_width()
                if r:
                    c.create_rectangle(0, 0, max(2, int(width*r)), 7,
                                       fill=color, outline="")
            track.bind("<Configure>", update)
