"""DUELTRACE Cloud local-first connector (prototype).

Only a loopback HTTP server. The actual ISO/BIN, Memory Card and emulator RAM
are accessed by the existing Python engine on the user's Windows PC.
Nothing is uploaded to or cached by the hosted web application's server.

Authentication: one ephemeral capability printed locally; strict Origin,
Host, content-type, bearer token and CORS preflight checks. No cookies,
path arguments, secret-bearing URLs or permissive CORS headers.
"""
from __future__ import annotations

import argparse
import hmac
import http.server
import json
import re
import secrets
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from dueltrace_cloud_browser import render_local_page

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
MAX_BODY = 2048
MAX_JSON = 2_000_000
DEV_ORIGINS = frozenset(("http://127.0.0.1:3000", "http://localhost:3000"))


def _is_allowed_origin(value: str | None, allowed: frozenset[str]) -> bool:
    return isinstance(value, str) and value in allowed and len(value) <= 256


def _int_param(query, name, default, *, minimum, maximum):
    raw = query.get(name, [str(default)])
    if len(raw) != 1 or not re.fullmatch(r"\d{1,7}", raw[0]):
        raise ValueError("Parâmetro numérico inválido")
    value = int(raw[0])
    if not minimum <= value <= maximum:
        raise ValueError("Parâmetro numérico fora do intervalo")
    return value


def _text_param(query, name, default="", limit=120):
    raw = query.get(name, [default])
    if len(raw) != 1 or len(raw[0]) > limit:
        raise ValueError("Parâmetro de pesquisa inválido")
    return raw[0]


def _local_state(bridge):
    """Only browser-displayable derived content; NEVER local paths or files."""
    state = bridge.get_state()
    mods = []
    for row in state.get("mods", []):
        if not isinstance(row, dict):
            continue
        sha = row.get("sha256")
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            continue
        mods.append({
            "sha256": sha, "name": str(row.get("name") or "Mod local")[:160],
            "cards": row.get("cards", 0),
            "fusions": row.get("fusions", 0),
            "opponents": row.get("opponents", 0),
            "dropEntries": row.get("dropEntries", 0),
        })
    cards = []
    for card in state.get("cards", []):
        if not isinstance(card, dict) or type(card.get("id")) is not int:
            continue
        if not 1 <= card["id"] <= 722:
            continue
        cards.append({key: card.get(key) for key in (
            "id", "name", "type", "category", "attribute", "atk", "def",
            "level", "effect", "effectSource", "description", "descriptionSource",
        )})
    sha = state.get("activeSha")
    return {
        "activeSha": sha if isinstance(sha, str) and SHA_RE.fullmatch(sha) else None,
        "activeName": str(state.get("activeName") or "")[:160],
        "mods": mods, "cards": cards, "connected": True,
        "storage": "local-only", "cloudUpload": False,
    }


def _local_live(bridge):
    hand = bridge.get_hand()
    rank = bridge.get_rank_auto()
    rows = []
    for card in (hand.get("hand") or [])[:5]:
        if isinstance(card, dict):
            rows.append({key: card.get(key) for key in (
                "id", "slot", "name", "type", "atk", "def",
            )})
    # Only derived, visible suggestion fields. Never forward engine objects
    # wholesale (future fields could include sensitive diagnostic addresses).
    pairs = []
    for item in (hand.get("pairs") or [])[:5]:
        if isinstance(item, dict):
            pairs.append({key: item.get(key) for key in (
                "slot_a", "slot_b", "result", "result_name", "atk", "validation",
            )})
    chains = []
    for item in (hand.get("chains") or [])[:5]:
        if isinstance(item, dict):
            chains.append({key: item.get(key) for key in (
                "result", "result_name", "atk",
            )})
    # Suggestions and RANK values are derived; raw address, PID and memory
    # dumps are never exposed to the page.
    return {
        "hand": {"ready": bool(hand.get("ready")), "status": str(
            hand.get("status") or "")[:220], "cards": rows,
            "pairs": pairs, "chains": chains},
        "rank": {key: rank.get(key) for key in (
            "ready", "state", "status", "category", "score", "rankSystem",
            "sourceMode", "final",
        )},
        "localOnly": True,
    }


