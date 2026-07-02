#!/usr/bin/env bash
# Wire Meteor MCP into Cursor (user-level config).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MCP="${ROOT}/.venv/bin/meteor-mcp"
CURSOR_DIR="${HOME}/.cursor"
CONFIG="${CURSOR_DIR}/mcp.json"

if [[ ! -x "$MCP" ]]; then
  echo "Installing Meteor venv..."
  (cd "$ROOT" && pip install -e . >/dev/null)
fi

mkdir -p "$CURSOR_DIR"

if [[ -f "$CONFIG" ]]; then
  echo "Existing $CONFIG — add meteor manually or merge:"
  echo '  "meteor": { "command": "'"$MCP"'" }'
else
  cat >"$CONFIG" <<EOF
{
  "mcpServers": {
    "meteor": {
      "command": "$MCP",
      "env": { "METEOR_LOG_LEVEL": "WARNING" }
    }
  }
}
EOF
  echo "Wrote $CONFIG"
fi

echo "Reload Cursor (Developer: Reload Window), then enable meteor in MCP settings."
echo "Smoke test: ask the agent to call arsenal__detect via meteor MCP."
