# JEV OAS Sentinel — System One Semantic Compatibility for OpenAPI

[![CI](https://github.com/ShuhanSun/jev-oas-sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/ShuhanSun/jev-oas-sentinel/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/jev-oas-sentinel.svg)](https://pypi.org/project/jev-oas-sentinel/)
[![Python](https://img.shields.io/pypi/pyversions/jev-oas-sentinel.svg)](https://pypi.org/project/jev-oas-sentinel/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Catch behavioral breaking changes hidden in OpenAPI prose—changes that structural schema diff tools cannot see.

`jev-oas-sentinel` compares two OpenAPI documents in two layers:

1. deterministic checks find definite structural compatibility problems;
2. TypeSafe Jev evaluates bounded semantic questions about changed descriptions, examples, defaults, retry behavior, ordering, pagination, authorization, and error semantics.

JEV never writes a review or changes a specification. It returns typed decisions and probabilities; deterministic Python code decides whether to pass, request review, or block.

## Try it in 30 seconds

No API key or network call to JEV is needed for this preview:

```bash
git clone https://github.com/ShuhanSun/jev-oas-sentinel.git
cd jev-oas-sentinel
uvx jev-oas-sentinel compare \
  --base examples/base-openapi.yaml \
  --head examples/head-openapi.yaml \
  --dry-run \
  --format markdown
```

The example changes an operation's consumer-facing prose. The structural schema remains compatible, but Sentinel identifies the operation that needs semantic review:

```text
| Block | Review | Notice |
|---:|---:|---:|
|0|1|0|

| Severity | Operation | Rule | Finding |
|---|---|---|---|
| review | GET /orders | semantic-evaluation-planned | Contract prose changed and would be sent to JEV |
```

## Status

The current public alpha supports OpenAPI JSON and standards-compliant safe YAML,
including anchors and merge keys. Internal and multi-file local `$ref` targets
are resolved with cycle protection. Remote `$ref` targets are rejected rather
than fetched implicitly. Advisory mode is the default.

Local references are restricted to the specification's directory tree by
default. For repositories that keep shared schemas in a parent directory, set
an explicit trusted root:

```bash
jev-oas-sentinel compare \
  --base api/base/openapi.yaml \
  --head api/head/openapi.yaml \
  --ref-root . \
  --no-jev
```

## Requirements

- [`uv`](https://docs.astral.sh/uv/) for the recommended installation and development workflow
- Python 3.9+ when running without `uv`
- A TypeSafe API key for live semantic evaluation

Runtime dependencies are PyYAML for standards-compliant OpenAPI parsing and,
on Python 3.10+, `truststore` for the operating system's native certificate
store. Tool installers keep the CLI isolated from system and project Python
environments. Python 3.9 uses its configured OpenSSL CA bundle and can be given
a private bundle explicitly.

## Install

Run the published CLI once without installing it:

```bash
uvx jev-oas-sentinel --version
```

Or install it as an isolated command:

```bash
uv tool install jev-oas-sentinel
# or
pipx install jev-oas-sentinel
```

To work on the current checkout, install it in editable mode:

```bash
uv tool install --editable .
jev-oas-sentinel --version
```

On a Mac or corporate network that relies on certificates from the operating-system trust store, add `--system-certs` to the `uv` install command.

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

Preview which operations would require JEV without an API key or network call:

```bash
jev-oas-sentinel compare \
  --base examples/base-openapi.yaml \
  --head examples/head-openapi.yaml \
  --dry-run \
  --format json
```

Bound API usage and transport behavior explicitly in CI:

```bash
--max-jev-calls 20 --timeout 30 --max-retries 3
```

## Project configuration

Put shared policy in `.jev-sentinel.yaml` at the directory where the command
runs. The format is versioned, CLI options override file settings, and
`--config PATH` selects another file. Use `--no-config` for a fully explicit
run.

```yaml
version: 1
mode: advisory
fail_on_review: false
model: jev-1.13.0
review_threshold: 0.65
block_threshold: 0.90
max_jev_calls: 20
timeout: 30
max_retries: 3

suppressions:
  - operation: GET /legacy/*
    rule: semantic-contract-review
    expires: 2099-12-31
    owner: api-platform
    reason: Migration is tracked in API-123
```

Suppressions require an owner, reason, and expiration date. A matching block or
review becomes a notice but remains in JSON, Markdown, and SARIF with its
original severity and suppression metadata. An expired suppression fails the
run so exceptions cannot silently become permanent. Operation and rule values
support shell-style `*`, `?`, and character-set patterns.

For security, repository configuration cannot set the JEV endpoint, API-key
file, CA bundle, local-reference root, report path, or trace path. Those remain
explicit CLI options. See [`examples/jev-sentinel.yaml`](examples/jev-sentinel.yaml)
for a complete example.

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

The versioned trace omits request headers and recursively redacts the configured
API key plus common credential fields from captured data. Trace files are
created with owner-only permissions on POSIX systems. They do include the
contract fragments sent to JEV, so treat them as potentially sensitive and do
not publish them unintentionally.

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
- uses: ShuhanSun/jev-oas-sentinel@v0.6.0
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
- removed request or response media types;
- removed request or response properties;
- request properties becoming required;
- response properties no longer being guaranteed;
- request enum narrowing and response enum expansion;
- incompatible schema type or nullability changes;
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
