#!/usr/bin/env bash
# Launch the tandc local web UI.
#
# Usage:
#   ./scripts/serve.sh                       # default 127.0.0.1:8765
#   ./scripts/serve.sh --port 9000           # override port
#   ./scripts/serve.sh --host 0.0.0.0        # LAN-accessible
#   ./scripts/serve.sh --reload --debug      # dev mode
#
# Prereqs (one-time):
#   - conda env `tandc` exists with `pip install -e ".[dev]"` done.
#   - ANTHROPIC_API_KEY exported in ~/.zshrc / ~/.zprofile.

set -euo pipefail

CONDA_BIN="/Users/nitin/anaconda3/envs/tandc/bin"

if [[ ! -x "${CONDA_BIN}/tandc" ]]; then
  echo "error: tandc not found at ${CONDA_BIN}/tandc" >&2
  echo "hint:  conda env 'tandc' may not be installed. From the repo root, run:" >&2
  echo "         conda create -n tandc python=3.11 -y" >&2
  echo "         PATH=\"${CONDA_BIN}:\$PATH\" pip install -e \".[dev]\"" >&2
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "error: ANTHROPIC_API_KEY is not set in the environment" >&2
  echo "hint:  add 'export ANTHROPIC_API_KEY=sk-...' to ~/.zshrc and open a new terminal" >&2
  exit 4
fi

PATH="${CONDA_BIN}:${PATH}" exec tandc serve "$@"
