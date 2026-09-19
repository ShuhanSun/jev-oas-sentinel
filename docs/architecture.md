# Architecture

```text
base/head OpenAPI
        |
        v
dependency-free JSON/YAML loader
        |
        v
deterministic operation diff ------> definite structural findings
        |
        v
minimal changed semantic fragments
        |
        v
one Jev request per changed operation
        |
        v
typed answers + distributions
        |
        v
deterministic policy engine
        |
        +------> JSON / Markdown / SARIF
```

## Boundaries

The loader and differ answer questions that code can answer exactly. Jev receives only judgments that require interpreting natural-language contract text. The policy engine, not the model, owns thresholds, exit codes, and side effects.

The implementation intentionally avoids asking Jev for explanations. Report messages are fixed templates backed by operation paths and typed results, so generated prose cannot become an enforcement input.

## YAML support

The internal YAML reader supports mappings, sequences, quoted and plain scalars, inline JSON-style collections, and literal/folded block strings. It rejects tabs, anchors, aliases, merge keys, and custom tags. A later adapter can integrate a fully compliant parser after dependency approval without changing the diff or policy interfaces.

## Extension points

- `DecisionClient` protocol: alternate TypeSafe transports or recorded responses.
- `report.render`: additional CI formats.
- `OpenApiDiffer`: deeper schema compatibility checks or an `oasdiff` JSON adapter.
- `PolicyEngine`: organization-specific risk policies and calibrated thresholds.
