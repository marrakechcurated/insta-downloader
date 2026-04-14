"""
Insta Downloader — Web app locale per scaricare foto e video da Instagram.
Avvia con: python app.py → apre http://localhost:5050
"""

import os
import re
import shutil
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

from flask import Flask, render_template, request, jsonify, send_from_directory, Response
import instaloader
import requests as http_requests

app = Flask(__name__)

DOWNLOADS_DIR = Path(__file__).parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Istanza Instaloader riutilizzata
L = instaloader.Instaloader(
    download_pictures=True,
    download_videos=True,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False,
    post_metadata_txt_pattern="",
)

# Cache per le info dei post (evita richieste doppie a Instagram)
_post_cache: dict[str, "instaloader.Post"] = {}


def extract_shortcode(url: str) -> str | None:
    """Estrai lo shortcode da un URL Instagram (post, reel, carousel)."""
    patterns = [
        r"instagram\.com/p/([A-Za-z0-9_-]+)",
        r"instagram\.com/reel/([A-Za-z0-9_-]+)",
        r"instagram\.com/reels/([A-Za-z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_post(shortcode: str) -> "instaloader.Post":
    """Ottieni un post (con cache)."""
    if shortcode not in _post_cache:
        _post_cache[shortcode] = instaloader.Post.from_shortcode(L.context, shortcode)
    return _post_cache[shortcode]


def get_media_items(post: "instaloader.Post") -> list[dict]:
    """Estrai la lista dei media da un post."""
    items = []

    if post.typename == "GraphSidecar":
        for i, node in enumerate(post.get_sidecar_nodes(), 1):
            items.append({
                "index": i,
                "is_video": node.is_video,
                "url": node.video_url if node.is_video else node.display_url,
                "thumbnail": node.display_url,
            })
    elif post.is_video:
        items.append({
            "index": 1,
            "is_video": True,
            "url": post.video_url,
            "thumbnail": post.url,
        })
    else:
        items.append({
            "index": 1,
            "is_video": False,
            "url": post.url,
            "thumbnail": post.url,
        })

    return items


def download_media_item(url: str, dest_dir: Path, filename: str) -> dict:
    """Scarica un singolo file media."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    # Evita sovrascritture
    if dest_path.exists():
        stem = dest_path.stem
        suffix = dest_path.suffix
        timestamp = datetime.now().strftime("%H%M%S")
        dest_path = dest_dir / f"{stem}_{timestamp}{suffix}"

    resp = http_requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }, timeout=60)
    resp.raise_for_status()

    with open(dest_path, "wb") as f:
        f.write(resp.content)

    return {
        "filename": dest_path.name,
        "path": str(dest_path.relative_to(DOWNLOADS_DIR)),
        "size": dest_path.stat().st_size,
        "is_video": dest_path.suffix.lower() in (".mp4", ".mov", ".webm"),
    }


# --- Routes ---

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/proxy-image")
def proxy_image():
    """Proxy per le immagini Instagram (aggira hotlink protection)."""
    img_url = request.args.get("url", "")
    if not img_url or "instagram" not in img_url and "cdninstagram" not in img_url and "fbcdn" not in img_url:
        return "URL non valido", 400

    try:
        resp = http_requests.get(img_url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }, timeout=15)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "image/jpeg")
        return Response(resp.content, content_type=content_type, headers={
            "Cache-Control": "public, max-age=3600",
        })
    except Exception:
        return "Errore proxy immagine", 502


@app.route("/api/preview", methods=["POST"])
def api_preview():
    """Anteprima di un URL Instagram (senza scaricare)."""
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "URL mancante"}), 400

    shortcode = extract_shortcode(url)
    if not shortcode:
        return jsonify({"error": "URL Instagram non valido. Usa un link a un post, reel o carousel."}), 400

    try:
        post = get_post(shortcode)
        media_items = get_media_items(post)

        return jsonify({
            "shortcode": shortcode,
            "owner": post.owner_username,
            "caption": (post.caption or "")[:200],
            "date": post.date_utc.isoformat(),
            "media_count": len(media_items),
            "media": media_items,
            "typename": post.typename,
        })
    except instaloader.exceptions.ProfileNotExistsException:
        return jsonify({"error": "Profilo non trovato o privato"}), 404
    except instaloader.exceptions.LoginRequiredException:
        return jsonify({"error": "Questo contenuto richiede il login (profilo privato)"}), 403
    except Exception as e:
        return jsonify({"error": f"Errore: {str(e)}"}), 500


@app.route("/api/download", methods=["POST"])
def api_download():
    """Scarica media selezionati di un URL Instagram."""
    data = request.get_json()
    url = data.get("url", "").strip()
    selected_indices = data.get("selected", None)  # lista di indici (1-based), None = tutti

    if not url:
        return jsonify({"error": "URL mancante"}), 400

    shortcode = extract_shortcode(url)
    if not shortcode:
        return jsonify({"error": "URL Instagram non valido"}), 400

    try:
        post = get_post(shortcode)
        username = post.owner_username
        media_items = get_media_items(post)

        # Filtra per selezione
        if selected_indices:
            media_items = [m for m in media_items if m["index"] in selected_indices]

        if not media_items:
            return jsonify({"error": "Nessun media selezionato"}), 400

        dest_dir = DOWNLOADS_DIR / username
        downloaded_files = []

        date_str = post.date_utc.strftime("%Y-%m-%d_%H-%M-%S_UTC")

        for item in media_items:
            ext = ".mp4" if item["is_video"] else ".jpg"
            filename = f"{date_str}_{item['index']}{ext}"

            file_info = download_media_item(item["url"], dest_dir, filename)
            downloaded_files.append(file_info)

        return jsonify({
            "shortcode": shortcode,
            "owner": username,
            "folder": username,
            "files": downloaded_files,
            "total_files": len(downloaded_files),
        })
    except instaloader.exceptions.ProfileNotExistsException:
        return jsonify({"error": "Profilo non trovato o privato"}), 404
    except instaloader.exceptions.LoginRequiredException:
        return jsonify({"error": "Questo contenuto richiede il login (profilo privato)"}), 403
    except Exception as e:
        return jsonify({"error": f"Errore: {str(e)}"}), 500


@app.route("/api/batch", methods=["POST"])
def api_batch():
    """Scarica più URL in sequenza."""
    data = request.get_json()
    urls = data.get("urls", [])

    if not urls:
        return jsonify({"error": "Nessun URL fornito"}), 400

    results = []
    for url in urls:
        url = url.strip()
        if not url:
            continue

        shortcode = extract_shortcode(url)
        if not shortcode:
            results.append({"url": url, "error": "URL non valido", "success": False})
            continue

        try:
            post = get_post(shortcode)
            username = post.owner_username
            media_items = get_media_items(post)
            dest_dir = DOWNLOADS_DIR / username
            date_str = post.date_utc.strftime("%Y-%m-%d_%H-%M-%S_UTC")

            downloaded = []
            for item in media_items:
                ext = ".mp4" if item["is_video"] else ".jpg"
                filename = f"{date_str}_{item['index']}{ext}"
                file_info = download_media_item(item["url"], dest_dir, filename)
                downloaded.append(file_info)

            results.append({
                "url": url,
                "owner": username,
                "folder": username,
                "files": downloaded,
                "total_files": len(downloaded),
                "success": True,
            })
        except Exception as e:
            results.append({"url": url, "error": str(e), "success": False})

    success_count = sum(1 for r in results if r.get("success"))
    return jsonify({
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "results": results,
    })


@app.route("/api/downloads")
def api_list_downloads():
    """Lista tutti i file scaricati, organizzati per username."""
    folders = {}
    for user_dir in sorted(DOWNLOADS_DIR.iterdir()):
        if user_dir.is_dir() and user_dir.name != ".gitkeep":
            files = []
            for f in sorted(user_dir.iterdir()):
                if f.is_file() and not f.name.startswith("."):
                    files.append({
                        "filename": f.name,
                        "path": str(f.relative_to(DOWNLOADS_DIR)),
                        "size": f.stat().st_size,
                        "is_video": f.suffix.lower() in (".mp4", ".mov", ".webm"),
                    })
            if files:
                folders[user_dir.name] = files

    return jsonify(folders)


@app.route("/downloads/<path:filepath>")
def serve_download(filepath):
    """Serve i file scaricati (per preview nel browser)."""
    return send_from_directory(DOWNLOADS_DIR, filepath)


if __name__ == "__main__":
    print("\n  Insta Downloader avviato!")
    print("  Apri http://localhost:5050 nel browser\n")
    app.run(host="127.0.0.1", port=5050, debug=True)
