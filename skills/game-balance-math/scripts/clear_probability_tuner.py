#!/usr/bin/env python3
"""Clear-probability tuner using a logistic model.

Usage:
  python3 clear_probability_tuner.py
  python3 clear_probability_tuner.py --input /path/to/input.json
  python3 clear_probability_tuner.py --input /path/to/input.json --format json
"""

from __future__ import annotations

import argparse
import json
import math
import random
from typing import Any, Dict, List, Optional


EPS = 1e-12

DEFAULT_INPUT: Dict[str, Any] = {
    "beta": {"b0": -0.2, "b1": 2.0, "b2": 0.8, "b3": 0.35},
    "mechanic_score": 0.5,
    "retry_bonus": 0.0,
    "power_gaps": [-0.3, -0.15, 0.0, 0.15, 0.3],
    "target_clear_probs": [0.55, 0.65, 0.75],
    "attempt_probs": [0.35, 0.45, 0.55, 0.65, 0.75],
    "simulation": {
        "enabled": True,
        "retry_bonus_step": 0.15,
        "retry_bonus_cap": 0.6,
        "max_attempts": 10,
        "trials": 30000,
        "seed": 42,
    },
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


def logistic(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def logit(p: float) -> float:
    p = clamp(p, EPS, 1.0 - EPS)
    return math.log(p / (1.0 - p))


def clear_prob(
    power_gap: float,
    b0: float,
    b1: float,
    b2: float,
    b3: float,
    mechanic_score: float,
    retry_bonus: float,
) -> float:
    z = b0 + b1 * power_gap + b2 * mechanic_score + b3 * retry_bonus
    return logistic(z)


def n_for_success(p: float, target_success: float) -> int:
    p = clamp(p, EPS, 1.0 - EPS)
    target_success = clamp(target_success, EPS, 1.0 - EPS)
    return math.ceil(math.log(1.0 - target_success) / math.log(1.0 - p))


def percentile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    arr = sorted(values)
    idx = int((len(arr) - 1) * q)
    return arr[idx]


def run_retry_simulation(
    power_gap: float,
    b0: float,
    b1: float,
    b2: float,
    b3: float,
    mechanic_score: float,
    retry_bonus_step: float,
    retry_bonus_cap: float,
    max_attempts: int,
    trials: int,
    seed: int,
) -> Dict[str, Any]:
    random.seed(seed)
    attempts: List[float] = []
    failures = 0
    for _ in range(trials):
        cleared = False
        for n in range(1, max_attempts + 1):
            retry_bonus = min((n - 1) * retry_bonus_step, retry_bonus_cap)
            p = clear_prob(power_gap, b0, b1, b2, b3, mechanic_score, retry_bonus)
            if random.random() < p:
                attempts.append(float(n))
                cleared = True
                break
        if not cleared:
            failures += 1
            attempts.append(float(max_attempts))

    mean_attempts = sum(attempts) / max(len(attempts), 1)
    return {
        "trials": trials,
        "seed": seed,
        "max_attempts": max_attempts,
        "failures_at_cap": failures,
        "attempts": {
            "mean": mean_attempts,
            "p50": percentile(attempts, 0.50),
            "p90": percentile(attempts, 0.90),
            "p95": percentile(attempts, 0.95),
        },
    }


def build_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    beta = payload.get("beta", {})
    b0 = to_float(beta.get("b0"), -0.2)
    b1 = to_float(beta.get("b1"), 2.0)
    b2 = to_float(beta.get("b2"), 0.8)
    b3 = to_float(beta.get("b3"), 0.35)
    mechanic_score = to_float(payload.get("mechanic_score"), 0.5)
    retry_bonus = to_float(payload.get("retry_bonus"), 0.0)

    power_gaps = [to_float(x) for x in payload.get("power_gaps", [])]
    target_probs = [clamp(to_float(x), EPS, 1.0 - EPS) for x in payload.get("target_clear_probs", [])]
    attempt_probs = [clamp(to_float(x), EPS, 1.0 - EPS) for x in payload.get("attempt_probs", [])]

    clear_curve = []
    for pg in power_gaps:
        p = clear_prob(pg, b0, b1, b2, b3, mechanic_score, retry_bonus)
        clear_curve.append({"power_gap": pg, "clear_prob": p})

    target_rows = []
    for p in target_probs:
        gap = (logit(p) - b0 - b2 * mechanic_score - b3 * retry_bonus) / max(EPS, b1)
        target_rows.append({"target_clear_prob": p, "required_power_gap": gap})

    attempt_rows = []
    for p in attempt_probs:
        attempt_rows.append(
            {
                "p": p,
                "expected_attempts": 1.0 / p,
                "n90": n_for_success(p, 0.90),
                "n95": n_for_success(p, 0.95),
            }
        )

    simulation_cfg = payload.get("simulation", {})
    sim_enabled = bool(simulation_cfg.get("enabled", False))
    simulation = None
    if sim_enabled:
        retry_bonus_step = to_float(simulation_cfg.get("retry_bonus_step"), 0.15)
        retry_bonus_cap = to_float(simulation_cfg.get("retry_bonus_cap"), 0.6)
        max_attempts = max(1, to_int(simulation_cfg.get("max_attempts"), 10))
        trials = max(1, to_int(simulation_cfg.get("trials"), 30000))
        seed = to_int(simulation_cfg.get("seed"), 42)

        per_gap = []
        for pg in power_gaps:
            sim = run_retry_simulation(
                pg,
                b0,
                b1,
                b2,
                b3,
                mechanic_score,
                retry_bonus_step,
                retry_bonus_cap,
                max_attempts,
                trials,
                seed,
            )
            per_gap.append({"power_gap": pg, **sim})
        simulation = {"per_power_gap": per_gap}

    return {
        "beta": {"b0": b0, "b1": b1, "b2": b2, "b3": b3},
        "mechanic_score": mechanic_score,
        "retry_bonus": retry_bonus,
        "clear_curve": clear_curve,
        "target_rows": target_rows,
        "attempt_rows": attempt_rows,
        "simulation": simulation,
    }


def _fmt(value: Optional[float], digits: int = 3) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def render_markdown(result: Dict[str, Any]) -> str:
    lines: List[str] = [
        "## Clear Probability by PowerGap",
        "| PowerGap | P(clear) |",
        "|---:|---:|",
    ]
    for row in result["clear_curve"]:
        lines.append(f"| {_fmt(row['power_gap'], 3)} | {_fmt(row['clear_prob'] * 100, 1)}% |")

    lines.extend(
        [
            "",
            "## Required PowerGap for Target P(clear)",
            "| Target P(clear) | Required PowerGap |",
            "|---:|---:|",
        ]
    )
    for row in result["target_rows"]:
        lines.append(
            f"| {_fmt(row['target_clear_prob'] * 100, 1)}% | {_fmt(row['required_power_gap'], 3)} |"
        )

    lines.extend(
        [
            "",
            "## Attempts from Fixed First-Try Probability",
            "| p | E[Attempts] | N@90% | N@95% |",
            "|---:|---:|---:|---:|",
        ]
    )
    for row in result["attempt_rows"]:
        lines.append(
            "| {p}% | {e} | {n90} | {n95} |".format(
                p=_fmt(row["p"] * 100, 1),
                e=_fmt(row["expected_attempts"], 2),
                n90=int(row["n90"]),
                n95=int(row["n95"]),
            )
        )

    simulation = result.get("simulation")
    if simulation:
        lines.extend(
            [
                "",
                "## Retry Simulation",
                "| PowerGap | Mean Attempts | p50 | p90 | p95 | Failures@Cap |",
                "|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in simulation["per_power_gap"]:
            a = row["attempts"]
            lines.append(
                "| {pg} | {mean} | {p50} | {p90} | {p95} | {fail} |".format(
                    pg=_fmt(row["power_gap"], 3),
                    mean=_fmt(a["mean"], 2),
                    p50=_fmt(a["p50"], 0),
                    p90=_fmt(a["p90"], 0),
                    p95=_fmt(a["p95"], 0),
                    fail=row["failures_at_cap"],
                )
            )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clear probability tuner")
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
