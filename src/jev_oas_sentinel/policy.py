from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .jev import SemanticDecision
from .openapi import OpenApiDiffer, OperationChange


class DecisionClient(Protocol):
    def evaluate(self, state: dict[str, Any]) -> SemanticDecision: ...


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    operation: str
    message: str
    source: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Evaluation:
    findings: tuple[Finding, ...]
    attempts: int
    calls: int
    failures: int
    input_tokens: int
    output_tokens: int


class PolicyEngine:
    def __init__(
        self,
        differ: OpenApiDiffer,
        client: DecisionClient | None,
        mode: str,
        review_threshold: float,
        block_threshold: float,
        source: str,
    ) -> None:
        if not 0 <= review_threshold <= block_threshold <= 1:
            raise ValueError("Thresholds must satisfy 0 <= review <= block <= 1")
        self.differ = differ
        self.client = client
        self.mode = mode
        self.review_threshold = review_threshold
        self.block_threshold = block_threshold
        self.source = source

    def evaluate(self, changes: list[OperationChange]) -> Evaluation:
        findings: list[Finding] = []
        attempts = calls = failures = input_tokens = output_tokens = 0
        for change in changes:
            findings.extend(Finding(
                issue.rule_id, issue.severity, issue.operation, issue.message,
                self.source, {"layer": "deterministic"},
            ) for issue in change.structural_issues)
            if not change.semantic_changed:
                continue
            if self.client is None:
                findings.append(Finding(
                    "semantic-evaluation-skipped", "review", change.operation,
                    "Contract prose changed but JEV evaluation was disabled",
                    self.source, {"layer": "semantic"},
                ))
                continue
            try:
                attempts += 1
                decision = self.client.evaluate(self.differ.semantic_state(change))
                calls += 1
                input_tokens += decision.input_tokens
                output_tokens += decision.output_tokens
                findings.append(self._finding(change, decision))
            except OSError as exc:
                failures += 1
                severity = "block" if self.mode == "enforce" else "review"
                findings.append(Finding(
                    "semantic-evaluation-failed", severity, change.operation,
                    f"JEV evaluation failed: {self._safe_message(exc)}",
                    self.source, {"layer": "semantic", "failure_mode": "closed"},
                ))
        return Evaluation(tuple(findings), attempts, calls, failures, input_tokens, output_tokens)

    def _finding(self, change: OperationChange, decision: SemanticDecision) -> Finding:
        violation_probability = 1.0 - decision.old_promise_preserved_probability
        enforceable = (
            self.mode == "enforce"
            and decision.breaking_probability >= self.block_threshold
            and violation_probability >= self.block_threshold
        )
        if enforceable:
            severity, rule_id = "block", "semantic-breaking-change"
        elif (
            decision.change_kind in {"breaking", "unclear", "behavioral_nonbreaking"}
            or decision.change_kind_confidence < self.review_threshold
            or decision.old_promise_preserved_probability < self.review_threshold
        ):
            severity, rule_id = "review", "semantic-contract-review"
        else:
            severity, rule_id = "notice", "semantic-contract-preserved"
        message = (
            f"JEV classified the prose change as {decision.change_kind} affecting "
            f"{decision.affected_dimension} (kind confidence {decision.change_kind_confidence:.3f}, "
            f"old-promise preservation {decision.old_promise_preserved_probability:.3f})"
        )
        evidence = {
            "layer": "semantic",
            "model": decision.model,
            "change_kind": decision.change_kind,
            "change_kind_probabilities": decision.change_kind_probabilities,
            "change_kind_confidence": decision.change_kind_confidence,
            "affected_dimension": decision.affected_dimension,
            "affected_dimension_probabilities": decision.affected_dimension_probabilities,
            "affected_dimension_confidence": decision.affected_dimension_confidence,
            "old_promise_preserved_probability": decision.old_promise_preserved_probability,
            "migration_burden": decision.migration_burden,
            "migration_burden_probabilities": decision.migration_burden_probabilities,
            "migration_burden_confidence": decision.migration_burden_confidence,
            "thresholds": {"review": self.review_threshold, "block": self.block_threshold},
            "usage": {"input_tokens": decision.input_tokens, "output_tokens": decision.output_tokens},
        }
        return Finding(rule_id, severity, change.operation, message, self.source, evidence)

    @staticmethod
    def _safe_message(exc: OSError) -> str:
        normalized = " ".join(str(exc).split()) or type(exc).__name__
        return normalized if len(normalized) <= 300 else normalized[:300] + "…"
