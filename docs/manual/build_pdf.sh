#!/usr/bin/env bash
# Render docs/manual/manual.html to docs/Panduan_AMR_Web_UI.pdf with headless
# Chrome. Images are referenced relative to the HTML, so run from anywhere.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/../Panduan_AMR_Web_UI.pdf"
CHROME="$(command -v google-chrome || command -v chromium || command -v chromium-browser)"

"$CHROME" --headless=new --disable-gpu --no-sandbox \
  --no-pdf-header-footer \
  --virtual-time-budget=5000 \
  --print-to-pdf="$OUT" \
  "file://$HERE/manual.html" 2>/dev/null

echo "wrote $OUT"
