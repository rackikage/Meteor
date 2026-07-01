#!/usr/bin/env bash
# Install Meteor as a real Linux desktop app for the current user.
# Registers Meteor.desktop under ~/.local/share/applications, installs the
# icon into the hicolor theme, and refreshes desktop + icon caches.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPS_DIR="$HOME/.local/share/applications"
ICONS_ROOT="$HOME/.local/share/icons/hicolor"

mkdir -p "$APPS_DIR"
mkdir -p "$ICONS_ROOT/64x64/apps" "$ICONS_ROOT/256x256/apps" "$ICONS_ROOT/1024x1024/apps"

# Install icons under a stable name so the .desktop file can refer to it
# without an absolute path.
install -m 0644 "$REPO_ROOT/assets/meteor_icon_64.png"   "$ICONS_ROOT/64x64/apps/meteor.png"
install -m 0644 "$REPO_ROOT/assets/meteor_icon_256.png"  "$ICONS_ROOT/256x256/apps/meteor.png"
install -m 0644 "$REPO_ROOT/assets/meteor_icon_1024.png" "$ICONS_ROOT/1024x1024/apps/meteor.png"

DESKTOP="$APPS_DIR/meteor.desktop"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Meteor
GenericName=Local AI Runtime
Comment=Local-first agentic AI — full shell, filesystem, nmap, pentest
Exec=$REPO_ROOT/Meteor
Icon=meteor
Path=$REPO_ROOT
Terminal=false
StartupNotify=true
Categories=Science;Network;Development;Utility;
Keywords=ai;llm;ollama;agent;pentest;chat;
EOF
chmod 0644 "$DESKTOP"

# Refresh caches when the tools are present. Both are best-effort.
command -v update-desktop-database >/dev/null 2>&1 && \
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
  gtk-update-icon-cache -f -t "$ICONS_ROOT" >/dev/null 2>&1 || true

echo "Meteor installed:"
echo "  Desktop entry: $DESKTOP"
echo "  Icon:          $ICONS_ROOT/{64,256,1024}/apps/meteor.png"
echo "  Launcher:      $REPO_ROOT/Meteor"
echo
echo "Search 'Meteor' in your app launcher, or run: $REPO_ROOT/Meteor"
