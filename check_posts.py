import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import instaloader

BASE_DIR = Path(__file__).resolve().parent
ACCOUNTS_FILE = BASE_DIR / "accounts.json"
STATE_FILE = BASE_DIR / "state.json"
POSTS_FILE = BASE_DIR / "posts.json"

IG_USERNAME = os.environ.get("IG_USERNAME", "").strip()
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def notify(username, post_url):
    if not NTFY_TOPIC:
        return
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=f"Neuer Post von @{username}: {post_url}".encode("utf-8"),
            headers={"Title": "Instagram Monitor"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError as exc:
        print(f"Benachrichtigung fehlgeschlagen: {exc}")


def main():
    accounts = load_json(ACCOUNTS_FILE, [])
    state = load_json(STATE_FILE, {})
    posts = load_json(POSTS_FILE, [])

    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )
    loader.load_session_from_file(IG_USERNAME)

    changed = False

    for username in accounts:
        try:
            profile = instaloader.Profile.from_username(loader.context, username)
            latest_post = next(profile.get_posts())
        except Exception as exc:
            print(f"Fehler bei @{username}: {exc}")
            continue

        shortcode = latest_post.shortcode
        last_known = state.get(username)
        if last_known == shortcode:
            continue

        state[username] = shortcode
        changed = True

        if last_known is not None:
            post_url = f"https://www.instagram.com/p/{shortcode}/"
            posts.insert(
                0,
                {
                    "account": username,
                    "post_url": post_url,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            notify(username, post_url)
            print(f"Neuer Post erkannt: @{username} -> {post_url}")
        else:
            print(f"Erster Check fuer @{username}, aktueller Post gemerkt (keine Benachrichtigung).")

        time.sleep(3)

    if changed:
        save_json(STATE_FILE, state)
        save_json(POSTS_FILE, posts[:200])


if __name__ == "__main__":
    main()
