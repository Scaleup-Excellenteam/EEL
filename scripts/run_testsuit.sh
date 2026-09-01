#!/usr/bin/env bash
# Run the full automated test suite, the same way README.md's Setup section
# does: a project-local virtualenv, dependencies from requirements.txt, then
# pytest (config picked up from pytest.ini at the repo root).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi

.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m pytest "$@"
