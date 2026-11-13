"""PCSX-Redux Windows integration regressions.

Synthetic HTTP and RAM only. No BIOS, ISO, real emulator or write request.
These tests validate the API contract and fail-closed behavior, not a claim
that all historic PCSX-Redux versions were exercised on a gaming PC.
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from dueltrace_pcsx_redux import (
    DEFAULT_PORT,RAM_2MB,RAM_8MB,HAND_BYTES,HAND_OFFSET,X15_RANK_OFFSET,
    _fetch,_PENDING,_CONFIRMED,connection_status,read_hand_from_redux,
    read_rank_candidate_redux,is_redux_process_name,valid_port,
)
from pcsx_redux_launcher import command_for_redux,launch_redux


def make_ram(ids=(449,145,447,629,468),*, megabytes=2):
    raw=bytearray(megabytes*1024*1024)
    for slot,cid in enumerate(ids):
        pos=HAND_OFFSET+slot*28
        struct.pack_into("<H",raw,pos,cid)
        struct.pack_into("<I",raw,pos+12,slot)
    # Hypothetical X15 rank record, separate from known hand.
    at=X15_RANK_OFFSET
    raw[at+1]=4  # turns
    raw[at+2]=2  # attacks
    raw[at+8]=1  # fusions
    raw[at+24]=5 # cards used
    struct.pack_into("<h",raw,at+20,7300)
    return bytes(raw)


class ReduxFixture:
    def __init__(self,ram=None,*,running=True):
        self.ram=ram if ram is not None else make_ram()
        self.running=running
        self.requests=[]
    def __call__(self,path,*,port,limit):
        self.requests.append((path,port,limit))
        if path=="/api/v1/execution-flow":
            return json.dumps({"running":self.running,"isDynarec":False,"8mb":False}).encode()
        if path=="/api/v1/cpu/ram/raw":
            return self.ram
        raise AssertionError("Unexpected HTTP route")


class ReduxHttpHandler(BaseHTTPRequestHandler):
    ram=make_ram()
    requests=[]
    redirect=False
    def do_GET(self):
        type(self).requests.append(("GET",self.path))
        if type(self).redirect:
            self.send_response(302);self.send_header("Location","http://example.org/evil")
            self.end_headers();return
        if self.path=="/api/v1/execution-flow":
            raw=b'{"running":true,"isDynarec":true,"8mb":false}'
            content_type="application/json"
        elif self.path=="/api/v1/cpu/ram/raw":
            raw=type(self).ram;content_type="application/octet-stream"
        else:
            self.send_response(404);self.end_headers();return
        self.send_response(200)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_POST(self):
        type(self).requests.append(("POST",self.path))
        self.send_response(405);self.end_headers()
    def log_message(self,*args): pass


class ReduxAdapterTests(unittest.TestCase):
    def setUp(self):
        _PENDING.clear()
        _CONFIRMED.clear()

    def test_accepts_emulator_version_styles_not_other_processes(self):
        for s in ("pcsx-redux.exe","PCSX-REDUX.EXE","pcsx-redux.main",
                  "pcsx-redux-2026.11.exe","pcsx-redux-v2.0.exe",
                  "pcsx-redux_2024-12_win64.exe"):
            with self.subTest(s=s):self.assertTrue(is_redux_process_name(s))
        for s in ("epsxe.exe","pcsx2.exe","random.exe","pcsx-redux.dll",
                  "pcsx-redux.exe.bak","C:/pcsx-redux.exe","pcsx-redux-evil.exe",
                  "",None):
            with self.subTest(s=s):self.assertFalse(is_redux_process_name(s))

    def test_fixed_api_and_port_validation_no_external_http(self):
        self.assertEqual(valid_port(8080),8080)
        for invalid in (0,80,1023,65536,"8080",None,True,-1):
            with self.subTest(port=invalid):
                with self.assertRaises(ValueError):valid_port(invalid)
        with self.assertRaises(ValueError):
            _fetch("/api/v1/cpu/ram/raw?offset=0",port=8080)
        with self.assertRaises(ValueError):
            _fetch("http://evil.com/",port=8080)

    def test_read_only_real_http_fixture_never_requests_mutation(self):
        server=ThreadingHTTPServer(("127.0.0.1",0),ReduxHttpHandler)
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        ReduxHttpHandler.requests=[]
        ReduxHttpHandler.redirect=False
        worker.start()
        try:
            port=server.server_port
            self.assertEqual(json.loads(_fetch("/api/v1/execution-flow",port=port,limit=32768))["running"],True)
            self.assertEqual(_fetch("/api/v1/cpu/ram/raw",port=port),ReduxHttpHandler.ram)
            self.assertEqual([method for method,_ in ReduxHttpHandler.requests],["GET","GET"])
            ReduxHttpHandler.redirect=True
            with self.assertRaises(Exception):
                _fetch("/api/v1/execution-flow",port=port,limit=32768)
        finally:
            ReduxHttpHandler.redirect=False
            server.shutdown();server.server_close();worker.join(timeout=3)

    def test_redux_hand_needs_real_card_transition_across_polls(self):
        fixture=ReduxFixture()
        kwargs={"fetch":fixture,"port":8080,"pids":[1520],"monotonic":lambda:100.0}
        a=read_hand_from_redux(**kwargs)
        self.assertFalse(a["ready"])
        self.assertEqual(a["pid"],1520)
        b=read_hand_from_redux(**kwargs)
        self.assertFalse(b["ready"]) # stable copy does not prove live hand
        fixture.ram=make_ram((461,16,635,10,123))
        c=read_hand_from_redux(**kwargs)
        self.assertTrue(c["ready"])
        self.assertEqual(c["hand_ids"],[461,16,635,10,123])
        self.assertEqual(c["ramLayout"],"ps1-physical")
        self.assertTrue(all(r[0].startswith("/api/v1/") for r in fixture.requests))

    def test_redux_handles_paused_and_unmapped_or_invalid_hand(self):
        fixture=ReduxFixture(running=False)
        sample=read_hand_from_redux(fetch=fixture,pids=[1520])
        self.assertFalse(sample["ready"])
        self.assertIn("pausado",sample["status"])
        fixture.running=True
        fixture.ram=bytes(RAM_2MB)
        sample=read_hand_from_redux(fetch=fixture,pids=[1520])
        self.assertFalse(sample["ready"])
        fixture.ram=bytes(8192)
        sample=read_hand_from_redux(fetch=fixture,pids=[1520])
        self.assertFalse(sample["ready"])
        self.assertIn("indisponíveis",sample["status"])

    def test_multiple_instances_are_not_silently_mapped(self):
        fixture=ReduxFixture()
        sample=read_hand_from_redux(fetch=fixture,pids=[12,13])
        self.assertFalse(sample["ready"])
        self.assertEqual(fixture.requests,[])
        self.assertFalse(connection_status(fetch=fixture,pids=[12,13])["available"])
        self.assertTrue(connection_status(fetch=fixture,pids=[12])["available"])

    def test_8mb_expansion_supported(self):
        fixture=ReduxFixture(make_ram(megabytes=8))
        a=read_hand_from_redux(fetch=fixture,pids=[313])
        self.assertFalse(a["ready"])
        fixture.ram=make_ram((461,16,635,10,123),megabytes=8)
        b=read_hand_from_redux(fetch=fixture,pids=[313])
        self.assertTrue(b["ready"])

    def test_rank_x15_candidate_requires_structural_record(self):
        fixture=ReduxFixture()
        rank=read_rank_candidate_redux(fetch=fixture,pids=[313])
        self.assertTrue(rank["ready"])
        self.assertEqual(rank["pid"],313)
        self.assertEqual(rank["counters"]["remaining_lp"],7300)
        self.assertEqual(rank["counters"]["turns"],4)
        fixture.ram=bytes(RAM_2MB)
        self.assertFalse(read_rank_candidate_redux(fetch=fixture,pids=[313])["ready"])

    def test_safe_launch_command_contains_no_webserver_or_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            exe=path/"pcsx-redux.exe"
            iso=path/"mod.iso"
            exe.write_bytes(b"fake test binary")
            iso.write_bytes(b"x"*110000)
            cmd,cwd=command_for_redux(exe,iso)
            self.assertEqual(cmd,[str(exe.resolve()),"-iso",str(iso.resolve()),"-run"])
            self.assertEqual(cwd,path.resolve())
            self.assertNotIn("-webserver",cmd)
            catalog=Mock()
            catalog.current.return_value={"sha256":"a"*64}
            catalog.list.return_value=[{"sha256":"a"*64,
                "source_path":str(iso),"size":iso.stat().st_size,
                "mtime_ns":iso.stat().st_mtime_ns}]
            catalog.profile_for.return_value={"cards":[]}
            created=Mock()
            launch_redux(catalog,exe,"a"*64,popen=created,platform="win32")
            self.assertEqual(created.call_args.kwargs["shell"],False)
            self.assertNotIn("-webserver",created.call_args.args[0])
            with self.assertRaises(PermissionError):
                launch_redux(catalog,exe,"b"*64,popen=created,platform="win32")


if __name__=="__main__":
    unittest.main()
