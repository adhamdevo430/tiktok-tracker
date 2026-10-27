import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

USER = "mariamelshahed5"
URL = f"https://www.tiktok.com/@{USER}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
DATA_DIR = "data"
LATEST = os.path.join(DATA_DIR, "latest.json")
LOG = os.path.join(DATA_DIR, "log.json")


def fetch():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    print("HTTP status:", r.status_code)
    if r.status_code != 200:
        sys.exit("FAIL: TikTok did not return the page (blocked?)")
    m = re.search(
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
        r.text,
        re.S,
    )
    if not m:
        sys.exit("FAIL: data block not found in page")
    try:
        data = json.loads(m.group(1))
        stats = data["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]["stats"]
        return {
            "followers": stats["followerCount"],
            "following": stats["followingCount"],
        }
    except (KeyError, TypeError, ValueError):
        sys.exit("FAIL: page structure changed or account data missing")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return default


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new = fetch()
    print("Current:", new)

    old = load(LATEST, None)
    log = load(LOG, [])

    if old is not None:
        for key in ("followers", "following"):
            if new[key] != old[key]:
                log.append(
                    {
                        "time": now,
                        "type": key,
                        "change": "up" if new[key] > old[key] else "down",
                        "from": old[key],
                        "to": new[key],
                    }
                )
                print("Change:", key, old[key], "->", new[key])

    new["checked_at"] = now
    with open(LATEST, "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=1)
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
