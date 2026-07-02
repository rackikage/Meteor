#!/usr/bin/env bash
# Interactive Composio login + optional toolkit link. See docs/composio-setup.md.
set -euo pipefail
COMPOSIO="${COMPOSIO_BIN:-$HOME/.composio/composio}"
if [[ ! -x "$COMPOSIO" ]]; then
  echo "Composio CLI not found at $COMPOSIO" >&2
  exit 1
fi
echo "Opening Composio login (browser)..."
"$COMPOSIO" login
echo ""
"$COMPOSIO" connections list
echo ""
echo "Link a toolkit, e.g.: $COMPOSIO link github"
echo "Search tools:       $COMPOSIO search web search"
