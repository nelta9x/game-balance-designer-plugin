#!/usr/bin/env python3
"""Automatic runner/scorer for game-balance-designer golden prompts.

Features:
1) Validate suite schema (basic lint)
2) Score model responses for each case
3) Optionally execute preferred math scripts to verify runtime health

Usage examples:
  python3 tests/golden-prompts/run_golden_checks.py
  python3 tests/golden-prompts/run_golden_checks.py --responses-dir tests/golden-prompts/sample-responses
  python3 tests/golden-prompts/run_golden_checks.py --responses-dir tests/golden-prompts/responses --check-scripts
  python3 tests/golden-prompts/run_golden_checks.py --responses results.json --format json --output report.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


DEFAULT_CASE_SCORE = 0.80
DEFAULT_SUITE_SCORE = 0.85
DEFAULT_WEIGHTS = {
    "sections": 0.35,
    "assumptions": 0.10,
    "keywords": 0.20,
    "references": 0.20,
    "traits": 0.10,
    "preferred_script": 0.05,
}

SAMPLE_EXTENSIONS = (".md", ".markdown", ".txt")
SECTION_RE = re.compile(r"(?m)^\s*##\s+(.+?)\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}")
LIST_ROW_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")
NUMBER_RE = re.compile(r"[-+]?(?:\d+\.\d+|\d+|\.\d+)(?:[eE][-+]?\d+)?")
NUMERIC_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")


def _now_utc_iso() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).replace(microsecond=0).isoformat()


def _canonical_section(section: str) -> str:
    return section.replace("##", "", 1).strip()


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return numerator / float(denominator)


def _contains_any(text: str, needles: Sequence[str]) -> bool:
    return any(needle.lower() in text.lower() for needle in needles)


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_numbers(text: str) -> List[float]:
    normalized = NUMERIC_COMMA_RE.sub("", text)
    out: List[float] = []
    for match in NUMBER_RE.finditer(normalized):
        try:
            out.append(float(match.group(0)))
        except (TypeError, ValueError):
            continue
    return out


def _value_at_path(payload: Any, path: str) -> Any:
    current = payload
    for raw_token in path.split("."):
        token = raw_token.strip()
        if not token:
            continue

        if isinstance(current, dict):
            if token not in current:
                raise KeyError(f"missing key '{token}' in path '{path}'")
            current = current[token]
            continue

        if isinstance(current, list):
            try:
                idx = int(token)
            except ValueError as exc:
                raise KeyError(f"non-integer index '{token}' in path '{path}'") from exc
            if idx < 0 or idx >= len(current):
                raise IndexError(f"index out of range ({idx}) in path '{path}'")
            current = current[idx]
            continue

        raise KeyError(f"cannot descend into scalar at token '{token}' for path '{path}'")

    return current


def evaluate_script_numeric_checks(
    response: str,
    preferred_script: str,
    validation: Mapping[str, Any],
    repo_root: Path,
    suite_dir: Path,
) -> Tuple[float, bool, str]:
    script_path = repo_root / "skills" / "game-balance-math" / "scripts" / preferred_script
    if not script_path.exists():
        return 0.0, False, f"script_not_found: {script_path}"

    input_rel = validation.get("input")
    if not isinstance(input_rel, str) or not input_rel.strip():
        return 0.0, False, "invalid_script_validation_input"
    input_path = Path(input_rel)
    if not input_path.is_absolute():
        input_path = (suite_dir / input_path).resolve()
    if not input_path.exists():
        return 0.0, False, f"input_not_found: {input_path}"

    extract_rules = validation.get("extract")
    if not isinstance(extract_rules, list) or not extract_rules:
        return 0.0, False, "invalid_script_validation_extract"

    cmd = [sys.executable, str(script_path), "--input", str(input_path), "--format", "json"]
    run = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    if run.returncode != 0:
        return 0.0, False, f"script_exit_{run.returncode}: {run.stderr.strip()}"

    stdout = run.stdout.strip()
    if not stdout:
        return 0.0, False, "script_empty_stdout"

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return 0.0, False, f"script_invalid_json: {exc}"

    response_numbers = _extract_numbers(response)
    if not response_numbers:
        return 0.0, False, "no_numeric_values_in_response"

    matched = 0
    missing: List[str] = []
    for idx, rule in enumerate(extract_rules, start=1):
        if not isinstance(rule, dict):
            missing.append(f"rule#{idx}:invalid_rule")
            continue

        path = rule.get("path") or rule.get("json_path")
        if not isinstance(path, str) or not path.strip():
            missing.append(f"rule#{idx}:missing_path")
            continue

        name = str(rule.get("name", path))
        try:
            expected = float(_value_at_path(payload, path))
        except (KeyError, IndexError, TypeError, ValueError):
            missing.append(f"{name}:path_error")
            continue

        atol = max(0.0, _to_float(rule.get("atol"), 0.0))
        rtol = max(0.0, _to_float(rule.get("rtol"), 0.02))
        tol = max(atol, abs(expected) * rtol)
        hit = any(abs(value - expected) <= tol for value in response_numbers)
        if hit:
            matched += 1
        else:
            missing.append(f"{name}≈{expected:.4g}±{tol:.4g}")

    total = len(extract_rules)
    min_matches = max(0, _to_int(validation.get("min_matches"), total))
    min_matches = min(min_matches, total)
    score = _safe_ratio(matched, total)
    passed = matched >= min_matches
    details = f"matched {matched}/{total} (min {min_matches})"
    if missing:
        details += "; missing: " + ", ".join(missing[:6])
        if len(missing) > 6:
            details += " ..."
    return score, passed, details


def load_data(path: Path) -> Any:
    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    raise ValueError(f"Unsupported file extension: {path} (only .json is supported)")


def lint_suite(suite: Mapping[str, Any]) -> List[str]:
    issues: List[str] = []

    if not isinstance(suite.get("templates"), dict):
        issues.append("suite.templates must be an object")
    if not isinstance(suite.get("cases"), list):
        issues.append("suite.cases must be an array")
        return issues

    templates = suite.get("templates", {})
    seen: set[str] = set()
    for idx, case in enumerate(suite.get("cases", []), start=1):
        if not isinstance(case, dict):
            issues.append(f"cases[{idx}] must be an object")
            continue

        case_id = str(case.get("id", "")).strip()
        if not case_id:
            issues.append(f"cases[{idx}] missing id")
        elif case_id in seen:
            issues.append(f"duplicate case id: {case_id}")
        else:
            seen.add(case_id)

        template = str(case.get("expected_template", "")).strip()
        if template and template not in templates:
            issues.append(f"case {case_id}: unknown expected_template '{template}'")

        for req_key in ("prompt", "required_references", "required_keywords"):
            if req_key not in case:
                issues.append(f"case {case_id}: missing '{req_key}'")

        preferred_script = case.get("preferred_script")
        script_validation = case.get("script_validation")
        if script_validation is not None:
            if not preferred_script:
                issues.append(f"case {case_id}: script_validation requires preferred_script")
            if not isinstance(script_validation, dict):
                issues.append(f"case {case_id}: script_validation must be an object")
            else:
                raw_input = script_validation.get("input")
                if not isinstance(raw_input, str) or not raw_input.strip():
                    issues.append(f"case {case_id}: script_validation.input must be a non-empty string")
                extract = script_validation.get("extract")
                if not isinstance(extract, list) or not extract:
                    issues.append(f"case {case_id}: script_validation.extract must be a non-empty array")
                else:
                    for ridx, rule in enumerate(extract, start=1):
                        if not isinstance(rule, dict):
                            issues.append(f"case {case_id}: script_validation.extract[{ridx}] must be an object")
                            continue
                        has_path = (
                            isinstance(rule.get("path"), str) and bool(str(rule.get("path")).strip())
                        ) or (
                            isinstance(rule.get("json_path"), str) and bool(str(rule.get("json_path")).strip())
                        )
                        if not has_path:
                            issues.append(
                                f"case {case_id}: script_validation.extract[{ridx}] requires path or json_path"
                            )

    return issues


def parse_sections(text: str) -> Dict[str, str]:
    matches = list(SECTION_RE.finditer(text))
    sections: Dict[str, str] = {}
    for i, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()
    return sections


def find_missing_sections(text: str, required_sections: Sequence[str]) -> List[str]:
    parsed = parse_sections(text)
    parsed_names = {name.strip() for name in parsed.keys()}
    missing: List[str] = []
    for required in required_sections:
        wanted = _canonical_section(str(required))
        if wanted not in parsed_names:
            missing.append(wanted)
    return missing


def _count_table_rows(lines: Sequence[str]) -> int:
    filtered = [line for line in lines if line.strip()]
    if len(filtered) < 3:
        return 0
    if not filtered[0].lstrip().startswith("|"):
        return 0
    if not TABLE_SEP_RE.search(filtered[1]):
        return 0
    return sum(1 for line in filtered[2:] if line.lstrip().startswith("|"))


def count_assumptions(text: str) -> int:
    sections = parse_sections(text)
    body = sections.get("가정", "").strip()
    if not body:
        return 0

    lines = [line.rstrip() for line in body.splitlines()]
    table_count = _count_table_rows(lines)
    if table_count > 0:
        return table_count

    list_count = sum(1 for line in lines if LIST_ROW_RE.search(line))
    if list_count > 0:
        return list_count

    return sum(1 for line in lines if line.strip())


def check_traits(text: str, traits: Sequence[str]) -> Tuple[float, List[str]]:
    raw = text
    lower = text.lower()
    missing: List[str] = []
    matched = 0

    for trait in traits:
        ok = False
        if trait == "근거 없는 매직 넘버 금지":
            ok = _contains_any(raw, ("근거", "기준")) and _contains_any(raw, ("매직 넘버", "파라미터", "수치"))
        elif trait == "영향 지표(TTK/TTE/클리어율 등) 명시":
            ok = _contains_any(raw, ("ttk", "tte", "클리어율", "승률", "레벨업 시간"))
        elif trait == "최소 1개 이상의 로그/텔레메트리 제안":
            ok = _contains_any(raw, ("로그", "텔레메트리", "telemetry", "모니터링"))
        elif trait == "모델/파라미터 선택 이유 설명":
            ok = _contains_any(raw, ("모델", "파라미터")) and _contains_any(raw, ("이유", "근거", "선택"))
        elif trait == "수치 제안은 표 또는 수식 포함":
            ok = "|" in raw or "$" in raw or "=" in raw
        elif trait == "콘텐츠/경제 파급효과 점검":
            ok = _contains_any(raw, ("콘텐츠", "경제", "파급", "영향"))
        elif trait == "원인-대응 매핑이 명확할 것":
            ok = _contains_any(raw, ("원인", "대응", "해결 방안"))
        elif trait == "트레이드오프를 표로 비교할 것":
            ok = "트레이드오프" in lower and "|" in raw
        elif trait == "패치 후 검증 지표 제시":
            ok = _contains_any(raw, ("검증", "지표")) and _contains_any(raw, ("로그", "ttk", "tte", "클리어율"))
        else:
            ok = trait.lower() in lower

        if ok:
            matched += 1
        else:
            missing.append(trait)

    return _safe_ratio(matched, len(traits)), missing


def parse_response_payload(payload: Any) -> Dict[str, str]:
    if isinstance(payload, dict):
        if "responses" in payload and isinstance(payload["responses"], dict):
            return {str(k): str(v) for k, v in payload["responses"].items()}

        if "cases" in payload and isinstance(payload["cases"], list):
            out: Dict[str, str] = {}
            for item in payload["cases"]:
                if isinstance(item, dict) and "id" in item and "response" in item:
                    out[str(item["id"])] = str(item["response"])
            return out

        # fallback: direct map {A01: "..."}
        direct = {str(k): str(v) for k, v in payload.items() if not isinstance(v, (dict, list))}
        if direct:
            return direct

    if isinstance(payload, list):
        out = {}
        for item in payload:
            if isinstance(item, dict) and "id" in item and "response" in item:
                out[str(item["id"])] = str(item["response"])
        return out

    raise ValueError("Unsupported responses payload shape.")


def load_responses_from_file(path: Path) -> Dict[str, str]:
    payload = load_data(path)
    return parse_response_payload(payload)


def load_responses_from_dir(path: Path, case_ids: Sequence[str]) -> Dict[str, str]:
    responses: Dict[str, str] = {}
    for case_id in case_ids:
        found: Optional[Path] = None
        for ext in SAMPLE_EXTENSIONS:
            candidate = path / f"{case_id}{ext}"
            if candidate.exists():
                found = candidate
                break
        if found:
            responses[case_id] = found.read_text(encoding="utf-8")
    return responses


def score_case(
    case: Mapping[str, Any],
    template: Mapping[str, Any],
    response: Optional[str],
    min_case_score: float,
    allow_missing_cases: bool,
    repo_root: Path,
    suite_dir: Path,
) -> Dict[str, Any]:
    case_id = str(case.get("id", "UNKNOWN"))
    title = str(case.get("title", ""))
    category = str(case.get("category", ""))

    if response is None:
        skipped = bool(allow_missing_cases)
        hard_fail = not skipped
        return {
            "id": case_id,
            "title": title,
            "category": category,
            "score": 0.0,
            "passed": False,
            "skipped": skipped,
            "hard_fail_reasons": ["missing_response"] if hard_fail else [],
            "checks": [
                {
                    "name": "response_presence",
                    "score": 0.0,
                    "passed": False,
                    "details": "No response provided for this case." if hard_fail else "No response provided; skipped.",
                }
            ],
        }

    required_sections = [str(x) for x in template.get("required_sections", [])]
    max_assumptions = int(template.get("max_assumptions", 3))
    required_traits = [str(x) for x in template.get("required_traits", [])]
    required_keywords = [str(x) for x in case.get("required_keywords", [])]
    required_refs = [str(x) for x in case.get("required_references", [])]
    preferred_script = case.get("preferred_script")
    script_validation = case.get("script_validation")

    missing_sections = find_missing_sections(response, required_sections)
    sections_score = _safe_ratio(len(required_sections) - len(missing_sections), len(required_sections))
    sections_pass = len(missing_sections) == 0

    assumption_count = count_assumptions(response)
    assumptions_pass = assumption_count <= max_assumptions
    assumptions_score = 1.0 if assumptions_pass else 0.0

    missing_keywords = [kw for kw in required_keywords if kw.lower() not in response.lower()]
    keywords_score = _safe_ratio(len(required_keywords) - len(missing_keywords), len(required_keywords))
    keywords_pass = len(missing_keywords) == 0

    missing_refs = [ref for ref in required_refs if ref.lower() not in response.lower()]
    refs_score = _safe_ratio(len(required_refs) - len(missing_refs), len(required_refs))
    refs_pass = len(missing_refs) == 0

    traits_score, missing_traits = check_traits(response, required_traits)
    traits_pass = len(missing_traits) == 0

    script_score: Optional[float] = None
    script_pass: Optional[bool] = None
    script_details = "N/A"
    if preferred_script:
        preferred_script = str(preferred_script)
        if script_validation is not None and isinstance(script_validation, Mapping):
            script_score, script_pass, script_details = evaluate_script_numeric_checks(
                response=response,
                preferred_script=preferred_script,
                validation=script_validation,
                repo_root=repo_root,
                suite_dir=suite_dir,
            )
        else:
            script_pass = preferred_script.lower() in response.lower()
            script_score = 1.0 if script_pass else 0.0
            script_details = (
                f"mentioned {preferred_script}" if script_pass else f"missing mention: {preferred_script}"
            )

    metric_scores = {
        "sections": sections_score,
        "assumptions": assumptions_score,
        "keywords": keywords_score,
        "references": refs_score,
        "traits": traits_score,
    }
    if script_score is not None:
        metric_scores["preferred_script"] = script_score

    total_weight = 0.0
    weighted_sum = 0.0
    for name, score in metric_scores.items():
        weight = DEFAULT_WEIGHTS[name]
        weighted_sum += weight * score
        total_weight += weight
    score = weighted_sum / total_weight if total_weight > 0 else 0.0

    hard_fail_reasons: List[str] = []
    if not sections_pass:
        hard_fail_reasons.append("missing_required_sections")
    if not assumptions_pass:
        hard_fail_reasons.append("assumptions_out_of_range")
    if preferred_script and script_validation is not None and not bool(script_pass):
        hard_fail_reasons.append("preferred_script_numeric_mismatch")

    passed = score >= min_case_score and len(hard_fail_reasons) == 0

    checks = [
        {
            "name": "sections",
            "score": round(sections_score, 4),
            "passed": sections_pass,
            "details": "missing: " + ", ".join(missing_sections) if missing_sections else "all required sections present",
        },
        {
            "name": "assumptions",
            "score": round(assumptions_score, 4),
            "passed": assumptions_pass,
            "details": f"count={assumption_count}, max={max_assumptions}",
        },
        {
            "name": "keywords",
            "score": round(keywords_score, 4),
            "passed": keywords_pass,
            "details": "missing: " + ", ".join(missing_keywords) if missing_keywords else "all keywords present",
        },
        {
            "name": "references",
            "score": round(refs_score, 4),
            "passed": refs_pass,
            "details": "missing: " + ", ".join(missing_refs) if missing_refs else "all references present",
        },
        {
            "name": "traits",
            "score": round(traits_score, 4),
            "passed": traits_pass,
            "details": "missing: " + ", ".join(missing_traits) if missing_traits else "all traits passed",
        },
    ]
    if script_score is not None:
        script_check_name = "preferred_script_numeric" if script_validation is not None else "preferred_script"
        checks.append(
            {
                "name": script_check_name,
                "score": round(script_score, 4),
                "passed": bool(script_pass),
                "details": script_details,
            }
        )

    return {
        "id": case_id,
        "title": title,
        "category": category,
        "score": round(score, 4),
        "passed": passed,
        "skipped": False,
        "hard_fail_reasons": hard_fail_reasons,
        "checks": checks,
    }


def execute_preferred_scripts(
    suite: Mapping[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    cases = suite.get("cases", [])
    preferred: List[str] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        value = case.get("preferred_script")
        if isinstance(value, str) and value and value not in preferred:
            preferred.append(value)

    results: List[Dict[str, Any]] = []
    for script in preferred:
        script_path = repo_root / "skills" / "game-balance-math" / "scripts" / script
        if not script_path.exists():
            results.append(
                {
                    "script": script,
                    "path": str(script_path),
                    "passed": False,
                    "details": "file_not_found",
                }
            )
            continue

        cmd = [sys.executable, str(script_path), "--format", "json"]
        run = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
        if run.returncode != 0:
            results.append(
                {
                    "script": script,
                    "path": str(script_path),
                    "passed": False,
                    "details": f"exit={run.returncode}: {run.stderr.strip()}",
                }
            )
            continue

        stdout = run.stdout.strip()
        if not stdout:
            results.append(
                {
                    "script": script,
                    "path": str(script_path),
                    "passed": False,
                    "details": "empty_stdout",
                }
            )
            continue

        try:
            json.loads(stdout)
        except json.JSONDecodeError as exc:
            results.append(
                {
                    "script": script,
                    "path": str(script_path),
                    "passed": False,
                    "details": f"invalid_json_output: {exc}",
                }
            )
            continue

        results.append(
            {
                "script": script,
                "path": str(script_path),
                "passed": True,
                "details": "ok",
            }
        )

    passed_count = sum(1 for item in results if item["passed"])
    total = len(results)
    return {
        "enabled": True,
        "score": round(_safe_ratio(passed_count, total), 4),
        "passed": passed_count == total,
        "total": total,
        "passed_count": passed_count,
        "results": results,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Golden Prompt Check Report",
        "",
        f"- Generated (UTC): {report['generated_at_utc']}",
        f"- Suite: {report['suite']} (version {report.get('version', 'unknown')})",
        f"- Suite lint: {'PASS' if report['suite_lint']['passed'] else 'FAIL'}",
        f"- Cases passed: {summary['cases_passed']}/{summary['cases_evaluated']} (evaluated) / {summary['cases_total']} (total)",
        f"- Suite score: {summary['suite_score']:.4f}",
        f"- Overall: {'PASS' if summary['overall_passed'] else 'FAIL'}",
    ]

    lint_issues = report["suite_lint"].get("issues", [])
    if lint_issues:
        lines.extend(["", "## Lint Issues"])
        for issue in lint_issues:
            lines.append(f"- {issue}")

    lines.extend(["", "## Case Results", "| Case | Score | Result | Hard Fail Reasons |", "|---|---:|---|---|"])
    for case in report.get("cases", []):
        reasons = ", ".join(case.get("hard_fail_reasons", [])) or "-"
        if case.get("skipped"):
            result = "SKIP"
        else:
            result = "PASS" if case["passed"] else "FAIL"
        lines.append(
            f"| {case['id']} | {case['score']:.4f} | {result} | {reasons} |"
        )

    skipped = [case for case in report.get("cases", []) if case.get("skipped")]
    if skipped:
        lines.append("")
        lines.append("## Skipped Cases")
        for case in skipped:
            lines.append(f"- {case['id']}")

    failed = [case for case in report.get("cases", []) if not case.get("passed") and not case.get("skipped")]
    if failed:
        lines.append("")
        lines.append("## Failed Details")
        for case in failed:
            lines.append(f"### {case['id']} - {case.get('title', '')}")
            for check in case.get("checks", []):
                mark = "PASS" if check["passed"] else "FAIL"
                lines.append(
                    f"- [{mark}] {check['name']} score={check['score']:.4f} ({check['details']})"
                )

    script_checks = report.get("script_checks")
    if script_checks and script_checks.get("enabled"):
        lines.extend(
            [
                "",
                "## Preferred Script Checks",
                f"- Passed: {script_checks['passed_count']}/{script_checks['total']}",
                f"- Score: {script_checks['score']:.4f}",
                f"- Status: {'PASS' if script_checks['passed'] else 'FAIL'}",
            ]
        )
        for item in script_checks.get("results", []):
            lines.append(
                f"- {'PASS' if item['passed'] else 'FAIL'} `{item['script']}`: {item['details']}"
            )

    return "\n".join(lines) + "\n"


def parse_case_ids(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    values = [part.strip() for part in raw.split(",")]
    return [value for value in values if value]


def filter_cases(cases: Sequence[Mapping[str, Any]], selected_ids: Optional[Sequence[str]]) -> List[Mapping[str, Any]]:
    if not selected_ids:
        return list(cases)
    wanted = set(selected_ids)
    return [case for case in cases if str(case.get("id")) in wanted]


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    suite_path = Path(args.suite).resolve()
    suite = load_data(suite_path)
    if not isinstance(suite, dict):
        raise ValueError("Suite file must decode to an object.")

    lint_issues = lint_suite(suite)
    suite_lint = {"passed": len(lint_issues) == 0, "issues": lint_issues}

    templates = suite.get("templates", {})
    all_cases = suite.get("cases", [])
    if not isinstance(templates, dict) or not isinstance(all_cases, list):
        raise ValueError("Suite has invalid templates/cases structure.")

    selected_case_ids = parse_case_ids(args.case_ids)
    cases = filter_cases([c for c in all_cases if isinstance(c, dict)], selected_case_ids)
    case_ids = [str(case.get("id")) for case in cases]

    responses: Dict[str, str] = {}
    response_source = None
    if args.responses:
        response_path = Path(args.responses).resolve()
        responses = load_responses_from_file(response_path)
        response_source = str(response_path)
    elif args.responses_dir:
        responses_dir = Path(args.responses_dir).resolve()
        responses = load_responses_from_dir(responses_dir, case_ids)
        response_source = str(responses_dir)

    case_results: List[Dict[str, Any]] = []
    for case in cases:
        expected_template = str(case.get("expected_template", ""))
        template = templates.get(expected_template, {})
        if not isinstance(template, dict):
            template = {}
        response = responses.get(str(case.get("id")))
        case_result = score_case(
            case=case,
            template=template,
            response=response,
            min_case_score=args.min_case_score,
            allow_missing_cases=args.allow_missing_cases,
            repo_root=suite_path.parents[2],
            suite_dir=suite_path.parent,
        )
        case_results.append(case_result)

    case_total = len(case_results)
    evaluated_cases = [item for item in case_results if not item.get("skipped")]
    evaluated_total = len(evaluated_cases)
    case_passed = sum(1 for item in evaluated_cases if item["passed"])
    suite_score = (
        _safe_ratio(sum(float(item["score"]) for item in evaluated_cases), evaluated_total)
        if evaluated_total > 0
        else 0.0
    )

    repo_root = suite_path.parents[2]
    script_checks: Optional[Dict[str, Any]] = None
    if args.check_scripts:
        script_checks = execute_preferred_scripts(suite=suite, repo_root=repo_root)
    else:
        script_checks = {"enabled": False, "passed": True, "score": 1.0, "total": 0, "passed_count": 0, "results": []}

    overall_passed = (
        suite_lint["passed"]
        and evaluated_total > 0
        and suite_score >= args.min_suite_score
        and case_passed == evaluated_total
        and script_checks["passed"]
    )

    report = {
        "generated_at_utc": _now_utc_iso(),
        "suite": suite.get("suite", suite_path.name),
        "version": suite.get("version", "unknown"),
        "suite_lint": suite_lint,
        "config": {
            "suite_path": str(suite_path),
            "response_source": response_source,
            "min_case_score": args.min_case_score,
            "min_suite_score": args.min_suite_score,
            "allow_missing_cases": args.allow_missing_cases,
            "check_scripts": bool(args.check_scripts),
            "case_ids": selected_case_ids,
        },
        "cases": case_results,
        "script_checks": script_checks,
        "summary": {
            "cases_total": case_total,
            "cases_evaluated": evaluated_total,
            "cases_passed": case_passed,
            "suite_score": round(suite_score, 4),
            "overall_passed": overall_passed,
        },
    }
    return report


def parse_args() -> argparse.Namespace:
    default_suite = Path(__file__).resolve().parent / "game-balance-designer-golden-prompts.json"
    parser = argparse.ArgumentParser(description="Golden prompt auto runner / scorer")
    parser.add_argument(
        "--suite",
        default=str(default_suite),
        help="Path to golden prompt suite file (.json).",
    )

    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--responses",
        help=(
            "Path to responses file (.json). "
            "Supported shapes: {responses:{id:text}}, {cases:[{id,response}]}, or direct map."
        ),
    )
    source_group.add_argument(
        "--responses-dir",
        help="Directory with per-case response files named <case_id>.md/.markdown/.txt",
    )

    parser.add_argument(
        "--case-ids",
        help="Optional comma-separated case ids to run (example: A01,A02,D03).",
    )
    parser.add_argument(
        "--min-case-score",
        type=float,
        default=DEFAULT_CASE_SCORE,
        help=f"Minimum score for each case (default: {DEFAULT_CASE_SCORE}).",
    )
    parser.add_argument(
        "--min-suite-score",
        type=float,
        default=DEFAULT_SUITE_SCORE,
        help=f"Minimum average suite score (default: {DEFAULT_SUITE_SCORE}).",
    )
    parser.add_argument(
        "--allow-missing-cases",
        action="store_true",
        help="Do not hard-fail cases with missing responses.",
    )
    parser.add_argument(
        "--check-scripts",
        action="store_true",
        help="Execute each unique preferred_script and verify JSON output.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Report output format.",
    )
    parser.add_argument(
        "--output",
        help="Optional file path to write the report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_report(args)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    else:
        rendered = render_markdown(report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 0 if report["summary"]["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
