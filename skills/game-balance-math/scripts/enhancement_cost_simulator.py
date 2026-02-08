#!/usr/bin/env python3
"""Enhancement expected-cost simulator.

Calculates:
1) Expected attempts/cost by solving linear equations
2) p50/p90/p95 via Monte Carlo simulation

Usage:
  python3 enhancement_cost_simulator.py
  python3 enhancement_cost_simulator.py --input /path/to/input.json
  python3 enhancement_cost_simulator.py --input /path/to/input.json --format json
"""

from __future__ import annotations

import argparse
import json
import random
from typing import Any, Dict, List, Optional, Tuple


EPS = 1e-12

DEFAULT_INPUT: Dict[str, Any] = {
    "start_level": 0,
    "target_level": 5,
    "levels": [
        {"success": 1.0, "cost": 100, "fail": {"stay": 1.0, "down": 0.0, "break": 0.0}},
        {"success": 0.8, "cost": 200, "fail": {"stay": 1.0, "down": 0.0, "break": 0.0}},
        {"success": 0.6, "cost": 400, "fail": {"stay": 1.0, "down": 0.0, "break": 0.0}},
        {"success": 0.45, "cost": 700, "fail": {"stay": 0.7, "down": 0.3, "break": 0.0}},
        {
            "success": 0.3,
            "cost": 1200,
            "fail": {"stay": 0.6, "down": 0.3, "break": 0.1},
            "break_to": 0,
            "break_cost": 500,
        },
    ],
    "trials": 200000,
    "seed": 42,
}


def to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def to_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def normalize_fail_probs(level: Dict[str, Any]) -> Tuple[float, float, float]:
    fail = level.get("fail", {})
    s = max(0.0, to_float(fail.get("stay"), 1.0))
    d = max(0.0, to_float(fail.get("down"), 0.0))
    b = max(0.0, to_float(fail.get("break"), 0.0))
    total = s + d + b
    if total < EPS:
        return 1.0, 0.0, 0.0
    return s / total, d / total, b / total


def solve_linear_system(a: List[List[float]], b: List[float]) -> List[float]:
    n = len(a)
    # Augmented matrix
    m = [row[:] + [b[i]] for i, row in enumerate(a)]

    for col in range(n):
        pivot = col
        for r in range(col + 1, n):
            if abs(m[r][col]) > abs(m[pivot][col]):
                pivot = r
        if abs(m[pivot][col]) < EPS:
            raise ValueError("Singular matrix while solving expected value equations.")

        if pivot != col:
            m[col], m[pivot] = m[pivot], m[col]

        pivot_val = m[col][col]
        for c in range(col, n + 1):
            m[col][c] /= pivot_val

        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            if abs(factor) < EPS:
                continue
            for c in range(col, n + 1):
                m[r][c] -= factor * m[col][c]

    return [m[i][n] for i in range(n)]


def build_expected_equations(
    levels: List[Dict[str, Any]], target_level: int
) -> Tuple[List[float], List[float]]:
    n = target_level
    a_attempt = [[0.0 for _ in range(n)] for _ in range(n)]
    b_attempt = [0.0 for _ in range(n)]
    a_cost = [[0.0 for _ in range(n)] for _ in range(n)]
    b_cost = [0.0 for _ in range(n)]

    for l in range(n):
        level = levels[l]
        p = clamp(to_float(level.get("success"), 0.0), 0.0, 1.0)
        q = 1.0 - p
        c = max(0.0, to_float(level.get("cost"), 0.0))
        s, d, b = normalize_fail_probs(level)
        break_to = to_int(level.get("break_to"), 0)
        break_to = max(0, min(target_level, break_to))
        break_cost = max(0.0, to_float(level.get("break_cost"), 0.0))
        down_idx = max(0, l - 1)

        # Attempts equation:
        # (1 - q*s)E_l - pE_{l+1} - q*dE_{down} - q*bE_{break} = 1
        a_attempt[l][l] += 1.0 - q * s
        if l + 1 < target_level:
            a_attempt[l][l + 1] += -p
        if q * d > 0:
            a_attempt[l][down_idx] += -(q * d)
        if q * b > 0 and break_to < target_level:
            a_attempt[l][break_to] += -(q * b)
        b_attempt[l] = 1.0

        # Cost equation:
        # (1 - q*s)C_l - pC_{l+1} - q*dC_{down} - q*bC_{break} = c + q*b*break_cost
        a_cost[l][l] += 1.0 - q * s
        if l + 1 < target_level:
            a_cost[l][l + 1] += -p
        if q * d > 0:
            a_cost[l][down_idx] += -(q * d)
        if q * b > 0 and break_to < target_level:
            a_cost[l][break_to] += -(q * b)
        b_cost[l] = c + q * b * break_cost

    e = solve_linear_system(a_attempt, b_attempt)
    c = solve_linear_system(a_cost, b_cost)
    return e, c


def percentile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    arr = sorted(values)
    idx = int((len(arr) - 1) * q)
    return arr[idx]


