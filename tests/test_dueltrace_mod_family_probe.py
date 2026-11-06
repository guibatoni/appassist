"""Original synthetic fixtures; never import game/ISO bytes in CI."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'scanner') if (ROOT / 'scanner').exists() else str(HERE))
from dueltrace_mod_family_probe import (
    CARD_COUNT, MATRIX_BYTES, decode_matrix, discover_weight_families,
    verify_block,
)

STEP = 0x1800
STRIDE = 0x5B4
BASE = 0x2000


def synthetic_resource(*, blocks=39, base=BASE, codec='plain',
                       stride=STRIDE, step=STEP, rules=True):
    blob = bytearray(b'\x00' * (base + blocks * step + 256))
    for i in range(blocks):
        start = base + i * step
        for g in range(4):
            weights = [0] * CARD_COUNT
            a, b, c = ((i * 7 + g * 13 + k) % CARD_COUNT for k in (1, 103, 305))
            weights[a] += 200
            weights[b] += 600
            weights[c] += 1248
            encoded = 'plain' if codec == 'plain_deck_masked_drops' and g == 0 else (
                'x15_masked' if codec == 'plain_deck_masked_drops' else codec)
            if encoded == 'x15_masked':
                weights = [2512 + weight * 8 + ((index + i + g) % 7)
                           for index, weight in enumerate(weights)]
            struct.pack_into('<722H', blob, start + g * stride, *weights)
        if rules and step - 4*stride == 304:
            blob[start+4*stride:start+4*stride+200] = bytes(range(200))
            blob[start+4*stride+200:start+step] = b'\xff' * 104
    return bytes(blob)


class ModFamilyProbeTests(unittest.TestCase):
    def test_plain_unique_39(self):
        blob = synthetic_resource()
        report = discover_weight_families(blob, layout_hypotheses=((STEP, STRIDE),))
        self.assertEqual(report['state'], 'unique_structural_candidate')
        self.assertEqual(report['candidateCount'], 1)
        self.assertEqual(report['selected']['base'], BASE)
        self.assertEqual(report['selected']['matrixCount'], 156)
        self.assertTrue(report['clusters'][0]['ffTailVerified'])
        self.assertTrue(report['clusters'][0]['ruleBytesIdenticalAcrossBlocks'])
        self.assertFalse(report['selected']['mayActivateDrops'])
        self.assertFalse(report['mayActivateRank'])

    def test_40_blocks_contains_two_39_windows(self):
        blob = synthetic_resource(blocks=40)
        report = discover_weight_families(blob, layout_hypotheses=((STEP, STRIDE),))
        self.assertEqual(report['state'], 'single_family_unmapped_windows')
        self.assertEqual(report['candidateCount'], 2)
        self.assertIsNone(report['selected'])
        self.assertEqual(report['clusters'][0]['consecutiveBlockCount'], 40)
        self.assertEqual(report['clusters'][0]['possible39BlockWindows'], 2)

    def test_relocated_resource_still_detected(self):
        blob = synthetic_resource(base=0x4000)
        report = discover_weight_families(blob, layout_hypotheses=((STEP, STRIDE),))
        self.assertEqual(report['selected']['base'], 0x4000)

    def test_masked_and_mixed_are_supported_with_explicit_hints(self):
        for codec in ('x15_masked', 'plain_deck_masked_drops'):
            with self.subTest(codec=codec):
                blob = synthetic_resource(codec=codec)
                report = discover_weight_families(
                    blob, layout_hypotheses=((STEP, STRIDE),), base_hints=(BASE,))
                self.assertEqual(report['candidateCount'], 1)
                self.assertEqual(report['selected']['encoding'], codec)
                self.assertFalse(report['selected']['rankGroupLabelsVerified'])

    def test_incomplete_matrix_must_not_become_a_profile(self):
        blob = bytearray(synthetic_resource())
        struct.pack_into('<H', blob, BASE + 12 * STEP + STRIDE + 2, 999)
        report = discover_weight_families(bytes(blob), layout_hypotheses=((STEP, STRIDE),))
        self.assertEqual(report['candidateCount'], 0)
        self.assertIsNone(report['selected'])

    def test_reject_random_and_oversized_input(self):
        self.assertIsNone(decode_matrix(b'\xff' * MATRIX_BYTES, 0))
        self.assertEqual(discover_weight_families(b'hello')['state'], 'invalid_input')
        self.assertIsNone(verify_block(b'hello', 0, STEP, STRIDE))

    def test_unknown_stride_stays_unrecognized(self):
        blob = synthetic_resource(step=0x2000, stride=0x600)
        report = discover_weight_families(blob, layout_hypotheses=((STEP, STRIDE),))
        self.assertIsNone(report['selected'])
        report2 = discover_weight_families(blob, layout_hypotheses=((0x2000, 0x600),))
        self.assertEqual(report2['selected']['matrixCount'], 156)

    def test_unknown_codec_does_not_fabricate_data(self):
        self.assertIsNone(decode_matrix(b'\x00' * MATRIX_BYTES, 0, 'unknown'))
        self.assertIsNone(decode_matrix(b'\x00' * MATRIX_BYTES, 0, 'plain'))


if __name__ == '__main__':
    unittest.main()

class ModAuditCliTests(unittest.TestCase):
    def test_arbitrary_resource_name_and_quarantine(self):
        from dueltrace_mod_probe_cli import audit_disc
        class DiscFixture:
            files = {'RENAMED/MY_CUSTOM_FILE.BIN':(5,len(synthetic_resource()))}
            def get(self, name):
                return synthetic_resource()
        report=audit_disc(DiscFixture())
        self.assertEqual(report['status'],'unique_structural_resource_unverified')
        self.assertEqual(report['resourcesWithFamily'],1)
        self.assertFalse(report['mayActivateDrops'])
        self.assertNotIn('cardId',str(report))

    def test_40_block_family_does_not_activate_rank(self):
        from dueltrace_mod_probe_cli import audit_disc
        blob=synthetic_resource(blocks=40)
        class DiscFixture:
            files={'G0SD/SOMETHING.CMP':(25,len(blob))}
            def get(self,name):return blob
        report=audit_disc(DiscFixture())
        self.assertEqual(report['status'],'family_found_runtime_mapping_pending')
        self.assertFalse(report['mayActivateRank'])

    def test_files_too_small_or_executables_are_not_scanned(self):
        from dueltrace_mod_probe_cli import ordered_resources
        files={'SYSTEM.CNF':(0,1000),'GOG_VNT.223':(1,2345678),
               'ANYTHING.DAT':(2,100),'NEWFILE.BIN':(3,250000)}
        self.assertEqual(ordered_resources(files),[('NEWFILE.BIN',250000)])