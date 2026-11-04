#!/usr/bin/env bash
# Clone the pinned Petri source (MIT) into vendor/inspect_petri. vendor/ is gitignored.
# Pin: meridianlabs-ai/inspect_petri, branch petri-v2, commit f02b3ec (f02b3ec70a6b9c2a1a7da172b2f3f69a1e1b0585).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/vendor/inspect_petri"
COMMIT="f02b3ec70a6b9c2a1a7da172b2f3f69a1e1b0585"
if [ ! -d "$DEST/.git" ]; then
  mkdir -p "$ROOT/vendor"
  git clone --quiet --branch petri-v2 https://github.com/meridianlabs-ai/inspect_petri.git "$DEST"
fi
git -C "$DEST" fetch --quiet origin petri-v2 || true
git -C "$DEST" checkout --quiet "$COMMIT"
test "$(git -C "$DEST" rev-parse HEAD)" = "$COMMIT"
echo "vendor/inspect_petri at $(git -C "$DEST" rev-parse --short HEAD)"
