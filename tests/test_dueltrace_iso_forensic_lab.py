"""Offline, source-bound regression for the one-click ISO forensic laboratory."""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_iso_forensic_lab import inspect_iso, IsoForensicError


class DummyDisc:
    closed=False
    sector=2352
    files={"DATA/SLUS_014.11":(2,2_000_000),
           "DATA/WA_MRG.MRG":(5,38_148_608)}
    def __init__(self,path):
        self.path=path
    def get(self,name,limit_bytes=None):
        return b"PRIVATE_ROM_BYTES"
    def close(self):
        self.closed=True


def full_family(*, ambiguous=False):
    hit={"base":0x2421800, "opponentStep":0x1800,
         "matrixStride":0x5b4,"encoding":"plain_deck_masked_drops",
         "opponentBlocks":39,"deckMatrices":39,
         "unlabeledDistributionMatrices":117,"matrixCount":156}
    return {
        "state":"single_family_unmapped_windows" if ambiguous else
                "unique_structural_candidate",
        "candidateCount":2 if ambiguous else 1,
        "selected":None if ambiguous else hit,
        "candidates":[hit,dict(hit,base=0x2423000)] if ambiguous else [hit],
        "ambiguous39BlockWindows":ambiguous,
        "clusters":[{"possible39BlockWindows":2 if ambiguous else 1}],
    }


def mocks(stack, *, ambiguous=False, mutation=None, source=None):
    stack.enter_context(patch(
        "dueltrace_iso_forensic_lab.Disc",DummyDisc))
    stack.enter_context(patch(
        "dueltrace_iso_forensic_lab._candidate_exes",
        return_value=["DATA/SLUS_014.11"]))
    stack.enter_context(patch(
        "dueltrace_iso_forensic_lab.select_known_executable_layout",
        return_value=("DATA/SLUS_014.11",b"PS-X EXE"+b"\0"*64,[],
                      [{"id":i} for i in range(1,723)],
                      "722 cartas", [{
                          "name":"DATA/SLUS_014.11",
                          "executableSectorPadding":{
                              "headerCoherent":True,
                              "state":"padding_zero_verificado"}}])))
    stack.enter_context(patch(
        "dueltrace_iso_forensic_lab.discover_independent_opponents",
        return_value={"selected":{"opponents":[
            {"id":i,"nome":"SECRET_NAME"} for i in range(1,40)],
            "lengthFieldAnomaly":True}}))
    stack.enter_context(patch(
        "dueltrace_iso_forensic_lab.inspect_mips_rank_routines",
        return_value={"status":"structural_only","candidate_count":5,
                      "rank_routine_confirmed":False}))
    stack.enter_context(patch(
        "dueltrace_iso_forensic_lab.discover_weight_families",
        return_value=full_family(ambiguous=ambiguous)))
    stack.enter_context(patch(
        "dueltrace_iso_forensic_lab._safe_fusions",
        return_value={"state":"seven_consistent_conflicts_quarantined",
                      "validBanks":7,"matchingBanks":7,
                      "recipes":5555,"conflictingPairs":3,
                      "unambiguousPairs":5549,"mayActivate":False}))
    if mutation is not None:
        def read_art(wa):
            mutation.write_bytes(b"x"*4097)
            return {"state":"complete","large":722,"thumbnails":722,
                    "duplicateDifferences":56,"checked":722}
        stack.enter_context(patch("dueltrace_iso_forensic_lab._art_integrity",
                                  side_effect=read_art))
    else:
        stack.enter_context(patch("dueltrace_iso_forensic_lab._art_integrity",
            return_value={"state":"complete","large":722,"thumbnails":722,
                          "duplicateDifferences":56,"checked":722}))
    def decode(*args,**kwargs):
        if not kwargs:
            return None,"offset legado incompatível"
        return {"verificacao":[{"peso_total":2048} for _ in range(117)],
                "drops":[{"carta_id":7,"peso":10}]}, "117 tabelas"
    stack.enter_context(patch("dueltrace_iso_forensic_lab.decode_drops",
                              side_effect=decode))


class IsoForensicLabTests(unittest.TestCase):
    def test_rising_like_iso_all_stages_but_no_runtime_promotion(self):
        with tempfile.TemporaryDirectory() as folder:
            image=Path(folder)/"sample.iso"
            image.write_bytes(b"x"*4096)
            sha=hashlib.sha256(image.read_bytes()).hexdigest()
            with ExitStack() as stack:
                mocks(stack)
                report=inspect_iso(image,sha)
        self.assertTrue(report["exactSha256Matched"])
        self.assertEqual(report["cards"]["count"],722)
        self.assertEqual(report["opponents"]["count"],39)
        self.assertTrue(report["opponents"]["affineLengthException"])
        self.assertEqual(report["images"]["large"],722)
        self.assertEqual(report["images"]["duplicateDifferences"],56)
        self.assertEqual(report["drops"]["validatedStructuralMatrices"],117)
        self.assertEqual(report["weightFamily"]["base"],0x2421800)
        self.assertEqual(report["fusions"]["recipes"],5555)
        self.assertEqual(report["fusions"]["conflictingPairs"],3)
        self.assertFalse(report["mayActivateDrops"])
        self.assertFalse(report["mayActivateFusions"])
        self.assertFalse(report["verifiedInGame"])
        self.assertFalse(report["networkTransmission"])
        rendered=json.dumps(report)
        for forbidden in (str(image),"sample.iso","PRIVATE_ROM_BYTES",
                          "SECRET_NAME","source_path","fusion_recipes"):
            self.assertNotIn(forbidden,rendered)

    def test_40_block_enhance_layout_refuses_opponent_assignment(self):
        with tempfile.TemporaryDirectory() as folder:
            image=Path(folder)/"enhance.bin"
            image.write_bytes(b"x"*4096)
            sha=hashlib.sha256(image.read_bytes()).hexdigest()
            with ExitStack() as stack:
                mocks(stack,ambiguous=True)
                report=inspect_iso(image,sha)
        self.assertEqual(report["drops"]["state"],"ambiguous_39_window")
        self.assertEqual(report["weightFamily"]["distinct39Windows"],2)
        self.assertIsNone(report["weightFamily"]["base"])
        self.assertFalse(report["drops"]["opponentMappingVerified"])
        self.assertFalse(report["rank"]["executionConfirmed"])

    def test_wrong_sha_fails_closed_without_opening_iso(self):
        with tempfile.TemporaryDirectory() as folder:
            image=Path(folder)/"wrong.iso"
            image.write_bytes(b"x"*4096)
            with patch("dueltrace_iso_forensic_lab.Disc") as disc:
                with self.assertRaisesRegex(IsoForensicError,"SHA"):
                    inspect_iso(image,"0"*64)
                disc.assert_not_called()

    def test_mutated_iso_during_probe_is_discarded(self):
        with tempfile.TemporaryDirectory() as folder:
            image=Path(folder)/"mutating.bin"
            image.write_bytes(b"x"*4096)
            sha=hashlib.sha256(image.read_bytes()).hexdigest()
            with ExitStack() as stack:
                mocks(stack,mutation=image)
                with self.assertRaisesRegex(IsoForensicError,"alterada"):
                    inspect_iso(image,sha)


if __name__=="__main__":
    unittest.main()
