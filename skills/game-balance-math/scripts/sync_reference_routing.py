#!/usr/bin/env python3
"""Sync request-to-reference routing tables from a single JSON source."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTING_PATH = REPO_ROOT / "skills" / "game-balance-math" / "routing" / "reference-routing.json"
AGENT_DOC_PATH = REPO_ROOT / "agents" / "game-balance-designer.md"
SKILL_DOC_PATH = REPO_ROOT / "skills" / "game-balance-math" / "SKILL.md"

AGENT_MARKERS = ("<!-- ROUTING_TABLE_START:agent -->", "<!-- ROUTING_TABLE_END:agent -->")
SKILL_MARKERS = ("<!-- ROUTING_TABLE_START:skill -->", "<!-- ROUTING_TABLE_END:skill -->")


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|")


def _code_filename(name: str) -> str:
    return f"`{name}`"


def load_entries(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("routing entries must be a non-empty array")

    normalized: List[Dict[str, Any]] = []
    for idx, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"entries[{idx}] must be an object")

        signal = str(entry.get("signal", "")).strip()
        primary = str(entry.get("primary", "")).strip()
        secondary = str(entry.get("secondary", "")).strip()
        output = str(entry.get("output", "")).strip()

        if not signal or not primary:
            raise ValueError(f"entries[{idx}] requires signal and primary")

        normalized.append(
            {
                "signal": signal,
                "primary": primary,
                "secondary": secondary,
                "output": output,
            }
        )
    return normalized


def build_agent_table(entries: List[Dict[str, Any]]) -> str:
    lines = [
        "| 요청 키워드/신호 | 우선 참조 | 보조 참조 |",
        "|---|---|---|",
    ]
    for entry in entries:
        secondary = _code_filename(entry["secondary"]) if entry["secondary"] else "-"
        lines.append(
            "| {signal} | {primary} | {secondary} |".format(
                signal=_escape_cell(entry["signal"]),
                primary=_code_filename(entry["primary"]),
                secondary=secondary,
            )
        )
    return "\n".join(lines)


def build_skill_table(entries: List[Dict[str, Any]]) -> str:
    lines = [
        "| 요청 신호(의도) | 먼저 볼 문서 | 핵심 산출 |",
        "|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| {signal} | {primary} | {output} |".format(
                signal=_escape_cell(entry["signal"]),
                primary=_code_filename(entry["primary"]),
                output=_escape_cell(entry["output"] or "-"),
            )
        )
    return "\n".join(lines)


def replace_between_markers(content: str, start_marker: str, end_marker: str, body: str) -> str:
    start_idx = content.find(start_marker)
    if start_idx < 0:
        raise ValueError(f"start marker not found: {start_marker}")

    start_line_end = content.find("\n", start_idx)
    if start_line_end < 0:
        raise ValueError(f"invalid start marker line: {start_marker}")

    end_idx = content.find(end_marker, start_line_end + 1)
    if end_idx < 0:
        raise ValueError(f"end marker not found: {end_marker}")

    return content[: start_line_end + 1] + body.rstrip() + "\n" + content[end_idx:]


def sync_file(path: Path, markers: Tuple[str, str], table_body: str, check: bool) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = replace_between_markers(original, markers[0], markers[1], table_body)
    changed = updated != original
    if changed and not check:
        path.write_text(updated, encoding="utf-8")
    return not changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync routing tables in docs")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check mode: return non-zero if docs are out of sync.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entries = load_entries(ROUTING_PATH)

    agent_table = build_agent_table(entries)
    skill_table = build_skill_table(entries)

    agent_ok = sync_file(AGENT_DOC_PATH, AGENT_MARKERS, agent_table, check=args.check)
    skill_ok = sync_file(SKILL_DOC_PATH, SKILL_MARKERS, skill_table, check=args.check)

    if args.check:
        if agent_ok and skill_ok:
            print("Routing tables are in sync.")
            return 0
        if not agent_ok:
            print(f"[drift] {AGENT_DOC_PATH}")
        if not skill_ok:
            print(f"[drift] {SKILL_DOC_PATH}")
        return 1

    print(f"[synced] {AGENT_DOC_PATH}")
    print(f"[synced] {SKILL_DOC_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
