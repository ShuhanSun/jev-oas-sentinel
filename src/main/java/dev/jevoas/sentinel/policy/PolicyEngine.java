package dev.jevoas.sentinel.policy;

import dev.jevoas.sentinel.jev.DecisionClient;
import dev.jevoas.sentinel.jev.SemanticDecision;
import dev.jevoas.sentinel.openapi.OpenApiDiffer;
import dev.jevoas.sentinel.openapi.OperationChange;
import dev.jevoas.sentinel.openapi.Severity;
import dev.jevoas.sentinel.openapi.StructuralIssue;
import dev.jevoas.sentinel.report.Finding;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class PolicyEngine {
    private final OpenApiDiffer differ;
    private final DecisionClient decisionClient;
    private final PolicyMode mode;
    private final double reviewThreshold;
    private final double blockThreshold;
    private final String source;

    public PolicyEngine(
            OpenApiDiffer differ,
            DecisionClient decisionClient,
            PolicyMode mode,
            double reviewThreshold,
            double blockThreshold,
            String source) {
        if (reviewThreshold < 0.0 || reviewThreshold > 1.0
                || blockThreshold < 0.0 || blockThreshold > 1.0
                || reviewThreshold > blockThreshold) {
            throw new IllegalArgumentException("Thresholds must satisfy 0 <= review <= block <= 1");
        }
        this.differ = differ;
        this.decisionClient = decisionClient;
        this.mode = mode;
        this.reviewThreshold = reviewThreshold;
        this.blockThreshold = blockThreshold;
        this.source = source;
    }

    public Evaluation evaluate(List<OperationChange> changes) throws InterruptedException {
        List<Finding> findings = new ArrayList<>();
        long calls = 0;
        long inputTokens = 0;
        long outputTokens = 0;
        for (OperationChange change : changes) {
            for (StructuralIssue issue : change.structuralIssues()) {
                findings.add(new Finding(
                        issue.ruleId(),
                        issue.severity(),
                        issue.operation(),
                        issue.message(),
                        source,
                        Map.of("layer", "deterministic")));
            }
            if (!change.semanticChanged()) {
                continue;
            }
            if (decisionClient == null) {
                findings.add(new Finding(
                        "semantic-evaluation-skipped",
                        Severity.REVIEW,
                        change.operation(),
                        "Contract prose changed but Jev evaluation was disabled",
                        source,
                        Map.of("layer", "semantic")));
                continue;
            }
            try {
                SemanticDecision decision = decisionClient.evaluate(differ.semanticState(change));
                calls++;
                inputTokens += decision.inputTokens();
                outputTokens += decision.outputTokens();
                findings.add(toFinding(change, decision));
            } catch (IOException exception) {
                Severity severity = mode == PolicyMode.ENFORCE ? Severity.BLOCK : Severity.REVIEW;
                findings.add(new Finding(
                        "semantic-evaluation-failed",
                        severity,
                        change.operation(),
                        "Jev evaluation failed: " + safeMessage(exception),
                        source,
                        Map.of("layer", "semantic", "failure_mode", "closed")));
            }
        }
        return new Evaluation(List.copyOf(findings), calls, inputTokens, outputTokens);
    }

    private Finding toFinding(OperationChange change, SemanticDecision decision) {
        double breakingProbability = decision.breakingProbability();
        double violationProbability = 1.0 - decision.oldPromisePreservedProbability();
        boolean enforceableBreak = mode == PolicyMode.ENFORCE
                && breakingProbability >= blockThreshold
                && violationProbability >= blockThreshold;

        Severity severity;
        String ruleId;
        if (enforceableBreak) {
            severity = Severity.BLOCK;
            ruleId = "semantic-breaking-change";
        } else if ("breaking".equals(decision.changeKind())
                || "unclear".equals(decision.changeKind())
                || "behavioral_nonbreaking".equals(decision.changeKind())
                || decision.changeKindConfidence() < reviewThreshold
                || decision.oldPromisePreservedProbability() < reviewThreshold) {
            severity = Severity.REVIEW;
            ruleId = "semantic-contract-review";
        } else {
            severity = Severity.NOTICE;
            ruleId = "semantic-contract-preserved";
        }

        String message = "Jev classified the prose change as " + decision.changeKind()
                + " affecting " + decision.affectedDimension()
                + String.format(Locale.ROOT, " (kind confidence %.3f, old-promise preservation %.3f)",
                decision.changeKindConfidence(), decision.oldPromisePreservedProbability());

        LinkedHashMap<String, Object> evidence = new LinkedHashMap<>();
        evidence.put("layer", "semantic");
        evidence.put("model", decision.model());
        evidence.put("change_kind", decision.changeKind());
        evidence.put("change_kind_probabilities", decision.changeKindProbabilities());
        evidence.put("change_kind_confidence", decision.changeKindConfidence());
        evidence.put("affected_dimension", decision.affectedDimension());
        evidence.put("affected_dimension_probabilities", decision.affectedDimensionProbabilities());
        evidence.put("affected_dimension_confidence", decision.affectedDimensionConfidence());
        evidence.put("old_promise_preserved_probability", decision.oldPromisePreservedProbability());
        evidence.put("migration_burden", decision.migrationBurden());
        evidence.put("migration_burden_probabilities", decision.migrationBurdenProbabilities());
        evidence.put("migration_burden_confidence", decision.migrationBurdenConfidence());
        evidence.put("thresholds", Map.of("review", reviewThreshold, "block", blockThreshold));
        evidence.put("usage", Map.of("input_tokens", decision.inputTokens(), "output_tokens", decision.outputTokens()));
        return new Finding(ruleId, severity, change.operation(), message, source, Map.copyOf(evidence));
    }

    private String safeMessage(IOException exception) {
        String message = exception.getMessage();
        if (message == null || message.isBlank()) {
            return exception.getClass().getSimpleName();
        }
        String normalized = message.replaceAll("[\\r\\n]+", " ");
        return normalized.length() <= 300 ? normalized : normalized.substring(0, 300) + "…";
    }

    public record Evaluation(
            List<Finding> findings,
            long calls,
            long inputTokens,
            long outputTokens) {
    }
}

