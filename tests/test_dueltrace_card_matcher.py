"""Equivalência de cartas entre ISO/BIN: nunca transferir IDs por coincidência.

Os testes criam perfis e PNGs sintéticos, sem incluir ROM ou arte licenciada.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from auto_mods import ModCatalog, atomic_json
from dueltrace_card_matcher import compare_profiles
from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_web_security import ProtectedDesktopApi

A="a"*64
B="b"*64


def card(cid,name,atk=100,defense=100,kind=7):
    return {"id":cid,"name":name,"atk":atk,"def":defense,
            "type_id":kind,"type_label":"Beast","level":5}


class CardMatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.sdir=self.home/"analises"/"source"
        self.tdir=self.home/"analises"/"target"
        for folder in (self.sdir,self.tdir):
            (folder/"artes_722").mkdir(parents=True)
        self.source=self.profile(A,self.sdir,[])
        self.target=self.profile(B,self.tdir,[])

    def profile(self,sha,folder,cards):
        return {"rom_sha256":sha,"scan_result_dir":str(folder),
                "cards":cards,"verified":{"cartas":"verificado"},
                "supported_features":{"cards":True,"art":True}}

    def save_art(self,folder,cid,variant=1,uniform=False):
        from PIL import Image
        image=Image.new("RGB",(102,96))
        if uniform:
            image.paste((255,255,255),(0,0,102,96))
        else:
            for y in range(96):
                for x in range(102):
                    image.putpixel((x,y),((x*3+variant)%256,
                                          (y*5+variant)%256,
                                          (x*y+variant)%256))
        image.save(folder/"artes_722"/f"{cid:03d}.png")

    def test_ids_reordered_by_name_not_position(self):
        self.source["cards"]=[card(1,"Flower Wolf",1800,1400)]
        self.target["cards"]=[card(35,"Flower Wolf",1800,1400),
                              card(1,"Unrelated",1800,1400)]
        result=compare_profiles(self.source,self.target,self.home)
        row=result["rows"][0]
        self.assertEqual(row["targetId"],35)
        self.assertEqual(row["confidence"],"alta")
        self.assertFalse(row["sameId"])
        self.assertIn("nome_exato",row["signals"])
        self.assertEqual(result["summary"]["reordered"],1)
        self.assertFalse(result["verifiedInGame"])
        self.assertNotIn(str(self.home),str(result))

    def test_identical_unique_art_finds_renamed_card_at_other_id(self):
        self.source["cards"]=[card(2,"Queen of Autumn Leaves",1800,1500)]
        self.target["cards"]=[card(41,"Forest Empress",2100,1800)]
        self.save_art(self.sdir,2,variant=19)
        self.save_art(self.tdir,41,variant=19)
        result=compare_profiles(self.source,self.target,self.home)
        row=result["rows"][0]
        self.assertEqual(row["targetId"],41)
        self.assertEqual(row["confidence"],"alta")
        self.assertIn("arte_rgb_identica",row["signals"])
        self.assertNotIn("nome_exato",row["signals"])
        self.assertEqual(result["summary"]["sourceArtCount"],1)

    def test_same_id_and_stats_are_never_identity_evidence(self):
        self.source["cards"]=[card(3,"Fungi of the Musk",400,300)]
        self.target["cards"]=[card(3,"Mechanical Soldier",400,300)]
        row=compare_profiles(self.source,self.target,self.home)["rows"][0]
        self.assertIsNone(row["targetId"])
        self.assertEqual(row["confidence"],"sem_correspondencia")

    def test_duplicate_names_are_review_only(self):
        self.source["cards"]=[card(4,"Wild beast",1200,700)]
        self.target["cards"]=[card(9,"Wild beast",1200,700),
                              card(10,"Wild beast",1200,700)]
        row=compare_profiles(self.source,self.target,self.home)["rows"][0]
        self.assertEqual(row["confidence"],"revisar")
        self.assertTrue(row["ambiguous"])
        self.assertEqual(row["candidateCount"],2)
        self.assertIn("nome_repetido",row["signals"])

    def test_name_equal_but_stats_changed_requires_review(self):
        self.source["cards"]=[card(8,"Flower Wolf",1800,1400)]
        self.target["cards"]=[card(17,"Flower Wolf",2600,2000)]
        row=compare_profiles(self.source,self.target,self.home)["rows"][0]
        self.assertEqual(row["confidence"],"revisar")
        self.assertEqual(row["targetId"],17)

    def test_recolored_art_with_same_stats_is_only_review_candidate(self):
        from PIL import Image
        self.source["cards"]=[card(2,"Queen of Autumn Leaves",1800,1500)]
        self.target["cards"]=[card(41,"Forest Sister",1800,1500)]
        # Mesmo padrão de desenho, recolorizado (+12 RGB), sem pixels iguais.
        for folder,cid,shift in ((self.sdir,2,0),(self.tdir,41,12)):
            img=Image.new("RGB",(102,96))
            for y in range(96):
                for x in range(102):
                    img.putpixel((x,y),(
                        30+x//2+shift,40+y//2+shift,
                        35+(x+y)//3+shift))
            img.save(folder/"artes_722"/f"{cid:03d}.png")
        row=compare_profiles(self.source,self.target,self.home)["rows"][0]
        self.assertEqual(row["targetId"],41)
        self.assertEqual(row["confidence"],"revisar")
        self.assertIn("arte_visual_semelhante",row["signals"])
        self.assertNotIn("arte_rgb_identica",row["signals"])

    def test_duplicate_art_not_proof(self):
        self.source["cards"]=[card(3,"Arboreal Queen",500,200)]
        self.target["cards"]=[card(9,"Mystic Shadow",800,100),
                              card(10,"Totem Wolf",1200,900)]
        self.save_art(self.sdir,3,variant=10)
        for cid in (9,10):
            self.save_art(self.tdir,cid,variant=10)
        row=compare_profiles(self.source,self.target,self.home)["rows"][0]
        self.assertIsNone(row["targetId"])

    def test_placeholder_art_cannot_create_false_match(self):
        self.source["cards"]=[card(1,"Fungi",400,300)]
        self.target["cards"]=[card(2,"Mushroom",400,300)]
        self.save_art(self.sdir,1,uniform=True)
        self.save_art(self.tdir,2,uniform=True)
        row=compare_profiles(self.source,self.target,self.home)["rows"][0]
        self.assertIsNone(row["targetId"])

    def test_no_extraction_no_implicit_cross_mod_fusion(self):
        self.source["cards"]=[card(1,"Flower Wolf",1800,1400)]
        self.target["cards"]=[card(88,"Flower Wolf",1800,1400)]
        self.source["fusion_recipes"]=[{"a":1,"b":2,"result":3}]
        result=compare_profiles(self.source,self.target,self.home)
        self.assertNotIn("fusion_recipes",str(result))
        self.assertNotIn("cross_mod_fusions",result)
        self.assertEqual(self.source["fusion_recipes"][0]["result"],3)

    def test_sha_and_verified_catalog_required(self):
        self.source["cards"]=[card(1,"One")]
        self.target["cards"]=[card(1,"One")]
        self.target["rom_sha256"]=A
        with self.assertRaises(ValueError):
            compare_profiles(self.source,self.target,self.home)
        self.target["rom_sha256"]=B
        self.target["verified"]["cartas"]="pendente"
        with self.assertRaises(ValueError):
            compare_profiles(self.source,self.target,self.home)

    def test_bridge_api_token_paging_and_cache(self):
        self.source["cards"]=[card(1,"Flower Wolf",1800,1400),
                              card(2,"Queen of Autumn Leaves",1800,1500)]
        self.target["cards"]=[card(17,"Flower Wolf",1800,1400),
                              card(33,"Queen of Autumn Leaves",1800,1500)]
        catalog=ModCatalog(self.home)
        entries=[]
        for sha,profile in ((A,self.source),(B,self.target)):
            path=self.home/"profiles"/sha[:16]/"profile.json"
            atomic_json(path,profile)
            entries.append({
                "sha256":sha,"file_name":f"Mod-{sha[0]}.iso",
                "source_path":str(self.home/"not_uploaded.iso"),
                "profile_path":str(path),
            })
        atomic_json(catalog.registry_file,{"schema":1,"entries":entries})
        bridge=DueltraceWebBridge(catalog)
        secure=ProtectedDesktopApi(bridge,"x"*64)
        with self.assertRaises(PermissionError):
            secure.compare_mod_cards("no",A,B)
        with patch("dueltrace_web_bridge.compare_profiles",
                   wraps=compare_profiles) as comparator:
            first=secure.compare_mod_cards("x"*64,A,B,limit=1)
            second=secure.compare_mod_cards("x"*64,A,B,offset=1,limit=1)
            self.assertEqual(comparator.call_count,1)
        self.assertEqual(first["total"],2)
        self.assertEqual(first["rows"][0]["targetId"],17)
        self.assertEqual(second["rows"][0]["targetId"],33)
        self.assertEqual(first["summary"]["reordered"],2)
        self.assertNotIn(str(self.home),str(first))
        self.assertFalse(first["verifiedInGame"])
        filtered=secure.compare_mod_cards("x"*64,A,B,query="Queen",limit=5)
        self.assertEqual(filtered["total"],1)
        with self.assertRaises(ValueError):
            secure.compare_mod_cards("x"*64,A,A)
        with self.assertRaises(ValueError):
            secure.compare_mod_cards("x"*64,A,"f"*64)


if __name__=="__main__":
    unittest.main()
