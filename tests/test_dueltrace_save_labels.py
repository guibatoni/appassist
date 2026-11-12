"""Names shown in the Memory Card selector must be truthful and per ISO."""
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_save_labels import (
    safe_mod_name, title_from_ps1_header, label_saves,
)

SHA_A="a"*64
SHA_B="b"*64
PATH="C:/epsxe/memcards/epsxe000.mcr"
MOD="RISING OF WICKED GODS 1.3.5 ver 2 - Drop 15 (NDC)"


def fixtures(sequence=3):
    return [
        {"block":1,"saveName":"BASLUS-01411-YUGIOH",
         "saveSequence":7,"duelistCode":456,"saveTitle":None},
        {"block":4,"saveName":"BAxLUS-01411-YUGIOH",
         "saveSequence":sequence,"duelistCode":123,"saveTitle":None},
    ]


def link(block, name, duelist, mod):
    return {"path":PATH,"selectedBlock":block,"selectedSaveName":name,
            "selectedDuelistCode":duelist,"modName":mod}


class SaveLabelsTests(unittest.TestCase):
    def test_user_confirmed_block_four_has_real_mod_alias(self):
        rows=fixtures()
        links={SHA_A:link(4,rows[1]["saveName"],123,MOD)}
        found=label_saves(rows,links,current_sha=SHA_A,
                          memory_path=PATH,mod_name=MOD)
        self.assertEqual(found[0]["association"],"unassigned")
        self.assertIn("mod não associado",found[0]["displayName"])
        self.assertNotIn(MOD,found[0]["displayName"])
        self.assertEqual(found[1]["association"],"linked_current_mod")
        self.assertIn("Bloco 4",found[1]["displayName"])
        self.assertIn(MOD,found[1]["displayName"])
        self.assertIn("seq. 3",found[1]["displayName"])
        self.assertNotIn("BAxLUS",found[1]["displayName"])

    def test_sequence_is_not_a_part_of_the_save_identity(self):
        rows=fixtures(sequence=19)
        links={SHA_A:link(4,rows[1]["saveName"],123,MOD)}
        found=label_saves(rows,links,current_sha=SHA_A,
                          memory_path=PATH,mod_name=MOD)
        self.assertEqual(found[1]["association"],"linked_current_mod")
        self.assertIn("seq. 19",found[1]["displayName"])

    def test_shared_game_serial_does_not_assign_other_mod(self):
        rows=fixtures()
        links={SHA_A:link(4,rows[1]["saveName"],123,MOD)}
        found=label_saves(rows,links,current_sha=SHA_B,
                          memory_path=PATH,mod_name="Remaster X15")
        self.assertEqual(found[1]["association"],"linked_other_mod")
        self.assertIn(MOD,found[1]["displayName"])
        self.assertNotIn("Remaster X15",found[1]["displayName"])

    def test_shared_block_is_marked_as_ambiguous(self):
        rows=fixtures()
        links={
            SHA_A:link(4,rows[1]["saveName"],123,MOD),
            SHA_B:link(4,rows[1]["saveName"],123,"Remaster X15"),
        }
        found=label_saves(rows,links,current_sha=SHA_A,
                          memory_path=PATH,mod_name=MOD)
        self.assertEqual(found[1]["association"],"shared_between_mods")
        self.assertIn("outro mod",found[1]["displayName"])

    def test_unrelated_card_or_different_save_is_not_claimed(self):
        rows=fixtures()
        links={SHA_A:link(4,rows[1]["saveName"],123,MOD)}
        for path in ("C:/epsxe/other.mcr",PATH):
            selected=[dict(x) for x in rows]
            if path==PATH:
                selected[1]["duelistCode"]=987
            found=label_saves(selected,links,current_sha=SHA_A,
                              memory_path=path,mod_name=MOD)
            self.assertEqual(found[1]["association"],"unassigned")

    def test_decode_ps1_title_from_header_not_directory_serial(self):
        data=bytearray(8192)
        data[0:2]=b"SC"
        title=b"Yu-Gi-Oh! Forbidden Memories"
        data[4:4+len(title)]=title
        self.assertEqual(title_from_ps1_header(bytes(data)),title.decode())
        data[4:68]=b"\xff"*64
        self.assertIsNone(title_from_ps1_header(bytes(data)))

    def test_clean_mod_name_and_hide_control_characters(self):
        self.assertEqual(safe_mod_name("Mod local —  Rising of Wicked Gods"),
                         "Rising of Wicked Gods")
        self.assertEqual(safe_mod_name("MOD\x00\nNAME"),"MOD NAME")

    def test_ui_uses_formatted_label_not_raw_save_identifier(self):
        ui=(ROOT/"web/components/desktop/decks-page.tsx").read_text("utf-8")
        self.assertIn("{save.displayName}",ui)
        self.assertIn("state.saveDisplayName",ui)
        self.assertNotIn("· {save.saveName} · sequência",ui)
        bridge=(ROOT/"scanner/dueltrace_web_bridge.py").read_text("utf-8")
        self.assertIn("mod_name=self._memory_mod_name",bridge)


if __name__=="__main__":
    unittest.main()
