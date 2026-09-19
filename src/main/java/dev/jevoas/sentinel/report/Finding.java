package dev.jevoas.sentinel.report;

import dev.jevoas.sentinel.openapi.Severity;

import java.util.Map;

public record Finding(
        String ruleId,
        Severity severity,
        String operation,
        String message,
        String source,
        Map<String, Object> evidence) {
}

