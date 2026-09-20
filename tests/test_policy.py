import unittest

from jev_oas_sentinel.jev import SemanticDecision
from jev_oas_sentinel.openapi import OpenApiDiffer, OperationChange
from jev_oas_sentinel.policy import PolicyEngine


class StubClient:
    def __init__(self, decision: SemanticDecision) -> None:
        self.decision = decision

    def evaluate(self, state):
        return self.decision


class FailingClient:
    def evaluate(self, state):
        raise OSError("network unavailable")


def decision(breaking: float, preserved: float) -> SemanticDecision:
    return SemanticDecision(
        "jev-test", "breaking", {"breaking": breaking}, breaking,
        "default_behavior", {"default_behavior": 1.0}, 1.0,
        preserved, 2.0, {"2": 1.0}, 1.0, 10, 5,
    )


class PolicyEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.change = OperationChange("GET /orders", {"description": "all"}, {"description": "active"}, semantic_changed=True)

    def test_advisory_never_blocks_semantic_change(self) -> None:
        result = PolicyEngine(OpenApiDiffer(), StubClient(decision(.99, .01)), "advisory", .65, .9, "head.yaml").evaluate([self.change])
        self.assertEqual("review", result.findings[0].severity)
        self.assertEqual(1, result.attempts)
        self.assertEqual(1, result.calls)
        self.assertEqual(0, result.failures)

    def test_enforce_requires_both_signals(self) -> None:
        result = PolicyEngine(OpenApiDiffer(), StubClient(decision(.95, .03)), "enforce", .65, .9, "head.yaml").evaluate([self.change])
        self.assertEqual("block", result.findings[0].severity)

    def test_enforce_does_not_block_on_one_signal(self) -> None:
        result = PolicyEngine(OpenApiDiffer(), StubClient(decision(.95, .5)), "enforce", .65, .9, "head.yaml").evaluate([self.change])
        self.assertEqual("review", result.findings[0].severity)

    def test_api_failure_closes_only_in_enforce_mode(self) -> None:
        advisory = PolicyEngine(OpenApiDiffer(), FailingClient(), "advisory", .65, .9, "head.yaml").evaluate([self.change])
        enforce = PolicyEngine(OpenApiDiffer(), FailingClient(), "enforce", .65, .9, "head.yaml").evaluate([self.change])
        self.assertEqual("review", advisory.findings[0].severity)
        self.assertEqual("block", enforce.findings[0].severity)
        self.assertEqual(1, advisory.attempts)
        self.assertEqual(0, advisory.calls)
        self.assertEqual(1, advisory.failures)


if __name__ == "__main__":
    unittest.main()
