#!/usr/bin/env python3
"""Economy flow simulator (Faucet / Sink / TTE).

Usage:
  python3 economy_flow_simulator.py
  python3 economy_flow_simulator.py --input /path/to/input.json
  python3 economy_flow_simulator.py --input /path/to/input.json --include-daily --format json

Input JSON schema:
{
  "days": 30,
  "initial_stock": 50000,
  "price": 12000,
  "scenarios": [
    {
      "name": "Base",
      "faucet": 1200,
      "sink": 1000
    },
    {
      "name": "Drop+20%",
      "faucet": 1440,
      "sink": 1000,
      "mandatory_sink": 1000,
      "overrides": [
        {"day": 15, "faucet": 1500, "sink": 1080}
      ]
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional, Tuple


EPS = 1e-9

DEFAULT_INPUT: Dict[str, Any] = {
    "days": 30,
    "initial_stock": 50000,
    "price": 12000,
    "scenarios": [
        {"name": "Base", "faucet": 1200, "sink": 1000},
        {"name": "Drop+20%", "faucet": 1440, "sink": 1000},
        {"name": "Drop+20% + Sink Adjust", "faucet": 1440, "sink": 1260},
    ],
}


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _daily_value(
    day: int, base_faucet: float, base_sink: float, overrides: List[Dict[str, Any]]
) -> Tuple[float, float]:
    faucet = base_faucet
    sink = base_sink
    for ov in overrides:
        if to_int(ov.get("day"), -1) == day:
            faucet = to_float(ov.get("faucet"), faucet)
            sink = to_float(ov.get("sink"), sink)
    return faucet, sink


def simulate(payload: Dict[str, Any], include_daily: bool) -> Dict[str, Any]:
    days = to_int(payload.get("days"), 30)
    initial_stock = to_float(payload.get("initial_stock"), 0.0)
    price = to_float(payload.get("price"), 0.0)
    scenarios = payload.get("scenarios", [])

    results: List[Dict[str, Any]] = []
    for idx, scenario in enumerate(scenarios, start=1):
        name = str(scenario.get("name", f"Scenario {idx}"))
        faucet_base = to_float(scenario.get("faucet"), 0.0)
        sink_base = to_float(scenario.get("sink"), 0.0)
        mandatory_sink = to_float(scenario.get("mandatory_sink"), sink_base)
        overrides = scenario.get("overrides", [])

        stock = initial_stock
        daily_rows: List[Dict[str, Any]] = []
        faucet_sum = 0.0
        sink_sum = 0.0

        for day in range(1, days + 1):
            faucet, sink = _daily_value(day, faucet_base, sink_base, overrides)
            net = faucet - sink
            stock += net
            faucet_sum += faucet
            sink_sum += sink
            if include_daily:
                daily_rows.append(
                    {
                        "day": day,
                        "faucet": faucet,
                        "sink": sink,
                        "net": net,
                        "stock": stock,
                    }
                )

        avg_faucet = faucet_sum / max(days, 1)
        avg_sink = sink_sum / max(days, 1)
        avg_net = avg_faucet - avg_sink
        fs_ratio = avg_faucet / max(EPS, avg_sink)
        disposable = avg_faucet - mandatory_sink
        tte_days: Optional[float] = None
        if price > 0 and disposable > EPS:
            tte_days = price / disposable

        item = {
            "name": name,
            "days": days,
            "initial_stock": initial_stock,
            "final_stock": stock,
            "avg_faucet": avg_faucet,
            "avg_sink": avg_sink,
            "avg_net": avg_net,
            "f_over_s": fs_ratio,
            "mandatory_sink": mandatory_sink,
            "disposable": disposable,
            "price": price,
            "tte_days": tte_days,
        }
        if include_daily:
            item["daily"] = daily_rows
        results.append(item)

    return {"results": results}


def _fmt(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def render_markdown(result: Dict[str, Any]) -> str:
    lines = [
        "| Scenario | Start Stock | Final Stock | Avg Faucet | Avg Sink | Avg Net | F/S | TTE(days) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result.get("results", []):
        lines.append(
            "| {name} | {start} | {final} | {faucet} | {sink} | {net} | {ratio} | {tte} |".format(
                name=row["name"],
                start=_fmt(row["initial_stock"], 0),
                final=_fmt(row["final_stock"], 0),
                faucet=_fmt(row["avg_faucet"], 1),
                sink=_fmt(row["avg_sink"], 1),
                net=_fmt(row["avg_net"], 1),
                ratio=_fmt(row["f_over_s"], 3),
                tte=_fmt(row["tte_days"], 2),
            )
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Economy flow simulator")
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
    parser.add_argument(
        "--include-daily",
        action="store_true",
        help="Include daily trajectory in result.",
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
    result = simulate(payload, include_daily=args.include_daily)

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(result))


if __name__ == "__main__":
    main()
