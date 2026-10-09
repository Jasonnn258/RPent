#!/usr/bin/env python3
"""Synthetic-only, no Stage R outcomes, for Stage2D frozen offline analyzer."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import h0_oe_stage2d_offline as h0


class TestFrozenAnalysis(unittest.TestCase):
    def test_grid_and_stable_likelihood(self):
        assert len(h0.MUS) == 19
        assert len(h0.TAUS) == 9
        a, b, mu, tau = h0.fit_m1([0] * 23)
        self.assertGreater(a, 0)
        self.assertGreater(b, 0)
        self.assertIn(mu, h0.MUS)
        self.assertIn(tau, h0.TAUS)
        self.assertAlmostEqual(h0.logbeta(a, b), h0.logbeta(b, a))

    def test_m0_prefix_includes_two_failures(self):
        train_s = 40
        m0_k0 = (1 + train_s) / (2 + 8 * 23)
        m0_k2 = (1 + train_s) / (2 + 8 * 23 + 2)
        self.assertLess(m0_k2, m0_k0)

    def test_m1_differs_after_two_failures(self):
        a, b, _, _ = h0.fit_m1([0] * 15 + [8] * 8)
        self.assertGreater(a / (a + b), a / (a + b + 2))

    def test_strict_parse_and_nesting(self):
        self.assertEqual(h0.parse_bit('False', 'x'), 0)
        self.assertEqual(h0.parse_bit('True', 'x'), 1)
        with self.assertRaises(h0.ProtocolStop):
            h0.parse_bit('unknown', 'x')
        cohort = [{'event_id': 'e1'}]
        x = {'SAME': {'e1': {1: {'stable': 'True', 'acquisition': 'False'}}},
             'RESAMPLE': {'e1': {}}}
        with self.assertRaisesRegex(h0.ProtocolStop, 'STOP_CONTRACT_NESTING_VIOLATION'):
            h0.extract_outcomes(cohort, x)

    def test_pair_loss_and_outcome_separation(self):
        cohort = [{'event_id': f'e{i:02d}', 'task': 't9'} for i in range(24)]
        data = {c['event_id']: {t: {'stable': int((i * 7 + t) % 8 == 0),
                                     'acquisition': int((i * 7 + t) % 8 == 0)}
                               for t in range(1, 9)}
                for i, c in enumerate(cohort)}
        preds = h0.predictions_for_arm(cohort, data, 'SAME')
        primary, pairs = h0.loss_for_prefix(cohort, data, preds, 2)
        self.assertEqual(primary['eligible_event_n'], len(pairs))
        self.assertTrue(0 <= primary['eligible_event_n'] <= 24)
        self.assertEqual(sum(primary['task_counts'].values()), len(pairs))
        if len(pairs) >= 1:
            c1 = h0.descriptive_bootstrap(pairs)
            c2 = h0.descriptive_bootstrap(pairs)
            self.assertEqual(c1, c2)
            self.assertLessEqual(c1[0], c1[1])
        self.assertEqual(h0.percentile([0, 10], 0.25), 2.5)

    def test_structural_validation_synthetic_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'analysis'
            d.mkdir()
            header = ['event_id', 'ord', 'role', 'task', 'seed', 't0']
            manifest = [{'event_id': f'e{i:02d}', 'ord': str(i + 1),
                         'role': 'R1_COHORT' if i < 24 else 'R0_DEV',
                         'task': 't9', 'seed': '42', 't0': '17'}
                        for i in range(32)]
            self.write_csv(d / 'stageR_manifest.csv', header, manifest)
            cols = ['event_id', 'arm', 'trial', 'task', 'seed', 't0', 'stable', 'acquisition']
            same = self.make_rows('SAME', 8)
            res = self.make_rows('RESAMPLE', 8) + self.make_rows('NATURAL', 4)
            self.write_csv(d / 'stageR_same_action_rollouts.csv', cols, same)
            self.write_csv(d / 'stageR_resample_rollouts.csv', cols, res)
            coh, by_arm, counts = h0.structural_scan(Path(tmp))
            self.assertEqual(len(coh), 24)
            self.assertEqual(counts, {'SAME': 192, 'RESAMPLE': 192, 'NATURAL': 96})
            # No outcomes are parsed during preflight.
            same[0]['stable'] = 'whatever'
            self.write_csv(d / 'stageR_same_action_rollouts.csv', cols, same)
            h0.structural_scan(Path(tmp))
            # Duplicate event-arm-trial must STOP (no silent de-duplication).
            same[1]['trial'] = same[0]['trial']
            self.write_csv(d / 'stageR_same_action_rollouts.csv', cols, same)
            with self.assertRaisesRegex(h0.ProtocolStop, 'STOP_DUPLICATE_TRIAL'):
                h0.structural_scan(Path(tmp))

    @staticmethod
    def make_rows(arm, n):
        return [{'event_id': f'e{i:02d}', 'arm': arm, 'trial': str(t),
                 'task': 't9', 'seed': '42', 't0': '17',
                 'stable': 'False', 'acquisition': 'False'}
                for i in range(24) for t in range(1, n + 1)]

    @staticmethod
    def write_csv(path, cols, rows):
        with path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)


if __name__ == '__main__':
    unittest.main(verbosity=2)
