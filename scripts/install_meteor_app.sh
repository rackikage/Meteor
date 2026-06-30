#!/bin/bash
# Install a single canonical Meteor.app to ~/Applications and pin to Dock.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$REPO_ROOT/packaging/meteor-app"
DEST="$HOME/Applications/Meteor.app"
LEGACY_DEST="$REPO_ROOT/app/Meteor.app"

if [[ ! -d "$TEMPLATE/Contents" ]]; then
  echo "Missing app template at $TEMPLATE" >&2
  exit 1
fi

python3 "$REPO_ROOT/scripts/build_macos_icon.py"

rm -rf "$DEST" "$LEGACY_DEST"

mkdir -p "$DEST/Contents/MacOS" "$DEST/Contents/Resources"
cp "$TEMPLATE/Contents/Info.plist" "$DEST/Contents/Info.plist"
cp "$TEMPLATE/Contents/MacOS/Meteor" "$DEST/Contents/MacOS/Meteor"
cp "$REPO_ROOT/assets/meteor.icns" "$DEST/Contents/Resources/meteor.icns"

sed -i '' "s|@METEOR_ROOT@|$REPO_ROOT|g" "$DEST/Contents/MacOS/Meteor"
chmod +x "$DEST/Contents/MacOS/Meteor"
touch "$DEST"

if command -v dockutil >/dev/null 2>&1; then
  dockutil --remove "Meteor" --no-restart 2>/dev/null || true
  dockutil --remove "Meteor Orchestrator" --no-restart 2>/dev/null || true
  dockutil --remove "Meteor.app" --no-restart 2>/dev/null || true
  dockutil --remove "$DEST" --no-restart 2>/dev/null || true
  dockutil --add "$DEST" --no-restart
  killall Dock 2>/dev/null || true
else
  echo "Install dockutil for automatic Dock pinning: brew install dockutil" >&2
fi

open -a "$DEST"

echo "Installed and pinned Meteor Orchestrator at $DEST"
