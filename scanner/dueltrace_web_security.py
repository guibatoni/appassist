"""API privilegiada da interface WebUI com token de capacidade por sessão.

A janela pywebview expõe SOMENTE estes métodos. O token aleatório de 256 bits
é injetado SOMENTE quando a página ativa pertence à origem local esperada.
Navegações para outros sites não recebem a capacidade. A proteção pressupõe
que o JavaScript da origem local seja confiável; não substitui CSP e auditoria.
"""
from __future__ import annotations

import hmac


class ProtectedDesktopApi:
    def __init__(self, bridge, token: str):
        if not isinstance(token, str) or len(token)<32:
            raise ValueError("Token de sessão inválido")
        self._bridge=bridge
        self._token=token

    def _authorize(self, credential):
        if not isinstance(credential,str) or not hmac.compare_digest(
                credential,self._token):
            raise PermissionError("Acesso não autorizado à API local.")

    def check_updates(self, credential):
        self._authorize(credential)
        return self._bridge.check_updates()

    def open_updates_page(self, credential):
        self._authorize(credential)
        return self._bridge.open_updates_page()

    def get_state(self, credential):
        self._authorize(credential)
        return self._bridge.get_state()

    def get_hand(self, credential):
        self._authorize(credential)
        return self._bridge.get_hand()

    def get_rank(self, credential):
        self._authorize(credential)
        return self._bridge.get_rank()

    def confirm_rank_lp(self, credential, life_points):
        self._authorize(credential)
        return self._bridge.confirm_rank_lp(life_points)

    def get_fusions(self, credential, query="", offset=0, limit=100):
        self._authorize(credential)
        return self._bridge.get_fusions(query,offset,limit)

    def activate_mod(self, credential, sha, acknowledge=False):
        self._authorize(credential)
        return self._bridge.activate_mod(sha,acknowledge)

    def scan_sources(self, credential, sha):
        self._authorize(credential)
        return self._bridge.scan_sources(sha)

    def import_iso(self, credential):
        self._authorize(credential)
        return self._bridge.import_iso()

    def configure_epsxe(self, credential):
        self._authorize(credential)
        return self._bridge.configure_epsxe()

    def start_game(self, credential):
        self._authorize(credential)
        return self._bridge.start_game()
