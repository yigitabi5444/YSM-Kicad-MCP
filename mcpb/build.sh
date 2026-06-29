#!/usr/bin/env bash
# Build the self-contained Claude Desktop extension (.mcpb).
# Freezes the server into one binary (PyInstaller) so the extension needs no
# Python, uv, or network at runtime — only kicad-cli, which it shells out to.
# Produces a platform-specific bundle: kicad-context-<os>-<arch>.mcpb
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PY="${PYTHON:-python3}"
"$PY" -m venv "$WORK/venv"
"$WORK/venv/bin/pip" -q install -e . pyinstaller

"$WORK/venv/bin/pyinstaller" --onefile --clean --noconfirm \
  --name kicad-context-mcp \
  --paths src \
  --collect-submodules kicad_context_mcp \
  --copy-metadata mcp \
  --distpath "$WORK/dist" --workpath "$WORK/build" --specpath "$WORK" \
  mcpb/entry.py

STAGE="$WORK/stage"
mkdir -p "$STAGE/server"
cp mcpb/manifest.json "$STAGE/"
cp "$WORK/dist/kicad-context-mcp" "$STAGE/server/"

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
OUT="$ROOT/kicad-context-$OS-$ARCH.mcpb"
npx --yes @anthropic-ai/mcpb@latest pack "$STAGE" "$OUT"
echo "Built $OUT"
