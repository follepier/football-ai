import math
import unittest

from app.services import analysis


class AnalysisInvariantTests(unittest.TestCase):
    def test_calibration_constants_are_frozen_v060_values(self):
        self.assertEqual(
            analysis.CALIBRAZIONE_XG_INTERCETTA,
            0.214047,
        )
        self.assertEqual(
            analysis.CALIBRAZIONE_XG_PENDENZA,
            0.765037,
        )

    def test_calibration_matches_known_inter_milan_reference(self):
        self.assertAlmostEqual(
            analysis.calibra_gol_attesi_xg(2.39),
            2.04248543,
            places=7,
        )
        self.assertAlmostEqual(
            analysis.calibra_gol_attesi_xg(1.5208),
            1.3775282296,
            places=7,
        )

    def test_calibration_never_returns_negative_lambda(self):
        self.assertEqual(
            analysis.calibra_gol_attesi_xg(-100.0),
            0.0,
        )

    def test_poisson_probability_is_valid(self):
        for lam in [0.25, 1.0, 2.5, 4.0]:
            for goals in range(10):
                with self.subTest(lam=lam, goals=goals):
                    p = analysis.probabilita_poisson(lam, goals)
                    self.assertGreaterEqual(p, 0.0)
                    self.assertLessEqual(p, 1.0)

    def test_poisson_mass_is_effectively_one_on_engine_grid(self):
        for lam in [0.5, 1.5, 3.5, 5.0]:
            with self.subTest(lam=lam):
                total = sum(
                    analysis.probabilita_poisson(lam, goals)
                    for goals in range(21)
                )
                self.assertAlmostEqual(total, 1.0, places=7)

    def test_zero_lambda_is_degenerate_at_zero_goals(self):
        self.assertEqual(analysis.probabilita_poisson(0.0, 0), 1.0)
        self.assertEqual(analysis.probabilita_poisson(0.0, 1), 0.0)

    def test_reference_over_under_complements_sum_to_one(self):
        home_lambda = analysis.calibra_gol_attesi_xg(2.39)
        away_lambda = analysis.calibra_gol_attesi_xg(1.5208)

        grid = []
        for home_goals in range(21):
            for away_goals in range(21):
                p = (
                    analysis.probabilita_poisson(home_lambda, home_goals)
                    * analysis.probabilita_poisson(away_lambda, away_goals)
                )
                grid.append((home_goals, away_goals, p))

        total_mass = sum(p for _, _, p in grid)
        self.assertAlmostEqual(total_mass, 1.0, places=7)

        for threshold in [1, 2, 3]:
            over = sum(
                p
                for home_goals, away_goals, p in grid
                if home_goals + away_goals > threshold
            )
            under = sum(
                p
                for home_goals, away_goals, p in grid
                if home_goals + away_goals <= threshold
            )
            with self.subTest(threshold=threshold):
                self.assertAlmostEqual(over + under, 1.0, places=7)

    def test_reference_1x2_probabilities_sum_to_one(self):
        home_lambda = analysis.calibra_gol_attesi_xg(2.39)
        away_lambda = analysis.calibra_gol_attesi_xg(1.5208)

        p1 = 0.0
        px = 0.0
        p2 = 0.0

        for home_goals in range(21):
            for away_goals in range(21):
                p = (
                    analysis.probabilita_poisson(home_lambda, home_goals)
                    * analysis.probabilita_poisson(away_lambda, away_goals)
                )
                if home_goals > away_goals:
                    p1 += p
                elif home_goals == away_goals:
                    px += p
                else:
                    p2 += p

        self.assertAlmostEqual(p1 + px + p2, 1.0, places=7)
        self.assertAlmostEqual(p1 * 100, 52.88, places=2)
        self.assertAlmostEqual(px * 100, 21.37, places=2)
        self.assertAlmostEqual(p2 * 100, 25.75, places=2)


if __name__ == "__main__":
    unittest.main()
