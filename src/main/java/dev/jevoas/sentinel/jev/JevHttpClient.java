package dev.jevoas.sentinel.jev;

import dev.jevoas.sentinel.json.Json;
import dev.jevoas.sentinel.openapi.OpenApiSpecLoader;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

public final class JevHttpClient implements DecisionClient {
    private static final int MAX_ATTEMPTS = 4;
    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(30);

    private final HttpClient httpClient;
    private final URI endpoint;
    private final String apiKey;
    private final String model;

    public JevHttpClient(URI endpoint, String apiKey, String model) {
        this(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build(), endpoint, apiKey, model);
    }

    JevHttpClient(HttpClient httpClient, URI endpoint, String apiKey, String model) {
        this.httpClient = Objects.requireNonNull(httpClient);
        this.endpoint = Objects.requireNonNull(endpoint);
        this.apiKey = requireNonBlank(apiKey, "API key");
        this.model = requireNonBlank(model, "model");
    }

    @Override
    public SemanticDecision evaluate(Map<String, Object> state) throws IOException, InterruptedException {
        LinkedHashMap<String, Object> requestBody = new LinkedHashMap<>();
        requestBody.put("state", state);
        requestBody.put("model", model);
        requestBody.put("questions", JevQuestions.questions());
        String payload = Json.write(requestBody);

        for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
            HttpRequest request = HttpRequest.newBuilder(endpoint)
                    .timeout(REQUEST_TIMEOUT)
                    .header("Authorization", "Bearer " + apiKey)
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(payload))
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            int status = response.statusCode();
            if (status >= 200 && status < 300) {
                return parseResponse(response.body());
            }
            if (attempt < MAX_ATTEMPTS && retryable(status)) {
                long delayMillis = retryDelayMillis(response, attempt);
                System.err.printf("JEV request returned HTTP %d; retrying in %d ms%n", status, delayMillis);
                Thread.sleep(delayMillis);
                continue;
            }
            throw new IOException("JEV request failed with HTTP " + status + ": " + safeBody(response.body()));
        }
        throw new IOException("JEV request exhausted retries");
    }

    private SemanticDecision parseResponse(String body) throws IOException {
        try {
            Map<String, Object> root = OpenApiSpecLoader.stringMap(Json.parse(body), "JEV response");
            Map<String, Object> answers = OpenApiSpecLoader.stringMap(root.get("answers"), "JEV answers");
            Map<String, Object> kind = answer(answers, "change_kind", "choice");
            Map<String, Object> dimension = answer(answers, "affected_dimension", "choice");
            Map<String, Object> preserved = answer(answers, "old_promise_preserved", "noul");
            Map<String, Object> burden = answer(answers, "migration_burden", "score");
            Map<String, Object> usage = OpenApiSpecLoader.stringMap(root.getOrDefault("usage", Map.of()), "usage");

            return new SemanticDecision(
                    Objects.toString(root.get("model"), model),
                    requiredString(kind, "choice"),
                    probabilities(kind),
                    requiredDouble(kind, "confidence"),
                    requiredString(dimension, "choice"),
                    probabilities(dimension),
                    requiredDouble(dimension, "confidence"),
                    requiredDouble(preserved, "noul"),
                    requiredDouble(burden, "score"),
                    probabilities(burden),
                    requiredDouble(burden, "confidence"),
                    optionalLong(usage.get("input_tokens")),
                    optionalLong(usage.get("output_tokens")));
        } catch (IllegalArgumentException | ClassCastException exception) {
            throw new IOException("Malformed JEV response: " + exception.getMessage(), exception);
        }
    }

    private Map<String, Object> answer(Map<String, Object> answers, String id, String expectedType) {
        Map<String, Object> answer = OpenApiSpecLoader.stringMap(answers.get(id), "answer " + id);
        String actualType = requiredString(answer, "type");
        if (!expectedType.equals(actualType)) {
            throw new IllegalArgumentException("Answer " + id + " has type " + actualType + ", expected " + expectedType);
        }
        return answer;
    }

    private Map<String, Double> probabilities(Map<String, Object> answer) {
        Map<String, Object> raw = OpenApiSpecLoader.stringMap(answer.get("probabilities"), "probabilities");
        LinkedHashMap<String, Double> result = new LinkedHashMap<>();
        raw.forEach((key, value) -> result.put(key, number(value, "probability " + key).doubleValue()));
        return Map.copyOf(result);
    }

    private String requiredString(Map<String, Object> map, String key) {
        Object value = map.get(key);
        if (!(value instanceof String string) || string.isBlank()) {
            throw new IllegalArgumentException("Missing string field: " + key);
        }
        return string;
    }

    private double requiredDouble(Map<String, Object> map, String key) {
        return number(map.get(key), key).doubleValue();
    }

    private Number number(Object value, String field) {
        if (!(value instanceof Number number)) {
            throw new IllegalArgumentException("Missing numeric field: " + field);
        }
        return number;
    }

    private long optionalLong(Object value) {
        return value instanceof Number number ? number.longValue() : 0L;
    }

    private boolean retryable(int status) {
        return status == 429 || status == 529 || status >= 500;
    }

    private long retryDelayMillis(HttpResponse<String> response, int attempt) {
        String retryAfter = response.headers().firstValue("retry-after").orElse("");
        try {
            long seconds = Long.parseLong(retryAfter);
            return Math.min(seconds * 1_000L, 10_000L);
        } catch (NumberFormatException ignored) {
            return Math.min(500L * (1L << (attempt - 1)), 4_000L);
        }
    }

    private String safeBody(String body) {
        String normalized = body == null ? "" : body.replaceAll("[\\r\\n]+", " ").strip();
        return normalized.length() <= 500 ? normalized : normalized.substring(0, 500) + "…";
    }

    private static String requireNonBlank(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " cannot be blank");
        }
        return value;
    }
}

