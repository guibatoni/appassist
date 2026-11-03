"""Auditoria de execução: dados sintéticos simulam logs de depurador MIPS."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_mips_duel_trace import inspect_duel_mips_trace, MAX_TRACE_BYTES


class DuelTraceTests(unittest.TestCase):
    def setUp(self):
        self.report={"available":True,"candidates":[
            {"pc":"0x80012040","score":15,"file_offset":0x840},
            {"pc":"0x80015000","score":14,"file_offset":0x3800},
        ]}

    def test_real_execution_pc_evidence_is_not_claimed_as_rank_routine(self):
        log=b"\n".join(
            (f"frame={i//10} PC=0x{0x80012000+(i%17)*4:08X}".encode()
             for i in range(100))
        )+b"\nPC=0x80012040\n"
        result=inspect_duel_mips_trace(log,self.report)
        self.assertTrue(result["available"])
        self.assertTrue(result["executionEvidence"])
        self.assertFalse(result["rankRoutineConfirmed"])
        self.assertEqual(result["status"],"candidate_pc_executed")
        self.assertEqual(result["executedCandidates"][0]["pc"],"0x80012040")
        self.assertEqual(len(result["traceSha256"]),64)

    def test_static_dump_without_pc_marker_not_considered_execution(self):
        log=b"\n".join(b"0x80012040 0x12345678" for i in range(200))
        r=inspect_duel_mips_trace(log,self.report)
        self.assertEqual(r["status"],"insufficient_execution_trace")
        self.assertFalse(r["executionEvidence"])

    def test_small_or_malicious_trace_never_confirms_execution(self):
        for raw in (b"PC=0x80012040",b"",b"x"*(MAX_TRACE_BYTES+1)):
            result=inspect_duel_mips_trace(raw,self.report)
            self.assertFalse(result["executionEvidence"])
        self.assertFalse(inspect_duel_mips_trace(b"PC=0x80012040",None)["executionEvidence"])

    def test_valid_trace_without_pc_hits_is_not_verified(self):
        log=b"\n".join(
            f"PC=0x{0x80014000+(i%80)*4:08X}".encode()
            for i in range(120))
        r=inspect_duel_mips_trace(log,self.report)
        self.assertEqual(r["status"],"candidate_pc_not_observed")
        self.assertFalse(r["executionEvidence"])


if __name__=="__main__":
    unittest.main()
