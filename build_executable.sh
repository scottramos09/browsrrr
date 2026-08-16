#!/usr/bin/env bash
set -euo pipefail
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --name BrowsRrr --windowed --collect-all PySide6 main.py
echo "Run from dist (not build): dist/BrowsRrr/BrowsRrr"