package dev.jevoas.sentinel.cli;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class CliRunnerTest {
    @TempDir
    Path temporaryDirectory;

    @Test
    void noJevModeReturnsReviewWithoutFailingByDefault() throws Exception {
        Path base = write("base.yaml", "Returns all orders.");
        Path head = write("head.yaml", "Returns active orders only.");
        ByteArrayOutputStream stdout = new ByteArrayOutputStream();
        ByteArrayOutputStream stderr = new ByteArrayOutputStream();
        CliRunner runner = new CliRunner(new PrintStream(stdout), new PrintStream(stderr), Map.of());

        int exit = runner.run(new String[]{
                "compare", "--base", base.toString(), "--head", head.toString(), "--no-jev", "--format", "json"});

        assertEquals(0, exit);
        assertTrue(stdout.toString().contains("semantic-evaluation-skipped"));
    }

    @Test
    void failOnReviewReturnsOne() throws Exception {
        Path base = write("base.yaml", "Returns all orders.");
        Path head = write("head.yaml", "Returns active orders only.");
        CliRunner runner = new CliRunner(
                new PrintStream(new ByteArrayOutputStream()),
                new PrintStream(new ByteArrayOutputStream()),
                Map.of());

        int exit = runner.run(new String[]{
                "compare", "--base", base.toString(), "--head", head.toString(), "--no-jev", "--fail-on-review"});

        assertEquals(1, exit);
    }

    private Path write(String name, String description) throws Exception {
        Path file = temporaryDirectory.resolve(name);
        Files.writeString(file, """
                openapi: 3.0.3
                paths:
                  /orders:
                    get:
                      description: %s
                      responses:
                        "200":
                          description: Success
                """.formatted(description));
        return file;
    }
}
