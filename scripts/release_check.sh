#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pytest -q
python3 -m build
python3 -m twine check dist/*

if python3 -m pip download -d /tmp/mailgoat-check-testpypi \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  mailgoat==1.0.0b1; then
  echo "mailgoat==1.0.0b1 is already available on TestPyPI/PyPI"
else
  echo "mailgoat==1.0.0b1 is not published yet; local package checks passed."
fi
