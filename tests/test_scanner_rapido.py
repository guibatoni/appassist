"""Teste da leitura otimizada de CD-ROM e análise sem hashes repetidos.

Dados sintéticos; nenhuma ISO comercial é distribuída.
"""
from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from scanner_multiiso import Disc, sha256, process


class ScannerSpeedTests(unittest.TestCase):
    @staticmethod
    def image(sector,offset,n=32):
        logical=[bytes(((i+j*7)%256 for i in range(2048))) for j in range(n)]
        if sector==2048:
            raw=b"".join(logical)
        else:
            raw=b"".join(b"X"*offset+part+b"Z"*(sector-offset-2048) for part in logical)
        disc=Disc.__new__(Disc)
        disc.f=io.BytesIO(raw)
        disc.sector=sector
        disc.offset=offset
        disc.size=len(raw)
        disc.files={"WA_MRG.MRG":(3,18000)}
        return disc,b"".join(logical)

    def test_raw_mode2_multiple_blocks(self):
        disc,logical=self.image(2352,24,64)
        self.assertEqual(disc.read(0,64*2048),logical)
        self.assertEqual(disc.read(3,10001),logical[3*2048:3*2048+10001])
        with self.assertRaises(ValueError):
            disc.read(63,4096)

    def test_raw_mode1(self):
        disc,logical=self.image(2352,16)
        self.assertEqual(disc.read(0,17*2048+100),logical[:17*2048+100])

    def test_2048_sectors(self):
        disc,logical=self.image(2048,0)
        self.assertEqual(disc.read(0,15*2048+33),logical[:15*2048+33])

    def test_get_only_needed_prefix(self):
        disc,logical=self.image(2352,24)
        self.assertEqual(disc.get("wa_mrg.mrg",limit_bytes=2500),
                         logical[3*2048:3*2048+2500])

    def test_single_stream_hash_with_callback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"data.bin"
            data=b"A"*3000000
            path.write_bytes(data)
            calls=[]
            result=sha256(path,progress=lambda stage,done,total:calls.append((stage,done,total)))
            self.assertEqual(result,hashlib.sha256(data).hexdigest())
            self.assertTrue(calls)
            self.assertEqual(calls[-1][1:],(len(data),len(data)))

    def test_process_does_not_rehash_when_digest_provided(self):
        class FakeDisc:
            def __init__(self,p):
                self.sector=2352
                self.files={"SLUS_014.11":(10,3000000),
                            "WA_MRG.MRG":(120,64*1024*1024)}
                self.limit=None
            def get(self,name,limit_bytes=None):
                if name=="WA_MRG.MRG":
                    self.limit=limit_bytes
                    self_obj["disc"]=self
                    return b"x"*64
                return b"exe"
            def close(self):pass
        self_obj={}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"test.iso"
            path.write_bytes(b"tiny synthetic header")
            out=Path(tmp)/"out"
            with patch("scanner_multiiso.sha256",side_effect=AssertionError("digest unexpectedly repeated")),\
                 patch("scanner_multiiso.Disc",FakeDisc),\
                 patch("scanner_multiiso.decode_names",return_value=([],[],"estruturas desconhecidas")) ,\
                 patch("scanner_multiiso.decode_drops",return_value=(None,"não validado")):
                info=process(path,out,digest="a"*64)
            self.assertEqual(info["sha256"],"a"*64)
            self.assertIsNone(info["hash_wa"])
            self.assertIsNone(self_obj["disc"].limit)
            # A busca de RANK exige o WA inteiro; o mock oferece só
            # 64 bytes, portanto o SHA integral não é atribuído.
            self.assertEqual(info["wa_total_bytes"],64*1024*1024)
            self.assertFalse(info["wa_lido_integralmente"])


if __name__=="__main__":
    unittest.main()
