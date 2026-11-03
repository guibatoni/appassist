"""Tabela binária de 39 oponentes × 3 drops lida diretamente do WA sintético."""
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from scanner_multiiso import (
    WA_OPP_BASE, WA_OPP_STEP, WA_RANK_STRIDE, WA_ARRAY_BYTES,
    OPP_COUNT, decode_drops,
)


def make_wa():
    length=WA_OPP_BASE+(OPP_COUNT-1)*WA_OPP_STEP+3*WA_RANK_STRIDE+WA_ARRAY_BYTES
    wa=bytearray(length)
    for oid in range(OPP_COUNT):
        base=WA_OPP_BASE+oid*WA_OPP_STEP
        struct.pack_into("<H",wa,base+0,2048)  # deck do oponente
        for rank in range(3):
            at=base+(rank+1)*WA_RANK_STRIDE
            struct.pack_into("<H",wa,at+(rank+1)*2,2048)
    return wa


class BinaryDropTests(unittest.TestCase):
    def test_automatic_117_tables_and_each_id_source_offset(self):
        tables,diagnostic=decode_drops(bytes(make_wa()))
        self.assertIn("117/117",diagnostic)
        self.assertEqual(len(tables["verificacao"]),117)
        self.assertEqual(len(tables["drops"]),117)
        self.assertEqual(len(tables["decks"]),39)
        first=tables["drops"][0]
        self.assertEqual(first["oponente_id"],1)
        self.assertEqual(first["carta_id"],2)
        self.assertEqual(first["peso"],2048)
        self.assertEqual(first["chance_percentual"],100.0)
        self.assertEqual(first["source_offset"],WA_OPP_BASE+WA_RANK_STRIDE+2)
        self.assertIn("DESCONHECIDO",first["rank"])

    def test_known_labels_must_be_supplied_explicitly(self):
        names=("Z-POW","S-POW","S-TEC")
        tables,_=decode_drops(bytes(make_wa()),names)
        self.assertEqual([row["rank"] for row in tables["drops"][:3]],list(names))

    def test_original_rank_pools_use_correct_physical_WA_table_order(self):
        from dueltrace_rank_system import CLASSIC_POOLS
        tables,_=decode_drops(bytes(make_wa()),CLASSIC_POOLS)
        self.assertEqual(
            [row["rank"] for row in tables["verificacao"][:3]],
            ["S/A POW","B/C/D POW/TEC","S/A TEC"])
        self.assertEqual(
            [row["source_offset"] for row in tables["verificacao"][:3]],
            [WA_OPP_BASE+WA_RANK_STRIDE,
             WA_OPP_BASE+2*WA_RANK_STRIDE,
             WA_OPP_BASE+3*WA_RANK_STRIDE])

    def test_corrupted_drop_table_is_never_published(self):
        wa=make_wa()
        at=WA_OPP_BASE+WA_RANK_STRIDE+2
        struct.pack_into("<H",wa,at,2047)
        tables,status=decode_drops(bytes(wa))
        self.assertIsNone(tables)
        self.assertIn("não validados",status)

    def test_truncated_wa_reports_unavailable(self):
        tables,status=decode_drops(b"")
        self.assertIsNone(tables)
        self.assertIn("menor",status)


if __name__=="__main__":
    unittest.main()