def _local_art(bridge, sha, card_id):
    """Authorized image bytes from active, SHA-bound scan cache only."""
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        return None
    if type(card_id) is not int or not 1 <= card_id <= 722:
        return None
    active, _entry, profile = bridge._active()
    if (not isinstance(profile, dict) or active.get("sha256") != sha
            or profile.get("rom_sha256") != sha
            or not profile.get("supported_features", {}).get("art")):
        return None
    try:
        root = Path(profile["scan_result_dir"]).resolve(strict=True)
        allowed = (Path(bridge.catalog.home) / "analises").resolve(strict=True)
        if not root.is_relative_to(allowed):
            return None
        card = next((c for c in profile.get("cards", [])
                     if isinstance(c, dict) and c.get("id") == card_id), None)
        target = root / "cartas_classicas_hd" / f"{card_id:03d}.png"
        if card is not None:
            from dueltrace_card_on_demand import ensure_card_hd
            try:
                target = ensure_card_hd(root, card, rom_sha256=sha)
            except (OSError, ValueError):
                pass
        target = Path(target).resolve(strict=True)
        if (not target.is_relative_to(root) or target.stat().st_size > 8_000_000
                or target.stat().st_size <= 0 or target.is_symlink()):
            return None
        with target.open("rb") as file:
            data = file.read(8_000_001)
        if len(data) > 8_000_000 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return None
        return data
    except (KeyError, OSError, ValueError, TypeError, RuntimeError):
        return None


