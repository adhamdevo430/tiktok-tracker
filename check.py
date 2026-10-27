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

# أرقام بنسجل كل تغيير فيها
NUMERIC = ["followers", "following", "videos"]
# نصوص بنسجل تغييرها
TEXT = ["name", "bio"]
# اللايكات بنعرض الرقم الحالي بس من غير تسجيل كل تغيير

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
NTFY_TEST = os.environ.get("NTFY_TEST", "").strip().lower() == "true"


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
        info = data["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]
        stats = info["stats"]
        user = info.get("user") or {}
        return {
            "followers": stats["followerCount"],
            "following": stats["followingCount"],
            "videos": stats.get("videoCount"),
            "likes": stats.get("heartCount", stats.get("heart")),
            "name": user.get("nickname"),
            "bio": user.get("signature"),
        }
    except (KeyError, TypeError, ValueError):
        sys.exit("FAIL: page structure changed or account data missing")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return default


def describe(e):
    t = e["type"]
    up = e["change"] == "up"
    if t == "followers":
        return f"{'زاد' if up else 'نقص'} المتابعين: {e['from']} ← {e['to']}"
    if t == "following":
        return f"{'زاد' if up else 'نقص'} عدد اللي بتتابعهم: {e['from']} ← {e['to']}"
    if t == "videos":
        word = "نزل فيديو جديد" if up else "اتحذف فيديو"
        return f"{word} (العدد: {e['to']})"
    if t == "name":
        return f"غيّر الاسم: {e['from']} ← {e['to']}"
    if t == "bio":
        return "غيّر البايو"
    return t


def notify(title, message):
    if not NTFY_TOPIC:
        print("Notifications off (no NTFY_TOPIC set)")
        return
    try:
        r = requests.post(
            "https://ntfy.sh",
            json={
                "topic": NTFY_TOPIC,
                "title": title,
                "message": message,
                "priority": 3,
            },
            timeout=20,
        )
        print("ntfy status:", r.status_code)
    except requests.RequestException as err:
        # لو الإشعار فشل ما نوقفش الفحص
        print("ntfy failed:", err)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new = fetch()
    print("Current:", new)

    old = load(LATEST, None)
    log = load(LOG, [])
    added = []

    if old is not None:
        for key in NUMERIC:
            o, n = old.get(key), new.get(key)
            if o is None or n is None or o == n:
                continue
            added.append(
                {
                    "time": now,
                    "type": key,
                    "change": "up" if n > o else "down",
                    "from": o,
                    "to": n,
                }
            )
            print("Change:", key, o, "->", n)

        for key in TEXT:
            o, n = old.get(key), new.get(key)
            if o is None or n is None or o == n:
                continue
            added.append(
                {"time": now, "type": key, "change": "changed", "from": o, "to": n}
            )
            print("Change:", key)

    log.extend(added)
    new["checked_at"] = now
    with open(LATEST, "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=1)
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)

    if added:
        notify("تحديث جديد على الحساب", "\n".join(describe(e) for e in added))
    if NTFY_TEST:
        notify("تجربة الإشعارات", "لو وصلتك الرسالة دي يبقى الإشعارات شغالة ✅")


if __name__ == "__main__":
    main()
