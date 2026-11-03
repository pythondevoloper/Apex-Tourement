# -*- coding: utf-8 -*-
# Firebase sozlamalari (README.md dagi 1-qadamga qarang)
FIREBASE_DB_URL = "https://apex-league-2e8fc-default-rtdb.europe-west1.firebasedatabase.app/"
FIREBASE_API_KEY = "AIzaSyB_eywUKDLB6UWChG7CmLircsYiEf9nRyM"
ADMIN_EMAIL = "computeruz559@gmail.com"
POLL_SECONDS = 6

# Gemini AI kaliti (o'yinchi kartasi rasmi + mashq video tahlili uchun).
# Kalitni GitHub'ga PUSH QILMANG! Bo'sh qoldirilsa AI funksiyalari o'chadi.
# Haqiqiy kalitni shu papkada GEMINI_SECRETS_FILE fayliga yozing (u .gitignore da).
#   masalan: gemini_secret.py ichida ->  GEMINI_API_KEY = "AIza..."
# Bepul kalit: https://aistudio.google.com
GEMINI_SECRETS_FILE = "gemini_secret.py"
GEMINI_API_KEY = ""
try:
    import importlib
    _sec = importlib.import_module(GEMINI_SECRETS_FILE[:-3])
    GEMINI_API_KEY = getattr(_sec, "GEMINI_API_KEY", "") or ""
except Exception:
    pass
