"""Autoimportação estrutural, com dados artificiais e sete espelhos."""
from __future__ import annotations
import sys, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from auto_mods import ModCatalog, atomic_json, supported_for_runtime
from extrator_fusoes import decode_bank, save_fusion_report
from fusion_autopromote import import_structural_fusions, validate_structural_fusions
from test_extrator_fusoes import make_bank


class StructuralAutoImportTests(unittest.TestCase):
    def make_catalog(self,root):
        home=Path(root)
        catalog=ModCatalog(home)
        rom=home/"local.iso"
        rom.write_bytes(b"controlled synthetic ROM fixture")
        sha="a"*64
        path=home/"profiles"/sha[:16]/"profile.json"
        profile={"rom_sha256":sha,"cards":[{"id":i,"name":f"C{i}"} for i in range(1,723)],
                 "verified":{"cartas":"verificado","fusoes":"não_extraídas"},
                 "supported_features":{"cards":True,"fusions":False},
                 "fusion_recipes":[]}
        atomic_json(path,profile)
        st=rom.stat()
        entry={"source_path":str(rom),"file_name":rom.name,"sha256":sha,
               "profile_path":str(path),"level":"parcial_revisar","approved":False,
               "size":st.st_size,"mtime_ns":st.st_mtime_ns,
               "features":supported_for_runtime(profile),"verified":profile["verified"]}
        atomic_json(catalog.registry_file,{"schema":1,"entries":[entry]})
        atomic_json(catalog.active_file,{"sha256":sha,"features":entry["features"]})
        parsed=decode_bank(make_bank())
        banks=[{"bank":j,"status":"decodificado","conflict_count":0,
                "unique_recipe_count":parsed["unique_recipe_count"],
                "recipelist_sha256":parsed["recipelist_sha256"]}
               for j in range(1,8)]
        report={"rom_sha256":sha,"banks":banks,
                "valid_banks":7,"matching_banks":7,"divergent_banks":False,
                "bank_conflicts":0,"candidate_count":parsed["unique_recipe_count"],
                "candidate_fingerprint":parsed["recipelist_sha256"],
                "candidates":parsed["recipes"]}
        outfile=home/"investigacoes"/(sha+".fusoes.json")
        save_fusion_report(outfile,report)
        return catalog,entry,report,outfile

    def test_imports_80_recipes_automatically_without_marking_game_verified(self):
        with tempfile.TemporaryDirectory() as root:
            cat,e,report,_=self.make_catalog(root)
            result=import_structural_fusions(cat,e["sha256"])
            self.assertEqual(result["count"],80)
            self.assertEqual(result["status"],"importadas")
            profile=cat.profile_for(e)
            self.assertTrue(profile["supported_features"]["fusions"])
            self.assertEqual(len(profile["fusion_recipes"]),80)
            self.assertTrue(all(r["validation"]=="extraida_sete_bancos_consistentes"
                                for r in profile["fusion_recipes"]))
            self.assertEqual(profile["fusion_review"]["in_game_individually_verified"],0)
            self.assertFalse(profile["verified"]["fusoes"].startswith("verificado"))
            self.assertTrue(cat.current()["features"]["fusoes"])
            self.assertTrue(Path(e["profile_path"]+".bak.before_structural_fusions").is_file())
            twice=import_structural_fusions(cat,e["sha256"])
            self.assertEqual(twice["status"],"cache")

    def test_rejects_different_rom_and_divergent_mirrors(self):
        with tempfile.TemporaryDirectory() as root:
            cat,e,r,p=self.make_catalog(root)
            with self.assertRaises(ValueError):
                validate_structural_fusions(r,sha256="b"*64)
            r["matching_banks"]=6
            save_fusion_report(p,r)
            with self.assertRaisesRegex(ValueError,"Bancos"):
                import_structural_fusions(cat,e["sha256"])
            self.assertFalse(cat.profile_for(e)["supported_features"]["fusions"])

    def test_does_not_promote_conflicting_symmetric_results(self):
        with tempfile.TemporaryDirectory() as root:
            cat,e,r,p=self.make_catalog(root)
            entry=r["candidates"][0]
            r["candidates"].append({"a":entry["b"],"b":entry["a"],"result":722})
            save_fusion_report(p,r)
            with self.assertRaises(ValueError):
                import_structural_fusions(cat,e["sha256"])

    def test_existing_manual_observation_survives_import(self):
        with tempfile.TemporaryDirectory() as root:
            cat,e,r,p=self.make_catalog(root)
            first=r["candidates"][0]
            profile=cat.profile_for(e)
            profile["fusion_recipes"]=[{**first,"validation":"observada_manualmente_no_jogo"}]
            atomic_json(Path(e["profile_path"]),profile)
            result=import_structural_fusions(cat,e["sha256"])
            self.assertEqual(result["manual_count"],1)
            updated=cat.profile_for(e)
            self.assertEqual(updated["fusion_review"]["in_game_individually_verified"],1)
            self.assertEqual(sum(x["validation"]=="observada_manualmente_no_jogo"
                                 for x in updated["fusion_recipes"]),1)

    def test_modified_rom_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            cat,e,r,p=self.make_catalog(root)
            Path(e["source_path"]).write_bytes(b"modified image has different byte length")
            with self.assertRaisesRegex(ValueError,"modificada"):
                import_structural_fusions(cat,e["sha256"])


if __name__=="__main__":
    unittest.main()
