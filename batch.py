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


def cleanup_videos(downloads_dir) -> tuple[int, int]:
    """Cancella .mp4 da tutte le sottocartelle e rimuove cartelle rimaste vuote.

    Default attivo per il workflow Timence: i reel scaricati come MP4 non vengono mai
    usati nel pool foto, lasciarli crea solo rumore (cartelle 'autore' che contengono
    solo video, falsi conteggi, confusione in fase di selezione).

    Returns:
        (n_videos_removed, n_empty_dirs_removed)
    """
    n_videos = 0
    for mp4 in downloads_dir.rglob("*.mp4"):
        mp4.unlink()
        n_videos += 1
    n_dirs = 0
    for d in sorted(downloads_dir.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            n_dirs += 1
    return n_videos, n_dirs


def batch_download(urls: list[str], keep_videos: bool = False) -> None:
    """Scarica una lista di URL Instagram.

    Args:
        urls: lista URL post/reel/carousel
        keep_videos: se True non cancella i .mp4 a fine batch (default: False, li cancella)
    """
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

    if not keep_videos:
        n_videos, n_dirs = cleanup_videos(DOWNLOADS_DIR)
        if n_videos > 0 or n_dirs > 0:
            print(f"Cleanup automatico: {n_videos} video MP4 cancellati, {n_dirs} cartelle vuote rimosse")
            print("(usa --keep-videos per mantenerli)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python batch.py [--keep-videos] URL1 URL2 URL3 ...")
        print("Esempio: python batch.py https://www.instagram.com/p/ABC123/ https://www.instagram.com/reel/XYZ789/")
        print("Default: i video MP4 vengono cancellati a fine batch (i reel non servono al pool foto Timence).")
        sys.exit(1)

    args = sys.argv[1:]
    keep_videos = False
    if "--keep-videos" in args:
        keep_videos = True
        args = [a for a in args if a != "--keep-videos"]

    batch_download(args, keep_videos=keep_videos)
