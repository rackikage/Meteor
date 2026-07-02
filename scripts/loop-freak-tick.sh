#!/usr/bin/env bash
# Loop Freak tick — emit sentinel for Cursor /loop skill (optional).
# Usage: ./scripts/loop-freak-tick.sh [interval_seconds]
# Or arm via: /loop 5m run scripts/loop-freak-tick.sh 300

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INTERVAL="${1:-300}"
PROMPT='Loop Freak tick: call meteor loopfreak__pulse + graph__counts; report graph delta and top exploit__prioritize target.'

while true; do
  sleep "$INTERVAL"
  echo "AGENT_LOOP_TICK_LOOPFREAK $(printf '%s' "{\"prompt\":\"$PROMPT\"}")"
done
