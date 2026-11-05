"""Offline evidence validation tests. No real game data is used."""
from __future__ import annotations
import hashlib
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))
from dueltrace_real_iso_validation import (
    validate_real_iso_samples, main, hash_local_file, MAX_IMAGE_BYTES
)

SHA = "a" * 64
EXE_SHA = "b" * 64


def candidate():
    return {
        "status": "catalogo_candidato_reconstruido",
        "romSha256": SHA, "exeSha256": EXE_SHA,
        "validated": False, "inGameVerified": False, "mayActivate": False,
        "cardsCount": 722, "opponentsCount": 39,
        "cards": [{"id": i, "nome": f"CARD {i:03d}", "atk": 100 + i,
                   "def": 200 + i, "tipo": i % 24} for i in range(1, 723)],
        "opponents": [{"id": i, "nome": f"OPP {i}"} for i in range(1, 40)],
    }


def evidence(cat):
    ids = (1, 50, 150, 200, 250, 350, 362, 410, 500, 544, 620, 722)
    return {"schema": 1, "source": "epsxe_observacao_independente",
            "romSha256": cat["romSha256"],
            "cards": [dict(cat["cards"][i-1], evidenceRef=f"local-frame-{i}")
                      for i in ids]}


class SampleValidationTests(unittest.TestCase):
    def test_all_quartiles_match_but_never_promote(self):
        cat = candidate()
        rep = validate_real_iso_samples(cat, evidence(cat))
        self.assertEqual(rep["status"], "amostra_coerente_pendente_prova_completa")
        self.assertEqual(rep["matchedCount"], 12)
        self.assertEqual(rep["quartileCoverage"], [3, 3, 3, 3])
        self.assertFalse(rep["mayActivate"])
        self.assertFalse(rep["inGameValidationClaimed"])
        self.assertFalse(rep["promoted"])
        self.assertNotIn("local-frame", str(rep))
        self.assertNotIn("CARD", str(rep))

    def test_wrong_rom_rejected_without_comparing(self):
        cat = candidate()
        observed = evidence(cat)
        observed["romSha256"] = "c" * 64
        rep = validate_real_iso_samples(cat, observed)
        self.assertEqual(rep["status"], "iso_sha_divergente")
        self.assertEqual(rep["matchedCount"], 0)

    def test_divergence_kept_for_investigation(self):
        cat = candidate()
        obs = evidence(cat)
        obs["cards"][0]["nome"] += "v"
        obs["cards"][1]["atk"] += 100
        obs["cards"][2]["tipo"] += 1
        rep = validate_real_iso_samples(cat, obs)
        self.assertEqual(rep["status"], "divergencias_detectadas")
        self.assertEqual(rep["mismatchedCount"], 3)
        self.assertEqual(rep["divergences"], [
            {"id": 1, "fields": ["nome"]},
            {"id": 50, "fields": ["atk"]},
            {"id": 150, "fields": ["tipo"]}])

    def test_small_coverage_does_not_certify_catalogue(self):
        cat = candidate()
        obs = evidence(cat)
        obs["cards"] = obs["cards"][:3]
        self.assertEqual(validate_real_iso_samples(cat, obs)["status"],
                         "amostra_coerente_mas_insuficiente")

    def test_duplicate_cards_and_missing_reference_refused(self):
        cat = candidate()
        obs = evidence(cat)
        obs["cards"].append(obs["cards"][0])
        self.assertEqual(validate_real_iso_samples(cat, obs)["status"],
                         "observacoes_duplicadas")
        obs = evidence(cat)
        del obs["cards"][0]["evidenceRef"]
        self.assertEqual(validate_real_iso_samples(cat, obs)["status"],
                         "referencia_evidencia_ausente")

    def test_quarantine_flags_required(self):
        original = candidate()
        for flag in ("validated", "inGameVerified", "mayActivate"):
            cat = candidate()
            cat[flag] = True
            self.assertEqual(
                validate_real_iso_samples(cat, evidence(original))["status"],
                "catalogo_candidato_invalido")

    def test_cli_report_contains_only_aggregates(self):
        cat = candidate()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "candidate.json").write_text(json.dumps(cat), encoding="utf8")
            (base / "observations.json").write_text(
                json.dumps(evidence(cat)), encoding="utf8")
            out = base / "out.json"
            with redirect_stdout(StringIO()):
                result = main(["--candidate", str(base / "candidate.json"),
                               "--observations", str(base / "observations.json"),
                               "--output", str(out)])
            self.assertEqual(result, 0)
            content = out.read_text(encoding="utf8")
            self.assertNotIn("local-frame", content)
            self.assertNotIn("CARD", content)
            self.assertEqual(json.loads(content)["matchedCount"], 12)

    def test_opponent_names_match_and_remain_quarantined(self):
        cat = candidate()
        obs = evidence(cat)
        obs["opponents"] = [
            {**cat["opponents"][0], "evidenceRef": "epsxe-opponent1"},
            {**cat["opponents"][38], "evidenceRef": "epsxe-opponent39"}]
        rep = validate_real_iso_samples(cat, obs)
        self.assertEqual(rep["opponentsMatched"], 2)
        self.assertEqual(rep["status"], "amostra_coerente_pendente_prova_completa")
        self.assertFalse(rep["mayActivate"])

    def test_opponent_trailing_glyph_not_stripped(self):
        cat = candidate()
        obs = evidence(cat)
        obs["opponents"] = [
            {**cat["opponents"][0], "nome": "OPP 1v",
             "evidenceRef": "local-frame"}]
        rep = validate_real_iso_samples(cat, obs)
        self.assertEqual(rep["opponentsMismatched"], 1)
        self.assertEqual(rep["divergences"], [
            {"opponentId": 1, "fields": ["nome"]}])

    def test_duplicate_opponent_rejected(self):
        cat = candidate()
        obs = evidence(cat)
        x = {**cat["opponents"][0], "evidenceRef": "frame"}
        obs["opponents"] = [x, x]
        self.assertEqual(validate_real_iso_samples(cat, obs)["status"],
                         "oponentes_duplicados")

    def test_boolean_id_is_not_integer_identity(self):
        cat = candidate()
        cat["cards"][0]["id"] = True
        self.assertEqual(validate_real_iso_samples(cat, evidence(candidate()))["status"],
                         "catalogo_candidato_invalido")

    def test_executable_hash_mismatch_rejected(self):
        cat = candidate()
        obs = evidence(cat)
        obs["exeSha256"] = "c" * 64
        self.assertEqual(validate_real_iso_samples(cat, obs)["status"],
                         "executavel_sha_divergente")
        self.assertEqual(validate_real_iso_samples(cat, obs,
                          exe_sha256="d" * 64)["status"],
                         "executavel_arquivo_divergente")

    def test_hash_of_actual_image_rejects_wrong_candidate(self):
        cat = candidate()
        obs = evidence(cat)
        bad = validate_real_iso_samples(cat, obs, image_sha256="b" * 64)
        self.assertEqual(bad["status"], "iso_arquivo_divergente")
        good = validate_real_iso_samples(cat, obs, image_sha256=SHA)
        self.assertTrue(good["imageHashChecked"])

    def test_out_of_bounds_card_attributes_rejected(self):
        cat = candidate()
        cat["cards"][99]["atk"] = 6000
        self.assertEqual(validate_real_iso_samples(cat, evidence(candidate()))["status"],
                         "catalogo_candidato_invalido")

    def test_invalid_name_rejected(self):
        cat = candidate()
        cat["cards"][0]["nome"] = "A" * 65
        self.assertEqual(validate_real_iso_samples(cat, evidence(candidate()))["status"],
                         "catalogo_candidato_invalido")

    def test_missing_type_can_be_unobserved(self):
        cat = candidate()
        obs = evidence(cat)
        for row in obs["cards"]:
            del row["tipo"]
        rep = validate_real_iso_samples(cat, obs)
        self.assertEqual(rep["typeComparedCount"], 0)
        self.assertFalse(rep["inGameValidationClaimed"])

    def test_binary_file_hash_is_full_and_stable(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "synthetic.bin"
            file.write_bytes(b"not a real game binary")
            self.assertEqual(hash_local_file(file, max_bytes=MAX_IMAGE_BYTES),
                             hashlib.sha256(file.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
