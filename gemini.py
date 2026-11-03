# -*- coding: utf-8 -*-
"""
Gemini API mijozi — himoyalangan (defensive).

Ikki vazifa:
  1) enhance_player_photo()  — o'yinchi rasmini yaxshilaydi, orqa fonni olib tashlaydi,
     FC Mobile uslubidagi oltin karta foniga joylaydi va tiniqlashtiradi.
  2) analyze_drill_video()   — mashq videosini tahlil qilib, berilgan kategoriya
     (shooting/pace/...) uchun 45-99 oralig'ida OVR taklif qiladi.

MUHIM:
  - config.py dagi GEMINI_API_KEY bo'sh bo'lsa, barcha funksiyalar None qaytaradi
    (ilova ishlashda davom etadi, hech qanday xato bermaydi).
  - Kalitni hech qachon GitHub'ga push qilmang! Uni faqat o'z kompyuteringizdagi
    config.py ga yozing. APK ichiga joylangan kalit xavfsiz emas.
  - Tarmoq/model xatolari yutiladi va None qaytariladi.
"""
import base64
import json
import re
import ssl
import urllib.error
import urllib.request

import config

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _CTX = ssl.create_default_context()

API_KEY = getattr(config, "GEMINI_API_KEY", "") or ""

# Rasm tahrirlash uchun image-generation modeli; video tahlili uchun multimodal model.
# Istasangiz config.py da GEMINI_MODEL_IMAGE / GEMINI_MODEL_VIDEO bilan almashtirasiz.
MODEL_IMAGE = getattr(config, "GEMINI_MODEL_IMAGE", "") or "gemini-2.5-flash-image"
MODEL_VIDEO = getattr(config, "GEMINI_MODEL_VIDEO", "") or "gemini-2.5-flash"

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Kategoriya -> atribut kodi va tavsifi (OVR belgilashda ishlatiladi)
DRILL_CATEGORIES = {
    "shooting":  ("sho", "aniq va kuchli zarba berish, darvozaga urish mahorati"),
    "pace":      ("pac", "yugurish tezligi, start va maksimal tezlik"),
    "dribbling": ("dri", "to'pni olib yurish, feynt va nazorat"),
    "passing":   ("pas", "uzatma aniqligi, vizyon va texnika"),
    "defending": ("def", "himoya, to'p tortib olish, pozitsiya"),
    "physical":  ("phy", "jismoniy kuch, chidamlilik, kurash"),
}

# Atribut kodlari (o'yinchi kartasida ko'rsatiladigan tartib)
ATTR_KEYS = ("pac", "sho", "pas", "dri", "def", "phy")
ATTR_MIN, ATTR_MAX = 45, 99
DEFAULT_ATTRS = {"pac": 50, "sho": 50, "pas": 50, "dri": 50, "def": 50, "phy": 50}


def available():
    """Gemini kaliti kiritilganmi?"""
    return bool(API_KEY)


def clamp_attr(value):
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return max(ATTR_MIN, min(ATTR_MAX, v))


def ovr_from_attrs(attrs):
    """Atributlardan umumiy OVR ni hisoblaydi (o'rtacha, yaxlitlangan)."""
    vals = [attrs.get(k) for k in ATTR_KEYS if isinstance(attrs.get(k), (int, float))]
    if not vals:
        return 50
    return int(round(sum(vals) / float(len(vals))))


# --------------------------------------------------------------------------
#  Past darajadagi HTTP so'rov
# --------------------------------------------------------------------------
def _post(model, payload, timeout=120):
    url = "%s/%s:generateContent?key=%s" % (_BASE, model, API_KEY)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def _extract_text(res):
    try:
        parts = res["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return ""
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict))


def _extract_image(res):
    """Javobdagi birinchi rasmni (base64, mime) qaytaradi yoki None."""
    try:
        parts = res["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return None
    for p in parts:
        if not isinstance(p, dict):
            continue
        blob = p.get("inlineData") or p.get("inline_data")
        if blob and blob.get("data"):
            return blob["data"], (blob.get("mimeType") or blob.get("mime_type") or "image/png")
    return None


# --------------------------------------------------------------------------
#  1) O'yinchi rasmini FC Mobile oltin kartasiga aylantirish
# --------------------------------------------------------------------------
_PHOTO_PROMPT = (
    "Turn this football (soccer) player photo into an FC Mobile style GOLD player card. "
    "Remove the original background completely and replace it with a premium shiny golden "
    "card background with subtle dark radial glow and elegant gold foil texture and thin "
    "gold border frame. Keep the player's face and body realistic and sharp, well lit, "
    "high detail, centered, portrait orientation. Do not add any text, numbers or logos. "
    "Sharpen the subject. Output a clean vertical card image."
)


def enhance_player_photo(image_b64, mime="image/jpeg"):
    """
    O'yinchi rasmini qayta ishlaydi.
    Qaytaradi: dict {"image_b64": str, "mime": str} yoki None (kalit/xato bo'lsa).
    """
    if not available() or not image_b64:
        return None
    payload = {
        "contents": [{
            "parts": [
                {"text": _PHOTO_PROMPT},
                {"inlineData": {"mimeType": mime, "data": image_b64}},
            ]
        }],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }
    try:
        res = _post(MODEL_IMAGE, payload)
    except Exception:
        return None
    img = _extract_image(res)
    if not img:
        return None
    return {"image_b64": img[0], "mime": img[1]}


# --------------------------------------------------------------------------
#  2) Mashq videosini tahlil qilib OVR taklif qilish
# --------------------------------------------------------------------------
def analyze_drill_video(video_b64, category, mime="video/mp4"):
    """
    Mashq videosini tahlil qiladi va kategoriya bo'yicha 45-99 OVR taklif qiladi.
    category: DRILL_CATEGORIES kalitlaridan biri (masalan "shooting").
    Qaytaradi: dict {"attr": kod, "score": int, "note": str} yoki None.
    """
    if not available() or not video_b64:
        return None
    cat = (category or "").strip().lower()
    attr, desc = DRILL_CATEGORIES.get(cat, ("sho", DRILL_CATEGORIES["shooting"][1]))
    prompt = (
        "You are a football (soccer) performance analyst. Watch this training drill video "
        "and rate the player's '%s' ability (%s) on a scale from %d to %d. "
        "Base the rating only on visible technique, speed, control and execution quality. "
        "Respond with ONLY strict JSON in this exact shape, no extra text:\n"
        '{"score": <integer %d-%d>, "note": "<one short sentence in Uzbek>"}'
        % (cat, desc, ATTR_MIN, ATTR_MAX, ATTR_MIN, ATTR_MAX)
    )
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": mime, "data": video_b64}},
            ]
        }],
        "generationConfig": {"temperature": 0.2},
    }
    try:
        res = _post(MODEL_VIDEO, payload, timeout=180)
    except Exception:
        return None
    text = _extract_text(res)
    score, note = _parse_score(text)
    if score is None:
        return None
    return {"attr": attr, "score": score, "note": note}


def _parse_score(text):
    """Javob matnidan {"score": N, "note": "..."} ni ajratib oladi."""
    if not text:
        return None, ""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            return clamp_attr(obj.get("score")), str(obj.get("note", "")).strip()
        except Exception:
            pass
    m = re.search(r"(\d{1,3})", text)
    return (clamp_attr(m.group(1)) if m else None), ""
