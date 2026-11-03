"""Fail a Windows WebUI release when Tailwind utilities are not compiled.

The initial v0.7.0 ZIP included a CSS file but it contained raw @apply
directives and no .flex/.grid classes, causing unstyled text and huge SVGs.
"""
from __future__ import annotations
import http.server
import re
import sys
import threading
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]
WEB=ROOT/"web"/"out"

def verify_css() -> tuple[Path, bytes]:
    html=WEB/"index.html"
    if not html.is_file():
        raise RuntimeError("Next.js static HTML missing.")
    source=html.read_text("utf-8")
    match=re.search(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+\.css)"',source)
    if not match:
        raise RuntimeError("No CSS stylesheet referenced in index.html.")
    url=match.group(1)
    if not url.startswith("/_next/static/") or ".." in url:
        raise RuntimeError("Unexpected stylesheet URL.")
    file=WEB/url.lstrip("/")
    if not file.is_file():
        raise RuntimeError(f"Referenced CSS file missing: {url}")
    data=file.read_bytes()
    css=data.decode("utf-8")
    if len(data) < 15000:
        raise RuntimeError(f"CSS suspiciously short ({len(data)} bytes); Tailwind probably not compiled.")
    if re.search(r"@(?:apply|theme)\b",css):
        raise RuntimeError("Uncompiled Tailwind @apply/@theme in shipped CSS.")
    for klass in ("flex","grid","relative","rounded-xl","text-gold","bg-background"):
        name=re.escape(klass)
        if not re.search(r"\."+name+r"\s*[{,:]",css):
            raise RuntimeError(f"Tailwind utility missing from shipped CSS: {klass}")
    return file,data

def verify_local_http(file:Path, expected:bytes) -> None:
    sys.path.insert(0,str(ROOT/"scanner"))
    from dueltrace_web_desktop import local_handler
    handler=local_handler(WEB,object())
    server=http.server.ThreadingHTTPServer(("127.0.0.1",0),handler)
    server.daemon_threads=True
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        endpoint=f"http://127.0.0.1:{server.server_port}/"+str(file.relative_to(WEB)).replace("\\","/")
        with urlopen(endpoint,timeout=10) as response:
            received=response.read()
            content_type=response.headers.get("Content-Type","")
            if response.status != 200 or "text/css" not in content_type:
                raise RuntimeError(f"CSS HTTP returned {response.status}: {content_type}")
            if received != expected:
                raise RuntimeError("Local HTTP CSS payload differs from built CSS file.")
    finally:
        server.shutdown()
        server.server_close()

if __name__=="__main__":
    file,data=verify_css()
    verify_local_http(file,data)
    print(f"OK: Tailwind compiled and served correctly: {file.name} ({len(data):,} bytes)")
