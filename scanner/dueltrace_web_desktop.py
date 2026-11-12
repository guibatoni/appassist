"""DUELTRACE Desktop WebUI: interface v0 local e motor Python existente.

Execução apenas Windows. O servidor entrega SOMENTE assets Next.js compilados
e PNGs explicitamente autorizados pelo perfil ativo. Comandos privilegiados
passam por pywebview JS API na janela local; não existe rota HTTP de escrita.
"""
from __future__ import annotations

import http.server
import json
import secrets
import re
import sys
import threading
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_web_security import ProtectedDesktopApi
from dueltrace_native_resize import enable_native_edge_resize
from dueltrace_display_layout import (
    window_geometry, tool_geometry, windows_work_area,
)

ART_PATTERN=re.compile(r"^/__art__/([0-9a-f]{64})/([0-9]{1,3})\.png$")
ART_HD_PATTERN=re.compile(r"^/__art_hd__/([0-9a-f]{64})/([0-9]{1,3})\.png$")
CARD_PATTERN=re.compile(r"^/__card__/([0-9a-f]{64})/([0-9]{1,3})\.png$")
CLASSIC_CARD_PATTERN=re.compile(r"^/__card_hd__/([0-9a-f]{64})/([0-9]{1,3})\.png$")


def trusted_window_url(current_url: str | None, base_url: str) -> bool:
    """A capacidade JS só pode ser injetada na porta desta execução."""
    if not isinstance(current_url,str) or not current_url:
        return False
    try:
        current=urlsplit(current_url)
        base=urlsplit(base_url)
        return (current.scheme==base.scheme=="http"
                and current.hostname==base.hostname=="127.0.0.1"
                and current.port==base.port
                and not current.username and not current.password
                and not current.fragment)
    except ValueError:
        return False


def assets_path() -> Path:
    base=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent.parent))
    candidates=(base/"web"/"out",base/"out",base.parent/"web"/"out")
    for path in candidates:
        if (path/"index.html").is_file():
            return path.resolve()
    raise FileNotFoundError(
        "Interface web não compilada. Execute 'npm run build' dentro da pasta web "
        "ou use o executável Windows que inclui os arquivos estáticos.")


