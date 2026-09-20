# Contributing

Thanks for helping JEV OAS Sentinel make API compatibility review more reliable.

## Good contributions

- reproducible OpenAPI changes that expose a compatibility edge case;
- deterministic checks with focused tests;
- semantic benchmark cases grounded in a concrete consumer risk;
- report, SARIF, GitHub Action, and documentation improvements;
- security reports submitted privately as described in [`SECURITY.md`](SECURITY.md).

Please open an issue before starting a large behavioral change. Small bug fixes and documentation improvements can go directly to a pull request.

## Development setup

```bash
git clone https://github.com/ShuhanSun/jev-oas-sentinel.git
cd jev-oas-sentinel
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run python benchmarks/run.py --check
```

Live Jev tests are not required for normal contributions. Unit tests and the routing benchmark run without an API key.

Regenerate the terminal demo from the current CLI output with an ephemeral Pillow dependency:

```bash
uv run --with pillow python scripts/render_demo_gif.py
```

Set `JEV_DEMO_FONT` to a local monospace font path when neither SF Mono nor DejaVu Sans Mono is installed.

## Pull requests

- Keep each pull request focused on one problem.
- Add or update tests for behavioral changes.
- Do not include API keys, private specifications, or unsanitized traces.
- Update the README or architecture documentation when public behavior changes.
- Preserve advisory mode as the safe default.

By submitting a contribution, you agree that it is licensed under Apache-2.0.
