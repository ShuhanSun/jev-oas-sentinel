#!/bin/sh
set -eu

if ! command -v mvn >/dev/null 2>&1; then
  echo "Maven is required but was not found on PATH." >&2
  exit 127
fi

exec mvn "$@"

