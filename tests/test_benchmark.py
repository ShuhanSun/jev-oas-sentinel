from __future__ import annotations

import unittest

from benchmarks.run import evaluate_cases, load_cases, render_markdown


class BenchmarkTest(unittest.TestCase):
    def test_all_semantic_cases_are_routed_without_structural_findings(self) -> None:
        results = evaluate_cases(load_cases())

        self.assertEqual(11, len(results))
        self.assertTrue(all(result["passed"] for result in results))
        self.assertTrue(all(result["structural_findings"] == 0 for result in results))
        self.assertTrue(all(result["semantic_review_planned"] for result in results))

    def test_markdown_report_is_reproducible(self) -> None:
        results = evaluate_cases(load_cases())
        report = render_markdown(results)

        self.assertIn("Result: 11/11 cases routed as expected", report)
        self.assertIn("`retry-idempotency`", report)
        self.assertIn("`webhook-retry-guarantee`", report)


if __name__ == "__main__":
    unittest.main()
