"""No-network regression tests for explicit private evidence upload."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from dueltrace_live_diagnostics import LiveDiagnosticsRecorder
from dueltrace_private_evidence_sync import (
    EvidenceSyncError, GitHubPrivateRepositorySink, PrivateEvidenceSync,
    WindowsTokenStore, validate_private_repository, validate_sanitized_report,
    validate_iso_forensic_report,
)


SHA = "a" * 64


def example_recorder(folder):
    rec = LiveDiagnosticsRecorder(Path(folder), SHA)
    rec.observe(
        {"ready": True, "hand": [
            {"id": id_value, "name": "NEVER_REMOTE"}
            for id_value in (284, 55, 58, 653, 281)
        ]},
        {"ready": True, "status": "runtime_id_candidate",
         "validationMethod": "known_hand_anchor",
         "runtimeOpponentId": 5, "playerLP": 3879, "opponentLP": 1062,
         "hostRAMAddress": "0xDEADBEEF"},
        {"ready": False, "state": "unavailable"}, SHA,
    )
    rec.stop()
    return rec


class FakeTokenStore:
    def __init__(self):
        self.value = None
    def save(self, value):
        self.value = value
    def load(self):
        return self.value
    def clear(self):
        self.value = None


class FakeSink:
    def __init__(self):
        self.calls = []
    def verify(self, repo, token):
        validate_private_repository(repo)
        self.calls.append(("verify",repo,token))
        return repo
    def upload(self, repo, token, session_id, report):
        self.calls.append(("upload", repo, token, session_id, report))
        validate_sanitized_report(report)
        return {"synced":True}
    def upload_iso_forensic(self,repo,token,report):
        validate_iso_forensic_report(report)
        self.calls.append(("iso",repo,token,report))
        return {"synced":True,"fingerprint":report["romFingerprint"]}


def example_iso_report():
    return {
        "schema":1,"subject":"DUELTRACE ISO Forensic Lab",
        "inspectedAtUTC":"2026-11-06T23:32:10+00:00",
        "romFingerprint":"a"*12,"exactSha256Matched":True,
        "fileSizeBytes":115_212_720,
        "disc":{"sectorBytes":2352,"indexedFiles":9,
                "resourceSelection":"unique_canonical_resource",
                "resourceBytesRead":38_148_608},
        "executable":{"state":"structural_psx_exe",
                      "coherent":True,
                      "physicalPaddingVerified":False,
                      "candidatesTried":1},
        "cards":{"state":"complete_722","count":722},
        "opponents":{"state":"independent_structural_39",
                     "count":39,"namesStructural":39,
                     "affineLengthException":False,
                     "inGameIdentityVerified":False},
        "rank":{"state":"structural_only","staticCandidates":5,
                "executionConfirmed":False},
        "drops":{"state":"117_structural_unlabeled",
                 "validatedStructuralMatrices":117,
                 "labelsVerified":False,"opponentMappingVerified":False},
        "weightFamily":{"state":"unique_structural_candidate",
                        "matrixCount":156,"distinct39Windows":1,
                        "ambiguous":False,
                        "base":0x2421800,"opponentStep":0x1800,
                        "matrixStride":0x5b4,
                        "distributionEncoding":"plain_deck_masked_drops",
                        "opponentMappingVerified":False,
                        "rankGroupLabelsVerified":False,
                        "mayActivateDrops":False},
        "fusions":{"state":"seven_consistent_conflicts_quarantined",
                   "validBanks":7,"matchingBanks":7,
                   "recipes":5555,"conflictingPairs":3,
                   "unambiguousPairs":5549,
                   "resourceMethod":"canonical",
                   "mayActivate":False},
        "images":{"state":"complete","large":722,"thumbnails":722,
                  "duplicateDifferences":56,"checked":722},
        "verifiedInGame":False,"mayActivateDrops":False,
        "mayActivateRank":False,"mayActivateFusions":False,
        "networkTransmission":False,
        "note":"A leitura estrutural da ISO nao confirma IDs ou grupos RANK no jogo.",
    }


class FakeResponse:
    status = 200
    def __init__(self, data):
        self.data = json.dumps(data).encode()
    def __enter__(self):
        return self
    def __exit__(self, typ, value, tb):
        return False
    def read(self, size):
        return self.data[:size]


class FakeOpener:
    def __init__(self, private=True):
        self.private = private
        self.calls = []
    def open(self, req, timeout):
        self.calls.append(req)
        if req.full_url == "https://api.github.com/repos/tester/private-evidence":
            return FakeResponse({
                "private": self.private, "full_name": "tester/private-evidence",
                "permissions": {"push": True},
            })
        if req.method == "GET":
            raise HTTPError(req.full_url, 404, "Not found", {}, None)
        if req.method == "PUT":
            return FakeResponse({"commit": {"sha": "a"*40}})
        raise AssertionError("unexpected network request")


class PrivateEvidenceTests(unittest.TestCase):
    def test_explicit_opt_in_and_disable_with_no_upload_on_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink, creds = FakeSink(), FakeTokenStore()
            sync = PrivateEvidenceSync(Path(tmp), sink=sink, token_store=creds)
            self.assertFalse(sync.status()["enabled"])
            rec = example_recorder(tmp)
            self.assertFalse(sync.upload(rec)["synced"])
            self.assertFalse(sink.calls)
            with self.assertRaises(EvidenceSyncError):
                sync.configure("tester/private-evidence", "fake-secret", False)
            self.assertFalse(sink.calls)
            status = sync.configure("tester/private-evidence", "fake-secret", True)
            self.assertTrue(status["enabled"])
            self.assertFalse(status["remoteIsChatGPTConnection"])
            self.assertNotIn("fake-secret", json.dumps(status))
            self.assertNotIn("fake-secret",
                (Path(tmp)/"private_sync_settings.json").read_text())
            self.assertTrue(sync.upload(rec)["synced"])
            self.assertEqual(sink.calls[-1][0], "upload")
            self.assertNotIn("NEVER_REMOTE", sink.calls[-1][-1])
            self.assertNotIn("0xDEADBEEF", sink.calls[-1][-1])
            self.assertNotIn("fake-secret", sink.calls[-1][-1])
            sync.disable()
            self.assertIsNone(creds.value)
            self.assertFalse(sync.upload(rec)["synced"])

    def test_private_repository_verification_refuses_public(self):
        sink = GitHubPrivateRepositorySink(FakeOpener(private=False))
        with self.assertRaisesRegex(EvidenceSyncError,"privados"):
            sink.verify("tester/private-evidence", "token-"+"x"*30)
        for repo in ("https://evil.net/repo", "../private", "a/../../b",
                     "a/.hidden", "a/b.git", "a/b/c"):
            with self.subTest(repo=repo), self.assertRaises(EvidenceSyncError):
                validate_private_repository(repo)

    def test_private_upload_never_sends_token_or_raw_rom(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec=example_recorder(tmp)
            token="github_pat_" + "x"*45
            opener=FakeOpener()
            sink=GitHubPrivateRepositorySink(opener)
            result=sink.upload("tester/private-evidence",token,
                               rec.session_id,rec.export_json())
            self.assertTrue(result["synced"])
            self.assertEqual(len(opener.calls),3)
            put=opener.calls[2]
            self.assertEqual(put.method, "PUT")
            self.assertEqual(put.full_url,
                "https://api.github.com/repos/tester/private-evidence/contents/"
                "reports/aaaaaaaaaaaa/" + rec.session_id + ".json")
            body=json.loads(put.data)
            decoded=base64.b64decode(body["content"]).decode()
            self.assertNotIn("0xDEADBEEF",decoded)
            self.assertNotIn("NEVER_REMOTE",decoded)
            self.assertNotIn(token,decoded)
            remote=json.loads(decoded)
            self.assertEqual(remote["transport"],"github_private_repository")
            self.assertEqual(remote["subject"],"DUELTRACE Private Evidence Sync")
            self.assertEqual(remote["diagnostics"]["networkTransmission"],False)
            self.assertFalse(remote["diagnostics"]["verifiedOpponentMapping"])

    def test_iso_forensic_send_is_separate_explicit_and_private(self):
        report=example_iso_report()
        sink=FakeSink()
        creds=FakeTokenStore()
        with tempfile.TemporaryDirectory() as tmp:
            sync=PrivateEvidenceSync(Path(tmp),sink=sink,token_store=creds)
            with self.assertRaises(EvidenceSyncError):
                sync.upload_forensic(report)
            self.assertFalse(sink.calls)
            sync.configure("tester/private-evidence","secret",True)
            self.assertEqual(len(sink.calls),1)  # verification only
            result=sync.upload_forensic(report)
            self.assertTrue(result["synced"])
            self.assertEqual(sink.calls[-1][0],"iso")
            sync.disable()
            with self.assertRaises(EvidenceSyncError):
                sync.upload_forensic(report)
            self.assertIsNone(creds.value)

    def test_real_galaxy_rank_scanner_exceeds_old_private_upload_limit(self):
        # Derived from the real 2025 Galaxy image: 1070 heuristic windows,
        # whereas the six best candidates are only a UI display subset.
        report=example_iso_report()
        report["rank"]["staticCandidates"]=1070
        self.assertEqual(
            validate_iso_forensic_report(report)["rank"]["staticCandidates"],
            1070)
        report["rank"]["staticCandidates"]=65537
        with self.assertRaises(EvidenceSyncError):
            validate_iso_forensic_report(report)
        # A static MIPS count never upgrades the in-game evidence flags.
        report["rank"]["staticCandidates"]=1070
        self.assertFalse(report["rank"]["executionConfirmed"])
        self.assertFalse(report["mayActivateRank"])

    def test_iso_forensic_endpoint_is_explicit_and_no_content_leaks(self):
        report=example_iso_report()
        token="github_pat_"+"x"*45
        opener=FakeOpener()
        sink=GitHubPrivateRepositorySink(opener)
        result=sink.upload_iso_forensic("tester/private-evidence",token,report)
        self.assertTrue(result["synced"])
        self.assertEqual(len(opener.calls),3)
        put=opener.calls[-1]
        self.assertEqual(put.method,"PUT")
        self.assertTrue(put.full_url.endswith(
            "/contents/reports/iso-forensics/aaaaaaaaaaaa.json"))
        envelope=json.loads(base64.b64decode(
            json.loads(put.data)["content"]))
        self.assertEqual(envelope["subject"],"DUELTRACE Private ISO Forensic Sync")
        self.assertEqual(envelope["diagnostics"]["fusions"]["conflictingPairs"],3)
        self.assertFalse(envelope["diagnostics"]["networkTransmission"])
        self.assertNotIn(token,json.dumps(envelope))
        self.assertNotIn("source_path",json.dumps(envelope))
        self.assertNotIn(".iso",json.dumps(envelope))
        with self.assertRaises(EvidenceSyncError):
            GitHubPrivateRepositorySink(FakeOpener(private=False)).upload_iso_forensic(
                "tester/private-evidence",token,report)

    def test_forensic_schema_rejects_raw_names_paths_and_promotion(self):
        report=example_iso_report()
        self.assertEqual(validate_iso_forensic_report(report),report)
        report["rawRomBytes"]="SECRET"
        with self.assertRaises(EvidenceSyncError):
            validate_iso_forensic_report(report)
        report.pop("rawRomBytes")
        report["images"]["localPath"]="C:/USERS/private"
        with self.assertRaises(EvidenceSyncError):
            validate_iso_forensic_report(report)
        report["images"].pop("localPath")
        report["mayActivateFusions"]=True
        with self.assertRaises(EvidenceSyncError):
            validate_iso_forensic_report(report)
        report["mayActivateFusions"]=False
        report["fusions"]["resourceMethod"]="C:/secrets"
        with self.assertRaises(EvidenceSyncError):
            validate_iso_forensic_report(report)

    @unittest.skipUnless(sys.platform == "win32", "Windows DPAPI only")
    def test_windows_user_scoped_dpapi_credential_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=WindowsTokenStore(Path(tmp)/"credential.bin")
            secret="github_pat_" + "x"*50
            store.save(secret)
            self.assertTrue(store.path.is_file())
            self.assertNotIn(secret.encode(),store.path.read_bytes())
            self.assertEqual(store.load(),secret)
            store.clear()
            self.assertFalse(store.path.exists())
            self.assertIsNone(store.load())

    def test_fail_closed_on_unexpected_fields_or_raw_dumps(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec=example_recorder(tmp)
            report=json.loads(rec.export_json())
            report["ramDump"]="TOP_SECRET"
            with self.assertRaises(EvidenceSyncError):
                validate_sanitized_report(json.dumps(report))
            report.pop("ramDump")
            report["events"][0]["data"]["opponent"]["processPath"]="C:\\secret"
            with self.assertRaises(EvidenceSyncError):
                validate_sanitized_report(json.dumps(report))
            report["events"][0]["data"]["opponent"].pop("processPath")
            report["mayActivateDrops"]=True
            with self.assertRaises(EvidenceSyncError):
                validate_sanitized_report(json.dumps(report))


if __name__ == "__main__":
    unittest.main()
