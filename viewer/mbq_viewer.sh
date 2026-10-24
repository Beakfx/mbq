#!/usr/bin/env bash
# MBQ Viewer launcher for Linux — runs straight from this repo checkout.
#
#   viewer/mbq_viewer.sh [image-or-folder]   run (first run builds the venv)
#   viewer/mbq_viewer.sh --install           add 'mbq-viewer' command + app-menu entry
#   viewer/mbq_viewer.sh --uninstall         remove those, and the venv
#
# The venv lives in ~/.local/share/mbq-viewer/venv, outside the repo, so it never
# collides with a Windows .venv on a shared drive. It is rebuilt automatically
# whenever viewer/requirements.txt changes.

set -euo pipefail

SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
VIEWER_DIR="$(dirname "$SCRIPT")"
REPO_DIR="$(dirname "$VIEWER_DIR")"
REQS="$VIEWER_DIR/requirements.txt"

DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_DIR/mbq-viewer"
VENV="$APP_DIR/venv"
STAMP="$VENV/.requirements.sha256"
BIN_LINK="$HOME/.local/bin/mbq-viewer"
DESKTOP_FILE="$DATA_DIR/applications/mbq-viewer.desktop"
ICON_FILE="$DATA_DIR/icons/hicolor/256x256/apps/mbq-viewer.png"

# Don't let a Flame (or other DCC) shell leak its own Python/Qt into ours
unset PYTHONPATH PYTHONHOME QT_PLUGIN_PATH QT_QPA_PLATFORM_PLUGIN_PATH

find_python() {
    local py
    for py in python3.13 python3.12 python3.11 python3; do
        if command -v "$py" >/dev/null 2>&1 &&
           "$py" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
            echo "$py"
            return
        fi
    done
    echo "MBQ Viewer needs Python 3.11+ (Rocky/RHEL: sudo dnf install python3.11)" >&2
    exit 1
}

ensure_venv() {
    local want
    want="$(sha256sum "$REQS" | cut -d' ' -f1)"
    if [[ -x "$VENV/bin/python" && -f "$STAMP" && "$(cat "$STAMP")" == "$want" ]]; then
        return
    fi
    echo "MBQ Viewer: setting up Python environment in $VENV ..."
    rm -rf "$VENV"
    "$(find_python)" -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --disable-pip-version-check -r "$REQS"
    echo "$want" > "$STAMP"
}

install_launcher() {
    ensure_venv
    mkdir -p "$(dirname "$BIN_LINK")" "$(dirname "$DESKTOP_FILE")" "$(dirname "$ICON_FILE")"
    ln -sf "$SCRIPT" "$BIN_LINK"
    cp "$REPO_DIR/assets/mbq_icon.png" "$ICON_FILE"
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=MBQ Viewer
Comment=Browse ComfyUI images and their generation settings
Exec="$SCRIPT" %f
Icon=mbq-viewer
Terminal=false
Categories=Graphics;Viewer;
MimeType=image/png;image/jpeg;image/webp;inode/directory;
StartupWMClass=mbq-viewer
EOF
    update-desktop-database "$(dirname "$DESKTOP_FILE")" 2>/dev/null || true
    gtk-update-icon-cache -q "$DATA_DIR/icons/hicolor" 2>/dev/null || true
    echo "Installed:"
    echo "  command   $BIN_LINK"
    echo "  app menu  $DESKTOP_FILE"
    echo "It runs this checkout ($REPO_DIR), so edits and git pulls take effect on next launch."
}

uninstall_launcher() {
    rm -f "$BIN_LINK" "$DESKTOP_FILE" "$ICON_FILE"
    rm -rf "$APP_DIR"
    update-desktop-database "$(dirname "$DESKTOP_FILE")" 2>/dev/null || true
    echo "Removed the mbq-viewer command, app-menu entry and venv. The repo itself is untouched."
}

case "${1:-}" in
    --install)   install_launcher ;;
    --uninstall) uninstall_launcher ;;
    *)
        ensure_venv
        exec "$VENV/bin/python" "$VIEWER_DIR/mbq_viewer.py" "$@"
        ;;
esac
