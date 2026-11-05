# -*- coding: utf-8 -*-
"""
Apex Pro League - umumiy qism (o'yinchi va admin ilovalari uchun).
Ma'lumotlar Firebase Realtime Database da saqlanadi (cloud.py), ikkala ilova bir xil
bazani ko'radi. O'zgartirishlar faqat admin ilovasida (Firebase Auth + qoidalar).
"""
import os
import io
import json
import time
import base64
import hashlib
import itertools
import threading
import traceback
import urllib.request

from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, Line, Ellipse
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.utils import platform
from kivymd.uix.floatlayout import MDFloatLayout

from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel, MDIcon
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.card import MDCard

import config
import push
import gemini
import glassui as G          # glass dizayn vidjetlari (o'yinchi/hakam/admin bir uslub)
import player_card as PC     # qalqon shaklidagi o'yinchi kartasi
from cloud import Firebase, RemoteStore, CloudError, TOKEN_START
from cloud import to_remote, from_remote, merge_into   # zaxira (backup) fayllari uchun

# Jamoa shakli: 1 darvozabon, 2 himoyachi, 1 yarim himoyachi, 2 hujumchi.
POS_QUOTA = {"GK": 1, "DF": 2, "MF": 1, "FW": 2}
# MF va FW o'zaro almashinadi: yarim himoyachi hujumda, hujumchi yarim himoyada
# o'ynay oladi. GK va DF boshqa pozitsiyada o'ynamaydi.
FLEX_SLOTS = ("MF", "FW")
LINEUP_SIZE = sum(POS_QUOTA.values())
LINEUP_LOCK_MIN = 15   # o'yin boshlanishidan shuncha daqiqa oldin tarkib avtomatik qulflanadi
CLOCK_HALF_MIN = 20    # hakam sekundomerida bir bo'lim davomiyligi (daqiqa)

# Ball tizimi
POINTS = {"goal": 3, "assist": 2, "win": 3, "yellow": -1, "red": -3}

# APEX TOKEN jarimalari (kod, nom, nechta token ketadi)
PENALTIES = [("late", "O'yinga kech qolish", 100),
             ("absent_bench", "O'yinga kelmaslik (zaxirada)", 200),
             ("absent_start", "O'yinga kelmaslik (asosiy tarkibda)", 300)]
PENALTY_BY_CODE = {c: v for c, _, v in PENALTIES}
PENALTY_NAMES = {c: n for c, n, _ in PENALTIES}
RED_PENALTY = 50                 # qizil kartochka uchun avtomatik jarima
TEAM_WIN_TOKENS = 200            # liga/final g'olibi jamoasiga APEX PRO TOKEN
OVR_DECAY_DAYS = 2               # token 0 bo'lsa: har shuncha kunda OVR -1
VERSION_CODE = 5                 # ilova versiyasi (version.json bilan solishtiriladi)
UPDATE_URL = getattr(config, "UPDATE_URL",
                     "https://raw.githubusercontent.com/pythondevoloper/Apex-Tourement/main/version.json")

# O'yinchi kartochkasi
POSITIONS = [("Darvozabon", "GK"), ("Himoyachi", "DF"),
             ("Yarim himoyachi", "MF"), ("Hujumchi", "FW")]
POS_NAME = {c: n for n, c in POSITIONS}
COUNTRIES = ["O'zbekiston", "Qozog'iston", "Qirg'iziston", "Tojikiston", "Turkmaniston",
             "Rossiya", "Turkiya", "Ozarbayjon", "Braziliya", "Argentina", "Portugaliya", "Ispaniya"]
DEFAULT_COUNTRY, DEFAULT_NUMBER, DEFAULT_POS = "O'zbekiston", 10, "MF"
BASE_OVR = 60          # admin o'zgartirmasa, boshlang'ich reyting
LOGO_COUNT = 12        # logo_1.png ... logo_12.png


# ---------------- Ranglar (Glassmorphism: binafsha→ko'k gradient, shisha kartalar) ----------------
GRAD_TOP = (0.294, 0.165, 0.549, 1)   # #4B2A8C binafsha — ekran yuqorisi
GRAD_BOT = (0.165, 0.294, 0.549, 1)   # #2A4B8C ko'k — ekran pasti
TRANSPARENT = (0, 0, 0, 0)

NAVY = (0.086, 0.075, 0.20, 1)        # to'q indigo: ekran zaxira foni
BLUE = (0.235, 0.176, 0.459, 1)       # toolbar / pastki nav (indigo)
CARD = (1, 1, 1, 0.10)                # shisha karta (yarim shaffof oq)
CARD2 = (1, 1, 1, 0.055)              # navbatma-navbat shisha qator
GOLD = (0.361, 0.820, 1.0, 1)         # aksent: yorqin firuza (cyan)
GOLD_HEX = "5CD1FF"
GREEN = (0.16, 0.62, 0.42, 1)         # draft ochiq
RED = (0.85, 0.29, 0.35, 1)           # draft yopiq
GROUP_COLORS = [(0.80, 0.22, 0.25, 1), (0.15, 0.45, 0.85, 1), (0.10, 0.60, 0.40, 1),
                (0.85, 0.50, 0.10, 1), (0.55, 0.30, 0.80, 1), (0.05, 0.60, 0.65, 1),
                (0.80, 0.30, 0.55, 1), (0.45, 0.55, 0.15, 1)]
HERE = os.path.dirname(os.path.abspath(__file__))
TROPHY = os.path.join(HERE, "trophy.png")


# ---------------- dialog vidjetlari: glass (eski KivyMD nomlari saqlangan) ----------------
OneLineListItem = G.MenuItem            # ro'yxat qatori (secondary_text ixtiyoriy)
TwoLineListItem = G.MenuItem


class MDRaisedButton(G.Btn):
    """Asosiy tugma: to'la rangli shisha."""

    def __init__(self, **kw):
        kw.setdefault("fill", GOLD)
        kw.setdefault("text_color", NAVY)
        super().__init__(**kw)


class MDFlatButton(G.Btn):
    """Ikkinci darajali tugma: shaffof, firuza matn."""

    def __init__(self, **kw):
        kw.setdefault("text_color", GOLD)
        super().__init__(**kw)


class StatRow(ButtonBehavior, MDBoxLayout):
    """Statistika jadvalidagi bosiladigan qator."""
    pass


def _glass_border(card, radius=None, color=(1, 1, 1, 0.16), width=1.0):
    """Shisha kartaga nozik nurli chegara chizadi (o'lcham o'zgarganda yangilanadi)."""
    try:
        r = radius
        if r is None:
            rr0 = getattr(card, "radius", None)
            r = rr0[0] if isinstance(rr0, (list, tuple)) and rr0 else 12
    except Exception:
        r = 12
    state = {"line": None}

    def _upd(*a):
        try:
            w, h = card.width, card.height
            if w <= 1 or h <= 1:
                return
            rr = min(r, w / 2, h / 2)
            if state["line"] is None:
                with card.canvas.after:
                    Color(*color)
                    state["line"] = Line(width=width,
                                         rounded_rectangle=(card.x, card.y, w, h, rr))
            else:
                state["line"].rounded_rectangle = (card.x, card.y, w, h, rr)
        except Exception:
            pass

    card.bind(pos=_upd, size=_upd)
    _upd()


def adaptive_card(**kw):
    """Ichidagi elementlarga qarab balandligi o'zgaradigan kartochka (MDCard da adaptive_height yo'q).

    size_hint_y chaqiruvchidan kelsa hurmat qilinadi (aks holda None): avval qattiq
    berilgani uchun `size_hint_y=None` uzatgan joyda 'multiple values' xatosi chiqardi.
    """
    kw.setdefault("size_hint_y", None)
    card = MDCard(**kw)
    card.bind(minimum_height=card.setter("height"))
    _glass_border(card)
    return card


# ---------------- Mockup uslubidagi "action" kartalar (admin dashboard) ----------------
ACCENTS = [
    (0.55, 0.36, 0.96, 1),   # binafsha
    (0.30, 0.55, 1.00, 1),   # ko'k
    (0.20, 0.80, 0.70, 1),   # firuza
    (0.95, 0.75, 0.25, 1),   # oltin
    (0.30, 0.80, 1.00, 1),   # och ko'k
    (0.95, 0.45, 0.70, 1),   # pushti
]


def glass_style(card, radius=16, accent=None, fill=(1, 1, 1, 0.15),
                border=(1, 1, 1, 0.34)):
    """Kuchaytirilgan shisha ko'rinish: yarim-shaffof to'ldirish + nurli oq chegara
    + ixtiyoriy accent rangli ichki glow (mockup 'liquid glass' uchun)."""
    try:
        card.md_bg_color = fill
    except Exception:
        pass
    _glass_border(card, radius=radius, color=border, width=1.5)
    if accent:
        st = {"l": None}

        def _g(*a):
            w, h = card.width, card.height
            if w <= 1 or h <= 1:
                return
            ins = dp(2.0)
            rr = min(radius, w / 2, h / 2)
            if st["l"] is None:
                with card.canvas.after:
                    Color(accent[0], accent[1], accent[2], 0.5)
                    st["l"] = Line(width=dp(1.3), rounded_rectangle=(
                        card.x + ins, card.y + ins, w - 2 * ins, h - 2 * ins, rr))
            else:
                st["l"].rounded_rectangle = (card.x + ins, card.y + ins,
                                             w - 2 * ins, h - 2 * ins, rr)
        card.bind(pos=_g, size=_g)
        _g()


def circle_icon(icon, color, d=46, icon_color=(1, 1, 1, 1)):
    """Rangli doira-ikonka + ortida yumshoq glow (mockup 'action' kartasi uchun)."""
    box = MDBoxLayout(size_hint=(None, None), size=(dp(d), dp(d)),
                      pos_hint={"center_y": 0.5})
    a = color[3] if len(color) > 3 else 1
    with box.canvas.before:
        Color(color[0], color[1], color[2], 0.28)
        glow = Ellipse(pos=box.pos, size=box.size)
        Color(color[0], color[1], color[2], a)
        solid = Ellipse(pos=box.pos, size=box.size)

    def _mv(*a2):
        cx, cy = box.center
        s = box.size[0]
        glow.size = (s * 1.7, s * 1.7)
        glow.pos = (cx - s * 0.85, cy - s * 0.85)
        solid.size = (s, s)
        solid.pos = (box.x, box.y)
    box.bind(pos=_mv, size=_mv)
    _mv()
    box.add_widget(MDIcon(icon=icon, theme_text_color="Custom", text_color=icon_color,
                          font_size=dp(24), size_hint=(None, None), size=(dp(d), dp(d)),
                          halign="center", valign="center"))
    return box


def make_action_card(icon, title, subtitle, cb, accent=None, height=88):
    """Bosiladigan kuchaytirilgan shisha 'action' karta: glow-ikonka + sarlavha +
    tavsif + chevron + accent nurli chegara."""
    accent = accent or ACCENTS[0]
    card = MDCard(orientation="horizontal", size_hint_y=None, height=dp(height),
                  radius=[16], md_bg_color=(1, 1, 1, 0.15), padding=dp(10), spacing=dp(10))
    card.size_hint_x = 1          # BoxLayout ustunida teng kenglik olishi uchun
    card.bind(on_release=lambda *a: cb())
    card.add_widget(circle_icon(icon, accent))
    col = MDBoxLayout(orientation="vertical", spacing=dp(2))
    col.add_widget(MDLabel(text="[b]%s[/b]" % title, markup=True, font_style="Subtitle2",
                           theme_text_color="Custom", text_color=(1, 1, 1, 0.96)))
    col.add_widget(MDLabel(text=subtitle, font_style="Caption", theme_text_color="Custom",
                           text_color=(1, 1, 1, 0.62)))
    card.add_widget(col)
    card.add_widget(MDIcon(icon="chevron-right", theme_text_color="Custom",
                           text_color=(1, 1, 1, 0.42), size_hint=(None, None),
                           size=(dp(22), dp(22)), pos_hint={"center_y": 0.5}))
    glass_style(card, radius=16, accent=accent)
    return card


def make_card_rows(items, cols=2, height=88, spacing=8, accent0=0):
    """items: [(icon, title, subtitle, cb), ...] — cols ustunli qatorlar (GridLayout emas).

    GridLayout MDCard kengligini boshqara olmaydi (size_hint_y=None bo'lsa kartalar
    ko'rinmay qoladi), shuning uchun har qatorni gorizontal MDBoxLayout qilamiz:
    har karta size_hint_x=1 bilan teng bo'linadi.
    """
    rows = (len(items) + cols - 1) // cols
    wrap = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(spacing),
                       height=dp(rows * height + max(0, rows - 1) * spacing))
    for i in range(0, len(items), cols):
        row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(height), spacing=dp(spacing))
        chunk = items[i:i + cols]
        for j, it in enumerate(chunk):
            accent = ACCENTS[(accent0 + i + j) % len(ACCENTS)]
            row.add_widget(make_action_card(it[0], it[1], it[2], it[3], accent, height))
        for _ in range(cols - len(chunk)):
            sp = Widget()
            sp.size_hint_x = 1
            row.add_widget(sp)
        wrap.add_widget(row)
    return wrap


def initials(name):
    """Ismning bosh harflari (avatar uchun): 'Jasur Karimov' -> 'JK'."""
    parts = [w for w in str(name).split() if w]
    s = "".join(w[0] for w in parts[:2]).upper()
    return s or "?"


def glow_badge(color, d=44, icon=None, text=None, text_color=(1, 1, 1, 1),
               font_style="Subtitle2"):
    """Glow halqali doira: ichida ikonka yoki bosh harflar (avatar / jamoa logotipi)."""
    box = MDBoxLayout(size_hint=(None, None), size=(dp(d), dp(d)), pos_hint={"center_y": 0.5})
    a = color[3] if len(color) > 3 else 1
    with box.canvas.before:
        Color(color[0], color[1], color[2], 0.28)
        glow = Ellipse(pos=box.pos, size=box.size)
        Color(color[0], color[1], color[2], a)
        solid = Ellipse(pos=box.pos, size=box.size)

    def _mv(*_):
        cx, cy = box.center
        s = box.size[0]
        glow.size = (s * 1.6, s * 1.6)
        glow.pos = (cx - s * 0.8, cy - s * 0.8)
        solid.size = (s, s)
        solid.pos = (box.x, box.y)
    box.bind(pos=_mv, size=_mv)
    _mv()
    if icon:
        box.add_widget(MDIcon(icon=icon, theme_text_color="Custom", text_color=text_color,
                              font_size=dp(int(d * 0.5)), size_hint=(None, None),
                              size=(dp(d), dp(d)), halign="center", valign="center"))
    elif text is not None:
        box.add_widget(MDLabel(text="[b]%s[/b]" % text, markup=True, halign="center",
                               valign="center", font_style=font_style,
                               theme_text_color="Custom", text_color=text_color))
    return box


def glass_panel(orientation="vertical", radius=16, fill=(1, 1, 1, 0.12),
                border=(1, 1, 1, 0.30), width=1.4, **kw):
    """Nurli chegarali yarim shaffof shisha panel (accentsiz)."""
    card = MDCard(orientation=orientation, radius=[radius], md_bg_color=fill, **kw)
    _glass_border(card, radius=radius, color=border, width=width)
    return card


class GlassChip(MDCard):
    """Filtr chiplari uchun bittasi — bosiladigan, tanlanganda nurli to'ladi."""

    def __init__(self, name, bar, unit=7.2, **kw):
        super().__init__(orientation="horizontal", size_hint=(None, None),
                         size=(dp(80), dp(38)), radius=[14], md_bg_color=(1, 1, 1, 0.10),
                         padding=(dp(14), dp(8)), **kw)
        self.name = name
        self.bar = bar
        self.lbl = MDLabel(text=name, theme_text_color="Custom", text_color=(1, 1, 1, 0.6),
                           font_style="Caption", halign="center", valign="center")
        self.add_widget(self.lbl)
        self.width = dp(24) + len(str(name)) * dp(unit)
        self.bind(on_release=lambda *a: self.bar.select(self.name))

    def set_on(self, on):
        self.md_bg_color = (0.30, 0.42, 0.85, 0.90) if on else (1, 1, 1, 0.10)
        self.lbl.text_color = (1, 1, 1, 0.98) if on else (1, 1, 1, 0.6)


class GlassChips(MDBoxLayout):
    """Gorizontal filtr chip'lari qatori. select(name) orqali bittasi yoriladi."""

    def __init__(self, names, on_select=None, unit=7.2, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(42),
                         spacing=dp(8), **kw)
        self.on_select = on_select
        self.by = {}
        for n in names:
            c = GlassChip(n, self, unit=unit)
            self.by[n] = c
            self.add_widget(c)
        self.current = None
        if names:
            self.select(names[0])

    def select(self, name):
        for k, c in self.by.items():
            c.set_on(k == name)
        self.current = name
        if self.on_select:
            self.on_select(name)

    def reselect(self, name):
        """Faqat ko'rinishni belgilaydi, callback chaqirmaydi (qayta chizishda)."""
        for k, c in self.by.items():
            c.set_on(k == name)
        self.current = name


class GradientBackground(Widget):
    """Vertikal binafsha→ko'k gradient fon (glassmorphism). Ekran ortiga qo'yiladi.

    Kivy'da tayyor gradient primitiv yo'q — ingichka rangli bo'laklar bilan
    silliq vertikal gradient chizamiz. O'lcham/o'rin o'zgarganda qayta chiziladi.
    """

    def __init__(self, c_top=GRAD_TOP, c_bot=GRAD_BOT, steps=64, **kw):
        super().__init__(**kw)
        self._c_top, self._c_bot, self._steps = c_top, c_bot, steps
        self.bind(size=self._redraw, pos=self._redraw)
        self._redraw()

    def _redraw(self, *a):
        self.canvas.before.clear()
        n = max(2, self._steps)
        h = self.height / n
        if h <= 0 or self.width <= 0:
            return
        r0, g0, b0 = self._c_top[:3]
        r1, g1, b1 = self._c_bot[:3]
        with self.canvas.before:
            for i in range(n):
                t = i / (n - 1)          # 0 = past (c_bot), 1 = yuqori (c_top)
                Color(r1 + (r0 - r1) * t, g1 + (g0 - g1) * t, b1 + (b0 - b1) * t, 1)
                Rectangle(pos=(self.x, self.y + h * i), size=(self.width, h + 0.6))
            # Yumshoq nur dog'lari (glassmorphism 'liquid' effekti uchun).
            blobs = [(0.18, 0.82, ACCENTS[0]), (0.86, 0.66, ACCENTS[1]),
                     (0.5, 0.12, ACCENTS[4]), (0.9, 0.2, ACCENTS[5])]
            for fx, fy, col in blobs:
                cx = self.x + self.width * fx
                cy = self.y + self.height * fy
                R = self.width * 0.55
                for k in range(6, 0, -1):
                    rr = R * k / 6.0
                    Color(col[0], col[1], col[2], 0.05)
                    Ellipse(pos=(cx - rr, cy - rr), size=(rr * 2, rr * 2))


