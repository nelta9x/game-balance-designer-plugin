from __future__ import annotations

import unittest

from tests.unit.helpers import load_script_module, run_script_json


class ClearProbabilityTunerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_script_module("clear_probability_tuner.py")

    def test_logistic_identity(self) -> None:
        self.assertAlmostEqual(self.mod.logistic(0.0), 0.5, places=9)
        z = 1.37
        self.assertAlmostEqual(self.mod.logistic(-z), 1.0 - self.mod.logistic(z), places=9)

    def test_n_for_success(self) -> None:
        # p=0.5, target=0.75 -> 2 attempts needed
        self.assertEqual(self.mod.n_for_success(0.5, 0.75), 2)
        self.assertGreaterEqual(self.mod.n_for_success(0.35, 0.95), 1)

    def test_required_gap_increases_with_target_probability(self) -> None:
        payload = {
            "beta": {"b0": -0.2, "b1": 2.0, "b2": 0.8, "b3": 0.35},
            "mechanic_score": 0.55,
            "retry_bonus": 0.0,
            "power_gaps": [-0.1, 0.0, 0.1],
            "target_clear_probs": [0.60, 0.65, 0.70],
            "attempt_probs": [0.60, 0.65, 0.70],
            "simulation": {"enabled": False},
        }
        result = self.mod.build_result(payload)
        gaps = [row["required_power_gap"] for row in result["target_rows"]]
        self.assertTrue(gaps[0] < gaps[1] < gaps[2])

    def test_simulation_is_deterministic_with_seed(self) -> None:
        payload = {
            "beta": {"b0": -0.2, "b1": 2.0, "b2": 0.8, "b3": 0.35},
            "mechanic_score": 0.45,
            "retry_bonus": 0.0,
            "power_gaps": [-0.12, 0.05],
            "target_clear_probs": [0.50, 0.60],
            "attempt_probs": [0.42, 0.55],
            "simulation": {
                "enabled": True,
                "retry_bonus_step": 0.10,
                "retry_bonus_cap": 0.40,
                "max_attempts": 10,
                "trials": 5000,
                "seed": 2026,
            },
        }
        r1 = self.mod.build_result(payload)
        r2 = self.mod.build_result(payload)
        self.assertEqual(r1["simulation"]["per_power_gap"][0]["attempts"]["p90"], r2["simulation"]["per_power_gap"][0]["attempts"]["p90"])
        self.assertEqual(r1["simulation"]["per_power_gap"][1]["attempts"]["p95"], r2["simulation"]["per_power_gap"][1]["attempts"]["p95"])

    def test_cli_json_output_schema(self) -> None:
        payload = {
            "beta": {"b0": -0.2, "b1": 2.0, "b2": 0.8, "b3": 0.35},
            "mechanic_score": 0.5,
            "retry_bonus": 0.0,
            "power_gaps": [-0.2, 0.0],
            "target_clear_probs": [0.55, 0.65],
            "attempt_probs": [0.45, 0.55],
            "simulation": {
                "enabled": True,
                "retry_bonus_step": 0.1,
                "retry_bonus_cap": 0.4,
                "max_attempts": 8,
                "trials": 4000,
                "seed": 42,
            },
        }
        out = run_script_json("clear_probability_tuner.py", payload=payload)
        self.assertIn("clear_curve", out)
        self.assertIn("target_rows", out)
        self.assertIn("simulation", out)
        self.assertIsInstance(out["simulation"]["per_power_gap"], list)


if __name__ == "__main__":
    unittest.main()
