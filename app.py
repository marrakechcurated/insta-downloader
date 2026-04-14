"""
Insta Downloader — Web app locale per scaricare foto e video da Instagram.
Avvia con: python app.py → apre http://localhost:5000
"""

import os
import json
import re
import shutil
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_from_directory
import instaloader

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


def get_post_info(shortcode: str) -> dict:
    """Scarica le info di un post senza scaricare i file."""
    post = instaloader.Post.from_shortcode(L.context, shortcode)

    media_items = []

    if post.typename == "GraphSidecar":
        # Carousel — più foto/video
        for i, node in enumerate(post.get_sidecar_nodes(), 1):
            media_items.append({
                "index": i,
                "is_video": node.is_video,
                "url": node.video_url if node.is_video else node.display_url,
                "thumbnail": node.display_url,
            })
    elif post.is_video:
        media_items.append({
            "index": 1,
            "is_video": True,
            "url": post.video_url,
            "thumbnail": post.url,  # thumbnail del video
        })
    else:
        media_items.append({
            "index": 1,
            "is_video": False,
            "url": post.url,
            "thumbnail": post.url,
        })

    return {
        "shortcode": shortcode,
        "owner": post.owner_username,
        "caption": (post.caption or "")[:200],
        "date": post.date_utc.isoformat(),
        "media_count": len(media_items),
        "media": media_items,
        "typename": post.typename,
    }


def download_post(shortcode: str) -> dict:
    """Scarica tutti i media di un post nella cartella downloads/username/."""
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    username = post.owner_username

    # Cartella di destinazione: downloads/username/
    dest_dir = DOWNLOADS_DIR / username
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Instaloader scarica in una temp dir, poi spostiamo
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        L.dirname_pattern = tmpdir
        L.download_post(post, target="")

        downloaded_files = []
        for f in Path(tmpdir).iterdir():
            if f.is_file() and not f.name.startswith("."):
                # Rinomina con timestamp per evitare sovrascritture
                dest_path = dest_dir / f.name
                if dest_path.exists():
                    stem = f.stem
                    suffix = f.suffix
                    timestamp = datetime.now().strftime("%H%M%S")
                    dest_path = dest_dir / f"{stem}_{timestamp}{suffix}"

                shutil.move(str(f), str(dest_path))
                downloaded_files.append({
                    "filename": dest_path.name,
                    "path": str(dest_path.relative_to(DOWNLOADS_DIR)),
                    "size": dest_path.stat().st_size,
                    "is_video": dest_path.suffix.lower() in (".mp4", ".mov", ".webm"),
                })

    return {
        "shortcode": shortcode,
        "owner": username,
        "folder": str(dest_dir.relative_to(DOWNLOADS_DIR)),
        "files": downloaded_files,
        "total_files": len(downloaded_files),
    }


# --- Routes ---

@app.route("/")
def index():
    return render_template("index.html")


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
        info = get_post_info(shortcode)
        return jsonify(info)
    except instaloader.exceptions.ProfileNotExistsException:
        return jsonify({"error": "Profilo non trovato o privato"}), 404
    except instaloader.exceptions.LoginRequiredException:
        return jsonify({"error": "Questo contenuto richiede il login (profilo privato)"}), 403
    except Exception as e:
        return jsonify({"error": f"Errore: {str(e)}"}), 500


@app.route("/api/download", methods=["POST"])
def api_download():
    """Scarica tutti i media di un URL Instagram."""
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "URL mancante"}), 400

    shortcode = extract_shortcode(url)
    if not shortcode:
        return jsonify({"error": "URL Instagram non valido"}), 400

    try:
        result = download_post(shortcode)
        return jsonify(result)
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
            result = download_post(shortcode)
            result["url"] = url
            result["success"] = True
            results.append(result)
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
    print("  Apri http://localhost:5000 nel browser\n")
    app.run(host="127.0.0.1", port=5000, debug=True)
