"""Leitura segura do perfil ativo pelo overlay.

O arquivo perfil_ativo.json é escrito somente após confirmação no
Gerenciador de Mods. Este adaptador NÃO afirma que o jogo ePSXe usa a
mesma ISO: a identificação da ROM ativa é uma etapa separada.

Exemplo de integração em um App Tkinter existente:
    observer = OverlayProfileObserver(root, on_profile_change)
    observer.start()

on_profile_change(profile) deve reconstruir os catálogos e atualizar
as abas; NÃO altere o estado do jogo ou memory cards.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable
from auto_mods import ModCatalog


def overlay_snapshot(catalog: ModCatalog | None = None) -> dict:
    catalog = catalog or ModCatalog()
    active = catalog.current()
    if not active:
        return {
            "ready": False, "reason": "Nenhum perfil validado e confirmado está ativo.",
            "cards": {}, "recipes": [], "drops": [], "opponents": {},
            "features": {}, "art_root": None,
        }
    sha = active.get("sha256", "")
    entry = next((r for r in catalog.list() if r.get("sha256") == sha), None)
    if entry is None or not entry.get("approved"):
        return {
            "ready": False, "reason": "Perfil não aprovado.",
            "cards": {}, "recipes": [], "drops": [], "opponents": {},
            "features": {}, "art_root": None,
        }
    profile = catalog.profile_for(entry)
    if not profile:
        return {
            "ready": False, "reason": "Arquivo do perfil ausente ou inconsistente.",
            "cards": {}, "recipes": [], "drops": [], "opponents": {},
            "features": {}, "art_root": None,
        }
    features = active.get("features", {})
    cards = {}
    opponents = {}
    recipes = []
    drops = []
    if features.get("nomes_cartas"):
        for c in profile.get("cards", []):
            try:
                cid = int(c["id"])
                cards[cid] = {
                    "name": str(c["name"]),
                    "atk": int(c["atk"]), "def": int(c["def"]),
                    "type_id": c.get("type_id"),
                }
            except (KeyError, ValueError, TypeError):
                continue
    if features.get("oponentes"):
        for x in profile.get("opponents", []):
            try:
                opponents[int(x["id"])] = str(x["name"])
            except (KeyError, ValueError, TypeError):
                continue
    if features.get("fusoes"):
        for row in profile.get("fusion_recipes", []):
            try:
                recipes.append((int(row["a"]), int(row["b"]), int(row["result"])))
            except (KeyError, ValueError, TypeError):
                continue
    if features.get("drops_brutos"):
        drops = list(profile.get("drops", []))
    return {
        "ready": True, "reason": "",
        "rom_sha256": sha,
        "profile_name": profile.get("name", "Mod local"),
        "level": entry.get("level"),
        "cards": cards,
        "opponents": opponents,
        "recipes": recipes,
        "drops": drops,
        "art_root": profile.get("art_root") if features.get("artes") else None,
        "features": features,
        "rank_labels": profile.get("rank_labels") if features.get("rank") else None,
    }


class OverlayProfileObserver:
    """Entrega mudanças na thread Tkinter por meio de root.after.

    Invocar callback é responsabilidade do aplicativo, que deve atualizar suas
    abas/estrategista/calculadora e não apenas alterar um título.
    """
    def __init__(self, root, on_change: Callable[[dict], None],
                 catalog: ModCatalog | None = None, poll_ms: int = 1500):
        self.root = root
        self.on_change = on_change
        self.catalog = catalog or ModCatalog()
        self.poll_ms = max(500, poll_ms)
        self._active = False
        self._after_id = None
        self._last_token = None

    def start(self):
        if not self._active:
            self._active = True
            self._poll()

    def stop(self):
        self._active = False
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = None

    def _poll(self):
        if not self._active:
            return
        path = self.catalog.active_file
        try:
            stat = path.stat()
            token = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            token = None
        if token != self._last_token:
            self._last_token = token
            self.on_change(overlay_snapshot(self.catalog))
        self._after_id = self.root.after(self.poll_ms, self._poll)
