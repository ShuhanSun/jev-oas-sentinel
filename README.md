# jev-oas-sentinel

Catch consumer-visible API changes hiding in “documentation-only” OpenAPI edits.

`jev-oas-sentinel` compares two OpenAPI documents in two layers:

1. deterministic checks find definite structural compatibility problems;
2. TypeSafe Jev evaluates bounded semantic questions about changed descriptions, examples, defaults, retry behavior, ordering, pagination, authorization, and error semantics.

JEV never writes a review or changes a specification. It returns typed decisions and probabilities; deterministic Python code decides whether to pass, request review, or block.

## Status

This is an MVP. It supports OpenAPI JSON and the common YAML subset used by the included fixtures. YAML anchors, custom tags, and merge keys are rejected rather than interpreted incorrectly. Advisory mode is the default.

Local `$ref` and remote `$ref` targets are not dereferenced in this release. A changed reference is routed to structural review rather than silently treated as compatible.

## Requirements

- Python 3.9+
- A TypeSafe API key for live semantic evaluation

The CLI has no third-party runtime dependencies. It runs directly from a checkout or can be installed with `pipx`/`pip`.

## Install and test

```bash
python3 -m pip install .
python3 -m unittest discover -s tests -v
```

For development without installing, prefix commands with `PYTHONPATH=src python3 -m jev_oas_sentinel`.

## Quick start

Run deterministic checks only:

```bash
jev-oas-sentinel compare \
  --base examples/base-openapi.yaml \
  --head examples/head-openapi.yaml \
  --no-jev \
  --format markdown
```

Run a live Jev evaluation:

```bash
export TYPESAFE_API_KEY="..."

jev-oas-sentinel compare \
  --base examples/base-openapi.yaml \
  --head examples/head-openapi.yaml \
  --format markdown
```

The client also accepts `--api-key-file PATH`. Never commit that file.

Write SARIF for GitHub code scanning:

```bash
jev-oas-sentinel compare \
  --base openapi-base.yaml \
  --head src/main/resources/openapi.yaml \
  --format sarif \
  --output reports/jev-oas-sentinel.sarif
```

## GitHub Action

The repository includes a composite action. A complete pull-request example is available at [`examples/github-workflow.yaml`](examples/github-workflow.yaml).

```yaml
- uses: your-org/jev-oas-sentinel@v0
  with:
    base: /tmp/openapi-base.yaml
    head: src/main/resources/openapi.yaml
    api-key: ${{ secrets.TYPESAFE_API_KEY }}
    format: sarif
    output: reports/jev-oas-sentinel.sarif
```

## Policy modes

- `--mode advisory` (default): definite structural breaks block; semantic risks request review.
- `--mode enforce`: a semantic break blocks only when both the `breaking` probability and promise-violation probability cross conservative thresholds.
- `--fail-on-review`: return a non-zero exit code for review findings as well as blocks.

Thresholds are configurable:

```bash
--review-threshold 0.65 --block-threshold 0.90
```

Do not enable enforcement until the questions and thresholds have been evaluated on representative changes from your own APIs.

## What is checked deterministically

- removed operations;
- removed parameters;
- new required parameters;
- optional parameters becoming required;
- required request bodies being introduced;
- removed response status codes;
- security requirement changes;
- other non-documentation structural changes, conservatively routed to review.

## What Jev evaluates

Each changed operation receives one request containing four independent questions:

- change kind: documentation-only, additive, behavioral, breaking, or unclear;
- affected dimension: defaults, response meaning, ordering/pagination, retry/idempotency, authorization, deprecation, error semantics, or another dimension;
- whether every old consumer-visible promise remains preserved;
- ordered migration burden.

The report retains the selected values, full probability distributions, confidence values, resolved model, token usage, and deterministic source location.

## Exit codes

- `0`: no blocking finding (and no review finding when `--fail-on-review` is used);
- `1`: policy blocked the change;
- `2`: invalid input or execution failure.

## Security model

- API keys are read from `TYPESAFE_API_KEY` or an explicit key file and are never included in reports.
- Only changed operation fragments are sent to Jev.
- Structural compatibility rules remain deterministic.
- API errors fail closed in enforcement mode and request review in advisory mode.
- OpenAPI descriptions are untrusted input. The tool does not execute examples, extensions, URLs, or code found in a specification.

See [docs/architecture.md](docs/architecture.md) for design boundaries and extension points.
