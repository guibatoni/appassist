"""Teste da ligação dinâmica LHU/LH com pares de pontuação do WA."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_rank_memory_trace import inspect_rank_memory_trace


PAIRS=[(5,12),(9,8),(29,0),(33,-8),(32767,-12)]
RANK={
    "available":True,
    "rules":{"criterion_01":[{"below":t,"points":p} for t,p in PAIRS]},
}
MIPS={"available":True,"candidates":[{"pc":"0x80012000","score":18}]}


def make_trace(*, pc=0x80012040, base=0x80030000,
               corrupt=False, scores_only=False, wrong_phase=False):
    text=[]
    for i,(limit,score) in enumerate(PAIRS):
        addr=base+i*4
        phase="DUEL" if wrong_phase else "RANK"
        if not scores_only:
            text.append(f"PC=0x{pc:08X} PHASE={phase} OP=LHU ADDR=0x{addr:08X} VALUE=0x{limit:04X}")
        actual=score+1 if corrupt else score
        text.append(f"PC=0x{pc+4:08X} PHASE={phase} OP=LH ADDR=0x{addr+2:08X} VALUE=0x{actual&0xffff:04X}")
    return ("\n".join(text)+"\n").encode()


class RankMemoryTraceTests(unittest.TestCase):
    def test_executed_accesses_match_wa_threshold_and_points(self):
        result=inspect_rank_memory_trace(make_trace(),RANK,MIPS)
        self.assertTrue(result["available"])
        self.assertTrue(result["tableReadsObserved"])
        self.assertEqual(result["matchedPairs"],5)
        self.assertEqual(result["candidateWindows"][0]["memoryBaseCandidate"],"0x80030000")
        self.assertFalse(result["rankRoutineConfirmed"])
        self.assertFalse(result["scoringCausalityConfirmed"])

    def test_executed_pc_outside_candidate_range_not_inferred(self):
        result=inspect_rank_memory_trace(make_trace(pc=0x80017000),RANK,MIPS)
        self.assertFalse(result["tableReadsObserved"])

    def test_scores_alone_or_wrong_phase_or_changed_value_rejected(self):
        for content in (
            make_trace(scores_only=True),
            make_trace(wrong_phase=True),
            make_trace(corrupt=True),
        ):
            with self.subTest(content=content[:40]):
                report=inspect_rank_memory_trace(content,RANK,MIPS)
                self.assertFalse(report["tableReadsObserved"])
                self.assertFalse(report["rankRoutineConfirmed"])

    def test_rejects_unknown_wa_and_empty_mips(self):
        self.assertEqual(inspect_rank_memory_trace(make_trace(),None,MIPS)["status"],
                         "rank_table_not_extracted")
        self.assertEqual(inspect_rank_memory_trace(make_trace(),RANK,None)["status"],
                         "mips_candidates_missing")

    def test_wrong_signed_scores_never_counted(self):
        data=make_trace()
        data=data.replace(b"VALUE=0xFFF8",b"VALUE=0x0008")
        data=data.replace(b"VALUE=0xFFF4",b"VALUE=0x000C")
        result=inspect_rank_memory_trace(data,RANK,MIPS)
        self.assertEqual(result["matchedPairs"],0)
        self.assertFalse(result["tableReadsObserved"])


if __name__=="__main__":
    unittest.main()