def local_handler(directory: Path, bridge: DueltraceWebBridge):
    """Servidor restrito ao 127.0.0.1 com caminhos sanitizados."""
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,directory=str(directory),**kwargs)

        def log_message(self,format,*args):
            return  # não escreve nomes de mods nem páginas em console

        def _valid_path(self):
            """Aceita somente requisições locais com Host exato.

            Reduz ataques de DNS rebinding, caminhos parent e acesso cross-site.
            """
            expected=f"127.0.0.1:{self.server.server_port}"
            host=self.headers.get("Host","")
            if (self.client_address[0]!="127.0.0.1" or
                    host.lower()!=expected or
                    self.headers.get("Sec-Fetch-Site","").lower()=="cross-site"):
                self.send_error(403,"Origem não autorizada")
                return None
            origin=self.headers.get("Origin")
            if origin and origin!=f"http://{expected}":
                self.send_error(403,"Origin não autorizado")
                return None
            parsed=urlsplit(self.path)
            raw=parsed.path
            decoded=unquote(raw)
            parts=decoded.split("/")
            if (parsed.scheme or parsed.netloc or self.path.startswith("//") or
                    not decoded.startswith("/") or decoded.startswith("//") or
                    "\\" in decoded or "\x00" in decoded or
                    unquote(decoded)!=decoded or
                    any(part.startswith(".") for part in parts[1:] if part) or
                    any(part=="" for part in parts[1:-1])):
                self.send_error(403,"Caminho local inválido")
                return None
            return decoded

        def do_POST(self):
            self.send_error(405,"Apenas conteúdo estático")

        def do_HEAD(self):
            clean=self._valid_path()
            if clean is None:
                return
            if clean.startswith(("/__art__/","/__art_hd__/","/__card__/","/__card_hd__/")):
                self.send_error(405,"Operação não suportada")
                return
            return super().do_HEAD()

        def send_head(self):
            # Bloqueia symlinks para fora da árvore estática e listagem de pastas.
            try:
                target=Path(self.translate_path(self.path)).resolve()
                if not target.is_relative_to(directory.resolve()):
                    self.send_error(403,"Arquivo fora do diretório estático")
                    return None
                if target.is_dir() and not (target/"index.html").is_file():
                    self.send_error(403,"Listagem de diretório bloqueada")
                    return None
            except (OSError,ValueError):
                self.send_error(404,"Recurso não encontrado")
                return None
            return super().send_head()

        def list_directory(self, path):
            self.send_error(403,"Listagem de diretório desativada")
            return None

        def do_GET(self):
            clean=self._valid_path()
            if clean is None:
                return
            raw_match=ART_PATTERN.fullmatch(clean)
            hd_match=ART_HD_PATTERN.fullmatch(clean)
            composite_match=CARD_PATTERN.fullmatch(clean)
            classic_match=CLASSIC_CARD_PATTERN.fullmatch(clean)
            match=raw_match or hd_match or composite_match or classic_match
            if clean.startswith(("/__art__/","/__art_hd__/","/__card__/","/__card_hd__/")) and match is None:
                self.send_error(404,"Imagem não encontrada")
                return
            if match:
                sha,cid=match.groups()
                try:
                    active,entry,profile=bridge._active()
                    if (not profile or active.get("sha256")!=sha or
                            not profile.get("supported_features",{}).get("art")):
                        self.send_error(404)
                        return
                    root=Path(profile["scan_result_dir"]).resolve(strict=True)
                    allowed=(bridge.catalog.home/"analises").resolve(strict=True)
                    if not root.is_relative_to(allowed):
                        self.send_error(404)
                        return
                    if composite_match and not profile.get("supported_features",{}).get("composed_cards"):
                        self.send_error(404)
                        return
                    folder=("cartas_classicas_hd" if classic_match else
                            "cartas_com_moldura" if composite_match else
                            "artes_upscaled" if hd_match else "artes_722")
                    if classic_match:
                        # Gera automaticamente a carta NOVA quando não existe,
                        # ou o cache antigo não corresponde ao perfil da ISO.
                        from dueltrace_card_on_demand import ensure_card_hd
                        card=next((row for row in profile.get("cards",[])
                                   if row.get("id")==int(cid)),None)
                        fallback=(root/folder/f"{int(cid):03d}.png")
                        if card is not None:
                            try:
                                image=ensure_card_hd(root,card,rom_sha256=sha)
                            except (OSError, ValueError):
                                # Preserve existing valid, SHA-bound cached art
                                # when an old profile has no usable source PNG.
                                image=fallback.resolve(strict=True)
                        else:
                            image=fallback.resolve(strict=True)
                    else:
                        image=(root/folder/f"{int(cid):03d}.png").resolve(strict=True)
                    max_size=8_000_000 if classic_match else 4_000_000 if hd_match else 1_000_000
                    if not image.is_relative_to(root) or image.stat().st_size>max_size:
                        self.send_error(404)
                        return
                    body=image.read_bytes()
                except (OSError,KeyError,ValueError,TypeError):
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type","image/png")
                self.send_header("Content-Length",str(len(body)))
                self.send_header("Cache-Control","private, no-store")
                self.end_headers()
                self.wfile.write(body)
                return

            # Next export com trailingSlash cria /biblioteca/index.html.
            if clean != "/" and not Path(clean).suffix and not clean.endswith("/"):
                self.send_response(308)
                self.send_header("Location",clean+"/")
                self.end_headers()
                return
            return super().do_GET()

        def end_headers(self):
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("X-Frame-Options","DENY")
            self.send_header("Referrer-Policy","no-referrer")
            self.send_header("Cross-Origin-Resource-Policy","same-origin")
            self.send_header("Permissions-Policy",
                             "camera=(), microphone=(), geolocation=(), payment=()")
            self.send_header("Content-Security-Policy",
                "default-src 'none'; base-uri 'none'; form-action 'none'; "
                "frame-ancestors 'none'; object-src 'none'; frame-src 'none'; "
                "navigate-to 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; font-src 'self' data:; connect-src 'self'")
            super().end_headers()

    return Handler


