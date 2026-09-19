package dev.jevoas.sentinel.openapi;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class OpenApiDifferTest {
    private final OpenApiDiffer differ = new OpenApiDiffer();

    @Test
    void detectsDescriptionOnlySemanticChange() {
        Map<String, Object> base = document(operation("Returns all orders."));
        Map<String, Object> head = document(operation("Returns active orders only."));

        List<OperationChange> changes = differ.compare(base, head);

        assertEquals(1, changes.size());
        assertTrue(changes.get(0).semanticChanged());
        assertTrue(changes.get(0).structuralIssues().isEmpty());
    }

    @Test
    void blocksNewRequiredParameter() {
        Map<String, Object> baseOperation = operation("Returns all orders.");
        Map<String, Object> headOperation = operation("Returns all orders.");
        headOperation.put("parameters", List.of(Map.of(
                "name", "tenant",
                "in", "query",
                "required", true,
                "schema", Map.of("type", "string"))));

        List<OperationChange> changes = differ.compare(document(baseOperation), document(headOperation));

        assertTrue(changes.get(0).structuralIssues().stream()
                .anyMatch(issue -> issue.ruleId().equals("required-parameter-added")
                        && issue.severity() == Severity.BLOCK));
        assertFalse(changes.get(0).semanticChanged());
    }

    @Test
    void appliesPathLevelParametersToOperations() {
        Map<String, Object> base = Map.of(
                "openapi", "3.0.3",
                "paths", Map.of("/orders", Map.of(
                        "parameters", List.of(Map.of(
                                "name", "tenant", "in", "query", "required", false,
                                "schema", Map.of("type", "string"))),
                        "get", operation("Returns all orders."))));
        Map<String, Object> head = document(operation("Returns all orders."));

        List<OperationChange> changes = differ.compare(base, head);

        assertTrue(changes.get(0).structuralIssues().stream()
                .anyMatch(issue -> issue.ruleId().equals("parameter-removed")));
    }

    private Map<String, Object> operation(String description) {
        return new java.util.LinkedHashMap<>(Map.of(
                "operationId", "listOrders",
                "description", description,
                "responses", Map.of("200", Map.of("description", "Success"))));
    }

    private Map<String, Object> document(Map<String, Object> operation) {
        return Map.of(
                "openapi", "3.0.3",
                "paths", Map.of("/orders", Map.of("get", operation)));
    }
}
