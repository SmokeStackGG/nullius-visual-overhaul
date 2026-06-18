#!/bin/bash
# Double-click to launch the tier-mask UI. Opens a Terminal window; close it
# when you quit the app.
cd "$(dirname "$0")/.."
exec python3 tools/mask_ui.py "$@"
