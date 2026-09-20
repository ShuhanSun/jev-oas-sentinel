# Releasing

Releases use PyPI Trusted Publishing. No long-lived PyPI API token is stored in GitHub.

## One-time PyPI setup

Create the `jev-oas-sentinel` PyPI project or a pending trusted publisher with:

- owner: `ShuhanSun`
- repository: `jev-oas-sentinel`
- workflow: `publish.yml`
- environment: `pypi`

Create a protected GitHub environment named `pypi`. For production releases, require an environment reviewer.

## Release checklist

1. Update the single version source in `src/jev_oas_sentinel/__init__.py`.
2. Run `uv lock`, `uv sync --locked`, and the test suite.
3. Run `uv build --no-sources` and `uvx --from twine==7.0.0 twine check dist/*`.
4. Commit the version and lockfile changes.
5. Create and publish a GitHub release tagged with the same version, for example `v0.6.0`.
6. Approve the protected `pypi` environment deployment if required.

Publishing the GitHub release triggers `.github/workflows/publish.yml`. The workflow rebuilds, tests, validates, and uploads both the wheel and source distribution through OIDC.
