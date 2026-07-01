#!/usr/bin/env bash
# One installer to bundle Meteor as a real local app on any OS.
# Dispatches to the platform-specific installer under scripts/.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
case "$(uname -s)" in
  Linux*)
    exec "$HERE/scripts/install_linux_app.sh" "$@"
    ;;
  Darwin*)
    exec "$HERE/scripts/install_meteor_app.sh" "$@"
    ;;
  MINGW*|CYGWIN*|MSYS*)
    echo "On Windows, right-click scripts/install_windows_app.ps1 → 'Run with PowerShell'."
    exit 0
    ;;
  *)
    echo "Unsupported OS: $(uname -s)" >&2
    exit 1
    ;;
esac
