#!/bin/sh
# Install Gemlin, a tiny AI creature that lives on your desktop: https://gemlin.dev
#
#   curl -LsSf https://gemlin.dev/install.sh | sh
#
# What this does, step by step:
#   1. Gets uv (https://docs.astral.sh/uv), a tool that installs Python apps, if you don't have it.
#   2. Uses uv to install Gemlin with its own copy of Python, so nothing else on your computer changes.
#   3. Makes the `gemlin` command work in new terminals.
#   4. Adds the Gemlin app (Applications, Launchpad and Spotlight on a Mac; your app launcher on Linux).
#   5. Wakes Gemlin up, and asks whether it should wake up whenever you log in.
# Run it again any time to update Gemlin. To remove it: gemlin uninstall
set -eu

SOURCE="${GEMLIN_SOURCE:-https://github.com/alexinslc/gemlin/archive/refs/heads/main.zip}"
PYTHON_VERSION="3.13"

say() { printf '%s\n' "$*"; }

say ""
say "  Installing Gemlin..."
say ""

if command -v uv >/dev/null 2>&1; then
    UV="$(command -v uv)"
elif [ -x "$HOME/.local/bin/uv" ]; then
    UV="$HOME/.local/bin/uv"
else
    say "  Getting uv (it installs Python apps)..."
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null
    UV="$HOME/.local/bin/uv"
fi

say "  Installing Gemlin and its own Python (this can take a minute the first time)..."
"$UV" tool install --quiet --force --python "$PYTHON_VERSION" "gemlin @ $SOURCE"
"$UV" tool update-shell >/dev/null 2>&1 || true

BIN="$("$UV" tool dir --bin)"
GEMLIN="$BIN/gemlin"
say "  ✓ Installed $("$GEMLIN" --version)"
if app="$("$GEMLIN" app 2>&1)"; then say "  ✓ $app"; else say "  ! $app"; fi

if [ -n "${GEMLIN_NO_START:-}" ]; then
    exit 0
fi

# Gemlin wakes up on its own at login, if you'd like. (The script itself comes through the pipe,
# so the question is asked on your terminal directly.)
answer="y"
if [ -r /dev/tty ]; then
    printf '\n  Wake Gemlin up whenever you log in? [Y/n] '
    read -r answer </dev/tty || answer="y"
fi
case "$answer" in
    [nN]*) ;;
    *) "$GEMLIN" autostart on ;;
esac

say ""
"$GEMLIN" start
say ""
say "  You can close this terminal. Gemlin lives in your menu bar (or system tray) and on your desktop:"
say "  open the Gemlin app to wake it, and right-click Gemlin for everything else."
say "  Make it yours: click \"Customize me\" under its chat box, or visit https://gemlin.dev/create"
say ""
