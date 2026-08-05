#!/usr/bin/env bash
set -euo pipefail
echo "Dev setup: creating virtual environment and installing dependencies..."

# Python version check (recommended 3.10+)
REQUIRED_PY="3.10"
PYBIN="$(which python3 || true)"
if [ -z "$PYBIN" ]; then
  echo "python3 not found; please install Python $REQUIRED_PY or use Docker (see README)."
  exit 1
fi

PYVER="$($PYBIN -c 'import sys; print("{}.{}".format(sys.version_info.major, sys.version_info.minor))')"
echo "Detected Python $PYVER at $PYBIN"
# venv
if [ ! -d ".venv" ]; then
  $PYBIN -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
else
  echo "requirements.txt not found — continuing without installing deps"
fi

echo "Environment created. Run 'source .venv/bin/activate' to enter."

echo "Run 'make test' or 'python -m pytest' to run tests."

echo
echo "Pythonista / iOS notes:"
echo " - Pythonista runs on iOS and has a different filesystem; to run tests on-device, see docs/pythonista-notes.md"

# Make the script executable: run 'chmod +x dev-setup.sh' after checkout
