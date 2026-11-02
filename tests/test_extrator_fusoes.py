"""Testes do formato de fusões (bancos sintéticos, nenhuma ROM real)."""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from extrator_fusoes import (
    BLOCK_SIZE, MIN_INDEX_SIZE, FUSION_BANK_OFFSETS,
    FusionFormatError, decode_bank, analyze_fusion_banks, save_fusion_report
)
from auto_mods import ModCatalog, atomic_json, supported_for_runtime


def make_bank(*, change_first=False):
    """40 cartas com 2 fusões cada = 80 receitas válidas no formato WA."""
    data=bytearray(BLOCK_SIZE)
    pos=MIN_INDEX_SIZE
    for a in range(1,41):
        struct.pack_into("<H",data,2+(a-1)*2,pos)
        b1=100+a
        r1=200+a+(1 if change_first and a==1 else 0)
        b2=300+a
        r2=400+a
        # ID <= 255 para b1/r1; demais IDs usam bits altos n3.
        flags=((b1>>8)&3)|(((r1>>8)&3)<<2)|(((b2>>8)&3)<<4)|(((r2>>8)&3)<<6)
        data[pos:pos+6]=bytes([2,flags,b1&255,r1&255,b2&255,r2&255])
        pos+=6
    return bytes(data)


class FakeDisc:
    prefix=None
    def __init__(self,path):
        self.files={"WA_MRG.MRG":(1,len(self.prefix))}
    def get(self,name,limit_bytes=None):
        assert name=="WA_MRG.MRG"
        return self.prefix[:limit_bytes]
    def close(self):
        pass


class FusionBankTests(unittest.TestCase):
    def test_decodes_10_bit_ids_and_mirrored_recipes(self):
        data=decode_bank(make_bank())
        self.assertEqual(data["pointer_count"],40)
        self.assertEqual(data["unique_recipe_count"],80)
        self.assertIn({"a":1,"b":301,"result":401},data["recipes"])
        self.assertIn({"a":1,"b":101,"result":201},data["recipes"])
        self.assertFalse(data["conflicts"])

    def test_rejects_truncated_or_fake_banks(self):
        with self.assertRaises(FusionFormatError):
            decode_bank(b"\0"*100)
        with self.assertRaises(FusionFormatError):
            decode_bank(b"\0"*BLOCK_SIZE)
        damaged=bytearray(make_bank())
        struct.pack_into("<H",damaged,2,1300)
        with self.assertRaises(FusionFormatError):
            decode_bank(bytes(damaged))

    def test_seven_mirrored_banks_and_detect_divergence(self):
        rom_data=bytearray(max(FUSION_BANK_OFFSETS)+BLOCK_SIZE)
        for offset in FUSION_BANK_OFFSETS:
            rom_data[offset:offset+BLOCK_SIZE]=make_bank()
        FakeDisc.prefix=bytes(rom_data)
        with tempfile.TemporaryDirectory() as folder:
            iso=Path(folder)/"fusions.iso"
            iso.write_bytes(b"test image is not really a game")
            with patch("extrator_fusoes.Disc",FakeDisc):
                report=analyze_fusion_banks(iso)
            self.assertEqual(report["valid_banks"],7)
            self.assertEqual(report["matching_banks"],7)
            self.assertEqual(report["candidate_count"],80)
            self.assertFalse(report["verified_in_game"])
            self.assertFalse(report["divergent_banks"])
            rom_data[FUSION_BANK_OFFSETS[-1]:FUSION_BANK_OFFSETS[-1]+BLOCK_SIZE]=make_bank(change_first=True)
            FakeDisc.prefix=bytes(rom_data)
            with patch("extrator_fusoes.Disc",FakeDisc):
                report=analyze_fusion_banks(iso)
            self.assertEqual(report["matching_banks"],6)
            self.assertTrue(report["divergent_banks"])
            self.assertIn("REVISÃO",report["status"])

    def test_review_one_pair_only_without_enabling_all(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog=ModCatalog(Path(folder))
            sha="c"*64
            base=Path(folder)
            profile={
                "rom_sha256":sha,"cards":[{"id":i,"name":f"C{i}"} for i in range(1,723)],
                "verified":{"cartas":"verificado","fusoes":"não_extraídas"},
                "supported_features":{"cards":True,"fusions":False,"ranks":False,"drops":False},
                "fusion_recipes":[],
            }
            location=base/"profiles"/sha[:16]/"profile.json"
            atomic_json(location,profile)
            entry={
                "sha256":sha,"file_name":"Teste ISO","profile_path":str(location),
                "source_path":str(base/"test.iso"),"approved":True,
                "level":"parcial_revisar","features":supported_for_runtime(profile),
                "verified":profile["verified"],
            }
            atomic_json(catalog.registry_file,{"schema":1,"entries":[entry]})
            atomic_json(catalog.active_file,{"sha256":sha,"features":entry["features"]})
            report={
                "rom_sha256":sha,"candidate_fingerprint":"f"*64,
                "candidates":[{"a":1,"b":101,"result":201},
                              {"a":1,"b":301,"result":401}],
            }
            save_fusion_report(base/"investigacoes"/(sha+".fusoes.json"),report)
            with self.assertRaises(ValueError):
                catalog.confirm_fusion(sha,1,101,202)
            self.assertFalse(catalog.profile_for(entry)["supported_features"]["fusions"])
            n=catalog.confirm_fusion(sha,1,101,201)
            self.assertEqual(n,1)
            updated=catalog.profile_for(entry)
            self.assertEqual(updated["fusion_recipes"][0]["result"],201)
            self.assertEqual(len(updated["fusion_recipes"]),1)
            self.assertTrue(catalog.current()["features"]["fusoes"])
            self.assertEqual(catalog.confirm_fusion(sha,1,101,201),1)


if __name__=="__main__":
    unittest.main()
