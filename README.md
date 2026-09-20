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

- [`uv`](https://docs.astral.sh/uv/) for the recommended installation and development workflow
- Python 3.9+ when running without `uv`
- A TypeSafe API key for live semantic evaluation

The CLI has no third-party runtime dependencies. Tool installers keep it isolated from system and project Python environments.

## Install

Install the current checkout as a managed, editable command:

```bash
uv tool install --editable .
jev-oas-sentinel --version
```

On a Mac or corporate network that relies on certificates from the operating-system trust store, add `--system-certs` to the install command.

After the package is published to PyPI, users can run it once without installing it:

```bash
uvx jev-oas-sentinel --version
```

Or install it persistently with either supported tool:

```bash
uv tool install jev-oas-sentinel
# or
pipx install jev-oas-sentinel
```

Managed installs can be upgraded or removed cleanly with `uv tool upgrade jev-oas-sentinel` and `uv tool uninstall jev-oas-sentinel`.

`./jev-oas-sentinel` remains available as a no-install fallback when working directly in a source checkout.

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

To inspect the exact JEV input and output, opt in to a sanitized trace:

```bash
# Show the trace on stderr while keeping the report on stdout.
jev-oas-sentinel compare \
  --base examples/base-openapi.yaml \
  --head examples/head-openapi.yaml \
  --show-jev-io \
  --format markdown

# Or write the trace as JSON.
jev-oas-sentinel compare \
  --base examples/base-openapi.yaml \
  --head examples/head-openapi.yaml \
  --jev-io-output reports/jev-io.json \
  --format markdown
```

The trace never includes the `Authorization` header or API key. It does include
the contract fragments sent to JEV, so treat trace files as potentially
sensitive and do not publish them unintentionally.

On Python 3.10 and newer, HTTPS verification uses the operating system's native
certificate store, including enterprise CAs installed in macOS Keychain or the
Windows certificate store. For Python 3.9 or a private CA bundle, use
`--ca-bundle PATH`, `JEV_CA_BUNDLE`, or the standard `SSL_CERT_FILE` environment
variable. TLS verification is never disabled.

```bash
jev-oas-sentinel compare \
  --base examples/base-openapi.yaml \
  --head examples/head-openapi.yaml \
  --ca-bundle /path/to/company-ca.pem \
  --format markdown
```

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
- uses: ShuhanSun/jev-oas-sentinel@v0.3.0
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

## Development

```bash
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run jev-oas-sentinel --version
uv build --no-sources
```

CI runs the tests on Python 3.9, 3.11, and 3.13 and validates both distribution artifacts. See [docs/releasing.md](docs/releasing.md) for the trusted-publishing release process.
