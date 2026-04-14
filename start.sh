#!/bin/bash
# Avvia Insta Downloader
cd "$(dirname "$0")"

# Crea venv se non esiste
if [ ! -d "venv" ]; then
    echo "Prima installazione — creo ambiente virtuale..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo ""
echo "  Insta Downloader"
echo "  Apri http://localhost:5000 nel browser"
echo ""

python3 app.py
