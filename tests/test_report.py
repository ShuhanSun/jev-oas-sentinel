from datetime import datetime, timezone
import json
import unittest

from jev_oas_sentinel.policy import Finding
from jev_oas_sentinel.report import Report, render


class ReportTest(unittest.TestCase):
    def test_sarif_is_valid_and_preserves_evidence(self) -> None:
        report = Report(
            "test", datetime(2026, 1, 1, tzinfo=timezone.utc), "base.yaml", "head.yaml", "advisory", "jev-test",
            (Finding("contract-review", "review", "GET /pets", "Review change", "head.yaml", {"probability": .8}),),
            {"semantic_calls": 1},
        )
        sarif = json.loads(render(report, "sarif"))
        result = sarif["runs"][0]["results"][0]
        self.assertEqual("warning", result["level"])
        self.assertEqual(.8, result["properties"]["evidence"]["probability"])


if __name__ == "__main__":
    unittest.main()
