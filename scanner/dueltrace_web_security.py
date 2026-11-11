"""API privilegiada da interface WebUI com token de capacidade por sessão.

A janela pywebview expõe SOMENTE estes métodos. O token aleatório de 256 bits
é injetado SOMENTE quando a página ativa pertence à origem local esperada.
Navegações para outros sites não recebem a capacidade. A proteção pressupõe
que o JavaScript da origem local seja confiável; não substitui CSP e auditoria.
"""
from __future__ import annotations

import hmac
import threading
import time


class ProtectedDesktopApi:
    def __init__(self, bridge, token: str):
        if not isinstance(token, str) or len(token)<32:
            raise ValueError("Token de sessão inválido")
        self._bridge=bridge
        self._token=token
        # Janela nativa só pode ser anexada pelo ponto de entrada Windows.
        # Ações expostas ao JS passam por token e uma lista estrita.
        self._native_window=None
        self._native_window_lock=threading.RLock()
        self._native_maximized=False
        self._native_close_requested=False
        self._drag_session=None
        self._drag_sequence=0
        self._tool_window_open=None
        self._tool_window_close=None

    def _authorize(self, credential):
        if not isinstance(credential,str) or not hmac.compare_digest(
                credential,self._token):
            raise PermissionError("Acesso não autorizado à API local.")

    def window_control(self, credential, action):
        """Controles da moldura customizada, limitados à janela deste processo.

        Nunca aceita comandos arbitrários, caminhos ou IDs de outras janelas.
        O encerramento é assíncrono para liberar a resposta ao WebView.
        """
        self._authorize(credential)
        if type(action) is not str or action not in (
                "state","minimize","toggle_maximize","close"):
            raise ValueError("Comando da janela inválido.")
        with self._native_window_lock:
            window=self._native_window
            if window is None:
                raise RuntimeError("Janela nativa ainda não está pronta.")
            if action=="state":
                return {"maximized":self._native_maximized}
            if action=="minimize":
                window.minimize()
            elif action=="toggle_maximize":
                if self._native_maximized:
                    window.restore()
                    self._native_maximized=False
                else:
                    window.maximize()
                    self._native_maximized=True
            elif action=="close" and not self._native_close_requested:
                self._native_close_requested=True
                def close_after_response():
                    time.sleep(0.25)
                    window.destroy()
                threading.Thread(
                    target=close_after_response,name="dueltrace-window-close",
                    daemon=True).start()
            return {"maximized":self._native_maximized}

    def _drag_coordinate(self, value):
        # The only movement permitted is the CURRENT DUELTRACE window.
        # No arbitrary HWND, code, command, URL or filesystem access.
        if type(value) is not int or not -50000 <= value <= 50000:
            raise ValueError("Coordenada de arraste inválida.")
        return value

    def drag_window_begin(self, credential, screen_x, screen_y):
        """Start an authenticated mouse drag using pywebview native geometry.

        Unlike pywebview's .pywebview-drag-region selector (which did not
        move the embedded WebView2 on the user's Windows), the following
        drag move requests call Window.move(x,y) directly. Coordinates are
        absolute and based on this window's original position.
        """
        self._authorize(credential)
        sx=self._drag_coordinate(screen_x)
        sy=self._drag_coordinate(screen_y)
        with self._native_window_lock:
            window=self._native_window
            if window is None:
                raise RuntimeError("Janela nativa ainda não está pronta.")
            if self._native_maximized:
                return {"started":False,"dragId":None}
            native=getattr(window,"native",None)
            if native is not None:
                # This also handles maximizing via OS shortcuts or the taskbar,
                # which might not have updated the custom maximize button.
                try:
                    if str(native.WindowState).casefold().endswith("maximized"):
                        return {"started":False,"dragId":None}
                except (AttributeError,RuntimeError):
                    pass
            start_x,start_y=int(window.x),int(window.y)
            self._drag_sequence+=1
            self._drag_session={
                "id":self._drag_sequence,
                "start_x":sx,"start_y":sy,
                "window_x":start_x,"window_y":start_y,
                "last":time.monotonic(),
            }
            return {"started":True,"dragId":self._drag_sequence}

    def drag_window_move(self, credential, drag_id, screen_x, screen_y):
        """Move only while the matching short-lived drag is active."""
        self._authorize(credential)
        sx=self._drag_coordinate(screen_x)
        sy=self._drag_coordinate(screen_y)
        if type(drag_id) is not int:
            raise ValueError("Sessão de arraste inválida.")
        with self._native_window_lock:
            session=self._drag_session
            window=self._native_window
            if session is None or window is None or drag_id!=session["id"]:
                # Late WebView2 RPCs from a previous drag must never clear a
                # newer drag session that has already begun.
                return {"moved":False}
            if time.monotonic()-session["last"]>10 or self._native_maximized:
                self._drag_session=None
                return {"moved":False}
            dx=sx-session["start_x"]
            dy=sy-session["start_y"]
            # Bound movement originating from a single mouse action. Multiple
            # monitors are allowed; remote programmatic commands are not.
            if abs(dx)>10000 or abs(dy)>10000:
                self._drag_session=None
                return {"moved":False}
            dest_x=session["window_x"]+dx
            dest_y=session["window_y"]+dy
            if not -50000<=dest_x<=50000 or not -50000<=dest_y<=50000:
                self._drag_session=None
                return {"moved":False}
            window.move(int(dest_x),int(dest_y))
            session["last"]=time.monotonic()
            return {"moved":True}

    def drag_window_end(self, credential, drag_id):
        """Stop movement as soon as the mouse button is released/cancelled."""
        self._authorize(credential)
        if type(drag_id) is not int:
            raise ValueError("Sessão de arraste inválida.")
        with self._native_window_lock:
            if self._drag_session and self._drag_session["id"]==drag_id:
                self._drag_session=None
                return {"ended":True}
            return {"ended":False}

    def get_alpha_discovery(self, credential, sha):
        self._authorize(credential)
        return self._bridge.get_alpha_discovery(sha)

    def get_alpha_preferences(self, credential):
        self._authorize(credential)
        return self._bridge.get_alpha_preferences()

    def set_alpha_preferences(self, credential, fusion_tips_visible):
        self._authorize(credential)
        return self._bridge.set_alpha_preferences(fusion_tips_visible)

    def open_tool_window(self, credential, kind):
        """Open only one of two local, authenticated auxiliary windows."""
        self._authorize(credential)
        if type(kind) is not str or kind not in ("calculadora", "fusoes"):
            raise ValueError("Ferramenta desconhecida.")
        callback=self._tool_window_open
        if not callable(callback):
            raise RuntimeError("Janelas auxiliares indisponíveis nesta plataforma.")
        return callback(kind)

    def close_tool_window(self, credential, kind):
        self._authorize(credential)
        if type(kind) is not str or kind not in ("calculadora", "fusoes"):
            raise ValueError("Ferramenta desconhecida.")
        callback=self._tool_window_close
        if not callable(callback):
            raise RuntimeError("Janelas auxiliares indisponíveis nesta plataforma.")
        return callback(kind)

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

    def calculate_spoils(self, credential, counters, victory, reference="classic"):
        self._authorize(credential)
        return self._bridge.calculate_spoils(counters,victory,reference)

    def set_rank_experimental(self, credential, enabled):
        self._authorize(credential)
        return self._bridge.set_rank_experimental(enabled)

    def calibrate_rank(self, credential):
        self._authorize(credential)
        return self._bridge.calibrate_rank()

    def get_rank(self, credential):
        self._authorize(credential)
        return self._bridge.get_rank()

    def get_rank_auto(self, credential):
        self._authorize(credential)
        return self._bridge.get_rank_auto()

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
                    sort="id", card_type="", search_scope="all"):
        self._authorize(credential)
        return self._bridge.get_fusions(
            query,offset,limit,sort,card_type,search_scope)

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

    def undo_last_window_observation(self, credential, sha):
        self._authorize(credential)
        return self._bridge.undo_last_window_observation(sha)

    def start_live_diagnostics(self, credential):
        self._authorize(credential)
        return self._bridge.start_live_diagnostics()

    def stop_live_diagnostics(self, credential):
        self._authorize(credential)
        return self._bridge.stop_live_diagnostics()

    def get_live_diagnostics_status(self, credential):
        self._authorize(credential)
        return self._bridge.get_live_diagnostics_status()

    def export_live_diagnostics(self, credential):
        self._authorize(credential)
        return self._bridge.export_live_diagnostics()

    def configure_private_evidence_sync(self, credential, repository, token, consent):
        self._authorize(credential)
        return self._bridge.configure_private_evidence_sync(repository, token, consent)

    def disable_private_evidence_sync(self, credential):
        self._authorize(credential)
        return self._bridge.disable_private_evidence_sync()

    def get_private_evidence_sync_status(self, credential):
        self._authorize(credential)
        return self._bridge.get_private_evidence_sync_status()

    def get_live_opponent(self, credential):
        self._authorize(credential)
        return self._bridge.get_live_opponent()

    def get_candidate_matrix(self, credential, sha, physical_block_index=-1,
                             matrix_group=1, query="", offset=0, limit=30):
        self._authorize(credential)
        return self._bridge.get_candidate_matrix(
            sha, physical_block_index, matrix_group, query, offset, limit)

    def get_window_observations(self, credential, sha):
        self._authorize(credential)
        return self._bridge.get_window_observations(sha)

    def record_window_observation(self, credential, sha, opponent_slot,
                                  observed_rank, reward_card_id, played_card_ids):
        self._authorize(credential)
        return self._bridge.record_window_observation(
            sha, opponent_slot, observed_rank, reward_card_id, played_card_ids)

    def get_duel_evidence(self, credential):
        self._authorize(credential)
        return self._bridge.get_duel_evidence()

    def record_duel_result(self, credential, opponent_id, observed_rank,
                           card_id, observed_points=None, victory_type="unknown",
                           capture_id=None):
        self._authorize(credential)
        return self._bridge.record_duel_result(
            opponent_id,observed_rank,card_id,observed_points,victory_type,capture_id)

    def rename_mod(self, credential, sha, display_name):
        self._authorize(credential)
        return self._bridge.rename_mod(sha,display_name)

    def remove_mod(self, credential, sha):
        self._authorize(credential)
        return self._bridge.remove_mod(sha)

    def activate_mod(self, credential, sha, acknowledge=False):
        self._authorize(credential)
        return self._bridge.activate_mod(sha,acknowledge)

    def audit_mod_iso(self, credential, sha):
        self._authorize(credential)
        return self._bridge.audit_mod_iso(sha)

    def upload_iso_forensic(self, credential, sha):
        self._authorize(credential)
        return self._bridge.upload_iso_forensic(sha)

    def compare_mod_layouts(self, credential, baseline_sha):
        self._authorize(credential)
        return self._bridge.compare_mod_layouts(baseline_sha)

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
