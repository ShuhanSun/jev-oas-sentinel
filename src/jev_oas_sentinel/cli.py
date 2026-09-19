from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time
from typing import Sequence, TextIO

from . import __version__
from .jev import DEFAULT_ENDPOINT, DEFAULT_MODEL, JevClient
from .openapi import OpenApiDiffer, load_spec
from .policy import PolicyEngine
from .report import Report, render


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="jev-oas-sentinel", description="Detect semantic OpenAPI compatibility risks")
    root.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = root.add_subparsers(dest="command", required=True)
    compare = commands.add_parser("compare", help="Compare two OpenAPI documents")
    compare.add_argument("--base", type=Path, required=True, help="Baseline OpenAPI document")
    compare.add_argument("--head", type=Path, required=True, help="Candidate OpenAPI document")
    compare.add_argument("--format", choices=("json", "markdown", "sarif"), default="json")
    compare.add_argument("--output", type=Path, help="Write output to a file")
    compare.add_argument("--mode", choices=("advisory", "enforce"), default="advisory")
    compare.add_argument("--no-jev", action="store_true", help="Run deterministic checks only")
    compare.add_argument("--fail-on-review", action="store_true", help="Exit 1 when review findings exist")
    compare.add_argument("--model", default=DEFAULT_MODEL)
    compare.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    compare.add_argument("--api-key-file", type=Path)
    compare.add_argument("--review-threshold", type=_probability, default=0.65)
    compare.add_argument("--block-threshold", type=_probability, default=0.90)
    return root


def run(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    environment: dict[str, str] | None = None,
) -> int:
    try:
        args = parser().parse_args(argv)
        if args.review_threshold > args.block_threshold:
            raise ValueError("Thresholds must satisfy 0 <= review <= block <= 1")
        base = load_spec(args.base)
        head = load_spec(args.head)
        differ = OpenApiDiffer()
        changes = differ.compare(base, head)
        client = None if args.no_jev else _live_client(args, environment or dict(os.environ))
        started = time.monotonic()
        evaluation = PolicyEngine(
            differ, client, args.mode, args.review_threshold, args.block_threshold, str(args.head)
        ).evaluate(changes)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        report = Report(
            __version__, datetime.now(timezone.utc), str(args.base), str(args.head), args.mode,
            "disabled" if args.no_jev else args.model,
            evaluation.findings,
            {
                "changed_operations": len(changes),
                "semantic_calls": evaluation.calls,
                "input_tokens": evaluation.input_tokens,
                "output_tokens": evaluation.output_tokens,
                "elapsed_ms": elapsed_ms,
            },
        )
        rendered = render(report, args.format)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
            print(f"Wrote report to {args.output}", file=stderr)
        else:
            stdout.write(rendered)
        return int(report.has_blocks or (args.fail_on_review and report.has_reviews))
    except (OSError, ValueError) as exc:
        print(f"Error: {' '.join(str(exc).split())}", file=stderr)
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)


def _live_client(args: argparse.Namespace, environment: dict[str, str]) -> JevClient:
    if args.api_key_file:
        api_key = args.api_key_file.read_text(encoding="utf-8").strip()
    else:
        api_key = environment.get("TYPESAFE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("No TypeSafe API key found; set TYPESAFE_API_KEY, use --api-key-file, or pass --no-jev")
    return JevClient(api_key, args.endpoint, args.model)


def _probability(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed

