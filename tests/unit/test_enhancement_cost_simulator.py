from __future__ import annotations

import unittest

from tests.unit.helpers import load_script_module, run_script_json


class EnhancementCostSimulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_script_module("enhancement_cost_simulator.py")

    def test_normalize_fail_probs(self) -> None:
        stay, down, brk = self.mod.normalize_fail_probs({"fail": {"stay": 2, "down": 1, "break": 1}})
        self.assertAlmostEqual(stay + down + brk, 1.0, places=9)
        self.assertAlmostEqual(stay, 0.5, places=9)
        self.assertAlmostEqual(down, 0.25, places=9)
        self.assertAlmostEqual(brk, 0.25, places=9)

    def test_normalize_fail_probs_zero_total_defaults_to_stay(self) -> None:
        stay, down, brk = self.mod.normalize_fail_probs({"fail": {"stay": 0, "down": 0, "break": 0}})
        self.assertEqual((stay, down, brk), (1.0, 0.0, 0.0))

    def test_solve_linear_system_known_case(self) -> None:
        # x + y = 3, x - y = 1 -> x=2, y=1
        sol = self.mod.solve_linear_system([[1.0, 1.0], [1.0, -1.0]], [3.0, 1.0])
        self.assertAlmostEqual(sol[0], 2.0, places=9)
        self.assertAlmostEqual(sol[1], 1.0, places=9)

    def test_build_result_invalid_target_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.mod.build_result({"target_level": 0, "levels": []})

    def test_simulation_is_deterministic_with_fixed_seed(self) -> None:
        payload = {
            "start_level": 0,
            "target_level": 4,
            "levels": [
                {"success": 1.0, "cost": 100, "fail": {"stay": 1, "down": 0, "break": 0}},
                {"success": 0.8, "cost": 200, "fail": {"stay": 1, "down": 0, "break": 0}},
                {"success": 0.6, "cost": 300, "fail": {"stay": 1, "down": 0, "break": 0}},
                {"success": 0.5, "cost": 500, "fail": {"stay": 0.7, "down": 0.3, "break": 0}},
            ],
            "trials": 3000,
            "seed": 2026,
        }
        r1 = self.mod.build_result(payload)
        r2 = self.mod.build_result(payload)
        self.assertEqual(r1["simulation"]["attempts"]["p90"], r2["simulation"]["attempts"]["p90"])
        self.assertEqual(r1["simulation"]["cost"]["p95"], r2["simulation"]["cost"]["p95"])

    def test_cli_json_output_schema(self) -> None:
        payload = {
            "start_level": 0,
            "target_level": 3,
            "levels": [
                {"success": 1.0, "cost": 100, "fail": {"stay": 1, "down": 0, "break": 0}},
                {"success": 0.8, "cost": 200, "fail": {"stay": 1, "down": 0, "break": 0}},
                {"success": 0.6, "cost": 300, "fail": {"stay": 1, "down": 0, "break": 0}},
            ],
            "trials": 1500,
            "seed": 7,
        }
        out = run_script_json("enhancement_cost_simulator.py", payload=payload)
        self.assertIn("expected", out)
        self.assertIn("simulation", out)
        self.assertIn("rows", out["expected"])
        self.assertIn("p95", out["simulation"]["cost"])


if __name__ == "__main__":
    unittest.main()
