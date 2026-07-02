#!/usr/bin/env bash
# Resolve Meteor root from plugin install or METEOR_HOME, then exec meteor-mcp.
set -euo pipefail

ROOT="${METEOR_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
MCP="${ROOT}/.venv/bin/meteor-mcp"

if [[ ! -x "$MCP" ]]; then
  echo "meteor-mcp not found at $MCP — run: cd $ROOT && pip install -e ." >&2
  exit 1
fi

exec "$MCP"
