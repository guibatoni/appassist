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

    def open_updates_page(self, credential, run_id=None):
        self._authorize(credential)
        return self._bridge.open_updates_page(run_id)

    def install_signed_update(self, credential):
        self._authorize(credential)
        return self._bridge.install_signed_update()

    def install_preview_update(self, credential):
        self._authorize(credential)
        return self._bridge.install_preview_update()

    def install_portable_update(self, credential):
        self._authorize(credential)
        return self._bridge.install_portable_update()

    def get_state(self, credential):
        self._authorize(credential)
        return self._bridge.get_state()

    def get_hand(self, credential):
        self._authorize(credential)
        return self._bridge.get_hand()

    def get_rank_diagnostic(self, credential):
        self._authorize(credential)
        return self._bridge.get_rank_diagnostic()

    def calculate_spoils(self, credential, counters, victory):
        self._authorize(credential)
        return self._bridge.calculate_spoils(counters,victory)

    def get_rank(self, credential):
        self._authorize(credential)
        return self._bridge.get_rank()

    def confirm_rank_lp(self, credential, life_points):
        self._authorize(credential)
        return self._bridge.confirm_rank_lp(life_points)

    def capture_rank_prediction(self, credential):
        self._authorize(credential)
        return self._bridge.capture_rank_prediction()

    def get_pending_rank_capture(self, credential):
        self._authorize(credential)
        return self._bridge.get_pending_rank_capture()

    def get_rank_comparison(self, credential):
        self._authorize(credential)
        return self._bridge.get_rank_comparison()

    def review_card_matches(self, credential, source_sha, target_sha):
        self._authorize(credential)
        return self._bridge.review_card_matches(source_sha,target_sha)

    def compare_mod_cards(self, credential, source_sha, target_sha,
                          query="", offset=0, limit=40, confidence="todas"):
        self._authorize(credential)
        return self._bridge.compare_mod_cards(
            source_sha,target_sha,query,offset,limit,confidence)

    def get_fusions(self, credential, query="", offset=0, limit=100,
                    sort="id", card_type=""):
        self._authorize(credential)
        return self._bridge.get_fusions(query,offset,limit,sort,card_type)

    def get_drops(self, credential, opponent_id=0, group="", query="",
                  offset=0, limit=36, sort="id", card_type="", rank=""):
        self._authorize(credential)
        return self._bridge.get_drops(opponent_id,group,query,offset,limit,sort,card_type,rank)

    def get_card_drop_sources(self, credential, card_id):
        self._authorize(credential)
        return self._bridge.get_card_drop_sources(card_id)

    def export_rank_audit(self, credential):
        self._authorize(credential)
        return self._bridge.export_rank_audit()

    def get_rank_trace_status(self, credential):
        self._authorize(credential)
        return self._bridge.get_rank_trace_status()

    def import_rank_trace(self, credential, duel_id=None):
        self._authorize(credential)
        return self._bridge.import_rank_trace(duel_id)

    def get_duel_evidence(self, credential):
        self._authorize(credential)
        return self._bridge.get_duel_evidence()

    def record_duel_result(self, credential, opponent_id, observed_rank,
                           card_id, observed_points=None, victory_type="unknown",
                           capture_id=None):
        self._authorize(credential)
        return self._bridge.record_duel_result(
            opponent_id,observed_rank,card_id,observed_points,victory_type,capture_id)

    def activate_mod(self, credential, sha, acknowledge=False):
        self._authorize(credential)
        return self._bridge.activate_mod(sha,acknowledge)

    def get_mod_scan_diagnostic(self, credential, sha, with_ollama=False):
        self._authorize(credential)
        return self._bridge.get_mod_scan_diagnostic(sha,with_ollama)

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
