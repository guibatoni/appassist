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
        w, h = max(self.winfo_width(), 80), max(self.winfo_height(), 80)
        self.create_rectangle(2, 2, w-3, h-3,
                              fill=blend(PANEL, PANEL_ALT, self._hover),
                              outline=blend(BORDER, self.accent, self._hover),
                              width=2)
        self.create_line(12, h-7, w-12, h-7, fill=self.accent, width=2)
        self.create_text(w/2, 27, text=self.symbol, fill=self.accent,
                         font=("Segoe UI Symbol", 25))
        self.create_text(w/2, 61, text=self.caption, fill=TEXT,
                         width=w-14, font=("Segoe UI Semibold", 10))
        self.create_text(w/2, 86, text=self.subtitle, fill=MUTED,
                         width=w-15, font=("Segoe UI", 8))


class HeroArt(tk.Canvas):
    """Arte original com geometria egípcia abstrata e cartas holográficas."""
    def __init__(self, parent, *, width=350, height=190):
        super().__init__(parent, width=width, height=height, bg=PANEL,
                         bd=0, highlightthickness=0)
        self.bind("<Configure>", lambda _: self._draw())
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = max(250, self.winfo_width()), max(150, self.winfo_height())
        cx, cy = w*0.52, h*0.53
        # Linhas douradas e azuis lembram arquitetura egípcia e circuitos.
        for i in range(6):
            y = h*(i+1)/7
            self.create_line(0, y, w, y-14, fill=blend(PANEL, BORDER, .35))
        for j in range(4):
            m = j*12
            self.create_oval(cx-120+m, cy-63+m/2, cx+120-m, cy+63-m/2,
                             outline=blend(BLUE, PANEL, j*.19), width=2)
        self.create_polygon(cx-63, h-13, cx, 15, cx+63, h-13,
                            outline=GOLD, fill=PANEL_ALT, width=2)
        self.create_polygon(cx-43, h-19, cx, 43, cx+43, h-19,
                            outline=BLUE, fill=PANEL, width=2)
        # Cartões são símbolos abstratos, não imagens ou dados de cartas.
        for offset, angle_color in ((-106, GOLD), (4, BLUE), (114, GOLD)):
            x = cx+offset
            height = h*.48
            top = h*.26 if offset != 4 else h*.18
            self.create_rectangle(x-32, top, x+32, top+height,
                                  outline=angle_color, fill=SIDEBAR, width=3)
            self.create_rectangle(x-24, top+8, x+24, top+height-13,
                                  outline=BORDER, fill=PANEL_ALT, width=1)
            self.create_oval(x-14, top+27, x+14, top+55,
                             outline=angle_color, width=2)
            self.create_polygon(x-8, top+50, x, top+30, x+8, top+50,
                                fill=angle_color, outline="")
        self.create_line(8, h-6, w-8, h-6, fill=GOLD, width=2)
        self.create_text(cx, h-18, text="DUELTRACE  /  MULTIMOD",
                         fill=GOLD, font=("Segoe UI Semibold", 9))


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
        self.create_rectangle(4, 4, w-5, h-5, fill=SIDEBAR, outline=BORDER, width=2)
        self.create_rectangle(11, 11, w-12, h-12, fill=PANEL_ALT, outline=GOLD, width=1)
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
