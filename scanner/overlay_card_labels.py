"""Compatibilidade visual: nomes de cartas validadas em painéis Tk legados.

Há versões do painel_compacto que desenham literalmente "Carta #123 (ID somente)"
usando Label/Canvas, sem consultar o dicionário atualizado pelo MultiMod.
Este adaptador substitui APENAS esses textos, após ativação manual do perfil.

Não modifica RAM, ISO, saves, pontuação, cálculo, fusões ou nomes de outro mod.
Não confirma a ISO realmente aberta no ePSXe.
"""
from __future__ import annotations

import re
import weakref
from collections.abc import Mapping

UNKNOWN_CARD = re.compile(r"Carta\s*#\s*(\d+)\s*\(\s*ID\s+somente\s*\)", re.IGNORECASE)


def card_text(text: str, cards: Mapping) -> str:
    """Substituir somente marcador explicitamente desconhecido, nunca texto arbitrário."""
    if not isinstance(text, str) or "somente" not in text.lower():
        return text

    def repl(match):
        try:
            cid = int(match.group(1))
            item = cards.get(cid)
            if item is None:
                item = cards.get(str(cid))
            if not isinstance(item, Mapping):
                return match.group(0)
            name = str(item.get("name", "")).strip()
            if not name or name.lower().startswith("carta #"):
                return match.group(0)
            return f"{name} (#{cid})"
        except (ValueError, TypeError):
            return match.group(0)
    return UNKNOWN_CARD.sub(repl, text)


class CardLabelSync:
    """Sincroniza labels da mão em Tk usando root.after na thread da interface.

    Guarda o texto original para reverter ao trocar de perfil. Processa somente
    widgets que contêm 'Carta #n (ID somente)' e itens Canvas do tipo text.
    """

    def __init__(self, scheduler, roots=(), interval_ms=850):
        self.scheduler = scheduler
        self.roots = tuple(r for r in roots if r is not None)
        self.interval_ms = max(350, int(interval_ms))
        self.cards = {}
        self._labels = weakref.WeakKeyDictionary()
        self._canvas = weakref.WeakKeyDictionary()
        self._running = False
        self._after_id = None
        self.last_changed = 0

    def use_snapshot(self, snapshot: dict) -> None:
        features = snapshot.get("features", {})
        if snapshot.get("ready") and features.get("nomes_cartas"):
            self.cards = dict(snapshot.get("cards", {}))
        else:
            self.cards = {}
        self.refresh()

    def _update_label(self, widget):
        try:
            current = widget.cget("text")
        except Exception:
            return 0
        if not isinstance(current, str):
            return 0
        old = self._labels.get(widget)
        if old and current == old[1]:
            original = old[0]
        else:
            original = current
            if old:
                self._labels.pop(widget, None)
        desired = card_text(original, self.cards)
        if desired == current:
            return 0
        try:
            widget.configure(text=desired)
            if desired == original:
                self._labels.pop(widget, None)
            else:
                self._labels[widget] = (original, desired)
            return 1
        except Exception:
            return 0

    def _update_canvas(self, canvas):
        try:
            ids = canvas.find_all()
        except Exception:
            return 0
        changed = 0
        previous = self._canvas.setdefault(canvas, {})
        for item_id in ids:
            try:
                if canvas.type(item_id) != "text":
                    continue
                current = canvas.itemcget(item_id, "text")
            except Exception:
                continue
            old = previous.get(item_id)
            if old and current == old[1]:
                original = old[0]
            else:
                original = current
                previous.pop(item_id, None)
            desired = card_text(original, self.cards)
            if desired != current:
                try:
                    canvas.itemconfigure(item_id, text=desired)
                    if desired == original:
                        previous.pop(item_id, None)
                    else:
                        previous[item_id] = (original, desired)
                    changed += 1
                except Exception:
                    continue
        for stale_id in list(previous):
            if stale_id not in ids:
                previous.pop(stale_id, None)
        return changed

    def refresh(self) -> int:
        changed = 0
        seen = set()
        stack = list(self.roots)
        while stack and len(seen) < 6000:
            widget = stack.pop()
            wid = id(widget)
            if wid in seen:
                continue
            seen.add(wid)
            try:
                if hasattr(widget, "winfo_exists") and not widget.winfo_exists():
                    continue
            except Exception:
                continue
            # Não usar widgets Text/Entry: a modificação poderia perder
            # informações digitadas ou destruir a formatação.
            if getattr(widget, "winfo_class", lambda: "")() in ("Label", "TLabel"):
                changed += self._update_label(widget)
            if all(hasattr(widget, a) for a in ("find_all", "itemcget", "itemconfigure")):
                changed += self._update_canvas(widget)
            try:
                stack.extend(widget.winfo_children())
            except Exception:
                pass
        self.last_changed = changed
        return changed

    def start(self):
        if self._running:
            return
        self._running = True
        self._tick()

    def _tick(self):
        if not self._running:
            return
        try:
            self.refresh()
        except Exception as exc:
            # Não derrubar o overlay se uma janela for destruída no meio do ciclo.
            print("MultiMod: atualização visual indisponível:", exc, flush=True)
        try:
            self._after_id = self.scheduler.after(self.interval_ms, self._tick)
        except Exception:
            self._running = False

    def stop(self):
        self._running = False
        if self._after_id is not None:
            try:
                self.scheduler.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
