package dev.jevoas.sentinel;

import dev.jevoas.sentinel.cli.CliRunner;

public final class Main {
    private Main() {
    }

    public static void main(String[] args) {
        int exitCode = new CliRunner(System.out, System.err, System.getenv()).run(args);
        if (exitCode != 0) {
            System.exit(exitCode);
        }
    }
}

