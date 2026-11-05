"""Testes unitários do catálogo e da integração, sem ISOs comerciais."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))

from auto_mods import ModCatalog, report_level, supported_for_runtime, atomic_json
from integracao_overlay import overlay_snapshot
from epsxe_launcher import launch_epsxe
from scanner_multiiso import X15_SHA


def example_profile(sha: str) -> dict:
    return {
        "rom_sha256": sha,
        "name": "Teste seguro",
        "verified": {
            "cartas": "verificado",
            "oponentes": "verificado",
            "tabelas_drops": "pendente",
            "fusoes": "não_extraídas",
        },
        "supported_features": {
            "cards": True, "opponents": True, "drops": False,
            "ranks": False, "scoring": False, "fusions": False, "art": False,
        },
        "cards": [{"id": 1, "name": "Carta Teste", "atk": 1200, "def": 1000, "type_id": 2}],
        "opponents": [{"id": 1, "name": "Adversário Teste"}],
        "drops": [], "fusion_recipes": [],
    }


class ProfileTests(unittest.TestCase):
    def test_unknown_never_inherits_rank(self):
        p = example_profile("a" * 64)
        p["supported_features"]["ranks"] = True
        p["supported_features"]["scoring"] = True
        self.assertEqual(report_level(p), "parcial_revisar")
        self.assertFalse(supported_for_runtime(p)["rank"])
        self.assertFalse(supported_for_runtime(p)["pontuacao"])
        self.assertFalse(supported_for_runtime(p)["fusoes"])

    def test_known_x15_requires_verified_tables(self):
        p = example_profile(X15_SHA)
        self.assertEqual(report_level(p), "parcial_revisar")
        p["verified"]["tabelas_drops"] = "verificado"
        self.assertEqual(report_level(p), "conhecido_validado")

    def test_import_does_not_change_input_and_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rom = root / "teste.iso"
            rom.write_bytes(b"p" * 110_000)
            source_digest = hashlib.sha256(rom.read_bytes()).hexdigest()
            home = root / "userspace"
            catalog = ModCatalog(home)
            p = example_profile(source_digest)
            profile_path = home / "profiles" / source_digest[:16] / "profile.json"
            atomic_json(profile_path, p)
            with patch("auto_mods.import_rom", return_value=(p, profile_path)):
                entry = catalog.analyse(rom)
            self.assertEqual(hashlib.sha256(rom.read_bytes()).hexdigest(), source_digest)
            self.assertEqual(entry["level"], "parcial_revisar")
            with self.assertRaises(PermissionError):
                catalog.activate(source_digest)
            active = catalog.activate(source_digest, acknowledge_uncertainty=True)
            self.assertEqual(active["sha256"], source_digest)
            snapshot = overlay_snapshot(catalog)
            self.assertTrue(snapshot["ready"])
            self.assertEqual(snapshot["cards"][1]["name"], "Carta Teste")
            self.assertEqual(snapshot["opponents"][1], "Adversário Teste")
            self.assertEqual(snapshot["recipes"], [])
            self.assertIsNone(snapshot["rank_labels"])
            self.assertEqual(catalog.current()["sha256"], source_digest)

    def test_unrecognized_structure_cannot_be_activated(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rom = root / "unknown.bin"
            rom.write_bytes(b"x" * 110_000)
            sha = hashlib.sha256(rom.read_bytes()).hexdigest()
            catalog = ModCatalog(root / "settings")
            profile = example_profile(sha)
            profile["verified"]["cartas"] = "pendente"
            profile["verified"]["oponentes"] = "pendente"
            profile["supported_features"] = {k: False for k in profile["supported_features"]}
            path = catalog.home / "profiles" / sha[:16] / "profile.json"
            atomic_json(path, profile)
            with patch("auto_mods.import_rom", return_value=(profile, path)):
                catalog.analyse(rom)
            with self.assertRaises(PermissionError):
                catalog.activate(sha)
            active=catalog.activate(sha, acknowledge_uncertainty=True)
            self.assertEqual(active["sha256"],sha)
            self.assertEqual(active["compatibility_mode"],"basic")
            self.assertFalse(active["features"]["nomes_cartas"])
            self.assertFalse(active["features"]["rank"])
            self.assertFalse(active["features"]["fusoes"])
            self.assertTrue(active["features"]["ids_e_lp"])
            snapshot=overlay_snapshot(catalog)
            self.assertTrue(snapshot["ready"])
            self.assertEqual(snapshot["cards"],{})
            self.assertEqual(snapshot["drops"],[])
            self.assertEqual(snapshot["recipes"],[])
            self.assertIsNone(snapshot["rank_labels"])

    def test_basic_mode_can_launch_selected_iso_with_no_unverified_catalog(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            rom=root/"unknown_mod.bin"
            rom.write_bytes(b"b"*110_000)
            exe=root/"ePSXe.exe"
            exe.write_bytes(b"test launcher")
            sha=hashlib.sha256(rom.read_bytes()).hexdigest()
            catalog=ModCatalog(root/"settings")
            profile=example_profile(sha)
            profile["verified"]={"cartas":"pendente","oponentes":"pendente"}
            profile["supported_features"]={
                k:False for k in profile["supported_features"]}
            path=catalog.home/"profiles"/sha[:16]/"profile.json"
            atomic_json(path,profile)
            with patch("auto_mods.import_rom",return_value=(profile,path)):
                catalog.analyse(rom)
            catalog.activate(sha,acknowledge_uncertainty=True)
            process=Mock()
            process.return_value=object()
            launch_epsxe(catalog,exe,sha,popen=process,platform="win32")
            self.assertEqual(process.call_count,1)
            args=process.call_args.args[0]
            self.assertEqual(Path(args[-1]).resolve(),rom.resolve())
            self.assertIn("-loadiso",args)
            self.assertIs(process.call_args.kwargs["shell"],False)

    def test_corrupt_image_is_not_activated_even_in_basic_mode(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            rom=root/"bad_image.bin"
            rom.write_bytes(b"x"*110_000)
            sha=hashlib.sha256(rom.read_bytes()).hexdigest()
            catalog=ModCatalog(root/"settings")
            profile=example_profile(sha)
            profile["scanner_error"]="Sem diretório ISO9660 coerente"
            profile["verified"]={"cartas":"pendente","oponentes":"pendente",
                                 "tabelas_drops":"pendente"}
            profile["supported_features"]={
                k:False for k in profile["supported_features"]}
            path=catalog.home/"profiles"/sha[:16]/"profile.json"
            atomic_json(path,profile)
            with patch("auto_mods.import_rom",return_value=(profile,path)):
                catalog.analyse(rom)
            with self.assertRaises(PermissionError):
                catalog.activate(sha,acknowledge_uncertainty=True)
            self.assertFalse(overlay_snapshot(catalog)["ready"])


if __name__ == "__main__":
    unittest.main()
