from __future__ import annotations

import unittest

from tests.unit.helpers import load_script_module, run_script_json


class EconomyFlowSimulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_script_module("economy_flow_simulator.py")

    def test_simulate_computes_expected_tte(self) -> None:
        payload = {
            "days": 10,
            "initial_stock": 0,
            "price": 200,
            "scenarios": [{"name": "Base", "faucet": 100, "sink": 80, "mandatory_sink": 80}],
        }
        result = self.mod.simulate(payload, include_daily=False)
        row = result["results"][0]
        self.assertAlmostEqual(row["disposable"], 20.0, places=6)
        self.assertAlmostEqual(row["tte_days"], 10.0, places=6)
        self.assertAlmostEqual(row["final_stock"], 200.0, places=6)

    def test_simulate_tte_is_none_when_disposable_non_positive(self) -> None:
        payload = {
            "days": 5,
            "initial_stock": 0,
            "price": 1000,
            "scenarios": [{"name": "Tight", "faucet": 100, "sink": 120, "mandatory_sink": 120}],
        }
        result = self.mod.simulate(payload, include_daily=False)
        row = result["results"][0]
        self.assertIsNone(row["tte_days"])
        self.assertLessEqual(row["disposable"], 0.0)

    def test_daily_overrides_are_applied(self) -> None:
        payload = {
            "days": 3,
            "initial_stock": 0,
            "price": 100,
            "scenarios": [
                {
                    "name": "Override",
                    "faucet": 100,
                    "sink": 90,
                    "mandatory_sink": 90,
                    "overrides": [{"day": 2, "faucet": 120, "sink": 80}],
                }
            ],
        }
        result = self.mod.simulate(payload, include_daily=True)
        daily = result["results"][0]["daily"]
        self.assertEqual(len(daily), 3)
        self.assertEqual(daily[1]["faucet"], 120.0)
        self.assertEqual(daily[1]["sink"], 80.0)

    def test_cli_json_output_schema(self) -> None:
        payload = {
            "days": 2,
            "initial_stock": 50,
            "price": 100,
            "scenarios": [{"name": "Base", "faucet": 60, "sink": 40, "mandatory_sink": 40}],
        }
        out = run_script_json("economy_flow_simulator.py", payload=payload)
        self.assertIn("results", out)
        self.assertEqual(len(out["results"]), 1)
        row = out["results"][0]
        self.assertIn("f_over_s", row)
        self.assertIn("tte_days", row)


if __name__ == "__main__":
    unittest.main()
