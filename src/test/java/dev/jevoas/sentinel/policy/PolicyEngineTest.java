package dev.jevoas.sentinel.policy;

import dev.jevoas.sentinel.jev.DecisionClient;
import dev.jevoas.sentinel.jev.SemanticDecision;
import dev.jevoas.sentinel.openapi.OpenApiDiffer;
import dev.jevoas.sentinel.openapi.OperationChange;
import dev.jevoas.sentinel.openapi.Severity;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PolicyEngineTest {
    @Test
    void advisoryModeRequestsReviewForSemanticBreak() throws Exception {
        DecisionClient client = mock(DecisionClient.class);
        when(client.evaluate(anyMap())).thenReturn(breakingDecision());
        PolicyEngine engine = new PolicyEngine(
                new OpenApiDiffer(), client, PolicyMode.ADVISORY, 0.65, 0.90, "head.yaml");

        PolicyEngine.Evaluation evaluation = engine.evaluate(List.of(semanticChange()));

        assertEquals(Severity.REVIEW, evaluation.findings().get(0).severity());
        assertEquals("semantic-contract-review", evaluation.findings().get(0).ruleId());
    }

    @Test
    void enforceModeBlocksOnlyDoubleConfirmedSemanticBreak() throws Exception {
        DecisionClient client = mock(DecisionClient.class);
        when(client.evaluate(anyMap())).thenReturn(breakingDecision());
        PolicyEngine engine = new PolicyEngine(
                new OpenApiDiffer(), client, PolicyMode.ENFORCE, 0.65, 0.90, "head.yaml");

        PolicyEngine.Evaluation evaluation = engine.evaluate(List.of(semanticChange()));

        assertEquals(Severity.BLOCK, evaluation.findings().get(0).severity());
        assertEquals("semantic-breaking-change", evaluation.findings().get(0).ruleId());
    }

    private SemanticDecision breakingDecision() {
        return new SemanticDecision(
                "jev-1.13.0",
                "breaking",
                Map.of("breaking", 0.96, "docs_only", 0.01, "unclear", 0.03),
                0.94,
                "default_behavior",
                Map.of("default_behavior", 0.93, "other", 0.07),
                0.90,
                0.04,
                2.8,
                Map.of("0", 0.01, "1", 0.02, "2", 0.13, "3", 0.84),
                0.87,
                410,
                0);
    }

    private OperationChange semanticChange() {
        return new OperationChange(
                "GET /orders",
                Map.of("description", "Omitting status returns all orders."),
                Map.of("description", "Omitting status returns active orders."),
                List.of(),
                true,
                false,
                false);
    }
}

