#!/usr/bin/env bash
# Build the self-contained server binary into bin/ so the plugin needs no
# Python, uv, or network at runtime — only kicad-cli, which it shells out to.
# The binary is platform-specific; run this on the platform you target.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PY="${PYTHON:-python3}"
"$PY" -m venv "$WORK/venv"
"$WORK/venv/bin/pip" -q install -e . pyinstaller

cat > "$WORK/entry.py" <<'PY'
from kicad_context_mcp.server import main
main()
PY

"$WORK/venv/bin/pyinstaller" --onefile --clean --noconfirm \
  --name kicad-context-mcp \
  --paths src \
  --collect-submodules kicad_context_mcp \
  --copy-metadata mcp \
  --distpath "$WORK/dist" --workpath "$WORK/build" --specpath "$WORK" \
  "$WORK/entry.py"

mkdir -p bin
cp "$WORK/dist/kicad-context-mcp" bin/kicad-context-mcp
chmod +x bin/kicad-context-mcp
echo "Built bin/kicad-context-mcp ($(uname -s)/$(uname -m))"
