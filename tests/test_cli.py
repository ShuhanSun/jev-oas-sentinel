from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from jev_oas_sentinel.cli import run


class CliTest(unittest.TestCase):
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
