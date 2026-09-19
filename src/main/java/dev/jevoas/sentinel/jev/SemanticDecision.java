package dev.jevoas.sentinel.jev;

import java.util.Map;

public record SemanticDecision(
        String model,
        String changeKind,
        Map<String, Double> changeKindProbabilities,
        double changeKindConfidence,
        String affectedDimension,
        Map<String, Double> affectedDimensionProbabilities,
        double affectedDimensionConfidence,
        double oldPromisePreservedProbability,
        double migrationBurden,
        Map<String, Double> migrationBurdenProbabilities,
        double migrationBurdenConfidence,
        long inputTokens,
        long outputTokens) {

    public double breakingProbability() {
        return changeKindProbabilities.getOrDefault("breaking", 0.0);
    }
}

