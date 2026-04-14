"""
Batch download — Scarica foto/video da una lista di URL Instagram.

Uso diretto:
    python batch.py URL1 URL2 URL3

Uso da Claude Code del redattore:
    Il redattore dà i link a Claude Code, che lancia questo script.
"""

import sys
import os

# Aggiungi la directory dello script al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import extract_shortcode, download_post


def batch_download(urls: list[str]) -> None:
    """Scarica una lista di URL Instagram."""
    total = len(urls)
    success = 0
    failed = 0

    for i, url in enumerate(urls, 1):
        url = url.strip()
        if not url:
            continue

        print(f"\n[{i}/{total}] {url}")

        shortcode = extract_shortcode(url)
        if not shortcode:
            print(f"  ERRORE: URL non valido")
            failed += 1
            continue

        try:
            result = download_post(shortcode)
            files_count = result["total_files"]
            folder = result["folder"]
            print(f"  OK: {files_count} file scaricati in downloads/{folder}/")
            success += 1
        except Exception as e:
            print(f"  ERRORE: {e}")
            failed += 1

    print(f"\n--- Risultato ---")
    print(f"Totale: {total} | Scaricati: {success} | Errori: {failed}")
    print(f"File salvati in: downloads/")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python batch.py URL1 URL2 URL3 ...")
        print("Esempio: python batch.py https://www.instagram.com/p/ABC123/ https://www.instagram.com/reel/XYZ789/")
        sys.exit(1)

    urls = sys.argv[1:]
    batch_download(urls)
