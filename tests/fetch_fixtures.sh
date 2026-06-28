#!/usr/bin/env bash
# Fetch a few KiCad demo projects for the test suite via a blobless sparse
# checkout of the official KiCad source mirror. Idempotent.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HERE/fixtures"
DEMOS=(jetson-agx-thor-baseboard complex_hierarchy video)

# already populated?
missing=0
for d in "${DEMOS[@]}"; do [ -d "$DEST/$d" ] || missing=1; done
if [ "$missing" -eq 0 ]; then echo "fixtures already present"; exit 0; fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Sparse-cloning KiCad demos (blobless, shallow)..."
git clone --filter=blob:none --no-checkout --depth 1 \
  https://github.com/KiCad/kicad-source-mirror.git "$TMP/kicad"
git -C "$TMP/kicad" sparse-checkout init --cone
git -C "$TMP/kicad" sparse-checkout set "${DEMOS[@]/#/demos/}"
git -C "$TMP/kicad" checkout

for d in "${DEMOS[@]}"; do
  if [ -d "$TMP/kicad/demos/$d" ]; then
    rm -rf "$DEST/$d"
    cp -R "$TMP/kicad/demos/$d" "$DEST/"
    echo "  fetched $d"
  else
    echo "  WARN: demos/$d not found in mirror" >&2
  fi
done
echo "Done. Run: pytest"
