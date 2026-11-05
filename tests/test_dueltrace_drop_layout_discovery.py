"""Procura tabelas WA realocadas sem assumir o RANK de um mod.

Contêineres sintéticos; nenhum jogo comercial é necessário. Uma tabela
completa é evidência estrutural e ainda exige catálogo e etiquetas de RANK.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from scanner_multiiso import (
    WA_OPP_BASE,WA_OPP_STEP,WA_RANK_STRIDE,SCAN_PARSER_REVISION,
    decode_drops
)
from dueltrace_drop_layout_discovery import discover_relocated_drops

GROUPS=("GRUPO_1","GRUPO_2","GRUPO_3")
WEIGHTS=struct.pack("<722H",2048,*([0]*721))


def fixture(layouts, *, mode="simple"):
    end=max(base+38*step+3*stride+len(WEIGHTS)
            for base,step,stride in layouts)
    wa=bytearray(end+2048)
    for base,step,stride in layouts:
        for opponent in range(39):
            for r in (1,2,3):
                off=base+opponent*step+r*stride
                if mode=="simple":
                    wa[off:off+len(WEIGHTS)]=WEIGHTS
                else:
                    encoded=struct.pack("<722H",2512+2048*8,
                                        *([2512]*721))
                    wa[off:off+len(encoded)]=encoded
    return bytes(wa)


def probe(wa,max_shift=128*1024):
    def decode(base,step,stride):
        return decode_drops(wa,GROUPS,
                            opp_base=base,opp_step=step,rank_stride=stride)
    return discover_relocated_drops(wa,known_base=WA_OPP_BASE,
                                   decode_at_layout=decode,
                                   max_shift=max_shift)


class RelocatedWATests(unittest.TestCase):
    def test_full_117_simple_matrices_at_shifted_base_are_discovered(self):
        base=WA_OPP_BASE+0x6000
        wa=fixture([(base,WA_OPP_STEP,WA_RANK_STRIDE)])
        raw,status=decode_drops(wa,GROUPS)
        self.assertIsNone(raw)
        found=probe(wa)
        self.assertEqual(found["state"],"layout_candidato_unico")
        self.assertFalse(found["validated"])
        self.assertFalse(found["rankLabelsVerified"])
        self.assertFalse(found["inGameVerified"])
        chosen=found["selected"]
        self.assertEqual(chosen["opponentBase"],base)
        self.assertEqual(chosen["opponentStep"],WA_OPP_STEP)
        self.assertEqual(chosen["rankStride"],WA_RANK_STRIDE)
        tables,status=decode_drops(wa,GROUPS,
                 opp_base=base,opp_step=WA_OPP_STEP,rank_stride=WA_RANK_STRIDE)
        self.assertEqual(len(tables["verificacao"]),117)
        self.assertEqual(len(tables["drops"]),117)
        self.assertEqual(tables["drops"][0]["rank"],"GRUPO_1")
        self.assertEqual(tables["drops"][-1]["oponente_id"],39)
        self.assertNotEqual(tables["drops"][0]["source_offset"],
                            WA_OPP_BASE+WA_RANK_STRIDE)

    def test_modified_opponent_stride_is_discovered(self):
        base=WA_OPP_BASE-0x6000
        step=0x2000
        wa=fixture([(base,step,WA_RANK_STRIDE)])
        found=probe(wa)
        self.assertEqual(found["state"],"layout_candidato_unico")
        self.assertEqual(found["selected"]["opponentStep"],step)
        self.assertFalse(found["validated"])

    def test_masked_weights_supported_without_rank_label_assumption(self):
        base=WA_OPP_BASE+0x4000
        wa=fixture([(base,WA_OPP_STEP,WA_RANK_STRIDE)],mode="masked")
        found=probe(wa)
        self.assertEqual(found["state"],"layout_candidato_unico")
        self.assertFalse(found["rankLabelsVerified"])
        tables,_=decode_drops(wa,GROUPS,opp_base=base,
                       opp_step=WA_OPP_STEP,rank_stride=WA_RANK_STRIDE)
        self.assertEqual(tables["codificacoes"],["mascarado_X15"])
        self.assertEqual(len(tables["verificacao"]),117)

    def test_two_distinct_valid_layouts_are_not_selected(self):
        first=(WA_OPP_BASE-0x20000,WA_OPP_STEP,WA_RANK_STRIDE)
        second=(WA_OPP_BASE+0x20000,WA_OPP_STEP,WA_RANK_STRIDE)
        wa=fixture([first,second])
        report=probe(wa)
        self.assertEqual(report["state"],"layouts_ambiguos")
        self.assertIsNone(report["selected"])
        self.assertGreaterEqual(len(report["candidates"]),2)

    def test_corruption_of_one_matrix_cannot_be_promoted(self):
        base=WA_OPP_BASE+0x6000
        raw=bytearray(fixture([(base,WA_OPP_STEP,WA_RANK_STRIDE)]))
        pos=base+38*WA_OPP_STEP+3*WA_RANK_STRIDE
        raw[pos:pos+2]=b"\0\0"
        found=probe(bytes(raw))
        self.assertEqual(found["state"],"nao_encontrado")
        self.assertIsNone(found["selected"])

    def test_missing_and_bounded_scan_remain_unavailable(self):
        small=probe(b"\0"*10000)
        self.assertEqual(small["state"],"recurso_pequeno_ou_incompativel")
        self.assertIsNone(small["selected"])
        base=WA_OPP_BASE+0x6000
        raw=fixture([(base,WA_OPP_STEP,WA_RANK_STRIDE)])
        limited=probe(raw,max_shift=2048)
        self.assertEqual(limited["state"],"nao_encontrado")
        self.assertEqual(limited["scanRadius"],2048)
        self.assertLessEqual(limited["offsetsExamined"],25000)

    def test_scanner_uses_only_unique_relabeled_matrices(self):
        code=(ROOT/"scanner/scanner_multiiso.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(SCAN_PARSER_REVISION,14)
        self.assertIn("discover_relocated_drops(",code)
        self.assertIn('unknown_groups=("GRUPO_1","GRUPO_2","GRUPO_3")',code)
        self.assertIn("chosen=relocated.get",code)
        self.assertIn("if chosen is not None:",code)
        self.assertIn('info["drop_group_mapping_status"]="grupos_nao_identificados"',code)


if __name__=="__main__":
    unittest.main()
