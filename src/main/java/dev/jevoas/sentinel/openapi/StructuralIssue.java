package dev.jevoas.sentinel.openapi;

public record StructuralIssue(
        String ruleId,
        Severity severity,
        String operation,
        String message) {
}

