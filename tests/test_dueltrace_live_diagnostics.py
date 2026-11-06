"""Privacy, opt-in state, sampling and deduplication regression tests."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from dueltrace_live_diagnostics import (
    LiveDiagnosticsRecorder, sanitise_sample, MAX_EVENTS,
)


SHA = "a" * 64


def hand(ids=(449,145,447,629,468)):
    return {"ready": True, "status": "INTERNAL_PATH_C:\\secrets\\game.iso",
            "hand": [{"id": x, "name": "DO_NOT_EXPORT"} for x in ids],
            "source_path": "C:\\private.iso", "token": "SECRET_TOKEN"}


def opponent(status="ram_mapping_not_validated", oid=None):
    return {
        "status": status, "ready": oid is not None, "runtimeOpponentId": oid,
        "validationBreakdown": {
            "implausibleDrawHistory": 1, "unreadableFields": 3,
            "privateMemory": "RAW_RAM_SECRET",
        },
        "hostRAMAddress": "0xDEADBEEF", "processPath": "C:\\Users\\PRIVATE",
        "candidateBasesExamined": 128,
        "memoryRegionsExamined": 927,
    }


class DiagnosticsTests(unittest.TestCase):
    def test_sanitizer_never_exposes_raw_rom_or_host_secrets(self):
        sample = sanitise_sample(
            hand(), opponent(), {
                "ready": True, "state": "provisional", "score": 86,
                "category": "A-POW", "rawMemory": "SUPER_SECRET"
            })
        payload = json.dumps(sample)
        self.assertEqual(sample["hand"]["ids"], [449,145,447,629,468])
        self.assertEqual(sample["opponent"]["candidateBasesExamined"],128)
        self.assertEqual(sample["rank"]["scoreCandidate"],86)
        for secret in ("SECRET_TOKEN", "private.iso", "DO_NOT_EXPORT",
                       "0xDEADBEEF", "RAW_RAM_SECRET", "SUPER_SECRET"):
            self.assertNotIn(secret, payload)
        self.assertFalse(sample["rank"]["modelVerified"])
        self.assertFalse(sample["opponent"]["handAnchorValidated"])

    def test_sanitized_hand_anchor_diagnostics_do_not_claim_verified_id(self):
        sample = sanitise_sample(
            hand(),
            {
                "ready": False, "status": "ram_mapping_not_validated",
                "knownHandAnchorAtHint": True,
                "hintValidationBreakdown": {
                    "validatedHandAnchors": 1, "implausibleLifePoints": 1,
                    "secret": "C:\\\\private\\\\sample.bin",
                },
                "hostRAMAddress": "0xDEADBEEF",
            }, {})
        self.assertTrue(sample["opponent"]["knownHandAnchorAtHint"])
        self.assertEqual(
            sample["opponent"]["hintRejectionCounts"]["validatedHandAnchors"], 1)
        self.assertEqual(
            sample["opponent"]["hintRejectionCounts"]["implausibleLifePoints"], 1)
        self.assertFalse(sample["opponent"]["ready"])
        self.assertFalse(sample["opponent"]["handAnchorValidated"])
        self.assertIsNone(sample["opponent"]["candidateId"])
        dumped = json.dumps(sample)
        self.assertNotIn("hostRAMAddress", dumped)
        self.assertNotIn("0xDEADBEEF", dumped)
        self.assertNotIn("secret", dumped)

    def test_record_changes_and_deduplicate_identical_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = LiveDiagnosticsRecorder(Path(tmp),SHA)
            self.assertTrue(rec.observe(hand(),opponent(),{},SHA))
            self.assertTrue(rec.observe(hand(),opponent(),{},SHA))
            self.assertEqual(rec.report()["sampleCount"],2)
            self.assertEqual(rec.report()["changeCount"],1)
            self.assertTrue(rec.observe(hand(),opponent(oid=11),{},SHA))
            self.assertEqual(rec.report()["changeCount"],2)
            self.assertEqual(rec.report()["opponentStatuses"],{"ram_mapping_not_validated":2})
            self.assertEqual(rec.report()["candidateEvents"],1)
            self.assertEqual(rec.report()["candidateIdsObserved"],[11])
            self.assertFalse(rec.report()["candidateIdStableAcrossReadableChanges"])
            self.assertEqual(len(list(Path(tmp).glob(SHA+"_*.json"))),1)
            report=json.loads(rec.export_json())
            self.assertFalse(report["networkTransmission"])
            self.assertFalse(report["mayActivateDrops"])
            self.assertFalse(report["mayActivateRank"])
            self.assertNotIn(SHA,rec.export_json())

    def test_provisional_id_stability_across_hand_and_lp_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = LiveDiagnosticsRecorder(Path(tmp), SHA)
            def stable(id_value, lp):
                return {
                    "ready": True, "status": "runtime_id_candidate",
                    "runtimeOpponentId": id_value,
                    "validationMethod": "known_hand_anchor",
                    "knownHandAnchorAtHint": True,
                    "playerLP": lp, "opponentLP": 8000,
                }
            rec.observe(hand(),stable(5,5408),{},SHA)
            rec.observe(hand((426,58,533,281,450)),stable(5,5408),{},SHA)
            rec.observe(hand((426,58,533,281,450)),stable(5,3879),{},SHA)
            report = rec.report()
            self.assertEqual(report["candidateEvents"],3)
            self.assertEqual(report["candidateIdsObserved"],[5])
            self.assertTrue(report["candidateIdStableAcrossReadableChanges"])
            self.assertEqual(report["handAnchorValidatedChanges"],3)
            self.assertEqual(report["distinctLpPairsInReadableChanges"],2)
            self.assertTrue(report["events"][0]["data"]["opponent"]["handAnchorValidated"])
            self.assertFalse(report["verifiedOpponentMapping"])
            self.assertFalse(report["mayActivateDrops"])
            rec.observe(hand(),stable(6,3879),{},SHA)
            report = rec.report()
            self.assertFalse(report["candidateIdStableAcrossReadableChanges"])
            self.assertEqual(report["candidateIdsObserved"],[5,6])
            self.assertFalse(report["verifiedOpponentMapping"])

    def test_change_of_iso_stops_local_diagnostics_without_cross_mod_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec=LiveDiagnosticsRecorder(Path(tmp),SHA)
            rec.observe(hand(),opponent(),{},SHA)
            self.assertFalse(rec.observe(hand(),opponent(),{},"b"*64))
            self.assertFalse(rec.running)
            self.assertFalse(rec.observe(hand(),opponent(),{},SHA))
            self.assertEqual(rec.report()["changeCount"],1)

    def test_malformed_fields_and_statuses_are_redacted(self):
        sample=sanitise_sample(
            {"ready":True,"hand":[{"id":True},{"id":1000}]},
            {"ready":True,"runtimeOpponentId":"11","status":"C:\\secret",
             "validationMethod":"private_host_address"},
            {"ready":True,"score":True,"category":"INVALID_SECRET",
             "state":"arbitrary-private-data"})
        self.assertFalse(sample["hand"]["ready"])
        self.assertEqual(sample["hand"]["ids"],[])
        self.assertIsNone(sample["opponent"]["candidateId"])
        self.assertEqual(sample["opponent"]["status"],"unknown")
        self.assertEqual(sample["rank"]["state"],"unknown")
        self.assertIsNone(sample["rank"]["scoreCandidate"])
        self.assertEqual(sample["rank"]["categoryCandidate"],"unknown")

    def test_invalid_session_sha_and_event_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                LiveDiagnosticsRecorder(Path(tmp),"../private")
            rec=LiveDiagnosticsRecorder(Path(tmp),SHA)
            for i in range(MAX_EVENTS+12):
                ids=(449,145,447,629, 1+(i%722))
                rec.observe(hand(ids),opponent(oid=i%40),{},SHA)
            report=rec.report()
            self.assertEqual(report["sampleCount"],MAX_EVENTS+12)
            self.assertLessEqual(report["changeCount"],MAX_EVENTS)
            exported=rec.export_json()
            self.assertLessEqual(len(exported.encode("utf-8")),140000)
            self.assertNotIn("C:\\",exported)


if __name__ == "__main__":
    unittest.main()
