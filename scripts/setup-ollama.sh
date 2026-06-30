#!/usr/bin/env bash
# Start Ollama and pull default Meteor models.
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

python3 - <<'PY'
import sys
sys.path.insert(0, ".")
from app.runtime.ollama_launcher import ensure_ollama_running, is_ollama_running

if not ensure_ollama_running():
    sys.exit(1)
print("Ollama is up at http://localhost:11434")
PY

echo "Pulling models (first time may take a while)..."
ollama pull llama3.1:8b
ollama pull llama3.2
echo "Done. Launch Meteor with: python3 run.py"