class LogoButton(ButtonBehavior, Image):
    """Bosiladigan logo."""
    pass


def logo_path(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 0
    if not 1 <= n <= LOGO_COUNT:
        return TROPHY
    return os.path.join(HERE, f"logo_{n}.png")


def hash_pw(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


# Kapitan paroli uchun: bitta sha256 telefon CPU'sida millionlab marta/s tekshiriladi,
# shuning uchun PBKDF2 bilan sekinlashtiramiz (login paytida ~0.1 s kutish normal).
PBKDF2_ROUNDS = 120000


def hash_secret(secret, salt):
    return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"),
                               salt.encode("utf-8"), PBKDF2_ROUNDS).hex()


def now_ts():
    return int(time.time())


# --------------------------------------------------------------------------
#  Rasmlar: telefondan yuklash va bazada base64 ko'rinishida saqlash
# --------------------------------------------------------------------------
def image_to_b64(path, size=96):
    """Rasmni kichraytirib JPEG base64 ga o'giradi (Firebase uchun yengil)."""
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((size, size))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=72)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def b64_to_path(key, b64):
    """Base64 rasmni diskka yozib, yo'lini qaytaradi (Kivy Image uchun)."""
    d = os.path.join(HERE, "uploads")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, key + ".jpg")
    data = base64.b64decode(b64)
    old = None
    if os.path.exists(p):
        with open(p, "rb") as f:
            old = f.read()
    if old != data:
        with open(p, "wb") as f:
            f.write(data)
    return p


def shrink_b64(b64, size=420, quality=78):
    """Base64 rasmni kichraytirib JPEG base64 ga o'giradi (Firebase uchun yengil)."""
    from PIL import Image as PILImage
    im = PILImage.open(io.BytesIO(base64.b64decode(b64)))
    im = im.convert("RGB")
    im.thumbnail((size, size))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def pick_media_file(mime, ext, title, callback):
    """callback(yo'l) ni tanlangan media fayli bilan chaqiradi. Android: fayl tanlagich, desktop: tkinter."""
    try:
        from jnius import autoclass
        from android import activity
        Intent = autoclass("android.content.Intent")

        def on_result(request_code, result_code, intent):
            try:
                activity.unbind(on_activity_result=on_result)
            except Exception:
                pass
            if result_code != -1 or intent is None or intent.getData() is None:
                return
            resolver = autoclass("org.kivy.android.PythonActivity").mActivity.getContentResolver()
            stream = resolver.openInputStream(intent.getData())
            buf = io.BytesIO()
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                buf.write(bytes(chunk))
            stream.close()
            d = os.path.join(HERE, "uploads")
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "pick_tmp." + ext)
            with open(p, "wb") as f:
                f.write(buf.getvalue())
            callback(p)
        activity.bind(on_activity_result=on_result)
        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.setType(mime)
        activity.startActivityForResult(intent)
        return
    except Exception:
        pass
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        p = filedialog.askopenfilename(filetypes=[(title, "*." + ext)])
        root.destroy()
        if p:
            callback(p)
    except Exception:
        toast("Fayl tanlab bo'lmadi")


def pick_image_file(callback):
    pick_media_file("image/*", "jpg", "Rasm", callback)


def pick_video_file(callback):
    pick_media_file("video/*", "mp4", "Video", callback)


def video_to_b64(path, max_mb=18):
    """Video faylni base64 ga o'giradi. Katta fayllarni rad etadi (Gemini cheklovi)."""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) > max_mb * 1024 * 1024:
        raise ValueError("video juda katta")
    return base64.b64encode(data).decode("ascii")


def open_url(url):
    try:
        from jnius import autoclass
        from android import activity
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        i = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        activity.startActivity(i)
        return
    except Exception:
        pass
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


def media_store_uri(path, mime):
    """Faylni MediaStore ga nusxalab content:// URI qaytaradi.

    Android 7+ 'Ulashish' oynasi file:// URI ni rad etadi (FileUriExposedException),
    shuning uchun tizim kutubxonasidagi manzil ishlatiladi.
    """
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    ContentValues = autoclass("android.content.ContentValues")
    MediaStore = autoclass("android.provider.MediaStore")
    Files = autoclass("java.nio.file.Files")
    Paths = autoclass("java.nio.file.Paths")
    ctx = PythonActivity.mActivity
    vals = ContentValues()
    vals.put("_display_name", os.path.basename(path))
    vals.put("mime_type", mime)
    if mime.startswith("image/"):
        vals.put("relative_path", "Pictures/")
        coll = MediaStore.Images.Media.EXTERNAL_CONTENT_URI
    else:
        vals.put("relative_path", "Download/")
        coll = MediaStore.Downloads.EXTERNAL_CONTENT_URI
    uri = ctx.getContentResolver().insert(coll, vals)
    if uri is None:
        raise IOError("MediaStore ruxsat bermadi")
    out = ctx.getContentResolver().openOutputStream(uri)
    try:
        Files.copy(Paths.get(path), out)
    finally:
        out.close()
    return uri


def share_file(path, mime="*/*", title="Ulashish"):
    """Faylni tizim 'Ulashish' oynasiga beradi (Telegram/WhatsApp/Drive...)."""
    try:
        from jnius import autoclass
        from android import activity
        Intent = autoclass("android.content.Intent")
        try:
            uri = media_store_uri(path, mime)
        except Exception:
            uri = autoclass("android.net.Uri").fromFile(autoclass("java.io.File")(path))
        i = Intent(Intent.ACTION_SEND)
        i.setType(mime)
        i.putExtra(Intent.EXTRA_STREAM, uri)
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        activity.startActivity(Intent.createChooser(i, title))
        return True
    except Exception:
        pass
    try:
        import webbrowser
        webbrowser.open("file:///" + os.path.abspath(path).replace("\\", "/"))
        toast("Fayl ochildi: " + os.path.basename(path))
        return True
    except Exception:
        toast("Fayl saqlandi: " + path)
        return False


# --------------------------------------------------------------------------
#  Ma'lumotlar ombori (JSON)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
#  Boshlang'ich sozlash ekrani
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
#  Asosiy ilova
# --------------------------------------------------------------------------
class _CrashGuard(ExceptionHandler):
    """Kutilmagan xatoda ilova yopilmasin: xato matni ekranda ko'rsatiladi va faylga yoziladi."""

    def handle_exception(self, inst):
        try:
            app = MDApp.get_running_app()
            if app is not None:
                app.report_crash(inst)
        except Exception:
            pass
        return ExceptionManager.PASS


class Chip(MDCard):
    """Tanlanadigan belgi (pozitsiya, davlat).

    Kenglik matn bo'yicha: belgilangan 72dp kenglik "Darvozabon" kabi uzun
    so'zlarni ikki qatorga bo'lib, xato joydan kesib tashlardi.
    """

    def __init__(self, text, value=None, **kw):
        kw.setdefault("size_hint_x", None)
        kw.setdefault("width", max(dp(64), min(dp(170), dp(26) + dp(9.4) * len(text or ""))))
        super().__init__(size_hint_y=None, height=dp(46), radius=[12], padding=(dp(8), 0),
                         md_bg_color=CARD, ripple_behavior=True, **kw)
        _glass_border(self, radius=12)
        self.value = value
        self.label = MDLabel(text=text, halign="center", theme_text_color="Custom",
                             text_color=(1, 1, 1, 1))
        self.add_widget(self.label)

    def set_on(self, on):
        self.md_bg_color = GOLD if on else CARD
        self.label.text_color = NAVY if on else (1, 1, 1, 1)


def glass_field(hint, max_len=None, digits=False, password=False, text=""):
    """Glass paneldagi matn maydoni (prototip uslubi)."""
    # Kivy TextInput padding = [chap, yuqori, o'ng, past] (4 ta). 2 ta berilsa
    # 3-chi element IndexError bo'ladi, shuning uchun to'liq ro'yxat yozamiz.
    # padding_top = (balandlik - qator balandligi) / 2 matnni vertikal markazlaydi.
    tf = G.TextInput(hint_text=hint, text=text, multiline=False, password=password,
                     background_color=(0, 0, 0, 0.28), foreground_color=(1, 1, 1, 1),
                     hint_text_color=G.MUTED, cursor_color=G.CYAN,
                     font_size=dp(15), padding=[dp(12), dp(14), dp(12), dp(14)],
                     size_hint_y=None, height=dp(48))
    if max_len:
        tf.max_length = max_len
    if digits:
        tf.input_filter = "int"
    return tf


class PosBar(G.BoxLayout):
    """Pozitsiya tanlash chiplari. Dastlab hech biri tanlanmagan - o'yinchi o'zi tanlaydi."""

    def __init__(self, **kw):
        super().__init__(size_hint_y=None, height=dp(42), spacing=dp(8), **kw)
        self.value = None
        self.chips = {}
        for _, code in POSITIONS:
            c = G.GlassButton(size_hint_x=1, radius=12)
            c.lbl = G.TL(code, 14, G.MUTED, bold=True, align="center")
            c.add_widget(c.lbl)
            c.bind(on_release=lambda w, k=code: self.select(k))
            self.chips[code] = c
            self.add_widget(c)
        self.deselect()

    def deselect(self):
        self.value = None
        for c in self.chips.values():
            c.set_style(G.GLASS, G.BORDER)
            c.lbl.color = G.MUTED

    def select(self, code):
        self.value = code
        for k, c in self.chips.items():
            on = k == code
            c.set_style(G.BLUE if on else G.GLASS, G.CYAN if on else G.BORDER)
            c.lbl.color = (1, 1, 1, 1) if on else G.MUTED


class RegisterScreen(MDScreen):
    """O'yinchi o'zi ro'yxatdan o'tadi: Ism, Familiya, raqam va pozitsiyasi so'raladi."""

    def __init__(self, **kw):
        super().__init__(**kw)
        root = FloatLayout()
        root.add_widget(G.Background())
        ui = G.BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(16), dp(20)))
        ui.add_widget(G.TL("APEX [b]PRO LEAGUE[/b]", 20, align="center",
                           size_hint_y=None, height=dp(34)))
        ui.add_widget(G.note(
            "Ma'lumotlaringizni kiriting. Ro'yxatdan o'tgach admin sizni guruhga "
            "biriktiradi va ilova to'liq ishga tushadi.", size=11.5))
        card = G.Glass(orientation="vertical", size_hint_y=None, spacing=dp(10),
                       padding=(dp(16), dp(16)), radius=22)
        card.bind(minimum_height=card.setter("height"))
        self.first_field = glass_field("Ism", max_len=30)
        self.last_field = glass_field("Familiya", max_len=30)
        self.num_field = glass_field("O'yindagi raqam (1-99)", max_len=2, digits=True)
        self.pos_bar = PosBar()
        for f in (self.first_field, self.last_field, self.num_field):
            card.add_widget(f)
        card.add_widget(G.TL("Pozitsiyangiz", 12, G.CYAN, bold=True))
        card.add_widget(self.pos_bar)
        card.add_widget(G.note("GK darvozabon  ·  DF himoyachi  ·  MF yarim himoyachi  ·  "
                               "FW hujumchi", size=10.5))
        ui.add_widget(card)
        ui.add_widget(Widget())
        ui.add_widget(G.solid_button("Yuborish", self.submit, h=52, fill=G.GREEN, size=15))
        root.add_widget(ui)
        self.add_widget(root)

    def reset(self):
        self.first_field.text = ""
        self.last_field.text = ""
        self.num_field.text = ""
        self.pos_bar.deselect()

    def submit(self):
        MDApp.get_running_app().submit_registration(
            self.first_field.text, self.last_field.text, self.num_field.text,
            self.pos_bar.value)


class StatusScreen(MDScreen):
    """Yuklanish / ulanish xatosi / turnir sozlanmagan ekrani."""

    def __init__(self, **kw):
        super().__init__(**kw)
        root = FloatLayout()
        root.add_widget(G.Background())
        box = G.BoxLayout(orientation="vertical", spacing=dp(16), padding=(dp(28), dp(24)))
        box.add_widget(Widget())
        badge = G.Badge(G.CYAN, 132, image=TROPHY if os.path.exists(TROPHY) else None,
                        icon=None if os.path.exists(TROPHY) else "trophy-outline")
        badge.pos_hint = {"center_x": .5}
        box.add_widget(badge)
        self.label = G.TL("Yuklanmoqda...", 14, G.MUTED, align="center", shorten=False,
                          valign="top", size_hint_y=None, height=dp(100))
        box.add_widget(self.label)
        self.btn = G.solid_button("Qayta urinish",
                                  lambda: MDApp.get_running_app().start_sync(),
                                  h=48, fill=G.BLUE, size=14)
        box.add_widget(self.btn)
        box.add_widget(Widget())
        root.add_widget(box)
        self.add_widget(root)

    def set(self, text, retry=True):
        self.label.text = text
        self.btn.opacity = 1 if retry else 0
        self.btn.disabled = not retry


