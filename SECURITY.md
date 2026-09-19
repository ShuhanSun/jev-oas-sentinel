# Security policy

## Reporting a vulnerability

Do not open a public issue for API-key exposure, unsafe parsing, report injection, or policy-bypass vulnerabilities. Contact the repository maintainers privately through the security-advisory feature after the repository is published.

## API keys

Use `TYPESAFE_API_KEY` or `--api-key-file`. The repository ignores `jev-api.key` and `.env`. Reports never include the API key.

If a key was ever committed, removing the file from the latest commit is not sufficient. Revoke the key, issue a replacement, and remove the secret from Git history before publishing.

## Trust boundaries

OpenAPI documents and all description/example text are untrusted. The parser does not execute tags, anchors, links, examples, extensions, or embedded code. Jev findings supplement deterministic checks and should begin in advisory mode on a new dataset.

