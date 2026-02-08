from __future__ import annotations

import unittest

from tests.unit.helpers import load_script_module, run_script_json


class TtkEhpCalculatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_script_module("ttk_ehp_calculator.py")

    def test_effective_hp_clamps_mitigation(self) -> None:
        self.assertAlmostEqual(self.mod.effective_hp(100.0, -1.0), 100.0, places=6)
        self.assertAlmostEqual(self.mod.effective_hp(100.0, 1.5), 1_000_000.0, places=3)

    def test_hp_target_ttk_round_trip(self) -> None:
        dps = 1600.0
        mitigation = 0.30
        target_ttk = 12.5
        hp = self.mod.hp_from_target_ttk(dps, target_ttk, mitigation)
        ttk = self.mod.ttk_from_hp(hp, dps, mitigation)
        self.assertAlmostEqual(ttk, target_ttk, places=6)

    def test_compute_rows_generates_hp_from_target(self) -> None:
        rows = self.mod.compute_rows(
            [
                {"name": "A", "dps": 1000, "mitigation": 0.2, "target_ttk": 10},
                {"name": "B", "dps": 1200, "mitigation": 0.1, "hp": 5000},
            ]
        )
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0]["hp"], 8000.0, places=6)
        self.assertAlmostEqual(rows[0]["ttk"], 10.0, places=6)
        self.assertAlmostEqual(rows[1]["ttk"], 5000.0 / (1.0 - 0.1) / 1200.0, places=6)

    def test_cli_json_output_schema(self) -> None:
        payload = {
            "rows": [
                {"name": "Stage 8", "dps": 1400, "hp": 18000, "mitigation": 0.20},
                {"name": "Stage 9", "dps": 1500, "hp": 21000, "mitigation": 0.22},
            ]
        }
        out = run_script_json("ttk_ehp_calculator.py", payload=payload)
        self.assertIn("rows", out)
        self.assertEqual(len(out["rows"]), 2)
        self.assertIn("ttk", out["rows"][0])
        self.assertGreater(out["rows"][0]["ttk"], 0.0)


if __name__ == "__main__":
    unittest.main()
