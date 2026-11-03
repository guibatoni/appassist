"""Regressões offline do banco de descrições do SLUS_014.11."""
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from fm_card_text import (DESCRIPTION_BANK, DESCRIPTION_POINTERS,
                          GLYPHS_OFFSET, extract_descriptions,
                          attach_descriptions)


def fake_slus():
    sl=bytearray(0x1D0800)
    # Mapeamento do teste local: 1=C, 2=A, 3=R, 4=D, 5=E, 6=F, 7=T.
    for code, char in enumerate("CARDEFT",start=1):
        struct.pack_into("<H",sl,GLYPHS_OFFSET+code*4,ord(char))
    for cid in range(1,723):
        pointer=0x1000+(cid-1)*6
        struct.pack_into("<H",sl,DESCRIPTION_POINTERS+(cid-1)*2,pointer)
        at=DESCRIPTION_BANK+pointer
        sl[at:at+6]=b"\x01\x02\x03\x04\x05\xff"
    return bytes(sl)


class SLUSTextTests(unittest.TestCase):
    def test_per_id_pointer_and_source_validation(self):
        rows,meta=extract_descriptions(fake_slus())
        self.assertTrue(meta["valid"])
        self.assertEqual(meta["count"],722)
        self.assertEqual(rows[1]["text"],"CARDE")
        self.assertIn("id=722",rows[722]["source"])
        self.assertEqual(rows[722]["exe_offset"],DESCRIPTION_BANK+0x1000+721*6)

    def test_partial_remaster_style_description_table_is_accepted(self):
        sl=bytearray(fake_slus())
        for cid in range(1,226):  # 225 cartões sem descrição, como no X15
            ptr=struct.unpack_from("<H",sl,DESCRIPTION_POINTERS+(cid-1)*2)[0]
            sl[DESCRIPTION_BANK+ptr]=255
        rows,meta=extract_descriptions(bytes(sl))
        self.assertTrue(meta["valid"])
        self.assertEqual(len(rows),497)
        self.assertNotIn(1,rows)
        self.assertIn(722,rows)

    def test_original_ps1_effect_markup_is_recognized(self):
        cards=[{"id":1,"category":"Monstros","effect_text":None}]
        enriched,meta=attach_descriptions(cards,{1:{
            "text":"《Effect》 Cause 500 damage.","source":"SLUS-offset-10"}})
        self.assertEqual(meta["effect_descriptions_attached"],1)
        self.assertEqual(enriched[0]["effect_text"],"《Effect》 Cause 500 damage.")
        self.assertFalse(meta["effects_executed_in_game_verified"])

    def test_no_assignment_for_unknown_or_corrupt_pointer_table(self):
        rows,meta=extract_descriptions(bytes(0x1D0800))
        self.assertEqual(rows,{})
        self.assertFalse(meta["valid"])
        sl=bytearray(fake_slus())
        for n in range(1,723):
            struct.pack_into("<H",sl,DESCRIPTION_POINTERS+(n-1)*2,0xFFFF)
        rows,meta=extract_descriptions(bytes(sl))
        self.assertEqual(rows,{})
        self.assertEqual(meta["status"],"tabela_incompativel")

    def test_description_is_not_necessarily_executable_effect(self):
        cards=[
            {"id":1,"name":"Monstro","category":"Monstros",
             "effect_text":None,"effect_source":None},
            {"id":2,"name":"Magia","category":"Mágicas",
             "effect_text":None,"effect_source":None},
        ]
        rows={1:{"text":"Um monstro sem efeito.","source":"SLUS:offset=1"},
              2:{"text":"Aumenta a força em 500.","source":"SLUS:offset=2"}}
        enriched,meta=attach_descriptions(cards,rows)
        self.assertEqual(meta["descriptions_attached"],2)
        self.assertEqual(meta["effect_descriptions_attached"],1)
        self.assertIsNone(enriched[0]["effect_text"])
        self.assertEqual(enriched[1]["effect_text"],"Aumenta a força em 500.")
        self.assertEqual(enriched[1]["effect_status"],
                         "texto_do_jogo_sem_confirmacao_de_mecanica")
        self.assertFalse(meta["effects_executed_in_game_verified"])

    def test_explicit_monster_effect_marker_may_be_declared(self):
        cards=[{"id":12,"category":"Monstros","effect_text":None}]
        output,info=attach_descriptions(cards,{12:{
            "text":"<Effect> Destroy target","source":"SLUS:offset=12"}})
        self.assertEqual(info["effect_descriptions_attached"],1)
        self.assertEqual(output[0]["effect_text"],"<Effect> Destroy target")
        self.assertEqual(output[0]["description_source"],"SLUS:offset=12")


if __name__=="__main__":
    unittest.main()
