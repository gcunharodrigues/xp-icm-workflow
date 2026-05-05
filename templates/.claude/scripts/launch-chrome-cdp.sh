#!/usr/bin/env bash
# ICM v3.6.0 — preview loop helper.
# Launches Chrome with remote-debugging-port=9222 + isolated user-data-dir.
# Doc: references/preview-loop-protocol.md
# Usage: scripts/launch-chrome-cdp.sh [URL]

set -euo pipefail

PROFILE_DIR="$(pwd)/.icm-chrome-profile"
TARGET_URL="${1:-http://localhost:3000}"

CHROME="${CHROME:-}"
if [ -z "$CHROME" ]; then
  for cand in \
    google-chrome \
    google-chrome-stable \
    chromium \
    chromium-browser \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium"; do
    if command -v "$cand" >/dev/null 2>&1; then
      CHROME="$(command -v "$cand")"
      break
    fi
    if [ -x "$cand" ]; then
      CHROME="$cand"
      break
    fi
  done
fi

if [ -z "$CHROME" ]; then
  echo "Chrome/Chromium not found. Set CHROME=<path> manually." >&2
  exit 1
fi

mkdir -p "$PROFILE_DIR"

echo "Launching Chrome with CDP on :9222"
echo "  profile: $PROFILE_DIR"
echo "  url:     $TARGET_URL"

"$CHROME" \
  --remote-debugging-port=9222 \
  --user-data-dir="$PROFILE_DIR" \
  "$TARGET_URL" \
  &

disown 2>/dev/null || true
