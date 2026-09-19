package dev.jevoas.sentinel.cli;

import dev.jevoas.sentinel.jev.DecisionClient;
import dev.jevoas.sentinel.jev.JevHttpClient;
import dev.jevoas.sentinel.openapi.OpenApiDiffer;
import dev.jevoas.sentinel.openapi.OpenApiSpecLoader;
import dev.jevoas.sentinel.openapi.OperationChange;
import dev.jevoas.sentinel.policy.PolicyEngine;
import dev.jevoas.sentinel.report.Report;
import dev.jevoas.sentinel.report.ReportRenderer;

import java.io.IOException;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class CliRunner {
    public static final String VERSION = "0.1.0";

    private final PrintStream output;
    private final PrintStream error;
    private final Map<String, String> environment;

    public CliRunner(PrintStream output, PrintStream error, Map<String, String> environment) {
        this.output = output;
        this.error = error;
        this.environment = environment;
    }

    public int run(String[] args) {
        try {
            CliOptions options = CliOptions.parse(args);
            return compare(options);
        } catch (CliOptions.HelpRequested ignored) {
            output.print(CliOptions.help());
            return 0;
        } catch (IllegalArgumentException exception) {
            error.println("Error: " + exception.getMessage());
            error.println("Run with --help for usage.");
            return 2;
        } catch (IOException exception) {
            error.println("I/O error: " + safeMessage(exception));
            return 2;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            error.println("Interrupted while evaluating the OpenAPI change.");
            return 2;
        }
    }

    private int compare(CliOptions options) throws IOException, InterruptedException {
        OpenApiSpecLoader loader = new OpenApiSpecLoader();
        Map<String, Object> base = loader.load(options.base());
        Map<String, Object> head = loader.load(options.head());
        OpenApiDiffer differ = new OpenApiDiffer();
        List<OperationChange> changes = differ.compare(base, head);
        DecisionClient client = options.noJev() ? null : liveClient(options);

        long started = System.nanoTime();
        PolicyEngine engine = new PolicyEngine(
                differ,
                client,
                options.mode(),
                options.reviewThreshold(),
                options.blockThreshold(),
                options.head().toString());
        PolicyEngine.Evaluation evaluation = engine.evaluate(changes);
        long elapsedMillis = (System.nanoTime() - started) / 1_000_000L;

        LinkedHashMap<String, Object> metrics = new LinkedHashMap<>();
        metrics.put("changed_operations", changes.size());
        metrics.put("semantic_calls", evaluation.calls());
        metrics.put("input_tokens", evaluation.inputTokens());
        metrics.put("output_tokens", evaluation.outputTokens());
        metrics.put("elapsed_ms", elapsedMillis);

        Report report = new Report(
                VERSION,
                Instant.now(),
                options.base().toString(),
                options.head().toString(),
                options.mode().name().toLowerCase(),
                options.noJev() ? "disabled" : options.model(),
                evaluation.findings(),
                Map.copyOf(metrics));
        String rendered = new ReportRenderer().render(report, options.format());
        writeOutput(options.output(), rendered);

        if (report.hasBlocks() || options.failOnReview() && report.hasReviews()) {
            return 1;
        }
        return 0;
    }

    private DecisionClient liveClient(CliOptions options) throws IOException {
        String apiKey;
        if (options.apiKeyFile() != null) {
            apiKey = Files.readString(options.apiKeyFile()).strip();
        } else {
            apiKey = environment.getOrDefault("TYPESAFE_API_KEY", "").strip();
        }
        if (apiKey.isEmpty()) {
            throw new IllegalArgumentException(
                    "No TypeSafe API key found; set TYPESAFE_API_KEY, use --api-key-file, or pass --no-jev");
        }
        return new JevHttpClient(options.endpoint(), apiKey, options.model());
    }

    private void writeOutput(Path destination, String rendered) throws IOException {
        if (destination == null) {
            output.print(rendered);
            return;
        }
        Path parent = destination.toAbsolutePath().getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        Files.writeString(destination, rendered);
        error.println("Wrote report to " + destination);
    }

    private String safeMessage(IOException exception) {
        String message = exception.getMessage();
        if (message == null || message.isBlank()) {
            return exception.getClass().getSimpleName();
        }
        return message.replaceAll("[\\r\\n]+", " ");
    }
}