class RefClockPanel(G.Glass):
    """Hakam sekundomeri paneli: jonli mm:ss + bo'lim almashtirish.

    Vaqt faqat shu qurilmada saqlanadi (clock.json) — bazaga yozilmaydi, shuning
    uchun boshqa telefonlar uni ko'rmaydi. Gol kiritilganda esa daqiqa
    bazadagi gol yoziga qo'shib qo'yiladi (jurnal shu daqiqani ko'rsatadi).
    """

    def __init__(self, mid, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, spacing=dp(8),
                         padding=(dp(12), dp(12)), radius=18,
                         fill=(0.055, 0.08, 0.21, 1), border=(0.35, 0.75, 1, .55), **kw)
        self.bind(minimum_height=self.setter("height"))
        self.mid = mid
        self.app = MDApp.get_running_app()
        self.time_lbl = G.TL("00:00", 40, G.WHITE, bold=True, align="center",
                             size_hint_y=None, height=dp(52))
        self.half_lbl = G.TL("", 12.5, G.CYAN, align="center", size_hint_y=None, height=dp(22))
        self.add_widget(self.time_lbl)
        self.add_widget(self.half_lbl)
        row = G.BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.run_btn = G.solid_button("Boshlash", self.toggle, h=48, fill=G.GREEN)
        row.add_widget(self.run_btn)
        row.add_widget(G.solid_button("Bo'lim", self.next_half, h=48, fill=G.INDIGO))
        row.add_widget(G.solid_button("Nolga", self.reset, h=48, fill=RED))
        self.add_widget(row)
        self.add_widget(G.note("Gol kiritganda shu soatning daqiqasi jurnalga yoziladi.", size=10.5))
        self._ev = Clock.schedule_interval(self.redraw, 0.25)
        self.bind(parent=self._gone)
        self.redraw(0)

    def _gone(self, widget, parent):
        """Dialog yopilganda (parent=None) jonli yangilanishni to'xtatamiz."""
        if parent is None:
            self._ev.cancel()
            self._ev = None

    @property
    def st(self):
        return self.app.clock_state(self.mid)

    def redraw(self, *a):
        s = self.st
        sec = self.app.clock_seconds(s)
        self.time_lbl.text = "%02d:%02d" % (sec // 60, sec % 60)
        self.half_lbl.text = "%d-bo'lim  ·  %s" % (
            s["half"], "YURMOQDA" if s["since"] else ("pauza" if s["acc"] else "to'xtagan"))
        self.run_btn.lbl.text = "Pauza" if s["since"] else "Boshlash"
        self.run_btn.set_style(fill=RED if s["since"] else G.GREEN)

    def toggle(self, *a):
        self.app.clock_toggle(self.mid)
        self.redraw(0)

    def next_half(self, *a):
        self.app.clock_next_half(self.mid)
        self.redraw(0)

    def reset(self, *a):
        def yes(*b):
            self.app.clock_reset(self.mid)
            self.redraw(0)
        self.app.confirm_dialog("Sekundomeri nolga qaytarilsinmi?",
                                "Vaqt 00:00 bo'ladi va 1-bo'limga qaytadi.", yes)


class LeagueApp(MDApp):
    dialog = None
    ADMIN_APP = False                  # AdminApp da True
    REFEREE_APP = False                # RefereeApp da True
    CAPTAIN_APP = False                # CaptainApp da True (kapitan login/parol bilan kiradi)
    APP_TITLE = "Apex Tournament"
    TOOLBAR_NAME = "Apex Pro League"
    CACHE_NAME = "apex_cache.json"
    _polling = False

    # ---------------- ishga tushirish ----------------
    # ---------------- ishga tushirish ----------------
    def build(self):
        try:
            ExceptionManager.add_handler(_CrashGuard())
        except Exception:
            pass
        try:
            return self._build_app()
        except Exception:
            if getattr(config, "DEBUG_RAISE", False):
                raise
            text = traceback.format_exc()
            self._write_crash(text)
            sv = ScrollView()
            lab = MDLabel(text="Ilova ishga tushmadi. Shu matnning skrinshotini yuboring:\n\n" + text[-1500:],
                          size_hint_y=None, font_style="Caption", padding=(dp(12), dp(12)))
            lab.bind(texture_size=lambda i, v: setattr(i, "height", v[1] + dp(24)))
            sv.add_widget(lab)
            return sv

    # ---------------- kutilmagan xatolar ----------------
    _crash_shown = False

    def _write_crash(self, text):
        try:
            with open(os.path.join(self.user_data_dir, "crash.log"), "a", encoding="utf-8") as f:
                f.write(text + "\n-----\n")
        except Exception:
            pass

    def report_crash(self, exc):
        text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        self._write_crash(text)
        if self._crash_shown:
            return
        self._crash_shown = True
        Clock.schedule_once(lambda dt: self._show_crash(text), 0)

    def _show_crash(self, text):
        try:
            lab = G.Wrap("Ilova ishlashda davom etadi. Xato matnining skrinshotini yuboring:\n\n"
                         + text.strip()[-900:], size=11.5, align="left")
            body = BoxLayout(orientation="vertical")
            body.add_widget(lab)
            self.show_dialog("Xatolik yuz berdi", content=body)
        except Exception:
            pass
        Clock.schedule_once(lambda dt: setattr(self, "_crash_shown", False), 5)

    def _on_key(self, window, key, *args):
        """Android 'Orqaga' tugmasi: avval ochiq dialogni yopadi, keyin ro'yxat
        ekranidan chiqsa holat qayta tekshiriladi."""
        if key != 27:
            return False
        if getattr(self, "dialog", None) is not None:
            self.close_dialog()
            return True
        if self.sm.current == "register":
            self.route()
            return True
        return False

    def _build_app(self):
        self.title = self.APP_TITLE
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.accent_palette = "Cyan"
        self.theme_cls.theme_style = "Dark"
        self.icon = TROPHY
        Window.softinput_mode = "below_target"

        self.fb = Firebase(config.FIREBASE_DB_URL, config.FIREBASE_API_KEY)
        self.store = RemoteStore(self.fb, os.path.join(self.user_data_dir, self.CACHE_NAME))
        self.store.on_error = lambda msg: toast(msg)
        self.store.load_cache()          # oflayn ochilish uchun oxirgi ma'lumot

        self.sm = MDScreenManager()
        self.main_screen = self.build_main()
        self.status_screen = StatusScreen(name="status", md_bg_color=NAVY)
        self.sm.add_widget(self.main_screen)
        self.sm.add_widget(self.status_screen)
        if not self.ADMIN_APP and not self.CAPTAIN_APP:
            self.register_screen = RegisterScreen(name="register", md_bg_color=NAVY)
            self.sm.add_widget(self.register_screen)
        self.build_extra_screens()
        Window.bind(on_keyboard=self._on_key)
        self.sm.current = self.first_screen()
        Clock.schedule_once(lambda dt: push.request_notification_permission(), 1.0)
        Clock.schedule_once(lambda dt: self.start_sync(), 0.3)
        Clock.schedule_interval(self.poll, getattr(config, "POLL_SECONDS", 6))
        Clock.schedule_interval(self._lock_tick, 20)
        self.check_update()
        return self.sm

    def _lock_tick(self, *a):
        """Boshlanish vaqti yetganda qulf holati o'zgaradi: ochiq Tarkib tab'ini yangilaymiz."""
        sig = tuple((m["id"], self.lineup_closed(m)) for m in self.d["matches"])
        if sig == self.__dict__.get("_lock_sig"):
            return
        self._lock_sig = sig
        if (self.sm.current == "main" and getattr(self, "_content_sm", None) is not None
                and self._content_sm.current == "lineup"):
            self.refresh_lineup()

    # ---------------- ilova yangilanishini tekshirish ----------------
    def check_update(self, *a):
        def work():
            try:
                with urllib.request.urlopen(UPDATE_URL, timeout=8) as r:
                    info = json.loads(r.read().decode("utf-8"))
            except Exception:
                return
            Clock.schedule_once(lambda dt: self._update_info(info), 0)
        threading.Thread(target=work, daemon=True).start()

    def _update_info(self, info):
        try:
            ver = int(info.get("version", 0))
        except (TypeError, ValueError):
            return
        if ver <= VERSION_CODE:
            return
        me = self.load_me()
        if me.get("seen_update") == ver:
            return
        me["seen_update"] = ver
        self._save_me(me)
        buttons = [MDFlatButton(text="Keyinroq", on_release=self.close_dialog),
                   MDRaisedButton(text="Yuklab olish",
                                  on_release=lambda *a: (self.close_dialog(),
                                                         open_url(info.get("url") or UPDATE_URL)))]
        self.show_dialog(f"Yangi versiya mavjud (v{ver})",
                         text=(info.get("note") or "Ilova yangilandi.")
                              + "\n\nBarcha ma'lumotlaringiz (bazada) saqlanib qoladi.",
                         buttons=buttons)

    # --- ilovaga xos qismlar (AdminApp o'zgartiradi) ---
    def build_extra_screens(self):
        pass

    def first_screen(self):
        return "status"

    def route(self):
        """Ma'lumot yuklangach qaysi ekranni ko'rsatishni hal qiladi.

        O'yinchi oqimi: turnir boshlanmagan -> kuting; boshlangan, lekin hali
        ro'yxatdan o'tmagan -> register; o'tgan, lekin guruhga biriktirilmagan ->
        'admin guruhga bo'lgach' xabari; guruhga tushgan -> asosiy ilova.
        """
        if not self.d["setup_done"]:
            self.status_screen.set(
                "Turnir hali boshlanmagan.\nAdmin 'Turnirni boshlash' tugmasini bosgach, "
                "ro'yxatdan o'tishingiz mumkin bo'ladi.", True)
            self.sm.current = "status"
            return
        pid = self.my_pid()
        p = self.player(pid) if pid else None
        if p is None:
            self.register_screen.reset()
            self.sm.current = "register"
            return
        if p["group"] is None:
            self.status_screen.set(
                f"Assalomu alaykum, [b]{p['name']}[/b]!\n\n"
                "Kuting — admin sizni guruhga biriktirgach ilova to'liq ishga tushadi.", True)
            self.sm.current = "status"
            return
        self.sm.current = "main"
        self.refresh_all()
        self.sync_push()

    def on_pause(self):
        return True

    def on_resume(self):
        self.poll(0)

    # ---------------- bulut bilan sinxronlash ----------------
    @staticmethod
    def config_ok():
        return "SIZNING" not in config.FIREBASE_DB_URL and "SIZNING" not in config.FIREBASE_API_KEY

    def start_sync(self, *a):
        """To'liq yangilash (ishga tushganda va 'Qayta urinish' bosilganda)."""
        if not self.config_ok():
            self.status_screen.set("config.py to'ldirilmagan:\nFirebase manzili va API kalitini kiriting.", False)
            self.sm.current = "status"
            return
        if self.sm.current == "status":
            self.status_screen.set("Serverga ulanmoqda...", False)
        self.store.etag = None

        def work():
            res = err = None
            try:
                res = self.store.fetch()
            except CloudError as e:
                err = e
            Clock.schedule_once(lambda dt: self._sync_done(res, err))
        threading.Thread(target=work, daemon=True).start()

    def _sync_done(self, res, err):
        if res:
            self.store.apply(res)
        if err and not self.d["setup_done"]:
            self.status_screen.set("Internetga ulanib bo'lmadi.\nUlanishni tekshirib, qayta urinib ko'ring.", True)
            self.sm.current = "status"
            return
        self.route()

    def poll(self, dt):
        """Har bir necha soniyada o'zgarishlarni tekshiradi (ETag: o'zgarmasa deyarli trafik yo'q)."""
        if self._polling or not self.config_ok():
            return
        self._polling = True

        def work():
            res = err = None
            try:
                res = self.store.fetch()
            except CloudError as e:
                err = e
            Clock.schedule_once(lambda dt: self._poll_done(res, err))
        threading.Thread(target=work, daemon=True).start()

    def _poll_done(self, res, err):
        self._polling = False
        changed = self.store.apply(res) if res else False
        if self.sm.current == "main":
            if changed:
                self.refresh_all()
            else:
                self.update_toolbar()
        elif self.sm.current == "status" and self.d["setup_done"]:
            self.route()

    def update_toolbar(self):
        """Header'dagi qator: so'rov soni, oflayn belgisi va yangi xabar nuqtasi."""
        h = getattr(self, "pl_header", None)
        if h is None:
            return
        on = "" if self.store.online else "  ·  OFLAYN"
        h.set_sub("So'rov: %d ta%s" % (len(self.free_players()), on))
        try:
            h.set_dot(bool(self.unread_notifs()))
        except Exception:
            pass

    # ---------------- UI qurish ----------------
    def build_main(self):
        """O'yinchi/hakam — glass prototip uslubi (admin.py bilan bir xil):
        gradient fon, Header, ichki ScreenManager va pastda NavBar."""
        if platform not in ("android", "ios"):
            try:
                Window.size = (390, 800)
            except Exception:
                pass
        scr = MDScreen(name="main", md_bg_color=NAVY)
        root = FloatLayout()
        root.add_widget(G.Background())
        mobile = platform in ("android", "ios")
        ui = G.BoxLayout(orientation="vertical", spacing=dp(10),
                         padding=(dp(12), dp(30) if mobile else dp(10), dp(12), dp(10)))

        self.pl_header = G.Header(
            on_bell=lambda: self.show_notifs(),
            on_user=lambda: self.profile_dialog(),
            on_search=None if (self.REFEREE_APP or self.CAPTAIN_APP) else (lambda: self.search_dialog()),
            title=("APEX [b]HAKAM[/b]" if self.REFEREE_APP else
                   "APEX [b]CAPTAIN[/b]" if self.CAPTAIN_APP else "APEX [b]LEAGUE[/b]"),
            sub=("Kapitan paneli" if self.CAPTAIN_APP else "O'yinchi paneli"),
            icon="shield-half-full" if self.CAPTAIN_APP else
                 "whistle" if self.REFEREE_APP else "trophy-outline")
        ui.add_widget(self.pl_header)

        if self.CAPTAIN_APP:
            tabs = [("lineup", "soccer-field", "Tarkib"),
                    ("groups", "account-group-outline", "Jamoam"),
                    ("transfer", "swap-horizontal", "Transfer"),
                    ("market", "storefront-outline", "Market")]
        else:
            tabs = [("groups", "account-group-outline", "Guruhlar"),
                    ("lineup", "soccer-field", "Tarkib"),
                    ("table", "trophy-outline", "Jadval")]
            if not self.REFEREE_APP:
                tabs.append(("market", "storefront-outline", "Market"))

        self._content_sm = ScreenManager()   # NoTransition: arzon telefon GPU'lari uchun xavfsiz
        for key, _ic, _lab in tabs:
            self._content_sm.add_widget(self._glass_tab(key))
        ui.add_widget(self._content_sm)

        self._nav = G.NavBar(on_go=lambda k: self.go_tab(k),
                             tabs=tuple((k, i, l) for k, i, l in tabs))
        ui.add_widget(self._nav)

        root.add_widget(ui)
        scr.add_widget(root)
        self._content_sm.current = tabs[0][0]
        self._nav.activate(tabs[0][0])
        return scr

    def _glass_tab(self, name):
        """Bir tab sahifasi: shaffof ScrollView + vertikal kontent qutisi."""
        s = Screen(name=name)
        sv, box = G.scroll_page()
        setattr(self, "b_" + name, box)
        s.add_widget(sv)
        return s

    def go_tab(self, key):
        if getattr(self, "_content_sm", None) is not None:
            self._content_sm.current = key
        if getattr(self, "_nav", None) is not None:
            self._nav.activate(key)

    def _grp_color(self, gid):
        """Guruh tartibiga qarab barqaror rang (jadval va kartalarda bir xil bo'lsin)."""
        ids = [g["id"] for g in self.d["groups"]]
        try:
            i = ids.index(gid)
        except ValueError:
            i = int(gid or 0) % len(GROUP_COLORS)
        return GROUP_COLORS[i % len(GROUP_COLORS)]

    def panel(self, *widgets, title=None):
        """Shisha kontent paneli: balandligi ichkiga qarab o'zi o'sadi."""
        p = G.Glass(orientation="vertical", size_hint_y=None, spacing=dp(4),
                   padding=(dp(12), dp(10)), radius=18)
        p.bind(minimum_height=p.setter("height"))
        if title:
            p.add_widget(G.TL(title, 12, G.CYAN, bold=True))
        for w in widgets:
            p.add_widget(w)
        return p

    def header(self, text, h=40):
        """Bo'lim sarlavhasi (glass uslub)."""
        return G.TL(text, 14.5, G.CYAN, size_hint_y=None, height=dp(h), shorten=False)

    def hero(self, subtitle):
        """Kubok rasmi bilan yuqori banner."""
        return G.Banner("APEX PRO LEAGUE", subtitle, image=TROPHY)

    def band(self, text, color, text_color=(1, 1, 1, 1), h=44, logo=None, group=None):
        """Rangli shisha tasma (ixtiyoriy logo/bosh harflar bilan)."""
        src = None
        if group is not None:
            src = self.logo_source(group)
            name = group.get("name") or ""
        elif logo is not None:
            src = logo_path(logo)
            name = str(logo)
        else:
            name = ""
        return G.Band(text, color, logo=src, name=name, h=h, text_color=text_color)

    @staticmethod
    def rank_text(i):
        col = {1: "F2C230", 2: "C0C8D8", 3: "CD7F32"}.get(i)
        return f"[color=#{col}][b]{i}[/b][/color]" if col else str(i)

    def note(self, text, h=None):
        """Izmat matn: uzunligiga qarab balandligi o'zi sozlanadi."""
        return G.note(text)

    @staticmethod
    def _fmt_ts(ts):
        if not ts:
            return "--:--"
        return time.strftime("%d.%m %H:%M", time.localtime(int(ts)))

    # ---------------- dialoglar ----------------
    def close_dialog(self, *a):
        if self.dialog:
            self.dialog.dismiss()
            self.dialog = None

    def show_dialog(self, title, text=None, items=None, content=None, buttons=None):
        """Shisha dialog. items/bosiladigan qatorlar, content=maxsus panel,
        buttons=og'a tugmalar (berilmasa 'Yopish' qo'yiladi)."""
        self.close_dialog()
        body = None
        if items:
            body = BoxLayout(orientation="vertical", spacing=dp(6))
            for it in items:
                body.add_widget(it)
        elif content is not None:
            body = content
        self.dialog = G.Dialog(title, body=body, text=text,
                               actions=buttons or
                               [MDFlatButton(text="Yopish", on_release=self.close_dialog)])
        self.dialog.open()

    def choose_dialog(self, title, options, callback):
        """options: [(label, value), ...]"""
        if not options:
            toast("Tanlash uchun ma'lumot yo'q")
            return
        items = [OneLineListItem(
            text=label,
            on_release=lambda x, v=val: (self.close_dialog(), callback(v)))
            for label, val in options]
        self.show_dialog(title, items=items)

    def input_dialog(self, title, hint, callback, text="", password=False, digits=False):
        field = glass_field(hint, digits=digits, password=password, text=text)

        def ok(*a):
            val = field.text.strip()
            self.close_dialog()
            callback(val)
        self.show_dialog(title, content=field, buttons=[
            MDFlatButton(text="Bekor", on_release=self.close_dialog),
            MDRaisedButton(text="OK", on_release=ok)])

    def confirm_dialog(self, title, text, on_yes):
        def yes(*a):
            self.close_dialog()
            on_yes()
        self.show_dialog(title, text=text, buttons=[
            MDFlatButton(text="Yo'q", on_release=self.close_dialog),
            MDRaisedButton(text="Ha", on_release=yes)])

    # ---------------- ma'lumot yordamchilari ----------------
    @property
    def d(self):
        return self.store.data

    def group(self, gid):
        return next((g for g in self.d["groups"] if g["id"] == gid), None)

    def player(self, pid):
        return next((p for p in self.d["players"] if p["id"] == pid), None)

    def match(self, mid):
        return next((m for m in self.d["matches"] if m["id"] == mid), None)

    def gname(self, gid):
        g = self.group(gid)
        return g["name"] if g else "—"

    def pname(self, pid):
        p = self.player(pid)
        return p["name"] if p else "?"

    def captain_name(self, g):
        p = self.player(g["captain_id"]) if g else None
        return p["name"] if p else "—"

    def is_captain(self, pid):
        return any(g["captain_id"] == pid for g in self.d["groups"])

    def captain_group(self, pid):
        """Bu o'yinchi qaysi guruhning kapitani (bo'lmasa None)."""
        return next((g for g in self.d["groups"] if g["captain_id"] == pid), None)

    def free_players(self):
        return [p for p in self.d["players"] if p["group"] is None]

    def members(self, gid):
        return [p for p in self.d["players"] if p["group"] == gid]

    def name_exists(self, name, ignore_id=None):
        return any(p["name"].lower() == name.lower() and p["id"] != ignore_id
                   for p in self.d["players"])

    @staticmethod
    def valid_pin(pin):
        return pin.isdigit() and len(pin) >= 4

    @staticmethod
    def ref_hash(pin, rid):
        return hash_pw("ref:" + pin, "r" + str(rid))

    # ---------------- kapitan login/parol (Apex Captain ilovasi) ----------------
    CAP_MAX_FAILS = 3
    CAP_LOCK_SECONDS = 60

    @staticmethod
    def cap_hash(password, gid):
        return hash_secret("cap:" + password, "g" + str(gid))

    @staticmethod
    def norm_login(login):
        return "".join(c for c in (login or "").strip().lower() if c.isalnum() or c == "-")

    @staticmethod
    def valid_password(password):
        return len((password or "").strip()) >= 6

    def group_by_login(self, login):
        lg = self.norm_login(login)
        if not lg:
            return None
        for g in self.d["groups"]:
            if self.norm_login(g.get("cap_login")) == lg:
                return g
        return None

    def login_taken(self, login, ignore_gid=None):
        lg = self.norm_login(login)
        return any(g["id"] != ignore_gid and self.norm_login(g.get("cap_login")) == lg
                   for g in self.d["groups"])

    def suggest_login(self, gname, gid):
        """Admin uchun tayyor login: guruh nomidan lotin harflari + guruh raqami."""
        base = self.norm_login(gname).replace("-", "") or "apex"
        lg = f"{base}-{gid}"
        n = 1
        while self.login_taken(lg):
            n += 1
            lg = f"{base}-{gid}-{n}"
        return lg

    def captain_login(self, login, password):
        """To'g'ri bo'lsa guruh id'si, aks holda None (qanday xato — aytmaymiz)."""
        g = self.group_by_login(login)
        if not g or not g.get("cap_pass_hash"):
            return None
        ok = self.cap_hash((password or "").strip(), g["id"]) == g["cap_pass_hash"]
        return g["id"] if ok else None

    # --- urinishlar limiti (qurilmada saqlanadi) ---
    def cap_wait(self):
        left = int(self.load_me().get("cap_lock_until") or 0) - now_ts()
        return left if left > 0 else 0

    def cap_fail(self):
        me = self.load_me()
        n = int(me.get("cap_fails") or 0) + 1
        if n >= self.CAP_MAX_FAILS:
            me["cap_lock_until"] = now_ts() + self.CAP_LOCK_SECONDS
            me.pop("cap_fails", None)
        else:
            me["cap_fails"] = n
        self._save_me(me)
        return max(0, self.CAP_MAX_FAILS - n)

    def cap_reset_fails(self):
        me = self.load_me()
        me.pop("cap_fails", None)
        me.pop("cap_lock_until", None)
        self._save_me(me)

    # --- sessiya: qaysi kapitan sifatida kirdik ---
    def set_cap_session(self, gid):
        me = self.load_me()
        me["cap_gid"] = gid
        self._save_me(me)
        self.my_cap_gid = gid

    def clear_cap_session(self):
        me = self.load_me()
        me.pop("cap_gid", None)
        self._save_me(me)
        self.my_cap_gid = None

    def saved_cap_gid(self):
        gid = self.load_me().get("cap_gid")
        return gid if self.group(gid) else None

    # ---------------- kartochka holati (hisoblanadi) ----------------
    def card_status(self, pid, before_mid=None):
        """
        before_mid o'yinidan OLDIN o'ynalgan o'yinlar bo'yicha holat.
        Qaytaradi: (joriy_sariq_soni, jarimada_mi)
        """
        p = self.player(pid)
        if not p:
            return 0, False
        y, susp = 0, False
        for m in self.d["matches"]:
            if before_mid is not None and m["id"] == before_mid:
                break
            if m["hs"] is None or p["group"] not in (m["home"], m["away"]):
                continue
            if susp:          # jarimani shu o'yinda o'tab bo'ldi
                susp = False
                continue
            for c in m["cards"]:
                if c["pid"] != pid:
                    continue
                if c["type"] == "red":
                    susp = True
                else:
                    y += 1
                    if y >= 2:
                        susp = True
                        y = 0
        return y, susp

    def card_totals(self, pid):
        ys = sum(1 for m in self.d["matches"] for c in m["cards"]
                 if c["pid"] == pid and c["type"] == "yellow")
        rs = sum(1 for m in self.d["matches"] for c in m["cards"]
                 if c["pid"] == pid and c["type"] == "red")
        return ys, rs

    def purge_from_lineups(self, pid):
        """O'yinchi guruhdan chiqsa, hali o'ynalmagan va qulflanmagan tarkiblardan olib tashlanadi."""
        for m in self.d["matches"]:
            if m["hs"] is None and not self.lineup_closed(m):
                for k in list(m["lineups"].keys()):
                    m["lineups"][k] = [x for x in m["lineups"][k] if x != pid]

    # ---------------- shaxsiy identifikatsiya (qurilmada saqlanadi) ----------------
    def _me_path(self):
        return os.path.join(self.user_data_dir, "me.json")

    def load_me(self):
        try:
            with open(self._me_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_me(self, me):
        try:
            with open(self._me_path(), "w", encoding="utf-8") as f:
                json.dump(me, f)
        except Exception:
            pass

    def my_pid(self):
        pid = self.load_me().get("pid")
        return pid if self.player(pid) else None

    def set_my_pid(self, pid):
        me = self.load_me()
        me["pid"] = pid
        self._save_me(me)
        self.sync_push()

    def clear_me(self):
        me = self.load_me()
        me.pop("pid", None)
        self._save_me(me)

    my_cap_gid = None          # shu sessiyada login/parol bilan kirilgan kapitan guruhi

    def my_group(self):
        pid = self.my_pid()
        p = self.player(pid) if pid else None
        return self.group(p["group"]) if p and p["group"] else None

    def captain_groups(self):
        """Men kapitan bo'lgan guruhlar: shaxsim kapitan bo'lsa yoki Apex Captain'da login bilan kirilgan."""
        gids = []
        if self.my_cap_gid is not None:
            gids.append(self.my_cap_gid)
        pid = self.my_pid()
        if pid:
            gids += [g["id"] for g in self.d["groups"] if g["captain_id"] == pid]
        return list(dict.fromkeys(gids))

    def my_team_gids(self):
        """Kapitan boshqaruv huquqi faqat Apex Captain ilovasida (login/parol bilan kirilgan).
        Player/Hakam ilovalari bu ro'yxatni bo'sh ko'radi — kapitan amallari u yerda yo'q."""
        return self.captain_groups() if self.CAPTAIN_APP else []

    def profile_dialog(self):
        pid = self.my_pid()
        if not pid:
            def chosen(v):
                self.set_my_pid(v)
                toast("Profilingiz saqlandi")
                self.update_toolbar()
            self.choose_dialog("Profil: o'zingizni tanlang",
                               [(p["name"], p["id"]) for p in self.d["players"]], chosen)
            return
        p = self.player(pid)
        items = [OneLineListItem(text="Shaxsiy kartochkam",
                                 on_release=lambda *a: (self.close_dialog(), self.player_card(pid))),
                 OneLineListItem(text="O'zimni almashtirish",
                                 on_release=lambda *a: (self.close_dialog(), self.clear_me(),
                                                        self.update_toolbar()))]
        self.show_dialog(f"Profil: {p['name']}  |  APEX TOKEN: {p.get('tokens', TOKEN_START)}",
                         items=items)

    # ---------------- xabarnomalar ----------------
    def my_audiences(self):
        out = ["all"]
        pid = self.my_pid()
        if pid:
            out.append(f"p{pid}")
        out += [f"g{gid}" for gid in self.captain_groups()]
        return out

    def sync_push(self):
        """Android'da FCM topic obunalarini joriy auditoriyalarga moslashtirish."""
        try:
            push.sync_topics(self.my_audiences())
        except Exception:
            pass

    def notifs_for_me(self):
        aud = set(self.my_audiences())
        out = [n for n in self.d["notifs"] if n["to"] in aud]
        out.sort(key=lambda n: -n["ts"])
        return out

    def unread_notifs(self):
        aud = set(self.my_audiences())
        return sum(1 for n in self.d["notifs"]
                   if n["to"] in aud and not any(k in n["read"] for k in aud))

    def push_notif(self, to, text):
        self.d["notifs"].append({"id": self.store.new_id(), "to": to, "text": text,
                                 "ts": now_ts(), "read": {}})

    def show_notifs(self):
        aud = set(self.my_audiences())
        ns = self.notifs_for_me()
        changed = False
        for n in ns:
            if n["to"] in aud and n["to"] not in n["read"]:
                n["read"][n["to"]] = now_ts()
                changed = True
        if changed:
            self.store.save()
        if not ns:
            self.show_dialog("Xabarnomalar", text="Hozircha xabarnomalar yo'q.")
            return
        items = [TwoLineListItem(
            text=n["text"],
            secondary_text=time.strftime("%d.%m.%Y %H:%M", time.localtime(n["ts"] or 0)),
            disabled=True) for n in ns[:50]]
        self.show_dialog("Xabarnomalar", items=items)

    # ---------------- APEX TOKEN ----------------
    def add_tokens(self, pid, delta, reason=""):
        p = self.player(pid)
        if not p:
            return
        p["tokens"] = max(0, int(p.get("tokens", TOKEN_START)) + delta)
        hist = p.setdefault("thist", [])
        hist.append({"ts": now_ts(), "delta": delta, "reason": reason or "-",
                     "bal": p["tokens"]})
        del hist[:-50]          # bazani shishirmaslik uchun oxirgi 50 ta
        if p["tokens"] <= 0:
            if not p.get("token_zero_since"):
                p["token_zero_since"] = now_ts()
                self.push_notif(
                    f"p{pid}", "APEX TOKEN 0 ga tushdi: asosiy tarkibga chiqish taqiqlandi va "
                               "OVR har 2 kunda 1 ballga pasayadi.")
        else:
            p["token_zero_since"] = None
        if reason:
            self.push_notif(f"p{pid}", f"APEX TOKEN {delta:+d}: {reason}. Balans: {p['tokens']}")

    def token_history(self, pid):
        """O'yinchining APEX TOKEN audit jurnali (oxirgisi tepada)."""
        p = self.player(pid)
        if not p:
            return
        hist = list(reversed(p.get("thist") or []))
        if not hist:
            toast("Token tarixi hali bo'sh")
            return
        items = [TwoLineListItem(
            text=f"{h['delta']:+d}  |  balans {h['bal']}",
            secondary_text=f"{self._fmt_ts(h.get('ts'))}  —  {h.get('reason') or '-'}",
            disabled=True) for h in hist]
        self.show_dialog(f"APEX TOKEN tarixi: {p['name']}", items=items)

    def token_decay(self, p):
        ts = p.get("token_zero_since")
        if not ts:
            return 0
        return max(0, (now_ts() - int(ts)) // (OVR_DECAY_DAYS * 86400))

    def token_banned(self, pid):
        p = self.player(pid)
        return bool(p) and int(p.get("tokens", TOKEN_START)) <= 0

    def apply_penalty(self, pid, mid, code):
        p, m = self.player(pid), self.match(mid)
        if not p or not m or code not in PENALTY_BY_CODE:
            return False
        if any(a["pid"] == pid and a["kind"] == code for a in m["attendance"]):
            toast("Bu jarima allaqachon belgilangan")
            return False
        m["attendance"].append({"pid": pid, "kind": code})
        self.add_tokens(pid, -PENALTY_BY_CODE[code], PENALTY_NAMES[code])
        return True

    # ---------------- TRANSFER LIST va MUZOKARA ----------------
    def transfer_find(self, tid):
        return next((t for t in self.d["transfers"] if t["id"] == tid), None)

    def transfer_of(self, pid, statuses=("listed", "offer")):
        return next((t for t in self.d["transfers"]
                     if t["pid"] == pid and t["status"] in statuses), None)

    def transfer_request(self, pid):
        p, g = self.player(pid), self.my_group()
        if not p or not g or p["group"] != g["id"]:
            toast("Faqat o'z jamoangiz uchun so'rov yuborishingiz mumkin (profilni tanlang)")
            return
        if p.get("tstatus"):
            toast("So'rovingiz allaqachon yuborilgan")
            return
        self.d["transfers"].append({"id": self.store.new_id(), "pid": pid, "status": "pending",
                                    "seller_gid": g["id"], "buyer_gid": None, "amount": 0,
                                    "side": "seller", "ts": now_ts(), "msg": ""})
        p["tstatus"] = "pending"
        self.push_notif(f"p{pid}", "So'rovingiz qabul qilindi va tez orada ko'rib chiqiladi.")
        self.push_notif(f"g{g['id']}",
                        f"Sizning {p['name']} jamoadoshingiz transfer listga qo'shilish uchun so'rov yubordi.")
        if self.store.save():
            toast("So'rov kapitaningizga yuborildi")
        self.refresh_all()

    def transfer_decide(self, tid, accept):
        t = self.transfer_find(tid)
        p = self.player(t["pid"]) if t else None
        if not t or not p or t["status"] != "pending":
            return
        if accept:
            t["status"], t["side"] = "listed", "buyer"
            p["tstatus"] = "listed"
            self.push_notif(f"p{p['id']}",
                            "Sizning transfer listga qo'shilish so'rovingiz qabul qilindi va "
                            "siz transfer listga qo'shildingiz.")
        else:
            t["status"] = "rejected"
            p["tstatus"] = None
            self.push_notif(f"p{p['id']}", "Sizning transfer listga qo'shilish so'rovingiz rad etildi.")
        self.store.save()
        self.refresh_all()

    def transfer_offer(self, pid, buyer_gid, amount):
        p = self.player(pid)
        g = self.group(buyer_gid)
        if not p or not g or p.get("tstatus") != "listed":
            toast("O'yinchi transfer listda emas")
            return
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            amount = 0
        if amount <= 0:
            toast("Taklif miqdorini (token) kiriting")
            return
        if g["ptokens"] < amount:
            toast(f"Jamoangizda token yetarli emas (balans: {g['ptokens']})")
            return
        t = self.transfer_of(pid)
        if t is None:
            toast("Transfer yozuvi topilmadi")
            return
        t.update(status="offer", buyer_gid=buyer_gid, amount=amount, side="seller", ts=now_ts())
        self.push_notif(f"g{t['seller_gid']}",
                        f"Biz sizning {p['name']} jamoadoshingizni sotib olishga qaror qildik. "
                        f"Taklif: {amount} APEX PRO TOKEN.")
        self.push_notif(f"g{buyer_gid}", f"{p['name']} uchun {amount} token taklif yuborildi.")
        self.store.save()
        self.refresh_all()

    def transfer_counter(self, tid, amount):
        t = self.transfer_find(tid)
        if not t or t["status"] != "offer":
            return
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            amount = 0
        if amount <= 0:
            toast("Miqdorni kiriting")
            return
        other = "buyer" if t["side"] == "seller" else "seller"
        t.update(amount=amount, side=other, ts=now_ts())
        gid = t["buyer_gid"] if other == "buyer" else t["seller_gid"]
        self.push_notif(f"g{gid}", f"Muzokara: qarshi taklif {amount} APEX PRO TOKEN.")
        self.store.save()
        self.refresh_all()

    def transfer_accept(self, tid):
        t = self.transfer_find(tid)
        if not t or t["status"] != "offer":
            return
        p, seller, buyer = self.player(t["pid"]), self.group(t["seller_gid"]), self.group(t["buyer_gid"])
        if not p or not seller or not buyer:
            return
        amt = int(t["amount"])
        if buyer["ptokens"] < amt:
            toast(f"Xaridor jamoada token yetarli emas (balans: {buyer['ptokens']})")
            return
        buyer["ptokens"] -= amt
        seller["ptokens"] += amt
        self.purge_from_lineups(p["id"])
        p["group"], p["tstatus"] = buyer["id"], None
        t.update(status="done", ts=now_ts())
        self.push_notif(f"p{p['id']}", f"Transfer yakunlandi: siz endi {buyer['name']} jamoasidasiz.")
        self.push_notif(f"g{seller['id']}", f"{p['name']} transfer qilindi: +{amt} APEX PRO TOKEN.")
        self.push_notif(f"g{buyer['id']}", f"{p['name']} jamoangizga qo'shildi: -{amt} APEX PRO TOKEN.")
        self.store.save()
        self.refresh_all()

    def transfer_drop_offer(self, tid):
        """Sotuvchi taklifni rad etadi yoki xaridor taklifni qaytarib oladi: o'yinchi listda qoladi."""
        t = self.transfer_find(tid)
        if not t or t["status"] != "offer":
            return
        gid = t["buyer_gid"] if t["side"] == "seller" else t["seller_gid"]
        t.update(status="listed", buyer_gid=None, amount=0, side="buyer", ts=now_ts())
        self.push_notif(f"g{gid}", "Muzokara bekor qilindi, o'yinchi transfer listda qoldi.")
        self.store.save()
        self.refresh_all()

    def captain_transfers(self):
        gids = self.my_team_gids()
        if not gids:
            toast("Kapitan sifatida kirmadingiz")
            return
        self.show_dialog("Transfer boshqaruvi (kapitan)", content=self.transfer_panel(gids))

    def transfer_panel(self, gids, into=None):
        """Kapitan uchun transfer bo'limi: dialogda va Captain ilovasi tab'ida bir xil."""
        inner = into if into is not None else BoxLayout(orientation="vertical",
                                                        spacing=dp(8), padding=dp(4))
        pend = [t for t in self.d["transfers"] if t["status"] == "pending"
                and t["seller_gid"] in gids]
        inner.add_widget(self.header(f"[b]Ko'rib chiqish kutilayotgan so'rovlar: {len(pend)}[/b]"))
        for t in pend:
            row = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
            row.add_widget(MDLabel(text=self.pname(t["pid"]), size_hint_x=1))
            row.add_widget(MDRaisedButton(text="Qabul",
                                          on_release=lambda *a, tid=t["id"]: (
                                              self.close_dialog(), self.transfer_decide(tid, True))))
            row.add_widget(MDFlatButton(text="Rad",
                                        on_release=lambda *a, tid=t["id"]: (
                                            self.close_dialog(), self.transfer_decide(tid, False))))
            inner.add_widget(row)
        offs = [t for t in self.d["transfers"] if t["status"] == "offer"
                and (t["seller_gid"] in gids or t["buyer_gid"] in gids)]
        inner.add_widget(self.header(f"[b]Muzokaralar: {len(offs)}[/b]"))
        for t in offs:
            me = "seller" if t["seller_gid"] in gids else "buyer"
            wait = "sizning navbatingiz" if t["side"] == me else "raqib javobini kutmoqda"
            row = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
            row.add_widget(MDLabel(
                text=f"{self.pname(t['pid'])}: {t['amount']} token ({wait})", size_hint_x=1))
            row.add_widget(MDRaisedButton(text="Muzokara",
                                          on_release=lambda *a, tid=t["id"]: (
                                              self.close_dialog(), self.negotiate_dialog(tid))))
            inner.add_widget(row)
        listed = [p for p in self.d["players"] if p.get("tstatus") == "listed"]
        inner.add_widget(self.header(f"[b]Transfer list: {len(listed)}[/b]"))
        for p in listed:
            row = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
            row.add_widget(MDLabel(
                text=f"{p['name']} [{self.gname(p['group'])}]", size_hint_x=1))
            row.add_widget(MDRaisedButton(text="Taklif",
                                          on_release=lambda *a, pid=p["id"]: (
                                              self.close_dialog(), self.offer_dialog(pid))))
            inner.add_widget(row)
        return inner

    def offer_dialog(self, pid):
        gids = list(self.my_team_gids())
        if not gids:
            return
        if len(gids) == 1:
            gid = gids[0]
        else:
            self.choose_dialog("Qaysi jamoa nomidan?", [(self.gname(g), g) for g in gids],
                               lambda g: self.offer_dialog_for(pid, g))
            return
        self.offer_dialog_for(pid, gid)

    def offer_dialog_for(self, pid, gid):
        g = self.group(gid)

        def cb(txt):
            self.transfer_offer(pid, gid, txt)
        self.input_dialog(f"{self.pname(pid)} uchun taklif",
                          f"APEX PRO TOKEN (balans: {g['ptokens']})", cb, digits=True)

    def negotiate_dialog(self, tid):
        t = self.transfer_find(tid)
        if not t:
            return
        gids = self.my_team_gids()
        me = "seller" if t["seller_gid"] in gids else "buyer"
        acting = t["side"] == me
        inner = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(4))
        inner.add_widget(MDLabel(
            text=f"[b]{self.pname(t['pid'])}[/b]\nSotuvchi: {self.gname(t['seller_gid'])}\n"
                 f"Xaridor: {self.gname(t['buyer_gid'])}\nJoriy taklif: [b]{t['amount']}[/b] token\n"
                 f"Rolingiz: {'sotuvchi' if me == 'seller' else 'xaridor'}"
                 + ("" if acting else "\nHozir raqib javobini kutmoqda"),
            markup=True, size_hint_y=None, height=dp(120)))
        btns = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        if acting:
            btns.add_widget(MDRaisedButton(
                text="Kelishdim (transfer)",
                on_release=lambda *a: (self.close_dialog(), self.transfer_accept(tid))))
            btns.add_widget(MDRaisedButton(
                text="Qarshi taklif",
                on_release=lambda *a: (self.close_dialog(), self.input_dialog(
                    "Qarshi taklif", "APEX PRO TOKEN",
                    lambda v: self.transfer_counter(tid, v), digits=True))))
        btns.add_widget(MDFlatButton(
            text="Bekor qilish",
            on_release=lambda *a: (self.close_dialog(), self.transfer_drop_offer(tid))))
        inner.add_widget(btns)
        self.show_dialog("Muzokara", content=inner)

    # ---------------- MARKET (kapitanlar) ----------------
    def market_dialog(self, gid=None):
        gids = [gid] if gid else self.my_team_gids()
        can_buy = bool(gids)
        inner = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(4))
        if can_buy:
            for g in [self.group(g) for g in gids]:
                if g:
                    inner.add_widget(self.band(
                        f"[b]{g['name']}[/b]  |  APEX PRO TOKEN: [b]{g['ptokens']}[/b]", GOLD,
                        text_color=NAVY))
        else:
            inner.add_widget(MDLabel(
                text="Narxlar bilan tanishib chiqing — xaridni kapitan Apex Captain ilovasida qiladi.",
                size_hint_y=None, height=dp(40)))
        items = [it for it in self.d["market"] if it["qty"] > 0]
        if not items:
            inner.add_widget(MDLabel(text="Hozircha sotuvda narsa yo'q.",
                                     size_hint_y=None, height=dp(40)))
        for it in items:
            card = adaptive_card(orientation="horizontal", radius=[12], md_bg_color=CARD,
                                 padding=dp(8), spacing=dp(8))
            if it.get("img"):
                card.add_widget(Image(source=b64_to_path(f"m{it['id']}", it["img"]),
                                      size_hint_x=None, width=dp(64)))
            col = MDBoxLayout(orientation="vertical", size_hint_x=1)
            col.add_widget(MDLabel(text=f"[b]{it['name']}[/b]", markup=True))
            col.add_widget(MDLabel(text=it.get("desc") or "", font_style="Caption"))
            col.add_widget(MDLabel(text=f"Narx: [b]{it['price']}[/b] token   |   Qolgan: {it['qty']}",
                                   markup=True, font_style="Caption"))
            card.add_widget(col)
            if can_buy:
                card.add_widget(MDRaisedButton(
                    text="Olish",
                    on_release=lambda *a, iid=it["id"]: self.market_buy_ask(iid, gids)))
            inner.add_widget(card)
        self.show_dialog("Market (APEX PRO TOKEN)", content=inner)

    def market_buy_ask(self, item_id, gids):
        if len(gids) == 1:
            self.market_buy(item_id, gids[0])
            return
        self.choose_dialog("Qaysi jamoa hisobidan?", [(self.gname(g), g) for g in gids],
                           lambda g: self.market_buy(item_id, g))

    def market_buy(self, item_id, gid):
        it = next((x for x in self.d["market"] if x["id"] == item_id), None)
        g = self.group(gid)
        if not it or not g:
            return
        if it["qty"] <= 0:
            toast("Bu narsa tugagan")
            return
        if g["ptokens"] < it["price"]:
            toast(f"Token yetarli emas (balans: {g['ptokens']}, narx: {it['price']})")
            return
        self.close_dialog()
        g["ptokens"] -= it["price"]
        it["qty"] -= 1
        it.setdefault("sold", []).append(gid)
        self.push_notif(f"g{gid}", f"Market: «{it['name']}» sotib olindi "
                                   f"(-{it['price']} token). Balans: {g['ptokens']}")
        if self.store.save():
            toast("Sotib olindi")
        self.refresh_all()

    # ---------------- guruh logosi: preset yoki telefondan yuklangan ----------------
    def logo_source(self, g):
        if g and g.get("logo_img"):
            try:
                return b64_to_path(f"g{g['id']}", g["logo_img"])
            except Exception:
                pass
        return logo_path(g.get("logo") if g else None)

    def apply_logo(self, g, value):
        """value: preset raqami yoki ("img", b64)."""
        if isinstance(value, tuple):
            g["logo_img"] = value[1]
            g["logo"] = None
        else:
            g["logo"] = value
            g["logo_img"] = None

    def captain_logo_upload(self):
        """Kapitan o'z guruhining logosini tanlaydi yoki telefondan yuklaydi."""
        gids = self.my_team_gids()
        if not gids:
            toast("Kapitan sifatida kirmadingiz")
            return
        gid = gids[0] if len(gids) == 1 else None
        if gid is None:
            self.choose_dialog("Qaysi guruh?", [(self.gname(g), g) for g in gids],
                               self._captain_logo_pick)
            return
        self._captain_logo_pick(gid)

    def _captain_logo_pick(self, gid):
        g = self.group(gid)
        if not g:
            return

        def got(value):
            self.apply_logo(g, value)
            if self.store.save():
                toast("Logo yangilandi")
            self.refresh_all()
        self.logo_picker(got)

    # ---------------- bayonnoma va statistika ----------------
    def team_starters(self, m, gid):
        return list(m["lineups"].get(str(gid), []))

    def team_appeared(self, m, gid):
        """Maydonga tushganlar: asosiy tarkib + zaxiradan kirganlar."""
        return self.team_starters(m, gid) + [s["in"] for s in m["subs"] if s["team"] == gid]

    def team_onfield(self, m, gid):
        """Hozir maydonda: tushganlar - almashtirilib chiqqanlar."""
        outs = {s["out"] for s in m["subs"] if s["team"] == gid}
        return [pid for pid in self.team_appeared(m, gid) if pid not in outs]

    # ---------------- hakam sekundomeri (faqat shu qurilmada saqlanadi) ----------------
    def _clock_path(self):
        return os.path.join(self.user_data_dir, "clock.json")

    def clock_all(self):
        if self.__dict__.get("_clocks") is None:
            try:
                with open(self._clock_path(), "r", encoding="utf-8") as f:
                    self._clocks = json.load(f)
            except Exception:
                self._clocks = {}
        return self._clocks

    def clock_state(self, mid):
        s = self.clock_all().get(str(mid)) or {}
        return dict(mid=mid, half=int(s.get("half") or 1),
                    acc=int(s.get("acc") or 0), since=s.get("since"))

    def clock_save(self, st):
        self._clocks = self.clock_all()
        self._clocks[str(st["mid"])] = {k: st[k] for k in ("half", "acc", "since")}
        try:
            tmp = self._clock_path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._clocks, f)
            os.replace(tmp, self._clock_path())
        except Exception:
            pass

    @staticmethod
    def clock_seconds(st):
        return st["acc"] + ((now_ts() - st["since"]) if st["since"] else 0)

    def clock_toggle(self, mid):
        st = self.clock_state(mid)
        if st["since"]:
            st["acc"], st["since"] = self.clock_seconds(st), None
        else:
            st["since"] = now_ts()
        self.clock_save(st)

    def clock_next_half(self, mid):
        st = self.clock_state(mid)
        st["half"] = 1 if st["half"] >= 2 else st["half"] + 1
        st["acc"] = 0
        if st["since"]:
            st["since"] = now_ts()
        self.clock_save(st)

    def clock_reset(self, mid):
        self.clock_save(dict(mid=mid, half=1, acc=0, since=None))

    def clock_minute(self, mid):
        """Ushbu o'yin uchun sekundomer daqiqasi (1..N); soat ishga tushmagan bo'lsa None."""
        st = self.clock_state(mid)
        if not st["since"] and not st["acc"]:
            return None
        return (st["half"] - 1) * CLOCK_HALF_MIN + self.clock_seconds(st) // 60 + 1

    def clock_running_text(self, mid):
        st = self.clock_state(mid)
        if not st["since"]:
            return ""
        sec = self.clock_seconds(st)
        return "  ·  ⏱ %02d:%02d (%d-bo'lim)" % (sec // 60, sec % 60, st["half"])

    @staticmethod
    def min_tag(ev):
        return "%d'  ·  " % ev["min"] if ev.get("min") else ""

    def clock_dialog(self, *a):
        opts = [(self.match_label(m), m["id"]) for m in self.d["matches"] if m["hs"] is None]
        if not opts:
            toast("Sekundomer uchun o'ynalmagan o'yin yo'q")
            return
        if len(opts) == 1:
            self.show_clock(opts[0][1])
            return
        self.choose_dialog("Qaysi o'yinning soati?", opts, self.show_clock)

    def show_clock(self, mid):
        m = self.match(mid)
        self.show_dialog("Sekundomer: " + (self.match_label(m) if m else ""),
                         content=RefClockPanel(mid))

    # ---------------- o'yin boshlanishi va avtomatik qulf ----------------
    def kick_ts(self, m):
        k = m.get("kick")
        return int(k) if isinstance(k, (int, float)) and k else None

    def lock_at(self, m):
        """Tarkib avtomatik yopiladigan vaqt: boshlanishdan LINEUP_LOCK_MIN oldin."""
        k = self.kick_ts(m)
        return None if k is None else k - LINEUP_LOCK_MIN * 60

    def auto_locked(self, m):
        at = self.lock_at(m)
        return at is not None and now_ts() >= at

    def lineup_closed(self, m):
        """Tarkib yopiqmi: qo'lab qulf, avtomatik qulf yoki o'yin tugagan."""
        return bool(m.get("lineup_locked")) or m.get("hs") is not None or self.auto_locked(m)

    def lock_note(self, m):
        """Qulf holatining qisqa matni (barcha ilovalar uchun bir xil)."""
        if m.get("hs") is not None:
            return "natija kiritilgan"
        if m.get("lineup_locked"):
            return "tarkib QULFLANGAN (admin)"
        at = self.lock_at(m)
        if at is None:
            return "tarkib ochiq"
        if now_ts() >= at:
            return "tarkib QULFLANGAN (avtomatik)"
        return "tarkib ochiq · %d daq. keyin qulflanadi" % ((at - now_ts() + 59) // 60)

    def recompute_score(self, m):
        """Hisob gollar ro'yxatidan avtomatik hisoblanadi."""
        m["hs"] = sum(1 for g in m["goals"] if g["team"] == m["home"])
        m["as"] = sum(1 for g in m["goals"] if g["team"] == m["away"])
        m["lineup_locked"] = True

    # ---------------- gol kiritish (hakam va admin) ----------------
    def goal_add(self):
        opts = [(self.match_label(m), m["id"]) for m in self.d["matches"]]
        if not opts:
            toast("Avval o'yinlar yaratilsin")
            return

        def got_match(mid):
            m = self.match(mid)
            if not m:
                return
            topts = [(self.gname(m["home"]), m["home"]), (self.gname(m["away"]), m["away"])]

            def got_team(gid):
                field = self.team_appeared(m, gid)
                if not field:
                    toast("Avval bu jamoaning boshlang'ich 6 tarkibi kiritilsin")
                    return
                sopts = [(self.pname(pid), pid) for pid in field]

                def got_scorer(sid):
                    aopts = [("— Assist yo'q", None)] + \
                            [(self.pname(pid), pid) for pid in field if pid != sid]

                    def got_assist(aid):
                        g = {"scorer": sid, "assist": aid, "team": gid, "ts": now_ts()}
                        mn = self.clock_minute(m["id"])
                        if mn:
                            g["min"] = mn
                        m["goals"].append(g)
                        self.recompute_score(m)
                        self.store.save()
                        self.refresh_all()
                        toast(f"Gol! Hisob {m['hs']}:{m['as']}")
                    self.choose_dialog("Assist bergan o'yinchi", aopts, got_assist)
                self.choose_dialog("Golni urgan o'yinchi", sopts, got_scorer)
            self.choose_dialog("Qaysi jamoa urdi?", topts, got_team)
        self.choose_dialog("Qaysi o'yin?", opts, got_match)

    def goal_remove(self):
        opts = []
        for m in self.d["matches"]:
            for i, g in enumerate(m["goals"]):
                ast = f", assist: {self.pname(g['assist'])}" if g.get("assist") else ""
                opts.append((f"{self.min_tag(g)}{self.pname(g['scorer'])}{ast} "
                             f"({self.match_label(m)})", (m["id"], i)))
        if not opts:
            toast("O'chirish uchun gol yo'q")
            return

        def chosen(v):
            mid, idx = v
            m = self.match(mid)
            if m and 0 <= idx < len(m["goals"]):
                m["goals"].pop(idx)
                self.recompute_score(m)
                self.store.save()
                self.refresh_all()
                toast("Gol o'chirildi")
        self.choose_dialog("Qaysi gol?", opts, chosen)

    def player_stats(self, pid):
        s = dict(starts=0, sub_in=0, sub_out=0, apps=0, goals=0, assists=0,
                 wins=0, yellow=0, red=0, motm=0)
        for m in self.d["matches"]:
            team, starter, came_on = None, False, False
            for gid in (m["home"], m["away"]):
                if pid in self.team_starters(m, gid):
                    team, starter = gid, True
            for sb in m["subs"]:
                if sb["in"] == pid:
                    came_on, team = True, sb["team"]
                if sb["out"] == pid:
                    s["sub_out"] += 1
            if starter:
                s["starts"] += 1
            elif came_on:
                s["sub_in"] += 1
            if team is not None:
                s["apps"] += 1
                if m["hs"] is not None:
                    if (team == m["home"] and m["hs"] > m["as"]) or \
                       (team == m["away"] and m["as"] > m["hs"]):
                        s["wins"] += 1
            if self.motm(m)[0] == pid:
                s["motm"] += 1
            s["goals"] += sum(1 for g in m["goals"] if g["scorer"] == pid)
            s["assists"] += sum(1 for g in m["goals"] if g.get("assist") == pid)
            for c in m["cards"]:
                if c["pid"] == pid:
                    s["red" if c["type"] == "red" else "yellow"] += 1
        s["points"] = (s["goals"] * POINTS["goal"] + s["assists"] * POINTS["assist"]
                       + s["wins"] * POINTS["win"] + s["yellow"] * POINTS["yellow"]
                       + s["red"] * POINTS["red"])
        return s

    def match_points(self, m, pid):
        """
        O'yinchining SHU o'yindagi balli.
        Qaytaradi: (ball, gollar, assistlar, kartochkalar_soni) yoki None (o'ynamagan).
        """
        team = None
        for gid in (m["home"], m["away"]):
            if pid in self.team_appeared(m, gid):
                team = gid
        if team is None:
            return None
        goals = sum(1 for g in m["goals"] if g["scorer"] == pid)
        assists = sum(1 for g in m["goals"] if g.get("assist") == pid)
        pts = goals * POINTS["goal"] + assists * POINTS["assist"]
        ncards = 0
        for c in m["cards"]:
            if c["pid"] == pid:
                ncards += 1
                pts += POINTS["red"] if c["type"] == "red" else POINTS["yellow"]
        if m["hs"] is not None:
            if (team == m["home"] and m["hs"] > m["as"]) or \
               (team == m["away"] and m["as"] > m["hs"]):
                pts += POINTS["win"]
        return pts, goals, assists, ncards

    def motm(self, m):
        """
        Player of the Match.
        Qaytaradi: (pid yoki None, rejim, teng_bo'lganlar)
        rejim: "admin" | "auto" | "tie" | "none"
        Avtomatik: eng ko'p ball -> teng bo'lsa ko'p gol -> ko'p assist -> kam kartochka.
        Hammasi teng bo'lsa admin tanlaydi.
        """
        if m["hs"] is None:
            return None, "none", []
        scores = {}
        for gid in (m["home"], m["away"]):
            for pid in self.team_appeared(m, gid):
                r = self.match_points(m, pid)
                if r:
                    scores[pid] = r
        if not scores:
            return None, "none", []
        adm = m.get("motm_admin")
        if adm in scores:
            return adm, "admin", []

        def key(pid):
            r = scores[pid]
            return (r[0], r[1], r[2], -r[3])
        best = max(key(p) for p in scores)
        if best[0] <= 0:      # hech kim ball to'plamagan (masalan 0:0)
            return None, "none", []
        tops = [p for p in scores if key(p) == best]
        if len(tops) == 1:
            return tops[0], "auto", []
        return None, "tie", tops

    # ---------------- o'yinchi ma'lumotlari: raqam, pozitsiya, davlat, OVR ----------------
    def player_ovr(self, pid):
        """
        OVR = boshlang'ich reyting + natija bonusi, 40..99 oralig'ida.
        Natija bonusi = jami ball / 3 + 2 x Player of the Match.
        Boshlang'ich reytingni admin belgilaydi (standart 60).
        """
        p = self.player(pid)
        base = int((p or {}).get("base_ovr") or BASE_OVR)
        s = self.player_stats(pid)
        bonus = int(s["points"] / 3) + 2 * s["motm"]
        decay = self.token_decay(p or {})
        return max(40, min(99, base + bonus - decay)), base, bonus - decay

    @staticmethod
    def ovr_color(ovr):
        if ovr >= 75:
            return (0.62, 0.46, 0.04, 1)      # oltin
        if ovr >= 65:
            return (0.36, 0.42, 0.52, 1)      # kumush
        return (0.48, 0.28, 0.12, 1)          # bronza

    def player_line(self, p):
        num = p.get("number")
        return (f"{('#' + str(num)) if num else '#-'} | {POS_NAME.get(p.get('pos'), '-')} | "
                f"{p.get('country') or '-'} | OVR {self.player_ovr(p['id'])[0]}")

    def logo_picker(self, callback):
        """12 ta tayyor logodan biri yoki telefondan yuklangan rasm. callback(raqam | ("img", b64))"""
        rows = (LOGO_COUNT + 3) // 4
        grid = GridLayout(cols=4, spacing=dp(8), padding=dp(4), size_hint_y=None,
                          height=dp(rows * 72 + 8))
        for n in range(1, LOGO_COUNT + 1):
            b = LogoButton(source=logo_path(n), size_hint_y=None, height=dp(64))
            b.bind(on_release=lambda *a, n=n: (self.close_dialog(), callback(n)))
            grid.add_widget(b)
        box = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(8))
        box.add_widget(grid)
        box.add_widget(MDRaisedButton(
            text="Telefondan yuklash", size_hint_x=1,
            on_release=lambda *a: self._upload_logo(callback)))
        self.show_dialog("Guruh logosini tanlang", content=box)

    def _upload_logo(self, callback):
        def got(path):
            try:
                b64 = image_to_b64(path)
            except Exception:
                toast("Rasmni o'qib bo'lmadi")
                return
            self.close_dialog()
            callback(("img", b64))
        self.close_dialog()
        pick_image_file(got)

    def search_dialog(self):
        """Qidiruv va filtr: ism/raqam, pozitsiya va guruh bo'yicha."""
        state = {"q": "", "pos": None, "gid": None}

        # Dialogning o'zi aylanadigan bo'lgani uchun ichki ScrollView shart emas
        content = BoxLayout(orientation="vertical", spacing=dp(6),
                            padding=(dp(4), dp(8), dp(4), 0))
        field = glass_field("Ism yoki raqam bo'yicha qidirish...", max_len=40)
        content.add_widget(field)

        def chip_line():
            # Chiplar bir qatorga sig'masa o'ngga qarab siljitiladi (dialog
            # balandligi keraksiz oshmasligi uchun qatorlarga bo'linmaydi).
            sv = ScrollView(size_hint_y=None, height=dp(46), do_scroll_x=True,
                            do_scroll_y=False, bar_width=0)
            row = MDBoxLayout(size_hint_x=None, size_hint_y=None, height=dp(46),
                              spacing=dp(6))
            row.bind(minimum_width=row.setter("width"))
            sv.add_widget(row)
            content.add_widget(sv)
            return row

        pos_row = chip_line()
        grp_row = chip_line()
        rlist = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        rlist.bind(minimum_height=rlist.setter("height"))
        content.add_widget(rlist)

        def matches():
            q = state["q"].strip().lower()
            out = []
            for p in self.d["players"]:
                if state["pos"] and p.get("pos") != state["pos"]:
                    continue
                if state["gid"] is not None and p.get("group") != state["gid"]:
                    continue
                if q and q not in p["name"].lower() and q not in str(p.get("number") or ""):
                    continue
                out.append(p)
            out.sort(key=lambda p: p["name"])
            return out

        def render():
            rlist.clear_widgets()
            res = matches()
            if not res:
                rlist.add_widget(TwoLineListItem(text="Hech narsa topilmadi",
                                                 secondary_text="Filtrlarni o'zgartiring",
                                                 disabled=True))
                return
            for p in res[:60]:
                grp = self.gname(p["group"]) if p["group"] is not None else "tanlanmagan"
                rlist.add_widget(TwoLineListItem(
                    text=p["name"],
                    secondary_text=f"{grp}  |  {self.player_line(p)}",
                    on_release=lambda x, pid=p["id"]: (self.close_dialog(),
                                                       self.player_card(pid))))

        def build_pos():
            pos_row.clear_widgets()
            opts = [("Hammasi", None)] + [(c, c) for _, c in POSITIONS]
            for label, val in opts:
                c = Chip(POS_NAME.get(val, label) if val else label, val)
                c.set_on(state["pos"] == val)
                c.bind(on_release=lambda x, v=val: (state.update(pos=v), build_pos(), render()))
                pos_row.add_widget(c)

        def build_grp():
            grp_row.clear_widgets()
            gs = self.d["groups"]
            opts = [("Barcha", None)] + [(g["name"], g["id"]) for g in gs]
            for label, val in opts:
                c = Chip(label, val)
                c.set_on(state["gid"] == val)
                c.bind(on_release=lambda x, v=val: (state.update(gid=v), build_grp(), render()))
                grp_row.add_widget(c)

        field.bind(text=lambda inst, val: (state.update(q=val), render()))
        build_pos()
        build_grp()
        render()
        self.show_dialog("Qidiruv va filtr", content=content,
                         buttons=[MDFlatButton(text="Yopish", on_release=self.close_dialog)])

    # ---------------- FC Mobile uslubidagi oltin o'yinchi kartasi ----------------
    FC_ATTR_LABELS = [("pac", "TEZ"), ("sho", "ZAR"), ("pas", "PAS"),
                      ("dri", "DRB"), ("def", "HIM"), ("phy", "JIS")]

    def player_attrs(self, p):
        """O'yinchi atributlari (yo'q bo'lsa standart 45-55 qiymatlar)."""
        a = dict(gemini.DEFAULT_ATTRS)
        for k, v in (p.get("attrs") or {}).items():
            if k in a and isinstance(v, (int, float)):
                a[k] = int(v)
        return a

    def fc_card_source(self, p):
        """Kartadagi rasm: AI kartasi > oddiy foto > yo'q."""
        for key in ("card_b64", "photo_b64"):
            b = p.get(key)
            if b:
                try:
                    return b64_to_path("p%s_%s" % (p["id"], key), b)
                except Exception:
                    pass
        return None

    CARD_ALT_POS = {"GK": ["GK"], "DF": ["CB", "LB", "RB"],
                    "MF": ["CDM", "CM", "CAM"], "FW": ["ST", "LW", "RW"]}

    def fc_card_widget(self, p):
        """O'yinchi kartasi: qalqon shaklidagi FC kartasi (player_card.py dizayni).

        Mavzu OVR bo'yicha: >=85 binafsha, >=75 oltin, qolgani ko'k. AI rasmi
        (card_b64) yoki yuklangan foto bo'lsa rasm joyiga qo'yiladi.
        """
        attrs = self.player_attrs(p)
        ovr = self.player_ovr(p["id"])[0]
        s = self.player_stats(p["id"])
        pos = (p.get("pos") or "MF").upper()
        theme = "purple" if ovr >= 85 else ("gold" if ovr >= 75 else "blue")
        return PC.PlayerCard(
            name=(p.get("last") or p.get("name") or "").upper()[:14],
            rating=ovr, position=pos, extra="++" if ovr >= 90 else "+",
            stats={code.upper(): attrs.get(code, 50)
                   for code, _lbl in self.FC_ATTR_LABELS},
            alt_positions=self.CARD_ALT_POS.get(pos, [pos]),
            photo=self.fc_card_source(p),
            theme=theme, width=dp(280),
            strip=[(G.fc_tier(ovr)[1], .9, False),
                   ("#%s" % (p.get("number") or "-"), 1.1, False),
                   ("%d tk" % int(p.get("tokens") or 0), 1.2, False),
                   ("%d ball" % s["points"], 1.4, True)])

    def player_photo_upload(self, pid):
        """O'yinchi o'zi rasmini yuklaydi; kalit bo'lsa Gemini uni oltin kartaga aylantiradi."""
        p = self.player(pid)
        if not p:
            return

        def got(path):
            try:
                b64 = image_to_b64(path, size=420)
            except Exception:
                toast("Rasmni o'qib bo'lmadi")
                return
            p["photo_b64"] = b64
            p["card_b64"] = None
            if gemini.available():
                toast("Rasm yuklandi. AI karta tayyorlanmoqda...")
                self._gemini_card_async(p)
            else:
                self.store.save()
                self.refresh_all()
                toast("Rasm saqlandi. AI yoqilmagan (config.py da GEMINI_API_KEY bo'sh)")

        self.close_dialog()
        pick_image_file(got)

    def _gemini_card_async(self, p):
        b64 = p.get("photo_b64")

        def work():
            res = gemini.enhance_player_photo(b64)
            img = None
            if res and res.get("image_b64"):
                try:
                    img = shrink_b64(res["image_b64"], size=440)
                except Exception:
                    img = res["image_b64"]

            def done(*a):
                if img:
                    p["card_b64"] = img
                    toast("AI oltin karta tayyor!")
                else:
                    toast("AI kartani yasay olmadi; oddiy rasm saqlandi")
                self.store.save()
                self.refresh_all()

            Clock.schedule_once(done, 0)

        threading.Thread(target=work, daemon=True).start()

    def _apply_attr(self, pid, attr, score):
        """Atributni 45-99 oralig'ida belgilaydi va OVR ni qayta hisoblaydi."""
        p = self.player(pid)
        if not p or attr not in gemini.ATTR_KEYS:
            return
        val = gemini.clamp_attr(score)
        if val is None:
            return
        p.setdefault("attrs", dict(gemini.DEFAULT_ATTRS))[attr] = val
        p["ovr"] = gemini.ovr_from_attrs(p["attrs"])
        self.store.save()
        self.refresh_all()
        toast("%s = %d  (OVR %d)" % (attr.upper(), val, p["ovr"]))

    def _attr_choice(self, pid, on_pick):
        opts = [(lbl.upper() + "  (" + code + ")", code)
                for code, lbl in self.FC_ATTR_LABELS]
        self.choose_dialog("Qaysi atribut?", opts, lambda code: on_pick(pid, code))

    def manual_attr(self, pid):
        """Admin atributni qo'lda kiritadi (AI o'rniga yoki AI taklifini tekshirib)."""
        def ask(pidx, code):
            cur = self.player_attrs(self.player(pidx)).get(code, 50)

            def got(val):
                self._apply_attr(pidx, code, val)
            self.input_dialog("Qo'lda: %s (%d-%d)" %
                              (code.upper(), gemini.ATTR_MIN, gemini.ATTR_MAX),
                              "Raqam kiriting (45-99)", got, text=str(cur), digits=True)
        self._attr_choice(pid, ask)

    def drill_video(self, pid):
        """Mashq videosini yuklash -> kategoriya -> Gemini tahlili -> gibrid tasdiqlash."""
        if not gemini.available():
            toast("Gemini kaliti yo'q. Atributlarni 'OVR qo'lda' bilan kiriting.")
            self.manual_attr(pid)
            return

        def pick_cat(code):
            def got(path):
                try:
                    vb64 = video_to_b64(path)
                except Exception:
                    toast("Video o'qilmadi yoki juda katta (18MB gacha). Qisqa video tanlang.")
                    return
                self.close_dialog()
                self._gemini_drill_async(pid, code, vb64)
            self.close_dialog()
            toast("Video tanlang...")
            pick_video_file(got)

        self._attr_choice(pid, pick_cat)

    def _gemini_drill_async(self, pid, code, vb64):
        lbl = dict(self.FC_ATTR_LABELS).get(code, code)

        def work():
            res = gemini.analyze_drill_video(vb64, code)

            def done(*a):
                if not res:
                    toast("AI tahlil qila olmadi. Qo'lda kiriting.")
                    manual_edit(pid, code, 50)
                    return

                def use_ai(*x):
                    self.close_dialog()
                    self._apply_attr(pid, code, res["score"])

                content = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(6))
                content.add_widget(MDLabel(text="[b]%s[/b] uchun AI taklifi: [b]%d[/b]" %
                                           (lbl, res["score"]), markup=True))
                if res.get("note"):
                    content.add_widget(MDLabel(text="AI izoh: " + res["note"], markup=True,
                                               theme_text_color="Secondary"))
                cur = self.player_attrs(self.player(pid)).get(code, 50)
                content.add_widget(MDLabel(text="Hozirgi: %d" % cur, markup=True,
                                           theme_text_color="Secondary"))

                def edit(*x):
                    self.close_dialog()
                    manual_edit(pid, code, res["score"])

                self.show_dialog("Mashq tahlili", content=content, buttons=[
                    MDFlatButton(text="Bekor", on_release=self.close_dialog),
                    MDFlatButton(text="Qo'lda", on_release=edit),
                    MDRaisedButton(text="Tasdiqlash", on_release=use_ai)])

            Clock.schedule_once(done, 0)

        def manual_edit(pidx, code2, default):
            def got(v):
                self._apply_attr(pidx, code2, v)
            self.input_dialog("%s qo'lda" % lbl, "Raqam (45-99)", got,
                              text=str(default), digits=True)

        threading.Thread(target=work, daemon=True).start()

    def player_card(self, pid):
        """O'yinchining shaxsiy kartochkasi."""
        p = self.player(pid)
        if not p:
            return
        s = self.player_stats(pid)
        y_now, susp = self.card_status(pid)
        role = " (kapitan)" if self.is_captain(pid) else ""
        ovr, base, bonus = self.player_ovr(pid)
        lines = [
            f"Guruh: [b]{self.gname(p['group']) if p['group'] else 'tanlanmagan'}[/b]{role}",
            f"OVR: boshlang'ich [b]{base}[/b] + natija [b]{bonus:+d}[/b] = [b]{ovr}[/b]",
            f"APEX TOKEN: [b]{p.get('tokens', TOKEN_START)}[/b]"
            + ("  [color=#c62828][b](0: tarkib taqiqlangan, OVR pasaymoqda)[/b][/color]"
               if self.token_banned(p["id"]) else ""),
            f"O'ynagan o'yinlar: [b]{s['apps']}[/b]",
            f"   Asosiy tarkibda boshlagan: [b]{s['starts']}[/b]",
            f"   Zaxiradan tushgan (sub in): [b]{s['sub_in']}[/b]",
            f"   Almashtirilib chiqqan (sub out): [b]{s['sub_out']}[/b]",
            f"Gollar: [b]{s['goals']}[/b]     Assistlar: [b]{s['assists']}[/b]",
            f"G'alabalar: [b]{s['wins']}[/b]",
            f"[color=#c79100]Player of the Match: [b]{s['motm']}[/b][/color]  (qo'shimcha ball bermaydi)",
            f"[color=#c79100]Sariq: {s['yellow']}[/color]     [color=#c62828]Qizil: {s['red']}[/color]",
        ]
        if susp:
            lines.append("[color=#c62828][b]Keyingi o'yinda jarimada[/b][/color]")
        lines += [
            "[b]Ball hisobi:[/b]",
            f"   Gol: {s['goals']} x {POINTS['goal']} = {s['goals'] * POINTS['goal']:+d}",
            f"   Assist: {s['assists']} x {POINTS['assist']} = {s['assists'] * POINTS['assist']:+d}",
            f"   G'alaba: {s['wins']} x {POINTS['win']} = {s['wins'] * POINTS['win']:+d}",
            f"   Sariq: {s['yellow']} x {POINTS['yellow']} = {s['yellow'] * POINTS['yellow']:+d}",
            f"   Qizil: {s['red']} x {POINTS['red']} = {s['red'] * POINTS['red']:+d}",
            f"[b]JAMI: {s['points']} ball[/b]",
        ]
        g = self.group(p["group"]) if p["group"] else None
        num = p.get("number")
        head = MDCard(orientation="horizontal", size_hint_y=None, height=dp(124), padding=dp(10),
                      spacing=dp(10), radius=[14], md_bg_color=self.ovr_color(ovr))
        ov = MDBoxLayout(orientation="vertical", size_hint_x=None, width=dp(64))
        ov.add_widget(MDLabel(text=f"[b]{ovr}[/b]", markup=True, font_style="H3", halign="center"))
        ov.add_widget(MDLabel(text=f"[b]{p.get('pos') or '-'}[/b]", markup=True, halign="center"))
        ov.add_widget(MDLabel(text="OVR", font_style="Caption", halign="center"))
        info = MDBoxLayout(orientation="vertical", spacing=dp(2))
        info.add_widget(MDLabel(text=f"[b]{p['name']}[/b]", markup=True, font_style="H6"))
        info.add_widget(MDLabel(
            text=f"Raqam: [b]{('#' + str(num)) if num else '-'}[/b]   {POS_NAME.get(p.get('pos'), '-')}",
            markup=True, font_style="Caption"))
        info.add_widget(MDLabel(text=f"Davlat: [b]{p.get('country') or DEFAULT_COUNTRY}[/b]",
                                markup=True, font_style="Caption"))
        info.add_widget(MDLabel(text=f"Jamoa: [b]{g['name'] if g else 'tanlanmagan'}[/b]",
                                markup=True, font_style="Caption"))
        head.add_widget(ov)
        head.add_widget(info)
        if g:
            head.add_widget(Image(source=self.logo_source(g), size_hint_x=None, width=dp(64)))
        inner = BoxLayout(orientation="vertical", spacing=dp(6))
        inner.add_widget(self.fc_card_widget(p))
        inner.add_widget(head)
        gold = (0.78, 0.57, 0, 1)
        badge = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44),
                            spacing=dp(8))
        badge.add_widget(MDIcon(icon="trophy", font_size=dp(30), theme_text_color="Custom",
                                text_color=gold if s["motm"] else (0.6, 0.6, 0.6, 1),
                                size_hint=(None, None), size=(dp(36), dp(36)),
                                pos_hint={"center_y": 0.5}))
        badge.add_widget(MDLabel(
            text=f"[b]MOTM: {s['motm']}[/b]   |   [b]Jami: {s['points']} ball[/b]",
            markup=True))
        inner.add_widget(badge)
        for ln in lines:
            inner.add_widget(MDLabel(text=ln, markup=True, size_hint_y=None, height=dp(26)))
        buttons = [MDFlatButton(text="Yopish", on_release=self.close_dialog),
                   MDFlatButton(text="Token tarixi",
                                on_release=lambda *a: self.token_history(p["id"]))]
        if p["id"] == self.my_pid() or self.ADMIN_APP:
            buttons.append(MDFlatButton(
                text="Rasm yuklash",
                on_release=lambda *a: self.player_photo_upload(p["id"])))
        if self.ADMIN_APP:
            buttons.append(MDFlatButton(
                text="AI / Mashq",
                on_release=lambda *a: self._admin_attr_menu(p["id"])))
        if p["id"] == self.my_pid() and p["group"] and not p.get("tstatus"):
            buttons.append(MDRaisedButton(
                text="Transfer listga so'rov",
                on_release=lambda *a: (self.close_dialog(), self.transfer_request(p["id"]))))
        self.show_dialog(p["name"], content=inner, buttons=buttons)

    def _admin_attr_menu(self, pid):
        self.choose_dialog("O'yinchi atributlari",
                           [("Mashq videosi tahlili (AI)", "drill"),
                            ("Atributni qo'lda kiritish", "manual")],
                           lambda kind: (self.drill_video(pid) if kind == "drill"
                                         else self.manual_attr(pid)))

    # --- umumiy statistika jadvali (G va A alohida ustunlarda) ---
    STAT_W = [22, None, 26, 26, 26, 26, 26, 26, 42]   # None = egiluvchan (ism ustuni)

    def stat_row(self, cells, header=False, pid=None, bg=CARD):
        row = G.GlassButton(orientation="horizontal", size_hint_y=None, height=dp(34),
                            padding=(dp(8), 0), spacing=dp(2), radius=12,
                            fill=(G.BLUE if header else bg),
                            border=((0, 0, 0, 0) if header else G.BORDER))
        for i, txt in enumerate(cells):
            box = ({"size_hint_x": 1} if self.STAT_W[i] is None
                   else {"size_hint_x": None, "width": dp(self.STAT_W[i])})
            text = f"[color=#{GOLD_HEX}][b]{txt}[/b][/color]" if header else str(txt)
            row.add_widget(G.TL(text, 11 if header else 12,
                                G.MUTED if header else G.WHITE,
                                align="left" if i == 1 else "center", **box))
        if pid is not None:
            row.bind(on_release=lambda *a: self.player_card(pid))
        return row

    def build_stats_table(self, box):
        box.add_widget(self.header("[b]O'yinchilar statistikasi[/b]"))
        box.add_widget(self.note(
            "O = o'yin, G = gol, A = assist, S = sariq, Q = qizil, M = Player of the Match (kubok). "
            "Ball: gol +3, assist +2, g'alaba +3, sariq -1, qizil -3. "
            "Shaxsiy kartochka uchun qatorni bosing.", 56))
        rows = []
        for p in self.d["players"]:
            if p["group"] is None:
                continue
            rows.append((p, self.player_stats(p["id"])))
        rows.sort(key=lambda r: (-r[1]["points"], -r[1]["goals"], -r[1]["assists"], r[0]["name"]))
        box.add_widget(self.stat_row(["#", "O'yinchi", "O", "G", "A", "S", "Q", "M", "Ball"], header=True))
        for i, (p, s) in enumerate(rows, 1):
            box.add_widget(self.stat_row(
                [self.rank_text(i), p["name"][:12], s["apps"], s["goals"], s["assists"],
                 s["yellow"], s["red"],
                 (f"[color=#c79100][b]{s['motm']}[/b][/color]" if s["motm"] else 0),
                 f"[b]{s['points']}[/b]"], pid=p["id"],
                bg=(CARD if i % 2 else CARD2)))

    def build_leaderboards(self, box):
        """Alohida reytinglar: bombardirlar, assistentlar, MOTM, umumiy ball."""
        rows = [(p, self.player_stats(p["id"])) for p in self.d["players"]
                if p["group"] is not None]
        if not rows:
            return
        box.add_widget(self.header("[b]Reytinglar[/b]"))
        icons = {"goals": "soccer", "assists": "account-arrow-right-outline",
                 "motm": "trophy-outline", "points": "star-outline"}

        def top(key, label, n=8):
            rr = sorted((r for r in rows if r[1][key] > 0),
                        key=lambda r: (-r[1][key], r[0]["name"]))[:n]
            if not rr:
                return
            box.add_widget(self.header(f"[b]{label}[/b]", h=30))
            for i, (p, s) in enumerate(rr, 1):
                box.add_widget(self.event_row(
                    icons[key],
                    f"{self.rank_text(i)}.  {p['name']}  —  {s[key]}   "
                    f"({self.gname(p['group'])} · {self.player_line(p)})",
                    G.YELLOW if key == "motm" else G.WHITE,
                    lambda pid=p["id"]: self.player_card(pid)))
        top("goals", "Bombardirlar (gol)")
        top("assists", "Assistentlar")
        top("motm", "Player of the Match")
        top("points", "Umumiy ball")

    # ---------------- boshlang'ich sozlashni yakunlash ----------------

    # ---------------- yangilash ----------------
    def refresh_all(self):
        self.update_toolbar()
        # Faqat shu ilova qurgan tab'larni yangilaymiz (Kivy App.__getattr__
        # yo'q atributda boshqa metodni qaytaradi, shuning uchun __dict__ bo'yicha).
        for key in ("groups", "lineup", "table", "transfer", "market"):
            if "b_" + key in self.__dict__:
                getattr(self, "refresh_" + key)()

    # --- o'yinchining o'zi ro'yxatdan o'tishi ---
    def submit_registration(self, first, last, number, pos):
        """O'yinchi o'zi ro'yxatdan o'tadi: ism, familiya, raqam va pozitsiya."""
        if not self.d["setup_done"]:
            toast("Turnir hali boshlanmagan. Admin boshlagach ro'yxatdan o'tasiz.")
            return False
        first = " ".join((first or "").split())
        last = " ".join((last or "").split())
        if not 2 <= len(first) <= 30:
            toast("Ismni to'liq kiriting (2-30 belgi)")
            return False
        if not 2 <= len(last) <= 30:
            toast("Familiyani to'liq kiriting (2-30 belgi)")
            return False
        if not (str(number).isdigit() and 1 <= int(number) <= 99):
            toast("O'yindagi raqam 1 dan 99 gacha bo'lsin")
            return False
        if pos not in POS_NAME:
            toast("Pozitsiyangizni tanlang")
            return False
        name = f"{first} {last}"
        if self.name_exists(name):
            toast("Bu ism allaqachon ro'yxatda")
            return False
        p = {"id": self.store.new_id(), "name": name, "first": first, "last": last,
             "group": None, "self_registered": True, "number": int(number),
             "pos": pos, "country": DEFAULT_COUNTRY,
             "tokens": TOKEN_START, "token_zero_since": None,
             "attrs": dict(gemini.DEFAULT_ATTRS), "ovr": gemini.ovr_from_attrs(gemini.DEFAULT_ATTRS),
             "photo_b64": None, "card_b64": None}
        self.d["players"].append(p)
        ok = self.store.save()
        if ok:
            self.set_my_pid(p["id"])   # qurilma endi shu o'yinchi sifatida taniladi
        self.route()
        if ok:
            toast("Ro'yxatdan o'tdingiz! Admin guruhga biriktirgach ilova ochiladi.")
        return ok

    # ---------------- GURUHLAR oynasi ----------------
    def refresh_groups(self):
        box = self.b_groups
        box.clear_widgets()
        box.add_widget(self.hero("Jamongiz tarkibi va statistikasi"))
        if not self.d["groups"]:
            box.add_widget(self.note(
                "Guruhlar hali tuzilmagan. Admin guruh yaratib, so'rovdagi o'yinchilarni "
                "bo'lgach, jamoalar shu bo'limda ko'rinadi."))
            return
        for g in self.d["groups"]:
            ms = self.members(g["id"])
            col = self._grp_color(g["id"])
            box.add_widget(G.Band(f"[b]{g['name']}[/b]  ·  kapitan: {self.captain_name(g)}",
                                  col, logo=self.logo_source(g), name=g["name"],
                                  chip=f"{len(ms)} o'yinchi"))
            box.add_widget(G.section_label(f"APEX PRO TOKEN: {g['ptokens']}"))
            if not ms:
                box.add_widget(self.note("Bu guruhda hali o'yinchi yo'q."))
            for p in ms:
                st = self.player_stats(p["id"])
                susp = self.card_status(p["id"])[1]
                star = "  ·  K" if self.is_captain(p["id"]) else ""
                num = f"#{p['number']}  " if p.get("number") else ""
                sub = (f"{p.get('pos') or '-'}  ·  OVR {self.player_ovr(p['id'])[0]}  ·  "
                       f"O:{st['apps']}  ·  Ball:{st['points']}"
                       + ("  ·  JARIMADA" if susp else ""))
                box.add_widget(G.PlayerRow(num + p["name"] + star, sub, col, st["goals"],
                                           st["yellow"] + st["red"],
                                           lambda pid=p["id"]: self.player_card(pid)))

    # ---------------- TARKIB (boshlang'ich 6) oynasi ----------------
    def event_row(self, icon, text, color=None, cb=None):
        """Panel ichidagi kichik qator: ikonka + matn (ixtiyoriy bosiladigan)."""
        r = G.GlassButton(orientation="horizontal", size_hint_y=None, height=dp(40),
                          padding=(dp(10), 0), spacing=dp(8), radius=12,
                          fill=G.GLASS, border=G.BORDER)
        r.add_widget(G.Icon(icon, 18, color or G.WHITE))
        r.add_widget(G.TL(text, 11.5, G.WHITE, shorten=False))
        if cb:
            r.bind(on_release=lambda *a: cb())
        return r

    def refresh_lineup(self):
        box = self.b_lineup
        box.clear_widgets()
        acts = []
        if self.CAPTAIN_APP:
            acts.append(("Guruh logosini yuklash", self.captain_logo_upload, G.INDIGO))
        if self.REFEREE_APP:
            acts.append(("Hakam sekundomeri", self.clock_dialog, G.CYAN))
            acts.append(("Hakam: gol kiritish (muallif + assist)", self.goal_add, G.GREEN))
            acts.append(("Hakam: golni o'chirish", self.goal_remove, RED))
        for text, cb, col in acts:
            box.add_widget(G.solid_button(text, cb, h=46, fill=col))
        box.add_widget(self.note(
            "Jamoa shakli: 1 darvozabon, 2 himoyachi, 1 yarim himoyachi, 2 hujumchi. "
            "MF va FW o'rin almashadi; GK va DF boshqa pozitsiyada o'ynamaydi. "
            "Tarkibni kapitan Apex Captain ilovasida login/parol bilan belgilaydi; "
            "kartochkalarni faqat admin kiritadi."))
        cap_gids = self.my_team_gids()
        if not self.d["matches"]:
            box.add_widget(self.note("O'yinlar hali yaratilmagan."))
        for m in self.d["matches"]:
            state = self.lock_note(m) + self.clock_running_text(m["id"])
            score = "—" if m["hs"] is None else f"{m['hs']} : {m['as']}"
            box.add_widget(G.MatchCard(
                self.gname(m["home"]), self._grp_color(m["home"]), score,
                self.gname(m["away"]), self._grp_color(m["away"]),
                ("FINAL" if m.get("stage") == "final" else state),
                m["hs"] is not None, lambda mm=m: self.match_journal(mm)))

            inner = [self.note("O'yin jurnali uchun kartani bosing.")]
            if self.kick_ts(m) and m["hs"] is None:
                inner.append(self.note("Boshlanishi: %s  ·  tarkib %s gacha ochiq."
                                       % (self._fmt_ts(self.kick_ts(m)),
                                          self._fmt_ts(self.lock_at(m)))))
            for gid in (m["home"], m["away"]):
                ids = m["lineups"].get(str(gid), [])
                names = ", ".join(self.pname(i) for i in ids) if ids else "kiritilmagan"
                inner.append(G.TL(f"{self.gname(gid)}: {len(ids)}/{LINEUP_SIZE}",
                                  12, G.CYAN, bold=True))
                inner.append(G.note(names))
                if ids:
                    inner.append(self.pitch_widget(m, gid))
                if gid in cap_gids and not self.lineup_closed(m):
                    opp = m["away"] if gid == m["home"] else m["home"]
                    inner.append(G.solid_button(
                        f"Boshlang'ich 6 — {self.gname(opp)} bilan",
                        lambda mm=m, g=gid: self.lineup_dialog(g, mm["id"]),
                        h=44, fill=G.GREEN, size=12.5))
            for gl in m["goals"]:
                ast = f" — assist: {self.pname(gl['assist'])}" if gl.get("assist") else ""
                inner.append(self.event_row("soccer", f"{self.min_tag(gl)}Gol "
                                                      f"({self.gname(gl['team'])}): "
                                                      f"{self.pname(gl['scorer'])}{ast}", G.GREEN))
            for sb in m["subs"]:
                inner.append(self.event_row(
                    "swap-horizontal",
                    f"{self.min_tag(sb)}Almashtirish ({self.gname(sb['team'])}): "
                    f"{self.pname(sb['out'])} chiqdi, {self.pname(sb['in'])} kirdi", G.MUTED))
            for c in m["cards"]:
                inner.append(self.event_row(
                    "circle", f"{self.min_tag(c)}{'Qizil' if c['type'] == 'red' else 'Sariq'} "
                              f"kartochka: {self.pname(c['pid'])}",
                    RED if c["type"] == "red" else G.YELLOW))
            top_pid, mode, tied = self.motm(m)
            if mode in ("auto", "admin"):
                r = self.match_points(m, top_pid)
                tag = "admin tanlovi" if mode == "admin" else "avtomatik"
                inner.append(self.event_row(
                    "trophy-outline",
                    f"Player of the Match: {self.pname(top_pid)} — {r[0]} ball ({tag})",
                    G.YELLOW, lambda pid=top_pid: self.player_card(pid)))
            elif mode == "tie":
                inner.append(self.event_row(
                    "trophy-outline",
                    "Player of the Match: ballar teng ("
                    + ", ".join(self.pname(i) for i in tied) + ") — admin tanlaydi", G.YELLOW))
            box.add_widget(self.panel(*inner, title=state.upper()))

    def pos_counts(self, pids):
        """Tarkibdagi pozitsiyalar soni: {kod: n}."""
        out = {}
        for pid in pids:
            p = self.player(pid)
            code = ((p.get("pos") or "MF").upper() if p else "MF")
            out[code] = out.get(code, 0) + 1
        return out

    def shape_error(self, pids):
        """Jamoa shakli: 1 darvozabon, 2 himoyachi, 3 tasi MF/FW almashinuvi.
        Xato bo'lsa matn qaytadi, to'g'ri bo'lsa None."""
        c = self.pos_counts(pids)
        if c.get("GK", 0) != POS_QUOTA["GK"]:
            return "Darvozabon: aynan %d ta kerak (hozir %d)" % (POS_QUOTA["GK"], c.get("GK", 0))
        if c.get("DF", 0) != POS_QUOTA["DF"]:
            return "Himoyachi: aynan %d ta kerak (hozir %d)" % (POS_QUOTA["DF"], c.get("DF", 0))
        flex = sum(c.get(k, 0) for k in FLEX_SLOTS)
        if flex != POS_QUOTA["MF"] + POS_QUOTA["FW"]:
            return "Yarim himoyachi + hujumchi: jami %d ta kerak (hozir %d)" % (
                POS_QUOTA["MF"] + POS_QUOTA["FW"], flex)
        return None

    def shape_summary(self, pids):
        """Tanlov uchun jonli sanog': 'Darvozabon 1/1 · Himoyachi 1/2 · MF+FW 2/3'."""
        c = self.pos_counts(pids)
        return " · ".join((
            "Darvozabon %d/%d" % (c.get("GK", 0), POS_QUOTA["GK"]),
            "Himoyachi %d/%d" % (c.get("DF", 0), POS_QUOTA["DF"]),
            "MF+FW %d/%d" % (sum(c.get(k, 0) for k in FLEX_SLOTS),
                             POS_QUOTA["MF"] + POS_QUOTA["FW"])))

    def best_six(self, gid, mid):
        """Eng kuchli 6 taklif: shakl (1 GK, 2 DF, 3 MF/FW) saqlanib, OVR bo'yicha."""
        elig = []
        for p in self.members(gid):
            pid = p["id"]
            if self.token_banned(pid) or self.card_status(pid, mid)[1]:
                continue
            elig.append(p)

        def by_pos(codes, take):
            xs = [p for p in elig if (p.get("pos") or "MF").upper() in codes]
            xs.sort(key=lambda p: self.player_ovr(p["id"])[0], reverse=True)
            return xs[:take]

        out = by_pos(("GK",), POS_QUOTA["GK"]) + by_pos(("DF",), POS_QUOTA["DF"])
        out += by_pos(FLEX_SLOTS, LINEUP_SIZE - len(out))
        return [p["id"] for p in out]

    def pitch_widget(self, m, gid):
        """Boshlang'ich 6 ni maydon ustida pozitsiyalar bo'yicha joylashtirish."""
        ids = m["lineups"].get(str(gid), [])
        pitch = G.Pitch(size_hint_y=None, height=dp(300))
        # pozitsiya qatlamlari (pastdan yuqoriga): GK, DF, MF, FW
        lanes = {"GK": 0.12, "DF": 0.36, "MF": 0.62, "FW": 0.86}
        buckets = {k: [] for k in lanes}
        for pid in ids:
            p = self.player(pid)
            if not p:
                continue
            buckets.get(p.get("pos") or "MF", buckets["MF"]).append(p)
        for pos, cy in lanes.items():
            row = buckets[pos]
            n = len(row)
            for i, p in enumerate(row):
                cx = (i + 1) / (n + 1)
                ovr = self.player_ovr(p["id"])[0]
                node = G.BoxLayout(orientation="vertical", size_hint=(None, None),
                                   size=(dp(86), dp(54)),
                                   pos_hint={"center_x": cx, "center_y": cy})
                nm = p["name"].split()[0]
                node.add_widget(G.TL(f"#{p.get('number') or '-'}", 11, G.YELLOW, bold=True,
                                     align="center", size_hint_y=None, height=dp(18)))
                node.add_widget(G.TL(nm, 11.5, G.WHITE, bold=True, align="center",
                                     size_hint_y=None, height=dp(18)))
                node.add_widget(G.TL(f"OVR {ovr}", 10, G.MUTED, align="center",
                                     size_hint_y=None, height=dp(16)))
                pitch.add_widget(node)
        return pitch

    def match_journal(self, m):
        """O'yin jurnali: gol/almashtirish/kartochka voqealari vaqt tartibida."""
        events = []
        for gl in m["goals"]:
            ast = f" (assist: {self.pname(gl['assist'])})" if gl.get("assist") else ""
            events.append((gl.get("ts"), self.min_tag(gl) + f"GOL — {self.gname(gl['team'])}: "
                             f"{self.pname(gl['scorer'])}{ast}"))
        for sb in m["subs"]:
            events.append((sb.get("ts"), self.min_tag(sb) + f"Almashtirish — {self.gname(sb['team'])}: "
                           f"{self.pname(sb['out'])} chiqdi, "
                           f"{self.pname(sb['in'])} kirdi"))
        for c in m["cards"]:
            kind = "QIZIL" if c["type"] == "red" else "SARIQ"
            events.append((c.get("ts"), self.min_tag(c) + f"{kind} kartochka — {self.pname(c['pid'])}"))
        events.sort(key=lambda e: e[0] or 0)
        items = [TwoLineListItem(text=txt, secondary_text=self._fmt_ts(ts), disabled=True)
                 for ts, txt in events]
        if not items:
            items = [OneLineListItem(text="Hozircha voqea yo'q", disabled=True)]
        title = f"Jurnal: {self.gname(m['home'])} — {self.gname(m['away'])}"
        self.show_dialog(title, items=items)

    def lineup_dialog(self, gid, mid):
        m = self.match(mid)
        if not m:
            return
        sel = set(m["lineups"].get(str(gid), []))
        items = []
        togglers = []          # (item_widget, pid, name)
        status = OneLineListItem(text="", disabled=True)
        items.append(status)   # jonli shakl sanog'i: Darvozabon 1/1 · Himoyachi 1/2 · MF+FW 3/3

        def render():
            status.text = self.shape_summary(list(sel))
            for it, pid, name in togglers:
                it.text = ("[+] " if pid in sel else "[  ] ") + name

        for p in self.members(gid):
            pid, name = p["id"], p["name"]
            pos = (p.get("pos") or "MF").upper()
            label = "%s (%s)" % (name, POS_NAME.get(pos, "-"))
            y, susp = self.card_status(pid, mid)
            if susp:
                sel.discard(pid)
                items.append(OneLineListItem(text=f"{label} — jarimada (o'ynay olmaydi)",
                                             disabled=True))
                continue
            if self.token_banned(pid):
                sel.discard(pid)
                items.append(OneLineListItem(text=f"{label} — APEX TOKEN 0 (o'ynay olmaydi)",
                                             disabled=True))
                continue
            it = OneLineListItem(text=("[+] " if pid in sel else "[  ] ") + label)

            def toggle(item, pid=pid, label=label):
                if pid in sel:
                    sel.discard(pid)
                else:
                    if len(sel) >= LINEUP_SIZE:
                        toast(f"Faqat {LINEUP_SIZE} ta tanlanadi")
                        return
                    sel.add(pid)
                render()
                toast(f"Tanlandi: {len(sel)}/{LINEUP_SIZE} — {self.shape_summary(list(sel))}")
            it.bind(on_release=toggle)
            items.append(it)
            togglers.append((it, pid, label))
        render()   # ochilishida ham jonli shakl sanog'i ko'rinsin

        def suggest(*a):
            best = self.best_six(gid, mid)
            if len(best) < LINEUP_SIZE:
                toast("Yetarli o'yinchi yo'q (jarima/token taqiqlanganlar bor)")
            sel.clear()
            sel.update(best)
            render()
            toast(f"Taklif: {len(sel)}/{LINEUP_SIZE} — eng yuqori OVR")

        def save(*a):
            if self.set_lineup(gid, mid, list(sel)):
                self.close_dialog()
        self.show_dialog(f"Boshlang'ich {LINEUP_SIZE} ta — {self.gname(gid)}", items=items,
                         buttons=[MDFlatButton(text="Bekor", on_release=self.close_dialog),
                                  MDFlatButton(text="Eng yaxshi 6", on_release=suggest),
                                  MDRaisedButton(text="Saqlash", on_release=save)])

    def set_lineup(self, gid, mid, pids):
        """Barcha qoidalar shu yerda qayta tekshiriladi."""
        m = self.match(mid)
        if not m or gid not in (m["home"], m["away"]):
            toast("O'yin topilmadi")
            return False
        if self.lineup_closed(m):
            toast("Tarkib yopiq — " + self.lock_note(m))
            return False
        if len(set(pids)) != LINEUP_SIZE:
            toast(f"Aynan {LINEUP_SIZE} ta o'yinchi tanlang")
            return False
        err = self.shape_error(pids)
        if err:
            toast("Shakl buzildi: " + err)
            return False
        for pid in pids:
            p = self.player(pid)
            if not p or p["group"] != gid:
                toast("O'yinchi bu guruhga tegishli emas")
                return False
            if self.token_banned(pid):
                toast(f"{p['name']} APEX TOKEN 0: asosiy tarkibga chiqolmaydi")
                return False
            if self.card_status(pid, mid)[1]:
                toast(f"{p['name']} jarimada")
                return False
        m["lineups"][str(gid)] = list(pids)
        ok = self.store.save()
        self.refresh_all()
        if ok:
            toast("Tarkib saqlandi")
        return ok

    # ---------------- JADVAL oynasi ----------------
    def stage_groups(self):
        """8 tadan ko'p jamoa bo'lsa guruh bosqichi: jamoalar ikki yarmga bo'linadi."""
        gs = [g["id"] for g in self.d["groups"]]
        if len(gs) <= 8:
            return None
        half = (len(gs) + 1) // 2
        return [gs[:half], gs[half:]]

    def planned_pairs(self, ids, double):
        out = []
        for a, b in itertools.combinations(ids, 2):
            out.append((a, b))
            if double:
                out.append((b, a))
        return out

    def group_stage_complete(self):
        if not self.d["groups"]:
            return False
        halves = self.stage_groups()
        scopes = halves if halves else [[g["id"] for g in self.d["groups"]]]
        for scope in scopes:
            want = set(self.planned_pairs(scope, halves is None))
            done = {(m["home"], m["away"]) for m in self.d["matches"]
                    if m.get("stage", "group") == "group" and m["hs"] is not None
                    and m["home"] in scope and m["away"] in scope}
            if not want <= done:
                return False
        return True

    def final_match(self):
        return next((m for m in self.d["matches"] if m.get("stage") == "final"), None)

    def final_candidates(self):
        halves = self.stage_groups()
        if halves:
            out = []
            for h in halves:
                st = self.standings(grp=h)
                if st:
                    out.append(st[0]["gid"])
            return out
        st = self.standings()
        return [r["gid"] for r in st[:2]]

    def award_final(self, m):
        """FINAL natijasi kiritilganda g'olib jamoaga APEX PRO TOKEN."""
        if m.get("stage") != "final" or m["hs"] is None or m["hs"] == m["as"] or m.get("awarded"):
            return
        w = m["home"] if m["hs"] > m["as"] else m["away"]
        g = self.group(w)
        if not g:
            return
        m["awarded"] = True
        g["ptokens"] = int(g.get("ptokens", 0)) + TEAM_WIN_TOKENS
        self.push_notif(f"g{w}", f"Tabriklaymiz! {g['name']} g'olib bo'ldi: "
                                 f"+{TEAM_WIN_TOKENS} APEX PRO TOKEN.")
        self.push_notif("all", f"{g['name']} turnir g'olibi bo'ldi!")

    def standings(self, grp=None, stage="group"):
        ids = set(grp) if grp is not None else None
        rows = {g["id"]: dict(gid=g["id"], name=g["name"], P=0, W=0, D=0, L=0, GF=0, GA=0, PTS=0,
                              HPTS=0, HGD=0, HGF=0)
                for g in self.d["groups"] if ids is None or g["id"] in ids}
        played = []
        for m in self.d["matches"]:
            if m.get("stage", "group") != stage or m["hs"] is None:
                continue
            if m["home"] not in rows or m["away"] not in rows:
                continue
            played.append(m)
            h, a = rows[m["home"]], rows[m["away"]]
            h["P"] += 1; a["P"] += 1
            h["GF"] += m["hs"]; h["GA"] += m["as"]
            a["GF"] += m["as"]; a["GA"] += m["hs"]
            if m["hs"] > m["as"]:
                h["W"] += 1; a["L"] += 1; h["PTS"] += 3
            elif m["hs"] < m["as"]:
                a["W"] += 1; h["L"] += 1; a["PTS"] += 3
            else:
                h["D"] += 1; a["D"] += 1; h["PTS"] += 1; a["PTS"] += 1
        clusters = {}
        for r in rows.values():
            clusters.setdefault(r["PTS"], []).append(r["gid"])
        for gids in clusters.values():
            if len(gids) > 1:
                self._h2h(rows, played, gids)
        return sorted(rows.values(),
                      key=lambda r: (-r["PTS"], -r["HPTS"], -r["HGD"], -r["HGF"],
                                     -(r["GF"] - r["GA"]), -r["GF"], r["name"]))

    @staticmethod
    def _h2h(rows, played, gids):
        """Teng balli jamoalar klasteri ichidagi o'zaro uchrashuv mini-jadvali.

        Qoida: klaster a'zolari o'zaro HAMMA juftliklarni o'ynab bo'lgan bo'lsagina
        o'zaro uchrashuv qo'llanadi — aks holda o'yinlar tugallanmagan, umumiy
        to'plar farqi asosiy ko'rsatkich bo'lib qoladi.
        """
        sel = set(gids)
        need = {(a, b) for a in gids for b in gids if a < b}
        done = {(min(m["home"], m["away"]), max(m["home"], m["away"]))
                for m in played if m["home"] in sel and m["away"] in sel}
        if not need <= done:
            return
        mini = {g: dict(PTS=0, GD=0, GF=0) for g in gids}
        for m in played:
            if m["home"] not in sel or m["away"] not in sel:
                continue
            h, a = mini[m["home"]], mini[m["away"]]
            h["GF"] += m["hs"]; h["GD"] += m["hs"] - m["as"]
            a["GF"] += m["as"]; a["GD"] += m["as"] - m["hs"]
            if m["hs"] > m["as"]:
                h["PTS"] += 3
            elif m["hs"] < m["as"]:
                a["PTS"] += 3
            else:
                h["PTS"] += 1; a["PTS"] += 1
        for g, x in mini.items():
            rows[g].update(HPTS=x["PTS"], HGD=x["GD"], HGF=x["GF"])

    def _table_rows(self, box, rows, top_mark=1):
        box.add_widget(G.table_row(["O'yin", "G'D'M", "To'plar", "Ball"],
                                   [40, 62, 62, 44], header=True, name="Jamoa", h=32))
        for i, r in enumerate(rows, 1):
            box.add_widget(G.table_row(
                [r["P"], f"{r['W']}-{r['D']}-{r['L']}", f"{r['GF']}-{r['GA']}"],
                [40, 62, 62], pts=r["PTS"], pts_w=44, h=42,
                name=f"{self.rank_text(i)}.  {r['name']}",
                hl=(i <= top_mark and r["PTS"] > 0)))

    @staticmethod
    def h2h_note(rows):
        """O'zaro uchrashuv qo'llangan bo'lsa (teng ballar ajratilsa) qisqa izoh."""
        tied = [r for r in rows if r["HPTS"] or r["HGD"] or r["HGF"]]
        if len(tied) < 2:
            return None
        return ("Ballar teng: %s. O'rinni avval [b]o'zaro uchrashuv[/b] "
                "(ball → to'plar farqi → to'plar) belgiladi."
                % ", ".join(r["name"] for r in tied[:4]))

    def table_image(self, halves, fin):
        """Jadvalning rasmga tushadigan ixcham ko'rinishi (ulashish uchun)."""
        p = G.Glass(orientation="vertical", size_hint_y=None, spacing=dp(6),
                    padding=(dp(14), dp(12)), radius=20,
                    fill=(0.055, 0.08, 0.21, 1), border=(0.35, 0.75, 1, .55))
        p.bind(minimum_height=p.setter("height"))
        p.add_widget(G.TL("APEX [b]PRO LEAGUE[/b]", 17, G.YELLOW, bold=True, align="center",
                          size_hint_y=None, height=dp(28)))
        p.add_widget(G.TL(time.strftime("%d.%m.%Y %H:%M"), 11, G.MUTED, align="center",
                          size_hint_y=None, height=dp(20)))
        if halves:
            for i, h in enumerate(halves, 1):
                rows = self.standings(grp=h)
                p.add_widget(G.TL("%d-guruh (guruh bosqichi)" % i, 12.5, G.CYAN, bold=True))
                self._table_rows(p, rows, top_mark=1)
                n = self.h2h_note(rows)
                if n:
                    p.add_widget(G.note(n, size=10))
        else:
            rows = self.standings()
            self._table_rows(p, rows, top_mark=2)
            n = self.h2h_note(rows)
            if n:
                p.add_widget(G.note(n, size=10))
        if fin and fin["hs"] is not None and fin["hs"] != fin["as"]:
            w = fin["home"] if fin["hs"] > fin["as"] else fin["away"]
            p.add_widget(G.TL("[b]CHEMPION: %s[/b]  (%d:%d)"
                              % (self.gname(w), fin["hs"], fin["as"]),
                              13, G.YELLOW, bold=True, align="center"))
        elif fin:
            p.add_widget(G.TL("FINAL: %s — %s" % (self.gname(fin["home"]), self.gname(fin["away"])),
                              12.5, G.WHITE, bold=True, align="center"))
        tops = self.top_scorers(3)
        if tops:
            p.add_widget(G.TL("Eng ko'p gol urganlar", 12.5, G.CYAN, bold=True))
            for pid, n in tops:
                p.add_widget(G.TL("%s — %d ta" % (self.pname(pid), n), 12, G.WHITE))
        return p

    def top_scorers(self, n=3):
        rows = [(p["id"], self.player_stats(p["id"])["goals"])
                for p in self.d["players"] if p["group"] is not None]
        rows = [r for r in rows if r[1] > 0]
        rows.sort(key=lambda r: (-r[1], self.pname(r[0])))
        return rows[:n]

    def share_table_image(self):
        """Jadvalni PNG qilib tayyorlaydi: ko'rib chiqish + 'PNG yuborish'."""
        panel = self.table_image(self.stage_groups(), self.final_match())

        def send(*a):
            self.export_png(panel, "jadval",
                            lambda path: share_file(path, "image/png", "Jadvalni ulashish")
                            if path else None)
        self.show_dialog("Jadval rasmi", content=panel, buttons=[
            MDFlatButton(text="Yopish", on_release=self.close_dialog),
            MDRaisedButton(text="PNG yuborish", on_release=send)])

    def export_png(self, widget, name, callback):
        """Vidjetni PNG ga aylantiradi (2× aniqlik) va callback(yo'l) chaqiriladi."""
        png = os.path.join(self.user_data_dir, "export", "%s_%s.png"
                           % (name, time.strftime("%Y%m%d_%H%M%S")))

        def do(*a):
            try:
                os.makedirs(os.path.dirname(png), exist_ok=True)
                widget.export_to_png(png, scale=2)
                callback(png)
            except Exception as e:
                toast("Rasmga olishning ilovasi bo'lmadi: " + str(e)[:60])
                callback(None)
        # dialog bir kadr chizgandan keyingina to'liq o'lchanadi
        Clock.schedule_once(do, 0.3)

    def refresh_table(self):
        box = self.b_table
        box.clear_widgets()
        box.add_widget(self.hero("Turnir jadvali va statistika"))
        box.add_widget(G.solid_button("Jadvalni rasm (PNG) qilib ulashish",
                                      self.share_table_image, h=46, fill=G.INDIGO))
        halves = self.stage_groups()
        if halves:
            for i, h in enumerate(halves, 1):
                box.add_widget(self.header(f"[b]{i}-guruh jadvali (guruh bosqichi)[/b]"))
                rows = self.standings(grp=h)
                self._table_rows(box, rows, top_mark=1)
                n = self.h2h_note(rows)
                if n:
                    box.add_widget(self.note(n))
            box.add_widget(self.note("Har ikki guruh g'olibi FINAL da o'ynaydi.", 30))
        else:
            box.add_widget(self.header("[b]Turnir jadvali[/b]"))
            rows = self.standings()
            self._table_rows(box, rows, top_mark=2)
            n = self.h2h_note(rows)
            if n:
                box.add_widget(self.note(n))
        fin = self.final_match()
        if fin:
            box.add_widget(self.header("[b]FINAL[/b]"))
            score = "—" if fin["hs"] is None else f"{fin['hs']} : {fin['as']}"
            box.add_widget(G.MatchCard(
                self.gname(fin["home"]), self._grp_color(fin["home"]), score,
                self.gname(fin["away"]), self._grp_color(fin["away"]),
                "Chempionlik o'yini", fin["hs"] is not None,
                lambda mm=fin: self.match_journal(mm)))
            if fin["hs"] is not None and fin["hs"] != fin["as"]:
                w = self.group(fin["home"] if fin["hs"] > fin["as"] else fin["away"])
                box.add_widget(G.Band(f"[b]CHEMPION: {self.gname(w['id'])}[/b]  "
                                      f"(+{TEAM_WIN_TOKENS} APEX PRO TOKEN)",
                                      G.YELLOW, logo=self.logo_source(w), name=w["name"]))
            box.add_widget(self.note("3-o'rin va undan past jamoalar musobaqani yakunlagan."))
        elif self.group_stage_complete():
            c = self.final_candidates()
            if len(c) == 2:
                box.add_widget(G.Band(
                    f"[b]FINAL juftligi: {self.gname(c[0])} — {self.gname(c[1])}[/b]  "
                    "(admin FINAL o'yinini yaratadi)", G.YELLOW))
            rest = [r for r in self.standings() if not halves][2:] if not halves else []
            if rest:
                box.add_widget(self.note("3-o'rin va undan past jamoalar musobaqani yakunlagan."))
        box.add_widget(self.header("[b]O'yinlar[/b]"))
        if not self.d["matches"]:
            box.add_widget(self.note("Hozircha o'yinlar yo'q."))
        for m in self.d["matches"]:
            score = "—" if m["hs"] is None else f"{m['hs']} : {m['as']}"
            box.add_widget(G.MatchCard(
                self.gname(m["home"]), self._grp_color(m["home"]), score,
                self.gname(m["away"]), self._grp_color(m["away"]),
                ("FINAL" if m.get("stage") == "final" else "Guruh bosqichi"),
                m["hs"] is not None, lambda mm=m: self.match_journal(mm)))
        self.build_stats_table(box)
        self.build_leaderboards(box)

    # ---------------- MARKET oynasi ----------------
    def product_card(self, it, gids):
        """Market mahsuloti: rasm/ikonka + nom + narx + 'Olish' tugmasi."""
        row = G.Glass(orientation="horizontal", size_hint_y=None, height=dp(78),
                      padding=(dp(10), dp(8)), spacing=dp(10), radius=18)
        if it.get("img"):
            img = Image(source=b64_to_path(f"m{it['id']}", it["img"]),
                        size_hint=(None, None), size=(dp(60), dp(60)),
                        allow_stretch=True, keep_ratio=True)
            img.pos_hint = {"center_y": .5}
            row.add_widget(img)
        else:
            b = G.Badge(G.PURPLE, 54, icon="package-variant-closed")
            b.pos_hint = {"center_y": .5}
            row.add_widget(b)
        col = G.BoxLayout(orientation="vertical", spacing=dp(2))
        col.add_widget(G.TL(it["name"], 13, G.WHITE, bold=True))
        if it.get("desc"):
            col.add_widget(G.TL(it["desc"], 10.5, G.MUTED, shorten=False))
        col.add_widget(G.TL(f"Narx: {it['price']} token  ·  Qolgan: {it['qty']}",
                            10.5, G.CYAN))
        row.add_widget(col)
        if gids:
            row.add_widget(G.solid_button(
                "Olish", lambda iid=it["id"]: self.market_buy_ask(iid, gids),
                w=78, h=40, fill=G.GREEN, size=12))
        return row

    def refresh_transfer(self):
        """Captain ilovasining Transfer tab'i: so'rovlar, muzokaralar, transfer list."""
        box = self.b_transfer
        box.clear_widgets()
        gids = self.my_team_gids()
        if not gids:
            box.add_widget(self.note("Kapitan sifatida kirmadingiz — Chiqish/Kirish orqali kiring."))
            return
        g = self.group(gids[0])
        if g:
            box.add_widget(G.Band(f"[b]{g['name']}[/b]  ·  balans: [b]{g['ptokens']}[/b] token",
                                  G.YELLOW, logo=self.logo_source(g), name=g["name"]))
        panel = G.BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        panel.bind(minimum_height=panel.setter("height"))
        box.add_widget(panel)
        self.transfer_panel(gids, panel)

    def refresh_market(self):
        box = self.b_market
        box.clear_widgets()
        box.add_widget(self.hero("Market — APEX PRO TOKEN"))
        gids = self.my_team_gids()
        if gids:
            for gid in gids:
                g = self.group(gid)
                if g:
                    box.add_widget(G.Band(
                        f"[b]{g['name']}[/b]  ·  balans: [b]{g['ptokens']}[/b] token",
                        G.YELLOW, logo=self.logo_source(g), name=g["name"]))
        else:
            box.add_widget(self.note(
                "Sotuvdagi mahsulotlar va transfer ro'yxati (o'qish uchun). "
                "Jamoa nomidan xaridni kapitan **Apex Captain** ilovasida qiladi."))
        items = [it for it in self.d["market"] if it["qty"] > 0]
        box.add_widget(self.header(f"[b]Sotuvda: {len(items)}[/b]"))
        if not items:
            box.add_widget(self.note("Hozircha sotuvda narsa yo'q. Admin qo'shadi."))
        for it in items:
            box.add_widget(self.product_card(it, gids))
        listed = [p for p in self.d["players"] if p.get("tstatus") == "listed"]
        box.add_widget(self.header(f"[b]Transfer list: {len(listed)}[/b]"))
        if not listed:
            box.add_widget(self.note("Transfer ro'yxatida hozircha o'yinchi yo'q."))
        for p in listed:
            t = self.transfer_of(p["id"])
            y_cnt, r_cnt = self.card_totals(p["id"])
            st = self.player_stats(p["id"])
            sec = f"{self.player_line(p)} · jamoa: {self.gname(p['group'])}"
            if t and t["status"] == "offer":
                sec += f" · taklif: {t['amount']} token ({self.gname(t['buyer_gid'])})"
            box.add_widget(G.PlayerRow(p["name"], sec, self._grp_color(p["group"]),
                                       st["goals"], y_cnt + r_cnt,
                                       lambda pid=p["id"]: self.player_card(pid)))
            if gids:
                box.add_widget(G.solid_button(
                    f"{p['name']} uchun taklif yuborish",
                    lambda pid=p["id"]: self.offer_dialog(pid), h=44, fill=G.INDIGO, size=12))
        if gids:
            box.add_widget(G.solid_button(
                "Transfer so'rovlarim va muzokaralar", self.captain_transfers,
                h=48, fill=G.BLUE))

    # ---------------- ADMIN oynasi ----------------





    # --- o'yinchilar ---

    def player_label(self, p):
        return f"{p['name']} [{self.gname(p['group']) if p['group'] else 'tanlanmagan'}]"




    # --- guruhlar / kapitanlar ---







    # --- o'yinlar va natijalar ---

    def match_label(self, m):
        sc = "—" if m["hs"] is None else f"{m['hs']}:{m['as']}"
        return f"{self.gname(m['home'])} {sc} {self.gname(m['away'])}"


    # --- bayonnoma: gol + assist ---


    # --- bayonnoma: almashtirishlar (zaxira) ---


    # --- Player of the Match (admin tanlovi) ---

    # --- kartochkalar (faqat admin) ---


    # --- tarkibni boshqarish (admin) ---

    # --- xizmat ---
