# Architecture

```text
base/head OpenAPI
        |
        v
safe JSON/YAML loader + local $ref resolver
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

## OpenAPI loading

PyYAML's safe loader handles JSON and standards-compliant YAML without
constructing arbitrary Python objects. Anchors and merge keys are supported.
Internal and relative-file `$ref` values are resolved before comparison, with
cycle boundaries preserved as references. Network references are rejected and
are never fetched implicitly. Relative references cannot escape the source
document's directory unless the caller supplies a broader trusted `--ref-root`.

## Extension points

- `DecisionClient` protocol: alternate TypeSafe transports or recorded responses.
- `report.render`: additional CI formats.
- `OpenApiDiffer`: deeper schema compatibility checks or an `oasdiff` JSON adapter.
- `PolicyEngine`: organization-specific risk policies and calibrated thresholds.