def run_simulation(
    levels: List[Dict[str, Any]],
    start_level: int,
    target_level: int,
    trials: int,
    seed: int,
    max_attempts_per_trial: int = 500000,
) -> Dict[str, Any]:
    random.seed(seed)
    attempts_list: List[float] = []
    costs_list: List[float] = []
    truncated = 0

    # Normalize per-level parameters once to keep the trial loop fast.
    probs_success: List[float] = []
    costs_per_attempt: List[float] = []
    stay_threshold: List[float] = []
    down_threshold: List[float] = []
    down_levels: List[int] = []
    break_levels: List[int] = []
    break_costs: List[float] = []

    for lv in range(target_level):
        level = levels[lv]
        probs_success.append(clamp(to_float(level.get("success"), 0.0), 0.0, 1.0))
        costs_per_attempt.append(max(0.0, to_float(level.get("cost"), 0.0)))

        s, d, _ = normalize_fail_probs(level)
        stay_threshold.append(s)
        down_threshold.append(s + d)

        down_levels.append(max(0, lv - 1))
        break_to = to_int(level.get("break_to"), 0)
        break_levels.append(max(0, min(target_level, break_to)))
        break_costs.append(max(0.0, to_float(level.get("break_cost"), 0.0)))

    rand = random.random
    append_attempt = attempts_list.append
    append_cost = costs_list.append

    for _ in range(trials):
        lv = start_level
        attempts = 0
        cost = 0.0
        while lv < target_level and attempts < max_attempts_per_trial:
            attempts += 1
            idx = lv
            cost += costs_per_attempt[idx]

            if rand() < probs_success[idx]:
                lv = idx + 1
                continue

            r = rand()
            if r < stay_threshold[idx]:
                continue
            if r < down_threshold[idx]:
                lv = down_levels[idx]
                continue

            cost += break_costs[idx]
            lv = break_levels[idx]

        if lv < target_level:
            truncated += 1
        append_attempt(float(attempts))
        append_cost(cost)

    mean_attempts = sum(attempts_list) / max(len(attempts_list), 1)
    mean_cost = sum(costs_list) / max(len(costs_list), 1)

    return {
        "trials": trials,
        "seed": seed,
        "truncated_trials": truncated,
        "attempts": {
            "mean": mean_attempts,
            "p50": percentile(attempts_list, 0.50),
            "p90": percentile(attempts_list, 0.90),
            "p95": percentile(attempts_list, 0.95),
        },
        "cost": {
            "mean": mean_cost,
            "p50": percentile(costs_list, 0.50),
            "p90": percentile(costs_list, 0.90),
            "p95": percentile(costs_list, 0.95),
        },
    }


def build_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    start_level = to_int(payload.get("start_level"), 0)
    target_level = to_int(payload.get("target_level"), 1)
    levels = payload.get("levels", [])
    if target_level <= 0:
        raise ValueError("target_level must be >= 1")
    if len(levels) < target_level:
        raise ValueError("levels length must be >= target_level")
    start_level = max(0, min(target_level, start_level))

    expected_attempts, expected_costs = build_expected_equations(levels, target_level)
    trials = max(1, to_int(payload.get("trials"), 200000))
    seed = to_int(payload.get("seed"), 42)
    simulation = run_simulation(levels, start_level, target_level, trials, seed)

    expected_rows = []
    for l in range(target_level):
        expected_rows.append(
            {
                "level": l,
                "expected_attempts_to_target": expected_attempts[l],
                "expected_cost_to_target": expected_costs[l],
            }
        )

    if start_level >= target_level:
        from_start_attempts = 0.0
        from_start_cost = 0.0
    else:
        from_start_attempts = expected_attempts[start_level]
        from_start_cost = expected_costs[start_level]

    return {
        "start_level": start_level,
        "target_level": target_level,
        "expected": {
            "rows": expected_rows,
            "from_start": {
                "level": start_level,
                "attempts": from_start_attempts,
                "cost": from_start_cost,
            },
        },
        "simulation": simulation,
    }


def _fmt(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def render_markdown(result: Dict[str, Any]) -> str:
    lines = [
        "## Expected (Linear Solve)",
        "| Level | E[Attempts to Target] | E[Cost to Target] |",
        "|---:|---:|---:|",
    ]
    for row in result["expected"]["rows"]:
        lines.append(
            "| {level} | {attempts} | {cost} |".format(
                level=row["level"],
                attempts=_fmt(row["expected_attempts_to_target"], 4),
                cost=_fmt(row["expected_cost_to_target"], 2),
            )
        )

    fs = result["expected"]["from_start"]
    sim = result["simulation"]
    lines.extend(
        [
            "",
            "## Summary",
            f"- Start Level: {result['start_level']}",
            f"- Target Level: {result['target_level']}",
            f"- Expected Attempts (start): {_fmt(fs['attempts'], 4)}",
            f"- Expected Cost (start): {_fmt(fs['cost'], 2)}",
            "",
            "## Simulation",
            f"- Trials: {sim['trials']}",
            f"- Truncated Trials: {sim['truncated_trials']}",
            f"- Attempts mean/p50/p90/p95: "
            f"{_fmt(sim['attempts']['mean'], 4)} / {_fmt(sim['attempts']['p50'], 0)} / "
            f"{_fmt(sim['attempts']['p90'], 0)} / {_fmt(sim['attempts']['p95'], 0)}",
            f"- Cost mean/p50/p90/p95: "
            f"{_fmt(sim['cost']['mean'], 2)} / {_fmt(sim['cost']['p50'], 0)} / "
            f"{_fmt(sim['cost']['p90'], 0)} / {_fmt(sim['cost']['p95'], 0)}",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enhancement expected-cost simulator")
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
    result = build_result(payload)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(result))


if __name__ == "__main__":
    main()
