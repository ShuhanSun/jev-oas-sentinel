package dev.jevoas.sentinel.report;

import dev.jevoas.sentinel.openapi.Severity;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public record Report(
        String toolVersion,
        Instant generatedAt,
        String base,
        String head,
        String mode,
        String requestedModel,
        List<Finding> findings,
        Map<String, Object> metrics) {

    public long count(Severity severity) {
        return findings.stream().filter(finding -> finding.severity() == severity).count();
    }

    public boolean hasBlocks() {
        return count(Severity.BLOCK) > 0;
    }

    public boolean hasReviews() {
        return count(Severity.REVIEW) > 0;
    }
}

