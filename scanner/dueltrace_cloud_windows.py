"""Windows GUI launcher for the DUELTRACE local Chrome Connector.

PyInstaller --onedir packages the existing engine and the no-JS local UI.
The user does not need Node.js, Python, a PowerShell prompt or a pairing key.
The application binds only 127.0.0.1 and never transfers game files online.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from pathlib import Path

from dueltrace_cloud_connector import DEFAULT_PORT, HOST, DEV_ORIGINS, create_server


LOCAL_URL = f"http://{HOST}:{DEFAULT_PORT}/local/"


def chrome_candidates():
    """Only fixed, local Windows Chrome install locations; no shell execution."""
    seen = set()
    folders = (
        os.environ.get("PROGRAMFILES", ""),
        os.environ.get("PROGRAMFILES(X86)", ""),
        os.environ.get("LOCALAPPDATA", ""),
    )
    for folder in folders:
        if folder:
            path = Path(folder) / "Google" / "Chrome" / "Application" / "chrome.exe"
            value = str(path)
            if value.lower() not in seen:
                seen.add(value.lower())
                yield path
    if sys.platform == "win32":
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                        entry, _ = winreg.QueryValueEx(key, None)
                        value = str(entry).strip('"')
                        if value.lower() not in seen:
                            seen.add(value.lower())
                            yield Path(value)
                except OSError:
                    pass
        except ImportError:
            pass


def open_local_chrome(url=LOCAL_URL):
    """Prefer Chrome; fall back to the user's default browser."""
    if not url.startswith(f"http://{HOST}:") or not url.endswith("/local/"):
        raise ValueError("Endereço do Connector inválido")
    for path in chrome_candidates():
        if path.is_file():
            try:
                subprocess.Popen([str(path), "--new-window", url],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, close_fds=True)
                return "Chrome"
            except OSError:
                continue
    return "navegador padrão" if webbrowser.open(url) else "não abriu"


class UiFilePicker:
    """Marshal native file dialogs to Tk's UI thread (not HTTP worker threads)."""
    def __init__(self, root):
        self.root = root
        self.jobs = queue.Queue()
        self.closed = False
        self.root.after(100, self.poll)

    def pick(self, kind):
        if self.closed:
            return ()
        done = threading.Event()
        box = {"path": ()}
        self.jobs.put((kind, done, box))
        if done.wait(300):
            return box["path"]
        return ()

    def poll(self):
        if self.closed:
            return
        try:
            from tkinter import filedialog
            while True:
                kind, done, box = self.jobs.get_nowait()
                try:
                    if kind == "iso":
                        filters = [("ISO/BIN do jogo", "*.iso *.bin")]
                    elif kind == "memory_card":
                        filters = [("Memory Card PS1", "*.mcr *.mcd *.mc *.srm *.mem *.vm1")]
                    else:
                        raise ValueError("Arquivo não suportado")
                    name = filedialog.askopenfilename(
                        parent=self.root, title="DUELTRACE — selecionar arquivo local",
                        filetypes=filters)
                    box["path"] = (name,) if name else ()
                except Exception:
                    box["path"] = ()
                finally:
                    done.set()
        except queue.Empty:
            pass
        if not self.closed:
            self.root.after(100, self.poll)

    def shutdown(self):
        self.closed = True
        while True:
            try:
                _, done, _ = self.jobs.get_nowait()
                done.set()
            except queue.Empty:
                break