def _picker(kind):
    """Browser triggers Windows native picker. No binary content in HTTP."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    try:
        if kind == "iso":
            filters = [("ISO/BIN do jogo", "*.iso *.bin")]
        elif kind == "memory_card":
            filters = [("Memory Card PS1", "*.mcr *.mcd *.mc *.srm *.mem *.vm1")]
        else:
            raise ValueError("Tipo de arquivo não suportado")
        path = filedialog.askopenfilename(
            parent=root, title="DUELTRACE — arquivo local", filetypes=filters)
        return (path,) if path else ()
    finally:
        root.destroy()


def make_handler(bridge, *, allowed_origins, token):
    """Dependency-injected handler for tests and real local connectors."""
    allowed = frozenset(allowed_origins)
    if not allowed or not all(
        x.startswith(("https://", "http://127.0.0.1:", "http://localhost:"))
        and "@" not in x and "/" not in x.split("://", 1)[1]
        for x in allowed
    ):
        raise ValueError("Configure apenas origens HTTPS ou localhost de desenvolvimento")
    if not isinstance(token, str) or len(token) < 24:
        raise ValueError("Token de sessão inválido")
    token_bytes = token.encode("ascii")

    class ConnectorHandler(http.server.BaseHTTPRequestHandler):
        server_version = "DUELTRACE-Local/0.1"
        sys_version = ""

        def log_message(self, format, *args):
            # Keep file names, card names and pairing credentials out of logs.
            return

        def _trusted(self):
            expected = f"{HOST}:{self.server.server_port}"
            return (
                self.client_address[0] == HOST
                and self.headers.get("Host", "").lower() == expected
                and _is_allowed_origin(self.headers.get("Origin"), allowed)
                # For the hosted HTTPS page Sec-Fetch-Site may be cross-site.
                # Exact Origin and a bearer token are the access controls.
            )

        def _headers(self, status=200, *, content_type="application/json; charset=utf-8",
                     length=None, browser_page=False):
            self.send_response(status)
            origin = self.headers.get("Origin")
            if _is_allowed_origin(origin, allowed):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if browser_page:
                # The local dashboard is server-rendered. No scripts, remote
                # fonts, frames, browser storage or external requests.
                self.send_header("Content-Security-Policy",
                    "default-src 'none'; style-src 'unsafe-inline'; "
                    "img-src 'self'; form-action 'self'; frame-ancestors 'none'; "
                    "base-uri 'none'; connect-src 'none'")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Content-Type", content_type)
            if length is not None:
                self.send_header("Content-Length", str(length))
            self.end_headers()

        def _json(self, status, data):
            raw = json.dumps(
                data, ensure_ascii=False, separators=(",", ":"),
            ).encode("utf-8")
            if len(raw) > MAX_JSON:
                raw = b'{"error":"Resposta excede o limite local"}'
                status = 413
            self._headers(status, length=len(raw))
            self.wfile.write(raw)

        def _local_browser_trusted(self, *, write=False):
            # Same-computer, same-origin HTML is separate from the existing
            # cross-origin bearer-protected /v1 API.
            expected_host = f"{HOST}:{self.server.server_port}"
            origin = f"http://{expected_host}"
            if (self.client_address[0] != HOST
                    or self.headers.get("Host", "").lower() != expected_host):
                return False
            # Forbid drive-by loads from unrelated web pages and iframes.
            site = self.headers.get("Sec-Fetch-Site", "").lower()
            if site not in ("", "none", "same-origin"):
                return False
            request_origin = self.headers.get("Origin")
            if write:
                return request_origin == origin
            return request_origin in (None, origin)

        def _browser_html(self, uri):
            if not self._local_browser_trusted():
                self._json(403, {"error": "Navegação local não autorizada"})
                return
            if uri.path == "/local/art":
                query = parse_qs(uri.query, keep_blank_values=True)
                try:
                    sha = _text_param(query, "sha", limit=64)
                    cid = _int_param(query, "id", 0, minimum=1, maximum=722)
                    data = _local_art(bridge, sha, cid)
                except (ValueError, TypeError):
                    data = None
                if data is None:
                    self._json(404, {"error": "Arte indisponível"})
                    return
                self._headers(200, content_type="image/png", length=len(data),
                              browser_page=True)
                self.wfile.write(data)
                return
            if uri.path not in ("/", "/local", "/local/"):
                self._json(404, {"error": "Página não encontrada"})
                return
            try:
                query = parse_qs(uri.query, keep_blank_values=True)
                tab = _text_param(query, "tab", "inicio", limit=24)
                search = _text_param(query, "q", "", limit=80)
                page = _int_param(query, "page", 0, minimum=0, maximum=10000)
                opponent = _int_param(query, "opponent", 0, minimum=0, maximum=39)
                card_id = _int_param(query, "id", 0, minimum=0, maximum=722)
                msg = _text_param(query, "msg", "", limit=24)
                messages = {
                    "activated": "Mod ativado. Os dados permanecem no PC.",
                    "imported": "Importação local concluída. Selecione o mod.",
                    "memory": "Memory Card selecionado localmente.",
                    "cancelled": "Seleção de arquivo cancelada.",
                    "error": "A operação não pôde ser concluída.",
                }
                state = _local_state(bridge)
                panel = {}
                if state["activeSha"]:
                    if tab == "inicio":
                        panel = _local_live(bridge)
                    elif tab == "fusoes":
                        panel = bridge.get_fusions(query=search, offset=0, limit=100)
                    elif tab == "carta" and 1 <= card_id <= 722:
                        panel = bridge.get_card_fusion_paths(card_id)
                    elif tab == "oponentes":
                        panel = bridge.get_opponent_deck(opponent)
                    elif tab == "drops":
                        panel = bridge.get_drops(opponent_id=opponent, offset=0,
                                                 limit=100, sort="id")
                        names = bridge.get_opponent_deck(opponent)
                        if isinstance(panel, dict) and isinstance(names, dict):
                            panel = {**panel, "opponents": names.get("opponents", [])}
                    elif tab == "decks":
                        panel = bridge.get_deck_library("")
                page_html = render_local_page(
                    state, token=token, tab=tab, query=search, opponent=opponent,
                    page=page, panel=panel, card_id=card_id,
                    notice=messages.get(msg, ""))
                raw = page_html.encode("utf-8")
                if len(raw) > MAX_JSON:
                    self._json(413, {"error": "Página muito grande"})
                    return
                self._headers(200, content_type="text/html; charset=utf-8",
                              length=len(raw), browser_page=True)
                self.wfile.write(raw)
            except (ValueError, TypeError):
                self._json(400, {"error": "Parâmetros de página inválidos"})
            except Exception:
                # The dashboard must never leak traces, paths or memory data.
                self._json(503, {"error": "Dados locais indisponíveis"})

        def _browser_action(self):
            if not self._local_browser_trusted(write=True):
                self._json(403, {"error": "Ação de origem não autorizada"})
                return
            try:
                count = int(self.headers.get("Content-Length", "-1"))
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0]
                if not 0 <= count <= MAX_BODY or content_type != "application/x-www-form-urlencoded":
                    self._json(413, {"error": "Formulário inválido"})
                    return
                form = parse_qs(self.rfile.read(count).decode("utf-8"),
                                keep_blank_values=True)
                if any(len(v) != 1 for v in form.values()):
                    raise ValueError()
                csrf = form.get("csrf", [""])[0]
                if not hmac.compare_digest(csrf, token):
                    self._json(403, {"error": "Sessão inválida"})
                    return
                action = form.get("action", [""])[0]
                if action == "activate":
                    if set(form) != {"action", "csrf", "sha"}:
                        raise ValueError()
                    sha = form.get("sha", [""])[0]
                    if not SHA_RE.fullmatch(sha):
                        raise ValueError()
                    _local_state_after_activation(bridge, sha)
                    msg = "activated"
                elif action in ("import", "memory-card"):
                    if set(form) != {"action", "csrf"}:
                        raise ValueError()
                    result = (bridge.import_iso() if action == "import" else
                              bridge.select_memory_card())
                    msg = ("cancelled" if isinstance(result, dict) and
                           result.get("cancelled") else
                           ("imported" if action == "import" else "memory"))
                else:
                    raise ValueError()
            except (ValueError, UnicodeDecodeError, TypeError):
                self._json(400, {"error": "Solicitação inválida"})
                return
            except Exception:
                # Never include paths, private filenames or tracebacks.
                self._json(503, {"error": "Operação local indisponível"})
                return
            destination = ("/local/?tab=mods" if action in ("activate", "import")
                           else "/local/?tab=decks") + "&msg=" + msg
            self.send_response(303)
            self.send_header("Location", destination)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _auth(self):
            if not self._trusted():
                self._json(403, {"error": "Origem não autorizada"})
                return False
            bearer = self.headers.get("Authorization", "")
            if (not bearer.startswith("Bearer ") or
                    not hmac.compare_digest(
                        bearer[7:].encode("utf-8"), token_bytes)):
                self._json(401, {"error": "Connector não autorizado"})
                return False
            return True

        def do_OPTIONS(self):
            if not self._trusted():
                self._json(403, {"error": "Origem não autorizada"})
                return
            requested = self.headers.get(
                "Access-Control-Request-Headers", "").lower()
            if any(
                part.strip() not in ("authorization", "content-type")
                for part in requested.split(",") if part.strip()
            ):
                self._json(403, {"error": "Cabeçalho não permitido"})
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            uri = urlsplit(self.path)
            if uri.path in ("/", "/local", "/local/", "/local/art"):
                self._browser_html(uri)
                return
            if not self._auth():
                return
            query = parse_qs(uri.query, keep_blank_values=True)
            try:
                if uri.path == "/v1/state":
                    result = _local_state(bridge)
                elif uri.path == "/v1/fusions":
                    result = bridge.get_fusions(
                        query=_text_param(query, "query"),
                        offset=_int_param(query, "offset", 0, minimum=0, maximum=1000000),
                        limit=_int_param(query, "limit", 80, minimum=1, maximum=100),
                    )
                elif uri.path == "/v1/drops":
                    result = bridge.get_drops(
                        opponent_id=_int_param(query, "opponent", 0, minimum=0, maximum=39),
                        offset=0, limit=100, sort="id",
                    )
                elif uri.path == "/v1/opponents":
                    result = bridge.get_opponent_deck(
                        _int_param(query, "opponent", 0, minimum=0, maximum=39),
                    )
                elif uri.path == "/v1/decks":
                    result = bridge.get_deck_library(
                        _text_param(query, "deck", limit=90),
                    )
                elif uri.path == "/v1/live":
                    result = _local_live(bridge)
                elif uri.path == "/v1/art":
                    sha = _text_param(query, "sha", limit=64)
                    cid = _int_param(query, "id", 0, minimum=1, maximum=722)
                    data = _local_art(bridge, sha, cid)
                    if data is None:
                        self._json(404, {"error": "Arte não disponível"})
                        return
                    self._headers(200, content_type="image/png", length=len(data))
                    self.wfile.write(data)
                    return
                else:
                    self._json(404, {"error": "Rota não encontrada"})
                    return
                self._json(200, result)
            except (ValueError, TypeError):
                self._json(400, {"error": "Parâmetros inválidos"})
            except Exception:
                # Never expose local filesystem paths, memory or Python tracebacks.
                self._json(503, {"error": "Leitura local indisponível"})

        def do_POST(self):
            uri = urlsplit(self.path)
            if uri.path == "/local/action":
                self._browser_action()
                return
            if not self._auth():
                return
            if uri.path not in ("/v1/activate", "/v1/import", "/v1/memory-card"):
                self._json(404, {"error": "Rota não encontrada"})
                return
            try:
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0]
                count = int(self.headers.get("Content-Length", "-1"))
                if content_type != "application/json" or not 0 <= count <= MAX_BODY:
                    self._json(413, {"error": "Solicitação inválida"})
                    return
                body = json.loads(self.rfile.read(count))
                if not isinstance(body, dict):
                    raise ValueError()
                if uri.path == "/v1/activate":
                    sha = body.get("sha")
                    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
                        raise ValueError()
                    result = _local_state_after_activation(bridge, sha)
                elif uri.path == "/v1/import":
                    if set(body) != {"chooseLocalFile"} or body["chooseLocalFile"] is not True:
                        raise ValueError()
                    result = bridge.import_iso()
                    if isinstance(result, dict) and isinstance(result.get("mod"), dict):
                        mod = result["mod"]
                        result = {"cancelled":result.get("cancelled", False),
                                  "mod":{"sha256":mod.get("sha256"),
                                         "name":mod.get("name")}}
                else:
                    if set(body) != {"chooseLocalFile"} or body["chooseLocalFile"] is not True:
                        raise ValueError()
                    result = bridge.select_memory_card()
                    if isinstance(result, dict):
                        # Only the result, not the local file path, is returned.
                        result = {key:result.get(key) for key in (
                            "selected", "cancelled", "cardName",
                            "detectedSaveCount", "status")}
                self._json(200, result)
            except (ValueError, KeyError, TypeError):
                self._json(400, {"error": "Solicitação inválida"})
            except Exception:
                self._json(503, {"error": "Operação local indisponível"})

    return ConnectorHandler


def _local_state_after_activation(bridge, sha):
    # Explicit SHA-bound action; never accept a filesystem path from the site.
    if not any(x["sha256"] == sha for x in _local_state(bridge)["mods"]):
        raise ValueError("Mod não cadastrado")
    bridge.activate_mod(sha, acknowledge=True)
    return _local_state(bridge)


def create_server(bridge, *, allowed_origins, token, port=DEFAULT_PORT):
    handler = make_handler(
        bridge, allowed_origins=allowed_origins, token=token)
    server = http.server.ThreadingHTTPServer((HOST, port), handler)
    server.daemon_threads = True
    server.allow_reuse_address = True
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="DUELTRACE Cloud — local-first Windows Connector")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--browser", action="store_true",
                        help="Abrir automaticamente o painel local no navegador")
    parser.add_argument("--origin", action="append", default=[],
                        help="Origem HTTPS exata autorizada; repetível")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("A porta deve estar entre 1024 e 65535")
    allowed = DEV_ORIGINS | frozenset(args.origin)
    token = secrets.token_urlsafe(32)
    from dueltrace_web_bridge import DueltraceWebBridge
    bridge = DueltraceWebBridge(file_picker=_picker)
    with create_server(bridge, allowed_origins=allowed, token=token,
                       port=args.port) as server:
        print("\nDUELTRACE CLOUD CONNECTOR — dados somente no PC")
        print(f"Endereço: http://{HOST}:{server.server_port}")
        print(f"Chave temporária: {token}")
        if args.browser:
            print("Abrindo painel local no navegador (sem colar chave)...")
            webbrowser.open(f"http://{HOST}:{server.server_port}/local/")
        else:
            print("Para abrir o painel local sem chave, acesse:")
            print(f"http://{HOST}:{server.server_port}/local/")
        print("A chave é necessária somente para a interface Next.js experimental.")
        print("ISOs, Memory Cards e RAM não são enviados à nuvem.")
        try:
            server.serve_forever(poll_interval=.25)
        except KeyboardInterrupt:
            print("\nConexão encerrada.")
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
