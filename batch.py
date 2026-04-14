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

from app import extract_shortcode, get_post, get_media_items, download_media_item, DOWNLOADS_DIR


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
            post = get_post(shortcode)
            username = post.owner_username
            media_items = get_media_items(post)
            dest_dir = DOWNLOADS_DIR / username
            date_str = post.date_utc.strftime("%Y-%m-%d_%H-%M-%S_UTC")

            for item in media_items:
                ext = ".mp4" if item["is_video"] else ".jpg"
                filename = f"{date_str}_{item['index']}{ext}"
                download_media_item(item["url"], dest_dir, filename)

            print(f"  OK: {len(media_items)} file scaricati in downloads/{username}/")
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
