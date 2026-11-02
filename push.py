# -*- coding: utf-8 -*-
"""
FCM push mijoz tomoni (faqat Android).

Nega topic-based: server (Cloud Functions) har xabarnomani `to` topiciga yuboradi
("all" | "p{pid}" | "g{gid}"). Mijoz shu topiclarga obuna bo'lsa yetarli — alohida
Java service yoki google-services gradle plugin talab qilinmaydi.

FirebaseApp qo'lda ishga tushiriladi: `google-services.json` (yoki config.py) dan
olingan identifikatorlar bilan. Shu sababli APK da `google-services.json` bo'lishi
shart (README "Push bildirishnoma (FCM)" bo'limiga qarang).

Cloud Function `notification` payload yuboradi, shuning uchun xabarni Android tizim
trayi avtomatik ko'rsatadi. Android 13+ da buning uchun POST_NOTIFICATIONS ruxsati
kerak — uni bir marta so'raymiz.

Desktop'da (yoki SDK topilmasa) barcha funksiyalar jim no-op qiladi: ilova yiqilmaydi.
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))

try:
    from kivy.utils import platform as _PLATFORM
except Exception:
    _PLATFORM = "unknown"

# Jarayon davomida bir marta to'ldiriladigan holat.
_state = {
    "inited": False,      # FirebaseApp muvaffaqiyatli init bo'ldimi
    "failed": False,      # init umuman olmadi (qayta urinmaslik uchun)
    "subscribed": set(),  # hozir obuna bo'lingan topiclar
    "error": None,
}


def is_android():
    return _PLATFORM == "android"


def status():
    """Diagnostika uchun qisqa holat (admin/profil oynasida ko'rsatish mumkin)."""
    if not is_android():
        return "Push faqat Android'da ishlaydi"
    if _state["error"]:
        return f"Push xatosi: {_state['error']}"
    if not _state["inited"]:
        return "Push hali ishga tushmagan"
    return f"Push yoqilgan: {len(_state['subscribed'])} topic"


def _current_package():
    """Joriy Android package nomi (masalan org.apex.apextournament). Bo'lmasa None."""
    if not is_android():
        return None
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        return str(PythonActivity.mActivity.getPackageName())
    except Exception:
        return None


def _load_ids():
    """FCM identifikatorlari: avval google-services.json, keyin config.py zaxira.

    google-services.json'da uchala ilova (player/admin/referee) uchun alohida
    `client` bo'lishi mumkin — joriy package nomiga mos client'ni tanlaymiz;
    mosi topilmasa birinchisiga qaytamiz. project_info (sender_id/project_id)
    barcha client'lar uchun umumiy.
    """
    try:
        with open(os.path.join(HERE, "google-services.json"), "r", encoding="utf-8") as f:
            gs = json.load(f)
        proj = gs["project_info"]
        clients = gs["client"]
        pkg = _current_package()
        client = clients[0]
        if pkg:
            for c in clients:
                pn = c.get("client_info", {}).get("android_client_info", {}).get("package_name")
                if pn == pkg:
                    client = c
                    break
        return {
            "api_key": client["api_key"][0]["current_key"],
            "app_id": client["client_info"]["mobilesdk_app_id"],
            "project_id": proj["project_id"],
            "sender_id": proj["project_number"],
        }
    except Exception:
        pass
    try:
        import config
        return {
            "api_key": getattr(config, "FIREBASE_API_KEY", None),
            "app_id": getattr(config, "FCM_APPLICATION_ID", None),
            "project_id": getattr(config, "FCM_PROJECT_ID", None),
            "sender_id": getattr(config, "FCM_SENDER_ID", None),
        }
    except Exception:
        return {}


def _init_firebase():
    """FirebaseApp ni qo'lda ishga tushirish. True/False."""
    if _state["inited"]:
        return True
    if _state["failed"]:
        return False
    ids = _load_ids()
    need = ("api_key", "app_id", "project_id", "sender_id")
    if not all(ids.get(k) for k in need):
        _state["failed"] = True
        _state["error"] = "google-services.json topilmadi yoki to'liq emas"
        return False
    try:
        from jnius import autoclass
        FirebaseApp = autoclass("com.google.firebase.FirebaseApp")
        Builder = autoclass("com.google.firebase.FirebaseOptions$Builder")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        ctx = PythonActivity.mActivity
        # Ba'zan Firebase allaqachon init bo'lgan (plugin yoki boshqa kutubxona) — tekshiramiz.
        try:
            apps = FirebaseApp.getApps(ctx)
            if apps is not None and apps.size() > 0:
                _state["inited"] = True
                return True
        except Exception:
            pass
        b = Builder()
        b.setApiKey(str(ids["api_key"]))
        b.setApplicationId(str(ids["app_id"]))
        b.setProjectId(str(ids["project_id"]))
        b.setGcmSenderId(str(ids["sender_id"]))
        FirebaseApp.initializeApp(ctx, b.build())
        _state["inited"] = True
        return True
    except Exception as e:
        _state["failed"] = True
        _state["error"] = f"Firebase init: {e}"
        return False


def sync_topics(audiences):
    """
    audiences: ["all", "p12", "g3", ...] — common.my_audiences() natijasi.
    Yangi topiclarga obuna qiladi, ortiqchalarini bekor qiladi. Android'dagina ishlaydi.
    """
    if not is_android():
        return
    try:
        if not _init_firebase():
            return
        FirebaseMessaging = autoclass_msg()
        if FirebaseMessaging is None:
            return
        want = {str(a) for a in (audiences or []) if a}
        msg = FirebaseMessaging.getInstance()
        for t in sorted(want - _state["subscribed"]):
            msg.subscribeToTopic(t)
        for t in sorted(_state["subscribed"] - want):
            msg.unsubscribeFromTopic(t)
        _state["subscribed"] = want
        _state["error"] = None
    except Exception as e:
        _state["error"] = f"topic sync: {e}"


def autoclass_msg():
    try:
        from jnius import autoclass
        return autoclass("com.google.firebase.messaging.FirebaseMessaging")
    except Exception:
        return None


def request_notification_permission():
    """Android 13+ (API 33) da POST_NOTIFICATIONS ruxsatini bir marta so'rash."""
    if not is_android():
        return
    try:
        from jnius import autoclass
        VERSION = autoclass("android.os.Build$VERSION")
        if int(VERSION.SDK_INT) < 33:
            return
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        ContextCompat = autoclass("androidx.core.content.ContextCompat")
        perm = "android.permission.POST_NOTIFICATIONS"
        if ContextCompat.checkSelfPermission(activity, perm) == 0:   # PERMISSION_GRANTED
            return
        ActivityCompat = autoclass("androidx.core.app.ActivityCompat")
        ActivityCompat.requestPermissions(activity, [perm], 9001)
    except Exception:
        pass
