#!/usr/bin/env python3
"""TTK/EHP calculator for balance iteration.

Usage:
  python3 ttk_ehp_calculator.py
  python3 ttk_ehp_calculator.py --input /path/to/input.json
  python3 ttk_ehp_calculator.py --input /path/to/input.json --format json

Input JSON schema:
{
  "rows": [
    {
      "name": "Lv10 Mob",
      "dps": 800,
      "mitigation": 0.15,
      "target_ttk": 8.0
    },
    {
      "name": "Boss Phase 1",
      "dps": 1800,
      "mitigation": 0.35,
      "hp": 90000
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional


EPS = 1e-9

DEFAULT_INPUT: Dict[str, Any] = {
    "rows": [
        {"name": "Lv10 Mob", "dps": 800, "mitigation": 0.15, "target_ttk": 8.0},
        {"name": "Lv20 Elite", "dps": 1300, "mitigation": 0.22, "target_ttk": 9.0},
        {"name": "Lv30 Mini Boss", "dps": 2100, "mitigation": 0.28, "target_ttk": 10.0},
        {"name": "Lv40 Boss Phase", "dps": 3200, "mitigation": 0.32, "target_ttk": 11.0},
    ]
}


def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def effective_hp(hp: float, mitigation: float) -> float:
    mitigation = max(0.0, min(0.9999, mitigation))
    return hp / max(EPS, 1.0 - mitigation)


def hp_from_target_ttk(dps: float, target_ttk: float, mitigation: float) -> float:
    mitigation = max(0.0, min(0.9999, mitigation))
    return target_ttk * dps * max(EPS, 1.0 - mitigation)


def ttk_from_hp(hp: float, dps: float, mitigation: float) -> float:
    ehp = effective_hp(hp, mitigation)
    return ehp / max(EPS, dps)


def compute_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        name = str(row.get("name", f"Row {idx}"))
        dps = to_float(row.get("dps"), 0.0) or 0.0
        mitigation = to_float(row.get("mitigation"), 0.0) or 0.0
        hp = to_float(row.get("hp"))
        target_ttk = to_float(row.get("target_ttk"))

        if hp is None and target_ttk is not None:
            hp = hp_from_target_ttk(dps, target_ttk, mitigation)

        ehp = effective_hp(hp, mitigation) if hp is not None else None
        ttk = ttk_from_hp(hp, dps, mitigation) if hp is not None else None

        delta_ttk = None
        if ttk is not None and target_ttk is not None:
            delta_ttk = ttk - target_ttk

        out.append(
            {
                "name": name,
                "dps": dps,
                "mitigation": mitigation,
                "hp": hp,
                "ehp": ehp,
                "ttk": ttk,
                "target_ttk": target_ttk,
                "delta_ttk": delta_ttk,
            }
        )
    return out


def _fmt(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def render_markdown(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "| Name | DPS | Mitigation | HP | EHP | TTK | Target TTK | Delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {name} | {dps} | {mitigation}% | {hp} | {ehp} | {ttk} | {target_ttk} | {delta} |".format(
                name=row["name"],
                dps=_fmt(row["dps"], 1),
                mitigation=_fmt((row["mitigation"] or 0.0) * 100.0, 1),
                hp=_fmt(row["hp"], 0),
                ehp=_fmt(row["ehp"], 0),
                ttk=_fmt(row["ttk"], 2),
                target_ttk=_fmt(row["target_ttk"], 2),
                delta=_fmt(row["delta_ttk"], 2),
            )
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TTK/EHP calculator")
    parser.add_argument(
        "--input",
        help="Path to input JSON. If omitted, built-in sample input is used.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format (default: markdown).",
    )
    return parser.parse_args()


def load_payload(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return DEFAULT_INPUT
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    args = parse_args()
    payload = load_payload(args.input)
    rows = payload.get("rows", [])
    result = compute_rows(rows)

    if args.format == "json":
        print(json.dumps({"rows": result}, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(result))


if __name__ == "__main__":
    main()