def runtime_smoke_test():
    """Check frozen engine imports and the local HTML response without a browser."""
    from dueltrace_web_bridge import DueltraceWebBridge
    bridge = DueltraceWebBridge(file_picker=lambda _kind: ())
    server = create_server(bridge, allowed_origins=DEV_ORIGINS,
                           token="smoke-test-" + "s" * 40, port=0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f"http://{HOST}:{server.server_port}/local/"
        with urllib.request.urlopen(url, timeout=15) as response:
            page = response.read()
            return (response.status == 200 and b"DUELTRACE Cloud" in page
                    and b"v0.5.0" in page and b"<script" not in page.lower())
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def run_window():
    import tkinter as tk
    from tkinter import messagebox
    from dueltrace_web_bridge import DueltraceWebBridge

    root = tk.Tk()
    root.title("DUELTRACE Connector — Chrome")
    root.geometry("510x310")
    root.minsize(470, 285)
    root.configure(background="#061126")
    try:
        root.iconbitmap(default="")
    except (OSError, tk.TclError):
        pass
    fg, muted, gold, cyan = "#e6f0ff", "#9cb0ce", "#f5b83d", "#7fe3ff"

    tk.Label(root, text="DUELTRACE", font=("Segoe UI", 24, "bold italic"),
             fg=fg, bg="#061126").pack(pady=(21, 1))
    tk.Label(root, text="MultiMod Companion  ·  Connector local",
             font=("Segoe UI", 10), fg=gold, bg="#061126").pack()
    status = tk.StringVar(value="Iniciando serviço local...")
    tk.Label(root, textvariable=status, font=("Segoe UI", 11, "bold"),
             fg=cyan, bg="#061126", wraplength=460).pack(pady=(19, 8))
    tk.Label(root, text=LOCAL_URL, fg=muted, bg="#061126",
             font=("Consolas", 10)).pack(pady=2)
    tk.Label(root, text="ISOs, Memory Cards e RAM permanecem no computador.",
             fg=muted, bg="#061126", font=("Segoe UI", 9)).pack(pady=(10, 9))

    picker = UiFilePicker(root)
    messages = queue.Queue()
    running = {"server": None, "closing": False, "ready": False}

    def open_browser():
        if not running["ready"]:
            messagebox.showwarning("DUELTRACE", "O Connector ainda não está pronto.")
            return
        try:
            browser = open_local_chrome()
            if browser == "não abriu":
                status.set("Abra manualmente " + LOCAL_URL)
        except Exception:
            status.set("Abra manualmente " + LOCAL_URL)

    button = tk.Button(root, text="Abrir DUELTRACE no Chrome", command=open_browser,
                       bg="#20496c", fg=fg, activebackground="#2a719a",
                       activeforeground="#ffffff", font=("Segoe UI", 11, "bold"),
                       padx=16, pady=8, relief="flat", state="disabled")
    button.pack(pady=6)

    def start_server():
        server = None
        try:
            bridge = DueltraceWebBridge(file_picker=picker.pick)
            # Port remains fixed so desktop links and browser bookmarks work.
            server = create_server(bridge, allowed_origins=DEV_ORIGINS,
                                   token=__import__("secrets").token_urlsafe(32),
                                   port=DEFAULT_PORT)
            running["server"] = server
            messages.put(("ready", None))
            server.serve_forever(poll_interval=.25)
        except OSError:
            messages.put(("error", "A porta 8765 já está em uso. Feche outro Connector antes de abrir este."))
        except Exception:
            messages.put(("error", "Não foi possível iniciar o motor local. Verifique a instalação."))
        finally:
            if server:
                server.server_close()

    def poll_messages():
        if running["closing"]:
            return
        try:
            while True:
                kind, info = messages.get_nowait()
                if kind == "ready":
                    running["ready"] = True
                    status.set("Conectado · serviço local ativo")
                    button.configure(state="normal")
                    # Auto-open once after the server confirms readiness.
                    root.after(180, open_browser)
                elif kind == "error":
                    status.set(info)
                    button.configure(state="disabled")
        except queue.Empty:
            pass
        root.after(120, poll_messages)

    def close_window():
        running["closing"] = True
        picker.shutdown()
        server = running["server"]
        if server is not None:
            # Avoid blocking the UI while existing HTTP requests exit.
            threading.Thread(target=server.shutdown, daemon=True).start()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_window)
    threading.Thread(target=start_server, name="dueltrace-local-http", daemon=True).start()
    poll_messages()
    root.mainloop()


def main():
    if "--self-test" in sys.argv:
        try:
            return 0 if runtime_smoke_test() else 1
        except Exception:
            return 1
    run_window()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
