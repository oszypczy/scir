#!/bin/bash
# Konwersja sprawozdanie.md -> sprawozdanie.pdf za pomocą pandoc + weasyprint

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT="$SCRIPT_DIR/sprawozdanie.md"
OUTPUT="$SCRIPT_DIR/sprawozdanie.pdf"

if ! command -v pandoc &>/dev/null; then
    echo "Błąd: pandoc nie jest zainstalowany (brew install pandoc)"
    exit 1
fi

if ! command -v weasyprint &>/dev/null; then
    echo "Błąd: weasyprint nie jest zainstalowany (pip install weasyprint)"
    exit 1
fi

CSS_FILE="$SCRIPT_DIR/style.css"
cat > "$CSS_FILE" << 'CSS'
@page {
    size: A4;
    margin: 2.5cm;
}
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 12pt;
    line-height: 1.5;
}
img {
    width: 100%;
    max-width: 100%;
    height: auto;
    image-rendering: high-quality;
    display: block;
    margin: 1em auto;
}
code, pre {
    font-family: "Andale Mono", "Courier New", monospace;
    font-size: 10pt;
}
pre {
    background: #f4f4f4;
    padding: 12px;
    border-radius: 4px;
    overflow-wrap: break-word;
    white-space: pre-wrap;
}
CSS

echo "Generowanie PDF..."
pandoc "$INPUT" -o "$OUTPUT" \
    --pdf-engine=weasyprint \
    --pdf-engine-opt="--presentational-hints" \
    --css="$CSS_FILE" \
    --metadata title="Sprawozdanie — Stacja Pogodowa" \
    2> >(grep -v "^WARNING:" | grep -v "^ERROR: No anchor" >&2)

if [ -f "$OUTPUT" ]; then
    echo "Gotowe: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
else
    echo "Błąd podczas generowania PDF"
    exit 1
fi
