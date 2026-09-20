import argparse
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev_oas_sentinel.cli import _live_client, run


class CliTest(unittest.TestCase):
    @patch("jev_oas_sentinel.cli.JevClient")
    def test_ca_bundle_environment_is_forwarded(self, client: unittest.mock.Mock) -> None:
        args = argparse.Namespace(
            api_key_file=None,
            ca_bundle=None,
            endpoint="https://example.test/jev",
            model="jev-test",
            timeout=30.0,
            max_retries=3,
        )

        _live_client(
            args,
            {"TYPESAFE_API_KEY": "test-key", "JEV_CA_BUNDLE": "/etc/company-ca.pem"},
        )

        client.assert_called_once_with(
            "test-key", "https://example.test/jev", "jev-test", "/etc/company-ca.pem", None,
            timeout=30.0, max_retries=3,
        )

    def test_dry_run_plans_calls_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            head = root / "head.json"
            base.write_text(json.dumps({
                "openapi": "3.0.3", "paths": {"/x": {"get": {"description": "all"}}},
            }))
            head.write_text(json.dumps({
                "openapi": "3.0.3", "paths": {"/x": {"get": {"description": "active"}}},
            }))
            output = StringIO()

            exit_code = run(
                ["compare", "--base", str(base), "--head", str(head), "--dry-run"],
                stdout=output, stderr=StringIO(), environment={},
            )

            report = json.loads(output.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual(1, report["metrics"]["planned_semantic_calls"])
            self.assertEqual(0, report["metrics"]["semantic_attempts"])
            self.assertEqual("semantic-evaluation-planned", report["findings"][0]["rule_id"])

    def test_max_jev_calls_stops_before_api_key_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            head = root / "head.json"
            base.write_text(json.dumps({
                "openapi": "3.0.3", "paths": {"/x": {"get": {"description": "all"}}},
            }))
            head.write_text(json.dumps({
                "openapi": "3.0.3", "paths": {"/x": {"get": {"description": "active"}}},
            }))
            stderr = StringIO()

            exit_code = run(
                [
                    "compare", "--base", str(base), "--head", str(head),
                    "--max-jev-calls", "0",
                ],
                stdout=StringIO(), stderr=stderr, environment={},
            )

            self.assertEqual(2, exit_code)
            self.assertIn("Planned JEV calls (1) exceed --max-jev-calls (0)", stderr.getvalue())

    def test_writes_empty_jev_trace_when_jev_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / "openapi.json"
            trace = root / "jev-io.json"
            document.write_text(json.dumps({"openapi": "3.0.3", "paths": {}}))

            exit_code = run(
                [
                    "compare", "--base", str(document), "--head", str(document),
                    "--no-jev", "--jev-io-output", str(trace),
                ],
                stdout=StringIO(), stderr=StringIO(), environment={},
            )

            self.assertEqual(0, exit_code)
            self.assertEqual({"schema_version": 1, "events": []}, json.loads(trace.read_text()))
            if os.name != "nt":
                self.assertEqual(0o600, trace.stat().st_mode & 0o777)

    def test_offline_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            head = root / "head.json"
            base.write_text(json.dumps({"openapi": "3.0.3", "paths": {"/x": {"get": {"description": "all"}}}}))
            head.write_text(json.dumps({"openapi": "3.0.3", "paths": {"/x": {"get": {"description": "active"}}}}))
            output = StringIO()
            exit_code = run(
                ["compare", "--base", str(base), "--head", str(head), "--no-jev", "--format", "json"],
                stdout=output,
                stderr=StringIO(),
                environment={},
            )
            report = json.loads(output.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual(1, report["summary"]["reviews"])
            self.assertEqual("semantic-evaluation-skipped", report["findings"][0]["rule_id"])
            self.assertEqual(0, report["metrics"]["semantic_attempts"])
            self.assertEqual(0, report["metrics"]["semantic_successes"])
            self.assertEqual(0, report["metrics"]["semantic_failures"])
            self.assertEqual(0, report["metrics"]["jev_http_attempts"])

    def test_missing_api_key_is_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "openapi.json"
            document.write_text(json.dumps({"openapi": "3.0.3", "paths": {}}))
            stderr = StringIO()
            with patch.dict(os.environ, {"TYPESAFE_API_KEY": "ambient-key"}, clear=True):
                exit_code = run(
                    ["compare", "--base", str(document), "--head", str(document)],
                    stdout=StringIO(), stderr=stderr, environment={},
                )
            self.assertEqual(2, exit_code)
            self.assertIn("No TypeSafe API key found", stderr.getvalue())

    def test_configuration_is_applied_and_cli_can_override_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            head = root / "head.json"
            config = root / "sentinel.yaml"
            base.write_text(json.dumps({
                "openapi": "3.0.3", "paths": {"/x": {"get": {"description": "all"}}},
            }))
            head.write_text(json.dumps({
                "openapi": "3.0.3", "paths": {"/x": {"get": {"description": "active"}}},
            }))
            config.write_text("""version: 1
mode: enforce
fail_on_review: true
review_threshold: 0.7
block_threshold: 0.95
""")
            configured_output = StringIO()

            configured_exit = run(
                [
                    "compare", "--base", str(base), "--head", str(head),
                    "--config", str(config), "--dry-run",
                ],
                stdout=configured_output, stderr=StringIO(), environment={},
            )
            overridden_output = StringIO()
            overridden_exit = run(
                [
                    "compare", "--base", str(base), "--head", str(head),
                    "--config", str(config), "--dry-run", "--mode", "advisory",
                    "--no-fail-on-review",
                ],
                stdout=overridden_output, stderr=StringIO(), environment={},
            )

            configured = json.loads(configured_output.getvalue())
            overridden = json.loads(overridden_output.getvalue())
            self.assertEqual(1, configured_exit)
            self.assertEqual("enforce", configured["mode"])
            self.assertEqual(str(config.resolve()), configured["metrics"]["config_file"])
            self.assertEqual(0, overridden_exit)
            self.assertEqual("advisory", overridden["mode"])

    def test_configuration_suppresses_finding_with_audit_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            head = root / "head.json"
            config = root / "sentinel.yaml"
            base.write_text(json.dumps({
                "openapi": "3.0.3", "paths": {"/orders": {"get": {"responses": {}}}},
            }))
            head.write_text(json.dumps({"openapi": "3.0.3", "paths": {}}))
            config.write_text("""version: 1
suppressions:
  - operation: GET /orders
    rule: operation-removed
    expires: 2099-12-31
    owner: orders-team
    reason: tracked in API-123
""")
            output = StringIO()

            exit_code = run(
                [
                    "compare", "--base", str(base), "--head", str(head),
                    "--config", str(config), "--no-jev",
                ],
                stdout=output, stderr=StringIO(), environment={},
            )

            report = json.loads(output.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual(0, report["summary"]["blocks"])
            self.assertEqual(1, report["summary"]["notices"])
            self.assertEqual(1, report["metrics"]["suppressed_findings"])
            self.assertEqual(
                "orders-team", report["findings"][0]["evidence"]["suppression"]["owner"]
            )

    def test_expired_suppression_fails_before_openapi_loading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "sentinel.yaml"
            config.write_text("""version: 1
suppressions:
  - operation: GET /orders
    rule: operation-removed
    expires: 2000-01-01
    owner: orders-team
    reason: obsolete exception
""")
            stderr = StringIO()

            exit_code = run(
                [
                    "compare", "--base", "missing-base.yaml", "--head", "missing-head.yaml",
                    "--config", str(config), "--no-jev",
                ],
                stdout=StringIO(), stderr=stderr, environment={},
            )

            self.assertEqual(2, exit_code)
            self.assertIn("Expired suppression", stderr.getvalue())
            self.assertNotIn("Cannot read", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
