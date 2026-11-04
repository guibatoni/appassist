"""Integrity of independent catalogues and 117 synthetic drop matrices."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from dueltrace_catalog_validation import validate_identity_catalogs, validate_drop_associations
from importador_perfis import import_rom


def identity_catalogs():
    return ([{"id": i, "nome": f"Carta {i}", "atk": 1000, "def": 800,
              "tipo": 3, "nivel": 4, "atributo": 1, "estrela_1": 2, "estrela_2": 5}
             for i in range(1, 723)],
            [{"id": i, "nome": f"Oponente {i}v"} for i in range(1, 40)])


def drop_matrices():
    checks = [{"oponente_id": oid, "rank": group, "peso_total": 2048}
              for oid in range(1, 40) for group in ("pool 1", "pool 2", "pool 3")]
    drops = [{"oponente_id": row["oponente_id"], "rank": row["rank"],
              "carta_id": 1, "peso": 2048} for row in checks]
    return checks, drops


class CatalogueIdentityTests(unittest.TestCase):
    def test_complete_catalogue_preserves_real_suffix_and_pending_game_verification(self):
        cards, opponents = identity_catalogs()
        result = validate_identity_catalogs(cards, opponents)
        self.assertTrue(result["cards_valid"])
        self.assertTrue(result["opponents_valid"])
        self.assertFalse(result["in_game_verified"])
        self.assertEqual(opponents[0]["nome"], "Oponente 1v")

    def test_all_722_attribute_records_and_ids_must_pass(self):
        for field, value in (("id", 721), ("atk", -10), ("def", 5111),
                             ("atk", 1001), ("tipo", 32), ("nivel", 16),
                             ("estrela_1", "garbage"), ("nome", "Bad\x00name")):
            with self.subTest(field=field, value=value):
                cards, opponents = identity_catalogs()
                cards[-1][field] = value
                result = validate_identity_catalogs(cards, opponents)
                self.assertFalse(result["cards_valid"])
                self.assertTrue(result["opponents_valid"])

    def test_each_opponent_id_and_name_must_pass(self):
        for field, value in (("id", 1), ("id", 40), ("nome", "\ufffd"), ("nome", "")):
            cards, opponents = identity_catalogs()
            opponents[-1][field] = value
            self.assertFalse(validate_identity_catalogs(cards, opponents)["opponents_valid"])


class DropAssociationTests(unittest.TestCase):
    def test_import_rejects_returned_result_from_another_iso(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            iso = root / "local.iso"
            iso.write_bytes(b"synthetic local image")
            digest = hashlib.sha256(iso.read_bytes()).hexdigest()
            output = root / "profiles"
            extracted = output / "analises" / "result"
            extracted.mkdir(parents=True)
            # Correct disk report cannot justify a returned result from another image.
            (extracted / "relatorio.json").write_text(json.dumps({
                "sha256": digest, "arquivo": iso.name}), encoding="utf-8")
            returned = {"resultado_dir": str(extracted), "sha256": "b" * 64,
                        "arquivo": iso.name}
            with patch("importador_perfis.process", return_value=returned):
                with self.assertRaisesRegex(RuntimeError, "não corresponde"):
                    import_rom(iso, output)
            self.assertFalse((output / "profiles").exists())

    def test_independent_matrices_bind_only_to_supplied_iso(self):
        checks, drops = drop_matrices()
        original = copy.deepcopy((checks, drops))
        result = validate_drop_associations(checks, drops, rom_sha256="a" * 64)
        self.assertTrue(result["valid"])
        self.assertEqual(result["rom_sha256"], "a" * 64)
        self.assertEqual(result["matrix_count"], 117)
        self.assertFalse(result["in_game_verified"])
        self.assertEqual((checks, drops), original)

    def test_declared_totals_do_not_replace_validation_of_actual_rows(self):
        for field, value in (("carta_id", 723), ("carta_id", True),
                             ("oponente_id", 40), ("rank", "other mod"),
                             ("peso", 2047), ("peso", -1)):
            with self.subTest(field=field, value=value):
                checks, drops = drop_matrices()
                drops[-1][field] = value
                result = validate_drop_associations(checks, drops, rom_sha256="a" * 64)
                self.assertFalse(result["valid"])

    def test_duplicate_matrix_and_duplicate_card_rows_are_rejected(self):
        checks, drops = drop_matrices()
        checks[-1] = checks[0]
        self.assertFalse(validate_drop_associations(checks, drops, rom_sha256="a" * 64)["valid"])
        checks, drops = drop_matrices()
        drops[0]["peso"] = 1024
        drops.append(dict(drops[0]))  # A correct sum still cannot justify duplicate card IDs.
        result = validate_drop_associations(checks, drops, rom_sha256="a" * 64)
        self.assertIn("drop_duplicate", result["errors"])
        self.assertFalse(result["valid"])

    def test_missing_rows_matrices_and_missing_iso_binding_are_rejected(self):
        checks, drops = drop_matrices()
        for a, b, sha in ((checks, drops[:-1], "a" * 64),
                          (checks[:-1], drops, "a" * 64),
                          (checks, drops, "61d58d83524683c8dc")):
            self.assertFalse(validate_drop_associations(a, b, rom_sha256=sha)["valid"])


if __name__ == "__main__":
    unittest.main()
