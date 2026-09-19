package dev.jevoas.sentinel.openapi;

import java.util.List;
import java.util.Map;

public record OperationChange(
        String operation,
        Map<String, Object> oldOperation,
        Map<String, Object> newOperation,
        List<StructuralIssue> structuralIssues,
        boolean semanticChanged,
        boolean added,
        boolean removed) {
}

