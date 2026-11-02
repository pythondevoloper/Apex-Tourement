# -*- coding: utf-8 -*-
"""
Bepul FCM push serveri (GitHub Actions cron orqali ishlaydi).

Cloud Functions (Blaze/tolov) o'rniga: bu skript har ~5 daqiqada ishga tushib,
Realtime Database'dagi yangi xabarnomalarni (/notifs) ko'radi va ularni FCM
HTTP v1 orqali tegishli topicga ("all" | "p{pid}" | "g{gid}") yuboradi.

Xavfsizlik: Firebase service account kaliti GitHub Secrets'da saqlanadi
(FIREBASE_SERVICE_ACCOUNT), APK ichida emas. FCM yuborish va service account
yaratish bepul — Blaze reja talab qilinmaydi.

Dedup: /push_state/last_id kursori. Faqat undan katta id'li xabarlar yuboriladi,
shuning uchun bir xabar ikki marta ketmaydi.
"""
import os
import re
import sys
import json

APP_TITLE = "Apex Pro League"
DEFAULT_PROJECT_ID = "apex-league-2e8fc"
DEFAULT_DB_URL = ("https://apex-league-2e8fc-default-rtdb."
                  "europe-west1.firebasedatabase.app")
CURSOR_PATH = "push_state/last_id"
TOPIC_RE = re.compile(r"^[a-zA-Z0-9-_.~%]{1,900}$")


def main():
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not sa_json:
        # Secret qo'yilmagan bo'lsa — jimdagan chiqamiz (workflow xato bermaydi).
        print("FIREBASE_SERVICE_ACCOUNT yo'q: push yuborilmadi (bu normal, "
              "agar hali secret qo'ymagan bo'lsangiz).")
        return 0

    project_id = os.environ.get("FIREBASE_PROJECT_ID", DEFAULT_PROJECT_ID)
    db_url = os.environ.get("FIREBASE_DB_URL", DEFAULT_DB_URL)

    # Lazy import: secret bo'lmaganda firebase-admin o'rnatilmagan bo'lsa ham ishlaydi.
    import firebase_admin
    from firebase_admin import credentials, messaging, db

    try:
        cert = json.loads(sa_json)
    except Exception as e:
        print(f"FIREBASE_SERVICE_ACCOUNT JSON emas: {e}")
        return 1

    cred = credentials.Certificate(cert)
    firebase_admin.initialize_app(cred, {"databaseURL": db_url,
                                         "projectId": project_id})

    notifs = db.reference("notifs").get() or {}
    cursor_ref = db.reference(CURSOR_PATH)
    try:
        last_id = int(cursor_ref.get() or 0)
    except (TypeError, ValueError):
        last_id = 0

    items = []
    for k, v in notifs.items():
        try:
            nid = int(k)
        except (TypeError, ValueError):
            continue
        items.append((nid, v or {}))
    items.sort(key=lambda t: t[0])

    new_items = [(nid, v) for nid, v in items if nid > last_id]
    max_id = last_id
    sent = 0
    for nid, v in new_items:
        max_id = max(max_id, nid)
        to = v.get("to")
        text = (v.get("text") or "").strip() if isinstance(v.get("text"), str) else ""
        if not to or not text or not TOPIC_RE.match(str(to)):
            continue
        msg = messaging.Message(
            notification=messaging.Notification(title=APP_TITLE, body=text[:175]),
            data={"nid": str(nid), "to": str(to), "click_action": "OPEN_APP"},
            topic=str(to),
            android=messaging.AndroidConfig(
                priority="normal" if str(to) == "all" else "high",
                ttl=86400,                       # soniya (1 kun)
                collapse_key=f"notif-{nid}",
            ),
        )
        try:
            messaging.send(msg)
            sent += 1
        except Exception as e:
            # Topic bo'sh bo'lishi mumkin (hech kim obuna bo'lmagan) — bu xato emas.
            print(f"yuborilmadi topic={to}: {type(e).__name__}: {e}")

    if new_items:
        cursor_ref.set(max_id)

    print(f"tekshirildi={len(items)} yangi={len(new_items)} yuborildi={sent} kursor={max_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
