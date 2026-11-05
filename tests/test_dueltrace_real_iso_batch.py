"""Batch compatibility review tests using only synthetic files."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))
sys.path.insert(0, str(ROOT / "tests"))
from dueltrace_real_iso_batch import run_batch, main
from test_dueltrace_real_iso_validation import candidate, evidence


class BatchTests(unittest.TestCase):
    def test_bad_batch_and_too_many_images_rejected(self):
        for invalid in (None, {}, {"schema": 1, "mods": []},
                        {"schema": 1, "mods": [{}]},
                        {"schema": 1, "mods": [{}] * 129}):
            with self.subTest(invalid=str(invalid)[:20]):
                with self.assertRaises(ValueError):
                    run_batch(invalid)

    def test_valid_synthetic_media_is_hash_bound_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            iso = p / "sample.iso"
            iso.write_bytes(b"LOCAL SYNTHETIC DISC IMAGE")
            sha = hashlib.sha256(iso.read_bytes()).hexdigest()
            cat = candidate()
            cat["romSha256"] = sha
            obs = evidence(cat)
            (p / "candidate.json").write_text(json.dumps(cat), encoding="utf8")
            (p / "observations.json").write_text(json.dumps(obs), encoding="utf8")
            report = run_batch({"schema": 1, "mods": [{"image": str(iso),
                "candidate": str(p / "candidate.json"),
                "observations": str(p / "observations.json")}]})
            self.assertEqual(report["processed"], 1)
            self.assertEqual(report["sampleCoherentCount"], 1)
            self.assertEqual(report["results"][0]["romSha256"], sha)
            self.assertFalse(report["validationComplete"])
            self.assertFalse(report["mayActivate"])
            self.assertFalse(report["inGameValidationClaimed"])
            self.assertNotIn(str(p), json.dumps(report))
            self.assertNotIn("CARD", json.dumps(report))
            self.assertNotIn("local-frame", json.dumps(report))

    def test_missing_catalogue_never_fabricates_data(self):
        with tempfile.TemporaryDirectory() as directory:
            iso = Path(directory) / "unknown.bin"
            iso.write_bytes(b"UNRECOGNIZED SYNTHETIC DISC")
            report = run_batch({"schema": 1, "mods": [{"image": str(iso)}]})
            self.assertEqual(report["results"][0]["status"], "sem_catalogo_candidato")
            self.assertEqual(report["results"][0]["cardSamples"], 0)
            self.assertFalse(report["anyModUniversallySupported"])

    def test_duplicate_images_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            iso = Path(directory) / "same.bin"
            iso.write_bytes(b"SAME SYNTHETIC DISC")
            with self.assertRaisesRegex(ValueError, "duplicada"):
                run_batch({"schema": 1, "mods": [
                    {"image": str(iso)}, {"image": str(iso)}]})

    def test_catalogue_of_another_image_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            iso = p / "other.iso"
            iso.write_bytes(b"DIFFERENT SYNTHETIC ISO")
            cat = candidate()
            obs = evidence(cat)
            (p / "candidate.json").write_text(json.dumps(cat), encoding="utf8")
            (p / "obs.json").write_text(json.dumps(obs), encoding="utf8")
            report = run_batch({"schema": 1, "mods": [{"image": str(iso),
                "candidate": str(p / "candidate.json"),
                "observations": str(p / "obs.json")}]})
            self.assertEqual(report["results"][0]["status"], "iso_arquivo_divergente")
            self.assertEqual(report["sampleCoherentCount"], 0)

    def test_missing_half_of_evidence_is_not_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            iso = p / "one.iso"
            iso.write_bytes(b"SYNTHETIC")
            report = run_batch({"schema": 1, "mods": [{"image": str(iso),
                "candidate": str(p / "candidate.json")}]})
            self.assertEqual(report["results"][0]["status"], "evidencia_incompleta")

    def test_cli_never_overwrites_iso_or_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            iso = p / "unique.iso"
            iso.write_bytes(b"SYNTHETIC ISO CONTENT")
            evidence_file = p / "candidate.json"
            evidence_file.write_text("{}", encoding="utf8")
            observations_file = p / "obs.json"
            observations_file.write_text("{}", encoding="utf8")
            manifest = p / "manifest.json"
            manifest.write_text(json.dumps({"schema": 1, "mods": [{
                "image": str(iso), "candidate": str(evidence_file),
                "observations": str(observations_file)}]}), encoding="utf8")
            for target in (iso, evidence_file, observations_file):
                before = target.read_bytes()
                with redirect_stderr(StringIO()):
                    with self.assertRaises(SystemExit):
                        main(["--manifest", str(manifest), "--output", str(target)])
                self.assertEqual(target.read_bytes(), before)

    def test_opponent_evidence_is_aggregate_only(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            iso = p / "sample.bin"
            iso.write_bytes(b"SYNTHETIC IMAGE FOR GAME")
            sha = hashlib.sha256(iso.read_bytes()).hexdigest()
            cat = candidate()
            cat["romSha256"] = sha
            obs = evidence(cat)
            obs["opponents"] = [{**cat["opponents"][0],
                                 "evidenceRef": "local-screenshot"}]
            (p / "candidate.json").write_text(json.dumps(cat), encoding="utf8")
            (p / "obs.json").write_text(json.dumps(obs), encoding="utf8")
            report = run_batch({"schema": 1, "mods": [{
                "image": str(iso), "candidate": str(p / "candidate.json"),
                "observations": str(p / "obs.json")}]})
            self.assertEqual(report["results"][0]["opponentSamples"], 1)
            self.assertNotIn("OPP", json.dumps(report))
            self.assertNotIn("screenshot", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
