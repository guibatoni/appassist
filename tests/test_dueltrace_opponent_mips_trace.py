"""Stage 32 regression: trace observations never unlock opponent or drops."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from dueltrace_opponent_mips_trace import (
    inspect_opponent_mips_trace, MAX_TRACE_BYTES,
)


def clock(pcs=16):
    return [f"frame={i//16} PC=0x{0x80012000+(i%pcs)*4:08X}"
            for i in range(96)]


class OpponentMipsTraceTests(unittest.TestCase):
    def test_legacy_field_access_is_a_lead_not_verified_identity(self):
        rows = clock()
        rows += [f"PC=0x80012200 PHASE=DUEL OP=LBU "
                 f"ADDR=0x8009B361 VALUE=0x05" for _ in range(14)]
        rows += ["PC=0x80012204 PHASE=DUEL OP=SB "
                 "ADDR=0x8009B361 VALUE=0x05" for _ in range(2)]
        rows += ["PC=0x80012208 OP=LBU ADDR=0x80030022 VALUE=0x0A"
                 for _ in range(7)]
        rows += ["PC=0x8001220C OP=SB ADDR=0x80030022 VALUE=0x0A"
                 for _ in range(2)]
        result = inspect_opponent_mips_trace("\n".join(rows).encode())
        self.assertTrue(result["available"])
        self.assertTrue(result["traceFormatRecognized"])
        self.assertEqual(result["legacyFieldReadEvents"], 14)
        self.assertEqual(result["legacyFieldWriteEvents"], 2)
        self.assertEqual(result["legacyObservedValues"], [5])
        self.assertEqual(result["candidateAddresses"][0]["address"], "0x80030022")
        self.assertFalse(result["opponentIdentityVerified"])
        self.assertFalse(result["physicalWindowMappingVerified"])
        self.assertFalse(result["rankRoutineConfirmed"])
        self.assertFalse(result["mayActivateDrops"])
        self.assertNotIn("PHASE", str(result))

    def test_other_mod_address_is_not_promoted_by_stable_byte(self):
        rows = clock()
        rows += ["PC=0x80040000 OP=LBU ADDR=0x8009B420 VALUE=0x07"] * 12
        rows += ["PC=0x80040004 OP=SB ADDR=0x8009B420 VALUE=0x07"] * 5
        result = inspect_opponent_mips_trace("\n".join(rows).encode())
        self.assertEqual(result["status"], "other_byte_field_candidates")
        self.assertEqual(result["legacyFieldReadEvents"], 0)
        self.assertEqual(result["candidateAddressCount"], 1)
        self.assertEqual(result["candidateAddresses"][0]["observedValues"], [7])
        self.assertFalse(result["opponentIdentityVerified"])

    def test_fake_lines_and_static_bytes_do_not_count(self):
        for value in (
            b"PC=0x80012040 OP=LB ADDR=0x8009B361 VALUE=0x05",
            b"0x80012040 LBU 0x8009B361 0x0005\n" * 300,
            b"PC=0xDEADBEEF OP=LBU ADDR=0x8009B361 VALUE=0x05\n" * 300,
            b"",
            b"x" * (MAX_TRACE_BYTES + 1),
        ):
            result = inspect_opponent_mips_trace(value)
            self.assertFalse(result["available"])
            self.assertEqual(result["legacyFieldReadEvents"], 0)
            self.assertFalse(result["opponentIdentityVerified"])

    def test_high_value_or_host_address_never_enters_result(self):
        rows = clock()
        rows += ["PC=0x80012080 OP=LBU ADDR=0x7FFABCDEF000 VALUE=0x05",
                 "PC=0x80012080 OP=LBU ADDR=0x8009B361 VALUE=0xFA",
                 "C:\\PRIVATE\\key.iso TOKEN=SECRET"]
        result = inspect_opponent_mips_trace("\n".join(rows).encode())
        self.assertEqual(result["byteMemoryEvents"],0)
        self.assertEqual(result["candidateAddresses"],[])
        self.assertNotIn("PRIVATE", str(result))
        self.assertNotIn("SECRET", str(result))

    def test_pc_only_trace_is_indeterminate(self):
        result = inspect_opponent_mips_trace("\n".join(clock()).encode())
        self.assertTrue(result["available"])
        self.assertEqual(result["status"], "no_opponent_address_evidence")
        self.assertEqual(result["legacyFieldReadEvents"], 0)
        self.assertFalse(result["opponentIdentityVerified"])


if __name__ == "__main__":
    unittest.main()
