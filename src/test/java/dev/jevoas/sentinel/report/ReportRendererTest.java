package dev.jevoas.sentinel.report;

import dev.jevoas.sentinel.json.Json;
import dev.jevoas.sentinel.openapi.Severity;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ReportRendererTest {
    @Test
    void rendersParseableSarif() {
        Report report = new Report(
                "0.1.0",
                Instant.parse("2026-09-19T00:00:00Z"),
                "base.yaml",
                "head.yaml",
                "advisory",
                "jev-1.13.0",
                List.of(new Finding(
                        "semantic-contract-review",
                        Severity.REVIEW,
                        "GET /orders",
                        "Review the semantic change",
                        "head.yaml",
                        Map.of("confidence", 0.7))),
                Map.of("semantic_calls", 1));

        String rendered = new ReportRenderer().render(report, "sarif");
        Map<?, ?> root = (Map<?, ?>) Json.parse(rendered);

        assertEquals("2.1.0", root.get("version"));
        assertTrue(root.containsKey("runs"));
    }
}

