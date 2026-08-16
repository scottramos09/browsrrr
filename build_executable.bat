@echo off
taskkill /IM BrowsRrr.exe /F >nul 2>&1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --name BrowsRrr --windowed --collect-all PySide6 --add-data "browsrrr;browsrrr" main.py
echo Run from dist: dist\BrowsRrr\BrowsRrr.exe
start "" "dist\BrowsRrr\BrowsRrr.exe"