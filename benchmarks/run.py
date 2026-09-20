from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from jev_oas_sentinel.openapi import OpenApiDiffer


ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "cases.json"


def load_cases(path: Path = CASES_PATH) -> list[dict[str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("benchmark cases must be a JSON array")
    required = {"id", "dimension", "operation", "old", "new", "risk"}
    cases: list[dict[str, str]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError(f"benchmark case {index} is missing required fields")
        cases.append({key: str(item[key]) for key in required})
    return cases


def evaluate_case(case: dict[str, str]) -> dict[str, Any]:
    method, path = case["operation"].split(" ", 1)
    base = _spec(path, method.lower(), case["old"])
    head = _spec(path, method.lower(), case["new"])
    changes = OpenApiDiffer().compare(base, head)
    issues = [issue for change in changes for issue in change.structural_issues]
    semantic_changes = [change for change in changes if change.semantic_changed]
    passed = len(changes) == 1 and len(semantic_changes) == 1 and not issues
    return {
        **case,
        "structural_findings": len(issues),
        "semantic_review_planned": len(semantic_changes) == 1,
        "passed": passed,
    }


def evaluate_cases(cases: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [evaluate_case(case) for case in cases]


def render_markdown(results: list[dict[str, Any]]) -> str:
    passed = sum(bool(result["passed"]) for result in results)
    lines = [
        "# Semantic routing benchmark",
        "",
        "These cases keep the OpenAPI structure stable while changing a consumer-facing promise in contract prose.",
        "The benchmark verifies that the deterministic layer reports no definite structural break and that Sentinel routes each change to JEV semantic review.",
        "It does not claim model accuracy and does not call JEV.",
        "",
        f"**Result: {passed}/{len(results)} cases routed as expected.**",
        "",
        "| Case | Dimension | Operation | Structural findings | JEV review planned |",
        "|---|---|---|---:|:---:|",
    ]
    for result in results:
        planned = "yes" if result["semantic_review_planned"] else "no"
        lines.append(
            f"| `{result['id']}` | {result['dimension']} | `{result['operation']}` | "
            f"{result['structural_findings']} | {planned} |"
        )
    lines.extend([
        "",
        "## Why these changes matter",
        "",
    ])
    for result in results:
        lines.append(f"- **{result['id']}**: {result['risk']}")
    return "\n".join(lines) + "\n"


def _spec(path: str, method: str, description: str) -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Benchmark API", "version": "1.0.0"},
        "paths": {
            path: {
                method: {
                    "description": description,
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object", "additionalProperties": True}
                                }
                            },
                        }
                    },
                }
            }
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the semantic routing benchmark")
    parser.add_argument("--check", action="store_true", help="return non-zero if a case is not routed as expected")
    parser.add_argument("--output", type=Path, help="write the Markdown report to this path")
    args = parser.parse_args(argv)

    results = evaluate_cases(load_cases())
    report = render_markdown(results)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    if args.check and not all(result["passed"] for result in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
