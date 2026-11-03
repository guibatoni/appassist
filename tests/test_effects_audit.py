"""Auditoria de efeitos distingue candidatos de efeitos comprovados."""
from __future__ import annotations

import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from effects_audit import audit_effect_sources


class FakeDisc:
    def __init__(self, image):
        self.files={
            "SLUS_014.11":(1,120),
            "DATA/WA_MRG.MRG":(10,220),
            "DATA/EFFECTS.TXT":(11,60),
        }
    def get(self,name,limit_bytes=None):
        if name=="SLUS_014.11":
            return b"\0"*12+b"Increase attack when a monster is summoned on the field"+b"\0"*200
        return b"\0"*70
    def close(self):
        pass


class EffectsAuditTests(unittest.TestCase):
    def test_unmapped_text_never_becomes_effect_of_specific_card(self):
        with patch("effects_audit.Disc",FakeDisc):
            result=audit_effect_sources(Path("mod.bin"),rom_sha256="a"*64)
        self.assertEqual(result["rom_sha256"],"a"*64)
        self.assertEqual(result["card_effects_mapped"],0)
        self.assertEqual(result["confidence"],"investigacao_apenas")
        self.assertIn("EFFECTS.TXT",result["candidate_files"][0]["name"])
        self.assertTrue(result["candidate_text_runs"])
        self.assertIsNone(result["candidate_text_runs"][0]["verified_card_id"])


if __name__=="__main__":
    unittest.main()
