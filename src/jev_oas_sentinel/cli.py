from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Sequence, TextIO

from . import __version__
from .jev import DEFAULT_ENDPOINT, DEFAULT_MODEL, JevClient, JevTransportMetrics
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
    compare.add_argument(
        "--ref-root",
        type=Path,
        help="Allowed root for local $ref files (defaults to each specification's directory)",
    )
    compare.add_argument("--format", choices=("json", "markdown", "sarif"), default="json")
    compare.add_argument("--output", type=Path, help="Write output to a file")
    compare.add_argument("--mode", choices=("advisory", "enforce"), default="advisory")
    compare.add_argument("--no-jev", action="store_true", help="Run deterministic checks only")
    compare.add_argument("--fail-on-review", action="store_true", help="Exit 1 when review findings exist")
    compare.add_argument("--model", default=DEFAULT_MODEL)
    compare.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    compare.add_argument("--api-key-file", type=Path)
    compare.add_argument(
        "--ca-bundle",
        type=Path,
        help="PEM CA bundle for TLS verification (also JEV_CA_BUNDLE or SSL_CERT_FILE)",
    )
    compare.add_argument(
        "--show-jev-io",
        action="store_true",
        help="Print JEV request/response JSON to stderr (never includes the API key)",
    )
    compare.add_argument(
        "--jev-io-output",
        type=Path,
        metavar="PATH",
        help="Write JEV request/response JSON to a file (never includes the API key)",
    )
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
        if args.output and args.jev_io_output and args.output.resolve() == args.jev_io_output.resolve():
            raise ValueError("--output and --jev-io-output must use different files")
        base = load_spec(args.base, args.ref_root)
        head = load_spec(args.head, args.ref_root)
        differ = OpenApiDiffer()
        changes = differ.compare(base, head)
        trace_events: list[dict[str, object]] | None = (
            [] if args.show_jev_io or args.jev_io_output else None
        )
        client = None if args.no_jev else _live_client(
            args,
            environment or dict(os.environ),
            trace_events.append if trace_events is not None else None,
        )
        started = time.monotonic()
        evaluation = PolicyEngine(
            differ, client, args.mode, args.review_threshold, args.block_threshold, str(args.head)
        ).evaluate(changes)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        transport = client.transport_metrics if client is not None else JevTransportMetrics()
        report = Report(
            __version__, datetime.now(timezone.utc), str(args.base), str(args.head), args.mode,
            "disabled" if args.no_jev else args.model,
            evaluation.findings,
            {
                "changed_operations": len(changes),
                "semantic_attempts": evaluation.attempts,
                "semantic_calls": evaluation.calls,
                "semantic_successes": evaluation.calls,
                "semantic_failures": evaluation.failures,
                "jev_http_attempts": transport.attempts,
                "jev_http_successes": transport.successes,
                "jev_http_failures": transport.failures,
                "jev_http_retries": transport.retries,
                "jev_http_latency_ms": transport.latency_ms,
                "input_tokens": evaluation.input_tokens,
                "output_tokens": evaluation.output_tokens,
                "elapsed_ms": elapsed_ms,
            },
        )
        if trace_events is not None:
            _write_jev_io(args, trace_events, stderr)
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


def _live_client(
    args: argparse.Namespace,
    environment: dict[str, str],
    trace: Callable[[dict[str, Any]], None] | None = None,
) -> JevClient:
    if args.api_key_file:
        api_key = args.api_key_file.read_text(encoding="utf-8").strip()
    else:
        api_key = environment.get("TYPESAFE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("No TypeSafe API key found; set TYPESAFE_API_KEY, use --api-key-file, or pass --no-jev")
    ca_bundle = args.ca_bundle or environment.get("JEV_CA_BUNDLE") or environment.get("SSL_CERT_FILE")
    return JevClient(api_key, args.endpoint, args.model, ca_bundle, trace)


def _write_jev_io(
    args: argparse.Namespace,
    events: list[dict[str, object]],
    stderr: TextIO,
) -> None:
    rendered = json.dumps(
        {"schema_version": 1, "events": events}, indent=2, ensure_ascii=False
    ) + "\n"
    if args.show_jev_io:
        print("JEV request/response trace:", file=stderr)
        stderr.write(rendered)
    if args.jev_io_output:
        args.jev_io_output.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(args.jev_io_output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(rendered)
        if os.name != "nt":
            os.chmod(args.jev_io_output, 0o600)
        print(f"Wrote JEV request/response trace to {args.jev_io_output}", file=stderr)


def _probability(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed
