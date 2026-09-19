package dev.jevoas.sentinel.cli;

import dev.jevoas.sentinel.policy.PolicyMode;

import java.net.URI;
import java.nio.file.Path;
import java.util.Locale;

public record CliOptions(
        Path base,
        Path head,
        String format,
        Path output,
        PolicyMode mode,
        boolean noJev,
        boolean failOnReview,
        String model,
        URI endpoint,
        Path apiKeyFile,
        double reviewThreshold,
        double blockThreshold) {

    public static CliOptions parse(String[] args) {
        if (args.length == 0 || isHelp(args[0])) {
            throw new HelpRequested();
        }
        if (!"compare".equals(args[0])) {
            throw new IllegalArgumentException("Expected command 'compare'");
        }
        Path base = null;
        Path head = null;
        String format = "json";
        Path output = null;
        PolicyMode mode = PolicyMode.ADVISORY;
        boolean noJev = false;
        boolean failOnReview = false;
        String model = "jev-1.13.0";
        URI endpoint = URI.create("https://api.typesafe.ai/v1/systemone");
        Path apiKeyFile = null;
        double reviewThreshold = 0.65;
        double blockThreshold = 0.90;

        for (int index = 1; index < args.length; index++) {
            String argument = args[index];
            switch (argument) {
                case "--base" -> base = Path.of(value(args, ++index, argument));
                case "--head" -> head = Path.of(value(args, ++index, argument));
                case "--format" -> format = value(args, ++index, argument).toLowerCase(Locale.ROOT);
                case "--output" -> output = Path.of(value(args, ++index, argument));
                case "--mode" -> mode = parseMode(value(args, ++index, argument));
                case "--model" -> model = value(args, ++index, argument);
                case "--endpoint" -> endpoint = URI.create(value(args, ++index, argument));
                case "--api-key-file" -> apiKeyFile = Path.of(value(args, ++index, argument));
                case "--review-threshold" -> reviewThreshold = probability(value(args, ++index, argument), argument);
                case "--block-threshold" -> blockThreshold = probability(value(args, ++index, argument), argument);
                case "--no-jev" -> noJev = true;
                case "--fail-on-review" -> failOnReview = true;
                case "--help", "-h" -> throw new HelpRequested();
                default -> throw new IllegalArgumentException("Unknown argument: " + argument);
            }
        }
        if (base == null || head == null) {
            throw new IllegalArgumentException("Both --base and --head are required");
        }
        if (!format.matches("json|markdown|md|sarif")) {
            throw new IllegalArgumentException("--format must be json, markdown, or sarif");
        }
        if (reviewThreshold > blockThreshold) {
            throw new IllegalArgumentException("--review-threshold cannot exceed --block-threshold");
        }
        return new CliOptions(
                base, head, format, output, mode, noJev, failOnReview, model, endpoint, apiKeyFile,
                reviewThreshold, blockThreshold);
    }

    public static String help() {
        return """
                jev-oas-sentinel 0.1.0

                Usage:
                  jev-oas-sentinel compare --base FILE --head FILE [options]

                Options:
                  --format json|markdown|sarif   Output format (default: json)
                  --output FILE                  Write output to a file
                  --mode advisory|enforce        Semantic policy mode (default: advisory)
                  --no-jev                       Run deterministic checks only
                  --fail-on-review               Exit 1 when review findings exist
                  --model MODEL                  JEV model (default: jev-1.13.0)
                  --endpoint URL                 TypeSafe endpoint
                  --api-key-file FILE            Read the API key from a file
                  --review-threshold NUMBER      Review confidence floor (default: 0.65)
                  --block-threshold NUMBER       Enforce threshold (default: 0.90)
                  -h, --help                     Show this help

                API key lookup order:
                  --api-key-file, then TYPESAFE_API_KEY
                """;
    }

    private static boolean isHelp(String argument) {
        return "--help".equals(argument) || "-h".equals(argument) || "help".equals(argument);
    }

    private static String value(String[] args, int index, String option) {
        if (index >= args.length) {
            throw new IllegalArgumentException("Missing value for " + option);
        }
        return args[index];
    }

    private static PolicyMode parseMode(String value) {
        return switch (value.toLowerCase(Locale.ROOT)) {
            case "advisory" -> PolicyMode.ADVISORY;
            case "enforce" -> PolicyMode.ENFORCE;
            default -> throw new IllegalArgumentException("--mode must be advisory or enforce");
        };
    }

    private static double probability(String value, String option) {
        try {
            double parsed = Double.parseDouble(value);
            if (parsed < 0.0 || parsed > 1.0) {
                throw new IllegalArgumentException(option + " must be between 0 and 1");
            }
            return parsed;
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException(option + " must be a number between 0 and 1");
        }
    }

    public static final class HelpRequested extends RuntimeException {
    }
}

