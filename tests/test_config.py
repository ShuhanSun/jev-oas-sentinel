from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev_oas_sentinel.config import apply_suppressions, discover_config, load_config
from jev_oas_sentinel.policy import Finding


class ConfigTest(unittest.TestCase):
    def test_discovers_only_the_current_directory_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ".jev-sentinel.yaml"
            path.write_text("version: 1\nmode: enforce\n")

            with patch("jev_oas_sentinel.config.Path.cwd", return_value=root):
                discovered = discover_config(None, disabled=False)
                disabled = discover_config(None, disabled=True)

            self.assertEqual(path.resolve(), discovered.path)
            self.assertEqual("enforce", discovered.mode)
            self.assertIsNone(disabled.path)

    def test_loads_versioned_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".jev-sentinel.yaml"
            path.write_text("""version: 1
mode: enforce
fail_on_review: true
model: jev-test
review_threshold: 0.7
block_threshold: 0.95
max_jev_calls: 12
timeout: 15
max_retries: 2
suppressions:
  - operation: GET /legacy/*
    rule: semantic-*
    expires: 2099-12-31
    owner: api-platform
    reason: tracked in API-123
""")

            config = load_config(path)

            self.assertEqual(path.resolve(), config.path)
            self.assertEqual("enforce", config.mode)
            self.assertTrue(config.fail_on_review)
            self.assertEqual(12, config.max_jev_calls)
            self.assertEqual(date(2099, 12, 31), config.suppressions[0].expires)

    def test_rejects_security_sensitive_endpoint_setting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".jev-sentinel.yaml"
            path.write_text("version: 1\nendpoint: https://example.test/collect\n")

            with self.assertRaisesRegex(ValueError, "Unknown configuration fields: endpoint"):
                load_config(path)

    def test_suppression_is_visible_and_preserves_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".jev-sentinel.yaml"
            path.write_text("""version: 1
suppressions:
  - operation: GET /orders
    rule: response-property-removed
    expires: 2099-12-31
    owner: orders-team
    reason: migration in progress
""")
            config = load_config(path)
            finding = Finding(
                "response-property-removed",
                "block",
                "GET /orders",
                "Response property was removed",
                "head.yaml",
                {"layer": "deterministic"},
            )

            findings, count = apply_suppressions(
                (finding,), config.suppressions, today=date(2026, 9, 19)
            )

            self.assertEqual(1, count)
            self.assertEqual("notice", findings[0].severity)
            self.assertEqual("response-property-removed", findings[0].rule_id)
            self.assertIn("block suppressed until 2099-12-31", findings[0].message)
            self.assertEqual("block", findings[0].evidence["suppression"]["original_severity"])
            self.assertEqual("orders-team", findings[0].evidence["suppression"]["owner"])

    def test_expired_suppression_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".jev-sentinel.yaml"
            path.write_text("""version: 1
suppressions:
  - operation: GET /orders
    rule: response-property-removed
    expires: 2026-09-18
    owner: orders-team
    reason: migration in progress
""")
            config = load_config(path)

            with self.assertRaisesRegex(ValueError, "Expired suppression"):
                apply_suppressions((), config.suppressions, today=date(2026, 9, 19))


if __name__ == "__main__":
    unittest.main()
