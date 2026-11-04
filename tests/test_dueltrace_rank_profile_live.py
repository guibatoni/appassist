"""Pontuação reaproveitável para mod não-X15, sem assumir tabela ou RAM."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_rank_profile_live import (
    validate_live_rank_binding, read_counters_from_record, project_rank_for_mod,
)


def profile():
    rom="a"*64
    exe="b"*64
    table="c"*64
    return {
        "rom_sha256":rom,"exe_sha256":exe,
        "rank_points":{"available":True,"table_sha256":table,"rules":{
            "criterion_01":[{"below":5,"points":12},{"below":32767,"points":-3}],
            "criterion_02":[{"below":7000,"points":0},{"below":32767,"points":4}],
        }},
        "rank_runtime_binding":{
            "validation_method":"independent_duel_trace","verified_duels":2,
            "rom_sha256":rom,"exe_sha256":exe,"table_sha256":table,
            "record_address":0xB41990,"record_length":32,
            "criterion_offsets":{
                "criterion_01":{"type":"u8","offset":1},
                "criterion_02":{"type":"u16le","offset":20},
            },
            "life_points_criterion":"criterion_02",
            "turns_criterion":"criterion_01",
            "base_points":50,
            "victory_bonuses":{"lp":2,"deckout":-5},
            "rank_bands":[
                {"label":"Z-POW","minimum":65},
                {"label":"S-POW","minimum":50},
                {"label":"S-TEC","minimum":-100},
            ],
        },
    }


class GenericRankTests(unittest.TestCase):
    def test_generic_mod_can_score_from_own_iso_rules(self):
        p=profile()
        self.assertIsNotNone(validate_live_rank_binding(p))
        record=bytearray(32)
        record[1]=1
        record[20:22]=(8000).to_bytes(2,"little")
        counters=read_counters_from_record(bytes(record),p["rank_runtime_binding"])
        result=project_rank_for_mod(p,counters)
        self.assertEqual(result["score"],68)
        self.assertEqual(result["category"],"Z-POW")
        self.assertFalse(result["final"])
        deckout=project_rank_for_mod(p,counters,victory="deckout")
        self.assertEqual(deckout["score"],61)
        self.assertEqual(deckout["category"],"S-POW")

    def test_other_iso_with_byte_identical_exe_and_scoring_table(self):
        from dueltrace_rank_profile_live import x15_compatible_runtime
        from fm_rank_tables import (
            KNOWN_X15_SLUS_SHA256,KNOWN_X15_TABLE_SHA256,LEGACY_OFFSET,STRIDE
        )
        p=profile()
        p["exe_sha256"]=KNOWN_X15_SLUS_SHA256
        p["rank_points"].update({
            "available":True,"structure_verified":True,
            "table_sha256":KNOWN_X15_TABLE_SHA256,
            "first_offset":LEGACY_OFFSET,"repeat_stride":STRIDE,
        })
        self.assertTrue(x15_compatible_runtime(p))
        for key,bad in (
            ("first_offset",LEGACY_OFFSET+2),
            ("repeat_stride",STRIDE+2048),
            ("table_sha256","e"*64),
        ):
            q={**p,"rank_points":{**p["rank_points"],key:bad}}
            self.assertFalse(x15_compatible_runtime(q))
        q={**p,"exe_sha256":"a"*64}
        self.assertFalse(x15_compatible_runtime(q))

    def test_modified_file_hash_or_unvalidated_duels_disables_rank(self):
        for change in ({"verified_duels":1},{"table_sha256":"d"*64},
                       {"rom_sha256":"e"*64},{"validation_method":"pattern_only"},
                       {"record_address":0},{"life_points_criterion":"unknown"}):
            p=profile()
            p["rank_runtime_binding"].update(change)
            self.assertIsNone(validate_live_rank_binding(p),msg=str(change))
            with self.assertRaises(ValueError):
                project_rank_for_mod(p,{"criterion_01":1,"criterion_02":8000})

    def test_malformed_offsets_do_not_read_other_ram(self):
        p=profile()
        p["rank_runtime_binding"]["criterion_offsets"]["criterion_02"]["offset"]=31
        self.assertIsNone(validate_live_rank_binding(p))
        with self.assertRaises(ValueError):
            read_counters_from_record(b"x"*12,profile()["rank_runtime_binding"])

    def test_wrong_or_missing_counters_rejected(self):
        p=profile()
        for counters in ({"criterion_01":1},{"criterion_01":1,"criterion_02":-100},
                         {"criterion_01":"1","criterion_02":8000}):
            with self.assertRaises(ValueError):
                project_rank_for_mod(p,counters)

    def test_unavailable_ruleset_cannot_authorize_ram_binding(self):
        for available in (False,None,1,"true"):
            p=profile()
            p["rank_points"]["available"]=available
            self.assertIsNone(validate_live_rank_binding(p))


if __name__ == "__main__":
    unittest.main()