def main():
    if sys.platform!="win32":
        raise OSError("A interface desktop nativa está disponível apenas no Windows.")
    import webview

    # A native Win32 caption loop performs the entire drag on the WinForms UI
    # thread; WebView2 pointermove loses capture when the form moves.
    work_width,work_height=windows_work_area()
    main_size=window_geometry(work_width,work_height)
    static=assets_path()
    bridge=DueltraceWebBridge()
    token=secrets.token_urlsafe(32)
    api=ProtectedDesktopApi(bridge,token)
    handler=local_handler(static,bridge)
    server=http.server.ThreadingHTTPServer(("127.0.0.1",0),handler)
    server.daemon_threads=True
    server_thread=threading.Thread(target=server.serve_forever,
                                   name="dueltrace-ui-assets",daemon=True)
    server_thread.start()
    url=f"http://127.0.0.1:{server.server_port}/"
    try:
        window=webview.create_window(
            "DUELTRACE — MultiMod Companion",
            url=url,js_api=api,
            width=main_size["width"],height=main_size["height"],
            min_size=(main_size["min_width"],main_size["min_height"]),
            background_color="#040a1a",
            frameless=True,easy_drag=False,resizable=True)
        if window is None:
            raise RuntimeError("Não foi possível criar a janela do DUELTRACE.")
        # pywebview WinForms 6.x removes the native resize frame when
        # frameless=True. Restore WS_THICKFRAME after the form is shown:
        # Windows handles the four edges and corners, without a title bar.
        # No HWND/system call is exposed to the browser.
        def restore_resize_border():
            enable_native_edge_resize(window)
        window.events.shown+=restore_resize_border
        # The local authenticated API starts the native Win32 caption drag.
        # Only the already attached main window can be moved.
        api._native_window=window
        def mark_maximized():
            with api._native_window_lock:
                api._native_maximized=True
        def mark_restored():
            with api._native_window_lock:
                api._native_maximized=False
        window.events.maximized+=mark_maximized
        window.events.restored+=mark_restored
        def secure_loaded(window):
            current=window.get_current_url()
            if current in ("about:blank", "", None):
                # A secondary window is born blank before its trusted route.
                return
            if trusted_window_url(current,url):
                # Uma navegação externa cria outro contexto JS e não recebe token.
                script=("Object.defineProperty(window,'__DUELTRACE_TOKEN__', "
                        +json.dumps({"value":token,"writable":False,
                                     "configurable":False,"enumerable":False})
                        +")")
                window.run_js(script)
            else:
                # Recupera a interface se alguma ação tentar sair da origem local.
                window.load_url(url)
        window.events.loaded+=secure_loaded
        tool_windows={}
        tool_windows_lock=threading.RLock()
        tool_routes={
            "calculadora":("RANK ao vivo — DUELTRACE",390,280),
            "fusoes":("Dicas de fusões — DUELTRACE",440,600),
        }
        def open_tool_window(kind):
            # The native JS API already checked the exact allowlisted kind.
            title,width,height=tool_routes[kind]
            tool_size=tool_geometry(
                work_width,work_height,width,height,
                min_width=330 if kind=="calculadora" else 380,
                min_height=230 if kind=="calculadora" else 380)
            with tool_windows_lock:
                existing=tool_windows.get(kind)
                if existing is not None:
                    try:
                        existing.restore()
                        existing.show()
                        return {"opened":True,"reused":True,"kind":kind}
                    except (OSError,RuntimeError):
                        tool_windows.pop(kind,None)
                child=webview.create_window(
                    title,
                    url="about:blank",
                    js_api=api,width=tool_size["width"],height=tool_size["height"],
                    min_size=tool_size["min_size"],resizable=True,
                    on_top=True,background_color="#040a1a",
                    frameless=False)
                child.events.loaded+=secure_loaded
                # Attach security handler BEFORE loading the trusted page;
                # otherwise a fast WebView2 first navigation can miss token.
                child.load_url(url+"ferramentas/"+kind+"/")
                def forget_child():
                    with tool_windows_lock:
                        if tool_windows.get(kind) is child:
                            tool_windows.pop(kind,None)
                child.events.closed+=forget_child
                tool_windows[kind]=child
                return {"opened":True,"reused":False,"kind":kind}

        def close_tool_window(kind):
            with tool_windows_lock:
                child=tool_windows.pop(kind,None)
            if child is None:
                return {"closed":True,"kind":kind}
            # Reply must arrive before destroying the calling WebView.
            def close_after_response():
                time.sleep(0.25)
                try:
                    child.destroy()
                except (OSError,RuntimeError):
                    pass
            threading.Thread(target=close_after_response,daemon=True,
                             name="dueltrace-tool-close").start()
            return {"closed":True,"kind":kind}
        api._tool_window_open=open_tool_window
        api._tool_window_close=close_tool_window

        def pick_file(kind):
            if kind=="rank_report":
                return window.create_file_dialog(
                    webview.FileDialog.SAVE,
                    save_filename="DUELTRACE-RANK-EVIDENCE.json",
                    file_types=("JSON (*.json)",))
            file_types=(
                ("Imagens de jogo (*.iso;*.bin)",)
                if kind=="iso" else
                ("Log MIPS de duelo (*.log;*.txt)",) if kind=="trace" else
                ("Executável ePSXe (*.exe)",))
            return window.create_file_dialog(
                webview.FileDialog.OPEN,allow_multiple=False,
                file_types=file_types)
        bridge._file_picker=pick_file
        def close_for_update():
            # Resposta JS é entregue antes de destruir a janela; helper externo
            # espera a saída do processo para substituir arquivos bloqueados.
            def shutdown():
                time.sleep(1.5)
                window.destroy()
            threading.Thread(target=shutdown,daemon=True).start()
        bridge._request_shutdown=close_for_update
        webview.start(debug=False,private_mode=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__=="__main__":
    main()
