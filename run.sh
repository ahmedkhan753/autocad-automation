#!/bin/bash
# AutoCAD Room Extractor — One-Click Launcher
set -e

echo "=== AutoCAD Room Area Extractor ==="
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "[*] Installing dependencies..."
pip install -r requirements.txt --quiet

# Create required directories
mkdir -p temp output logs

# Launch Flask app
echo "[✓] Starting web server on http://localhost:5000"
echo ""
python app.py
