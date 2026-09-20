import argparse
from io import StringIO
import json
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
        )

        _live_client(
            args,
            {"TYPESAFE_API_KEY": "test-key", "JEV_CA_BUNDLE": "/etc/company-ca.pem"},
        )

        client.assert_called_once_with(
            "test-key", "https://example.test/jev", "jev-test", "/etc/company-ca.pem", None
        )

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
            self.assertEqual({"events": []}, json.loads(trace.read_text()))

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

    def test_missing_api_key_is_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "openapi.json"
            document.write_text(json.dumps({"openapi": "3.0.3", "paths": {}}))
            stderr = StringIO()
            exit_code = run(
                ["compare", "--base", str(document), "--head", str(document)],
                stdout=StringIO(), stderr=stderr, environment={},
            )
            self.assertEqual(2, exit_code)
            self.assertIn("No TypeSafe API key found", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
