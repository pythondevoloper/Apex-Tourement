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
from kivy.uix.scrollview import ScrollView
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivymd.uix.floatlayout import MDFloatLayout

from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel, MDIcon
from kivymd.uix.button import (MDRaisedButton as _MDRaisedButton, MDFlatButton as _MDFlatButton,
                               MDIconButton)
from kivymd.uix.textfield import MDTextField
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import (OneLineListItem as _OneLineListItem, TwoLineListItem as _TwoLineListItem,
                             OneLineIconListItem as _OneLineIconListItem, IconLeftWidget, MDList)
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.card import MDCard

import config
import push
import gemini
from cloud import Firebase, RemoteStore, CloudError, TOKEN_START

LINEUP_SIZE = 6

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
VERSION_CODE = 4                 # ilova versiyasi (version.json bilan solishtiriladi)
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
NAVY2 = (0.157, 0.129, 0.329, 0.97)   # dialog foni (yarim shisha)
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


def _style_item(kw, two=False):
    kw.setdefault("bg_color", CARD)
    kw.setdefault("theme_text_color", "Custom")
    kw.setdefault("text_color", (1, 1, 1, 1))
    if two:
        kw.setdefault("secondary_theme_text_color", "Custom")
        kw.setdefault("secondary_text_color", (0.72, 0.80, 1, 1))
    # "disabled" o'rniga faqat ripple o'chiriladi (matn xira bo'lib qolmasin)
    return bool(kw.pop("disabled", False))


class OneLineListItem(_OneLineListItem):
    def __init__(self, **kw):
        flat = _style_item(kw)
        super().__init__(**kw)
        if flat:
            self._no_ripple_effect = True


class TwoLineListItem(_TwoLineListItem):
    def __init__(self, **kw):
        flat = _style_item(kw, two=True)
        super().__init__(**kw)
        if flat:
            self._no_ripple_effect = True


class OneLineIconListItem(_OneLineIconListItem):
    def __init__(self, **kw):
        flat = _style_item(kw)
        super().__init__(**kw)
        if flat:
            self._no_ripple_effect = True


class MDRaisedButton(_MDRaisedButton):
    def __init__(self, **kw):
        kw.setdefault("md_bg_color", GOLD)
        kw.setdefault("theme_text_color", "Custom")
        kw.setdefault("text_color", NAVY)
        # KivyMD konstruktordagi size_hint_x ni e'tiborsiz qoldiradi: keyin beramiz
        sx = kw.pop("size_hint_x", None)
        super().__init__(**kw)
        if sx is not None:
            self.size_hint_x = sx


class MDFlatButton(_MDFlatButton):
    def __init__(self, **kw):
        kw.setdefault("theme_text_color", "Custom")
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
    """Tanlanadigan belgi (pozitsiya, davlat)."""

    def __init__(self, text, value=None, **kw):
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


class RegisterScreen(MDScreen):
    """O'yinchi o'zi ro'yxatdan o'tadi: Ism, Familiya va o'yindagi raqami so'raladi."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.add_widget(GradientBackground())     # glassmorphism gradient fon (kontent ortida)
        root = MDBoxLayout(orientation="vertical")

        bar = MDBoxLayout(size_hint_y=None, height=dp(56), md_bg_color=BLUE,
                          padding=(dp(8), 0), spacing=dp(6))
        bar.add_widget(MDLabel(text="[b]Ro'yxatdan o'tish[/b]", markup=True, font_style="H6",
                               theme_text_color="Custom", text_color=GOLD))
        root.add_widget(bar)

        sv = ScrollView()
        body = MDBoxLayout(orientation="vertical", adaptive_height=True, padding=dp(16),
                           spacing=dp(12))
        body.add_widget(Widget(size_hint_y=None, height=dp(6)))
        body.add_widget(Image(source=TROPHY, size_hint_y=None, height=dp(120)))
        body.add_widget(MDLabel(text="Apex Pro League", font_style="H4", halign="center",
                                theme_text_color="Custom", text_color=GOLD,
                                size_hint_y=None, height=dp(40)))
        body.add_widget(MDLabel(
            text="Ma'lumotlaringizni kiriting. Ro'yxatdan o'tgach, admin sizni guruhga "
                 "biriktiradi va ilova to'liq ishga tushadi.",
            halign="center", font_style="Caption", theme_text_color="Secondary",
            size_hint_y=None, height=dp(48)))
        card = adaptive_card(orientation="vertical", radius=[16], md_bg_color=CARD,
                             padding=dp(14), spacing=dp(8))
        self.first_field = MDTextField(hint_text="Ism", max_text_length=30, icon_left="account")
        self.last_field = MDTextField(hint_text="Familiya", max_text_length=30,
                                      icon_left="account-outline")
        self.num_field = MDTextField(hint_text="O'yindagi raqam (1-99)", input_filter="int",
                                     max_text_length=2, icon_left="numeric")
        for f in (self.first_field, self.last_field, self.num_field):
            card.add_widget(f)
        body.add_widget(card)
        body.add_widget(Widget())
        sv.add_widget(body)
        root.add_widget(sv)

        foot = MDBoxLayout(size_hint_y=None, height=dp(74), padding=dp(12), md_bg_color=NAVY2)
        foot.add_widget(MDRaisedButton(text="Yuborish", size_hint_x=1,
                                       on_release=lambda *a: self.submit()))
        root.add_widget(foot)
        self.add_widget(root)

    def reset(self):
        self.first_field.text = ""
        self.last_field.text = ""
        self.num_field.text = ""

    def submit(self):
        MDApp.get_running_app().submit_registration(
            self.first_field.text, self.last_field.text, self.num_field.text)


class StatusScreen(MDScreen):
    """Yuklanish / ulanish xatosi / turnir sozlanmagan ekrani."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.add_widget(GradientBackground())     # glassmorphism gradient fon (kontent ortida)
        box = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(14))
        box.add_widget(Widget())
        box.add_widget(Image(source=TROPHY, size_hint_y=None, height=dp(160)))
        self.label = MDLabel(text="Yuklanmoqda...", halign="center",
                             size_hint_y=None, height=dp(100))
        box.add_widget(self.label)
        self.btn = MDRaisedButton(text="Qayta urinish", pos_hint={"center_x": 0.5},
                                  on_release=lambda *a: MDApp.get_running_app().start_sync())
        box.add_widget(self.btn)
        box.add_widget(Widget())
        self.add_widget(box)

    def set(self, text, retry=True):
        self.label.text = text
        self.btn.opacity = 1 if retry else 0
        self.btn.disabled = not retry


class LeagueApp(MDApp):
    dialog = None
    ADMIN_APP = False                  # AdminApp da True
    REFEREE_APP = False                # RefereeApp da True
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
            lab = MDLabel(text="Ilova ishlashda davom etadi. Xato matnining skrinshotini yuboring:\n\n"
                               + text.strip()[-900:], size_hint_y=None, font_style="Caption")
            lab.bind(texture_size=lambda i, v: setattr(i, "height", v[1] + dp(8)))
            sv = ScrollView(size_hint_y=None, height=dp(300))
            sv.add_widget(lab)
            self.show_dialog("Xatolik yuz berdi", content=sv)
        except Exception:
            pass
        Clock.schedule_once(lambda dt: setattr(self, "_crash_shown", False), 5)

    def _on_key(self, window, key, *args):
        """Android 'Orqaga' tugmasi: ro'yxat ekranidan chiqsa holat qayta tekshiriladi."""
        if key == 27 and self.sm.current == "register":
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
        if not self.ADMIN_APP:
            self.register_screen = RegisterScreen(name="register", md_bg_color=NAVY)
            self.sm.add_widget(self.register_screen)
        self.build_extra_screens()
        Window.bind(on_keyboard=self._on_key)
        self.sm.current = self.first_screen()
        Clock.schedule_once(lambda dt: push.request_notification_permission(), 1.0)
        Clock.schedule_once(lambda dt: self.start_sync(), 0.3)
        Clock.schedule_interval(self.poll, getattr(config, "POLL_SECONDS", 6))
        self.check_update()
        return self.sm

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
        self.toolbar.title = (self.TOOLBAR_NAME + " | Draft: "
                              + ("OCHIQ" if self.d["is_draft_open"] else "YOPIQ")
                              + ("" if self.store.online else " | OFLAYN"))
        bell = "bell-badge-outline" if self.unread_notifs() else "bell-outline"
        self.toolbar.right_action_items = [
            [bell, lambda x: self.show_notifs()],
            ["magnify", lambda x: self.search_dialog()],
            ["account-circle-outline", lambda x: self.profile_dialog()]]

    # ---------------- UI qurish ----------------
    def build_main(self):
        scr = MDScreen(name="main", md_bg_color=NAVY)
        scr.add_widget(GradientBackground())      # glassmorphism gradient fon (kontent ortida)
        root = MDBoxLayout(orientation="vertical")
        self.toolbar = MDTopAppBar(title="Apex Pro League", elevation=2, md_bg_color=BLUE,
                                   specific_text_color=GOLD,
                                   left_action_items=[["trophy", lambda x: None]],
                                   right_action_items=[
                                       ["bell-outline", lambda x: self.show_notifs()],
                                       ["magnify", lambda x: self.search_dialog()],
                                       ["account-circle-outline", lambda x: self.profile_dialog()]])
        root.add_widget(self.toolbar)
        nav = MDBottomNavigation()
        # Ranglar yaratilgandan KEYIN beriladi (konstruktorda bersak KivyMD yiqiladi)
        nav.panel_color = BLUE
        nav.text_color_active = GOLD
        nav.text_color_normal = (1, 1, 1, 0.65)
        self.t_draft, self.b_draft = self.make_tab("draft", "Draft", "account-multiple-plus")
        self.t_groups, self.b_groups = self.make_tab("groups", "Guruhlar", "account-group")
        self.t_lineup, self.b_lineup = self.make_tab("lineup", "Bayonnoma", "soccer-field")
        self.t_table, self.b_table = self.make_tab("table", "Jadval", "trophy")
        tabs = [self.t_draft, self.t_groups, self.t_lineup, self.t_table]
        if not self.REFEREE_APP:
            self.t_market, self.b_market = self.make_tab("market", "Market", "storefront")
            tabs.append(self.t_market)
        for t in tabs:
            nav.add_widget(t)
        root.add_widget(nav)
        scr.add_widget(root)
        return scr

    def make_tab(self, name, text, icon):
        item = MDBottomNavigationItem(name=name, text=text, icon=icon)
        sv = MDScrollView(md_bg_color=TRANSPARENT)  # shaffof — ortdagi gradient ko'rinsin
        box = MDBoxLayout(orientation="vertical", adaptive_height=True,
                          padding=dp(10), spacing=dp(6))
        sv.add_widget(box)
        item.add_widget(sv)
        return item, box

    @staticmethod
    def header(text, h=40):
        return MDLabel(text=f"[color=#{GOLD_HEX}]{text}[/color]", markup=True,
                       font_style="Subtitle1", size_hint_y=None, height=dp(h))

    def hero(self, subtitle):
        """Kubok rasmi bilan yuqori banner."""
        card = MDCard(orientation="horizontal", size_hint_y=None, height=dp(120),
                      padding=dp(10), spacing=dp(10), radius=[16], md_bg_color=BLUE)
        card.add_widget(Image(source=TROPHY, size_hint_x=None, width=dp(96)))
        col = MDBoxLayout(orientation="vertical", spacing=dp(2))
        col.add_widget(MDLabel(text="[b]APEX PRO LEAGUE[/b]", markup=True, font_style="H5",
                               theme_text_color="Custom", text_color=GOLD))
        col.add_widget(MDLabel(text=subtitle, font_style="Caption",
                               theme_text_color="Custom", text_color=(1, 1, 1, 0.85)))
        card.add_widget(col)
        return card

    def band(self, text, color, text_color=(1, 1, 1, 1), h=44, logo=None, group=None):
        """Rangli sarlavha tasmasi (ixtiyoriy logo bilan)."""
        card = MDCard(size_hint_y=None, height=dp(h), padding=(dp(12), dp(4)), radius=[10],
                      md_bg_color=color, spacing=dp(8))
        if group is not None:
            card.add_widget(Image(source=self.logo_source(group), size_hint_x=None, width=dp(36)))
        elif logo is not None:
            card.add_widget(Image(source=logo_path(logo), size_hint_x=None, width=dp(36)))
        card.add_widget(MDLabel(text=text, markup=True, theme_text_color="Custom",
                                text_color=text_color))
        return card

    @staticmethod
    def rank_text(i):
        col = {1: "F2C230", 2: "C0C8D8", 3: "CD7F32"}.get(i)
        return f"[color=#{col}][b]{i}[/b][/color]" if col else str(i)

    @staticmethod
    def note(text, h=60):
        return MDLabel(text=text, theme_text_color="Secondary", font_style="Caption",
                       size_hint_y=None, height=dp(h))

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
        self.close_dialog()
        kw = {"title": title}
        if items:
            # KivyMD 1.1.1 "simple" turi oddiy qatorlarda yiqiladi, shuning uchun ro'yxatni o'zimiz quramiz
            lst = MDList()
            for it in items:
                lst.add_widget(it)
            sv = ScrollView(size_hint_y=None, height=min(dp(56) * len(items) + dp(8), dp(320)))
            sv.add_widget(lst)
            kw.update(type="custom", content_cls=sv)
        elif content is not None:
            kw.update(type="custom", content_cls=content)
        elif text:
            kw["text"] = text
        kw["buttons"] = buttons or [MDFlatButton(text="Yopish", on_release=self.close_dialog)]
        kw["md_bg_color"] = NAVY2
        self.dialog = MDDialog(**kw)
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
        field = MDTextField(hint_text=hint, text=text, password=password)
        if digits:
            field.input_filter = "int"
        content = MDBoxLayout(orientation="vertical", size_hint_y=None, height=dp(80))
        content.add_widget(field)

        def ok(*a):
            val = field.text.strip()
            self.close_dialog()
            callback(val)
        self.show_dialog(title, content=content, buttons=[
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

    def current_group(self):
        gs = self.d["groups"]
        return gs[self.d["turn"] % len(gs)] if gs else None

    def free_players(self):
        return [p for p in self.d["players"] if p["group"] is None]

    def members(self, gid):
        return [p for p in self.d["players"] if p["group"] == gid]

    def name_exists(self, name, ignore_id=None):
        return any(p["name"].lower() == name.lower() and p["id"] != ignore_id
                   for p in self.d["players"])

    @staticmethod
    def pin_hash(pin, gid):
        return hash_pw("pin:" + pin, "g" + str(gid))

    @staticmethod
    def valid_pin(pin):
        return pin.isdigit() and len(pin) >= 4

    @staticmethod
    def ref_hash(pin, rid):
        return hash_pw("ref:" + pin, "r" + str(rid))

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
            if m["hs"] is None and not m["lineup_locked"]:
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

    my_cap_gid = None          # shu sessiyada PIN kiritib tasdiqlangan kapitan guruhi

    def my_group(self):
        pid = self.my_pid()
        p = self.player(pid) if pid else None
        return self.group(p["group"]) if p and p["group"] else None

    def captain_groups(self):
        """Men kapitan bo'lgan guruhlar: shaxsim kapitan bo'lsa yoki shu sessiyada PIN kiritilgan."""
        gids = []
        if self.my_cap_gid is not None:
            gids.append(self.my_cap_gid)
        pid = self.my_pid()
        if pid:
            gids += [g["id"] for g in self.d["groups"] if g["captain_id"] == pid]
        return list(dict.fromkeys(gids))

    def captain_auth(self, gid, cb):
        def got_pin(pin):
            if not self.check_pin(gid, pin):
                return
            self.my_cap_gid = gid
            self.sync_push()
            cb()
        self.input_dialog("Kapitan PIN", "PIN", got_pin, password=True, digits=True)

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
        g = self.my_group()
        if g and g["captain_id"] == pid:
            items.append(OneLineListItem(
                text="Kapitan: transfer so'rovlari va muzokaralar",
                on_release=lambda *a: (self.close_dialog(), self.captain_transfers())))
            items.append(OneLineListItem(
                text="Kapitan: Market",
                on_release=lambda *a: (self.close_dialog(), self.market_dialog(g["id"]))))
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
        gids = self.captain_groups()
        if not gids:
            toast("Avval kapitan sifatida PIN kiriting (Bayonnoma -> kapitan amali)")
            return
        inner = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(8),
                            padding=dp(4))
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
        sv = ScrollView(size_hint_y=None, height=dp(440))
        sv.add_widget(inner)
        self.show_dialog("Transfer boshqaruvi (kapitan)", content=sv)

    def offer_dialog(self, pid):
        gids = [g for g in self.captain_groups()]
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
        gids = self.captain_groups()
        me = "seller" if t["seller_gid"] in gids else "buyer"
        acting = t["side"] == me
        inner = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(8),
                            padding=dp(4))
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
        gids = [gid] if gid else self.captain_groups()
        if not gids:
            toast("Marketdan faqat jamoa kapitanlari foydalanadi (PIN kiriting)")
            return
        inner = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(8),
                            padding=dp(4))
        for g in [self.group(g) for g in gids]:
            if g:
                inner.add_widget(self.band(
                    f"[b]{g['name']}[/b]  |  APEX PRO TOKEN: [b]{g['ptokens']}[/b]", GOLD,
                    text_color=NAVY))
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
            card.add_widget(MDRaisedButton(
                text="Olish",
                on_release=lambda *a, iid=it["id"]: self.market_buy_ask(iid, gids)))
            inner.add_widget(card)
        sv = ScrollView(size_hint_y=None, height=dp(440))
        sv.add_widget(inner)
        self.show_dialog("Market (APEX PRO TOKEN)", content=sv)

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
        gids = self.captain_groups()
        if not gids:
            toast("Avval kapitan sifatida PIN kiriting")
            self.choose_dialog("Qaysi guruh kapitani?",
                               [(g["name"], g["id"]) for g in self.d["groups"]],
                               lambda gid: self.captain_auth(gid, self.captain_logo_upload))
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
                        m["goals"].append({"scorer": sid, "assist": aid, "team": gid,
                                           "ts": now_ts()})
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
                opts.append((f"{self.pname(g['scorer'])}{ast} ({self.match_label(m)})", (m["id"], i)))
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

    def has_history(self, pid):
        for m in self.d["matches"]:
            if any(pid in ids for ids in m["lineups"].values()):
                return True
            if any(pid in (s["in"], s["out"]) for s in m["subs"]):
                return True
            if any(pid in (g["scorer"], g.get("assist")) for g in m["goals"]):
                return True
            if any(c["pid"] == pid for c in m["cards"]):
                return True
            if m.get("motm_admin") == pid:
                return True
        return False

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

        content = MDBoxLayout(orientation="vertical", size_hint_y=None, height=dp(460),
                              spacing=dp(6), padding=(dp(4), dp(8), dp(4), 0))
        field = MDTextField(hint_text="Ism yoki raqam bo'yicha qidirish...",
                            icon_left="magnify", max_text_length=40)
        content.add_widget(field)

        pos_row = MDBoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        content.add_widget(pos_row)
        grp_row = MDBoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        content.add_widget(grp_row)
        results = ScrollView(size_hint_y=None, height=dp(300))
        rlist = MDList()
        results.add_widget(rlist)
        content.add_widget(results)

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
                c = Chip(POS_NAME.get(val, label) if val else label, val, size_hint_x=None,
                         width=dp(72))
                c.set_on(state["pos"] == val)
                c.bind(on_release=lambda x, v=val: (state.update(pos=v), build_pos(), render()))
                pos_row.add_widget(c)

        def build_grp():
            grp_row.clear_widgets()
            gs = self.d["groups"]
            opts = [("Barcha", None)] + [(g["name"], g["id"]) for g in gs]
            for label, val in opts:
                c = Chip(label, val, size_hint_x=None, width=dp(88))
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

    def fc_card_widget(self, p):
        attrs = self.player_attrs(p)
        ovr = gemini.ovr_from_attrs(attrs)
        ink = (0.14, 0.10, 0.02, 1)
        card = MDCard(orientation="vertical", size_hint_y=None, height=dp(312),
                      radius=[18], padding=dp(12), spacing=dp(8),
                      md_bg_color=(0.74, 0.58, 0.14, 1))
        top = MDBoxLayout(size_hint_y=None, height=dp(186), spacing=dp(10))
        left = MDBoxLayout(orientation="vertical", size_hint_x=None, width=dp(98))
        left.add_widget(MDLabel(text="[b]%d[/b]" % ovr, markup=True, font_style="H2",
                                halign="center", theme_text_color="Custom", text_color=ink,
                                size_hint_y=None, height=dp(58)))
        left.add_widget(MDLabel(text="[b]%s[/b]" % (p.get("pos") or "-"), markup=True,
                                halign="center", theme_text_color="Custom", text_color=ink,
                                size_hint_y=None, height=dp(22)))
        nm = (p.get("last") or p.get("name") or "").upper()[:12]
        left.add_widget(MDLabel(text="[b]%s[/b]" % nm, markup=True, halign="center",
                                font_style="Subtitle1", theme_text_color="Custom",
                                text_color=ink, size_hint_y=None, height=dp(30)))
        left.add_widget(Widget())
        num = p.get("number")
        left.add_widget(MDLabel(text="#%s" % (num if num else "-"), halign="center",
                                theme_text_color="Custom", text_color=ink, font_style="Caption"))
        top.add_widget(left)
        src = self.fc_card_source(p)
        if src:
            top.add_widget(Image(source=src, allow_stretch=True, keep_ratio=True))
        else:
            ph = MDBoxLayout()
            ph.add_widget(MDIcon(icon="account", font_size=dp(90), halign="center",
                                 valign="middle", theme_text_color="Custom",
                                 text_color=(0.2, 0.14, 0.03, 0.45)))
            top.add_widget(ph)
        card.add_widget(top)
        grid = GridLayout(cols=2, spacing=dp(6), size_hint_y=None, height=dp(94))
        for code, lbl in self.FC_ATTR_LABELS:
            cell = MDBoxLayout(size_hint_y=None, height=dp(30), spacing=dp(4))
            cell.add_widget(MDLabel(text="[b]%d[/b]" % attrs.get(code, 50), markup=True,
                                    halign="right", theme_text_color="Custom", text_color=ink,
                                    size_hint_x=None, width=dp(36)))
            cell.add_widget(MDLabel(text=lbl, font_style="Caption",
                                    theme_text_color="Custom", text_color=ink))
            grid.add_widget(cell)
        card.add_widget(grid)
        _glass_border(card, radius=18, color=(0.95, 0.83, 0.45, 0.9), width=1.4)
        return card

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
        info.add_widget(MDLabel(text=f"Davlat: [b]{p.get('country') or '-'}[/b]",
                                markup=True, font_style="Caption"))
        info.add_widget(MDLabel(text=f"Jamoa: [b]{g['name'] if g else 'tanlanmagan'}[/b]",
                                markup=True, font_style="Caption"))
        head.add_widget(ov)
        head.add_widget(info)
        if g:
            head.add_widget(Image(source=self.logo_source(g), size_hint_x=None, width=dp(64)))
        inner = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(6))
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
        sv = ScrollView(size_hint_y=None, height=dp(460))
        sv.add_widget(inner)
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
        self.show_dialog(p["name"], content=sv, buttons=buttons)

    def _admin_attr_menu(self, pid):
        self.choose_dialog("O'yinchi atributlari",
                           [("Mashq videosi tahlili (AI)", "drill"),
                            ("Atributni qo'lda kiritish", "manual")],
                           lambda kind: (self.drill_video(pid) if kind == "drill"
                                         else self.manual_attr(pid)))

    # --- umumiy statistika jadvali (G va A alohida ustunlarda) ---
    STAT_COLS = [0.07, 0.30, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.15]

    def stat_row(self, cells, header=False, pid=None, bg=CARD):
        row = StatRow(size_hint_y=None, height=dp(34), md_bg_color=(BLUE if header else bg))
        for i, (txt, w) in enumerate(zip(cells, self.STAT_COLS)):
            text = f"[color=#{GOLD_HEX}][b]{txt}[/b][/color]" if header else str(txt)
            row.add_widget(MDLabel(text=text, markup=True, font_style="Caption",
                                   size_hint_x=w, halign="left" if i == 1 else "center"))
        if pid is not None:
            row.bind(on_release=lambda *a, pid=pid: self.player_card(pid))
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

        def top(key, label, n=8):
            rr = sorted((r for r in rows if r[1][key] > 0),
                        key=lambda r: (-r[1][key], r[0]["name"]))[:n]
            if not rr:
                return
            box.add_widget(self.header(f"[b]{label}[/b]", h=30))
            for i, (p, s) in enumerate(rr, 1):
                box.add_widget(TwoLineListItem(
                    text=f"{self.rank_text(i)}.  {p['name']}  —  {s[key]}",
                    secondary_text=f"{self.gname(p['group'])}  |  {self.player_line(p)}",
                    on_release=lambda x, pid=p["id"]: self.player_card(pid)))
        top("goals", "Bombardirlar (gol)")
        top("assists", "Assistentlar")
        top("motm", "Player of the Match")
        top("points", "Umumiy ball")

    # ---------------- boshlang'ich sozlashni yakunlash ----------------

    # ---------------- yangilash ----------------
    def refresh_all(self):
        self.update_toolbar()
        self.refresh_draft()
        self.refresh_groups()
        self.refresh_lineup()
        self.refresh_table()
        if not self.REFEREE_APP:
            self.refresh_market()

    # ---------------- DRAFT oynasi ----------------
    def refresh_draft(self):
        box = self.b_draft
        box.clear_widgets()
        is_open = self.d["is_draft_open"]
        box.add_widget(self.hero("Draft - o'yinchilarni tanlash"))
        card = MDCard(orientation="vertical", padding=dp(12), size_hint_y=None,
                      height=dp(90), radius=[12], md_bg_color=(GREEN if is_open else RED))
        if is_open:
            g = self.current_group()
            card.add_widget(MDLabel(text="[b]Draft: OCHIQ[/b]", markup=True))
            card.add_widget(MDLabel(
                text=f"Navbat: {g['name']} (kapitan: {self.captain_name(g)})" if g else "Guruh yo'q"))
        else:
            card.add_widget(MDLabel(text="[b]Draft: YOPIQ (Locked)[/b]", markup=True))
            card.add_widget(MDLabel(text="O'zgartirish faqat Admin panelda mumkin."))
        box.add_widget(card)

        free = self.free_players()
        box.add_widget(self.header(f"Ro'yxatdan o'tgan, tanlanmagan: {len(free)}"))
        if not free:
            box.add_widget(MDLabel(text="Hamma o'yinchilar guruhlarga taqsimlangan.",
                                   size_hint_y=None, height=dp(40)))
        for p in free:
            pickable = is_open and not self.ADMIN_APP and not self.REFEREE_APP
            box.add_widget(TwoLineListItem(
                text=p["name"], secondary_text=self.player_line(p),
                on_release=(lambda x, pid=p["id"]: self.ask_pick(pid)) if pickable
                else (lambda x, pid=p["id"]: self.player_card(pid))))

    # --- o'yinchining o'zi ro'yxatdan o'tishi ---
    def submit_registration(self, first, last, number):
        """O'yinchi o'zi ro'yxatdan o'tadi: ism, familiya, raqam. Admin o'yinchi yaratmaydi."""
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
        name = f"{first} {last}"
        if self.name_exists(name):
            toast("Bu ism allaqachon ro'yxatda")
            return False
        p = {"id": self.store.new_id(), "name": name, "first": first, "last": last,
             "group": None, "self_registered": True, "number": int(number),
             "pos": DEFAULT_POS, "country": DEFAULT_COUNTRY,
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

    def ask_pick(self, pid):
        if not self.d["is_draft_open"]:
            toast("Draft yopilgan")
            return
        g, p = self.current_group(), self.player(pid)
        if not g or not p:
            return
        dup = any(q["id"] != pid and q["group"] == g["id"] and q.get("number")
                  and q.get("number") == p.get("number") for q in self.d["players"])
        warn = "\nDIQQAT: guruhda bu raqam band, admin keyin o'zgartiradi." if dup else ""
        self.confirm_dialog(
            "Tanlashni tasdiqlang",
            f"{g['name']} ({self.captain_name(g)}) uchun «{p['name']}» tanlansinmi?\n"
            f"{self.player_line(p)}{warn}",
            lambda: self.pick_player(pid))

    def pick_player(self, pid):
        # Mantiqiy himoya: UI dan qat'i nazar draft yopiq bo'lsa rad etiladi
        if not self.d["is_draft_open"]:
            toast("Draft yopilgan. Tanlash mumkin emas.")
            return False
        p, g = self.player(pid), self.current_group()
        if not p or not g or p["group"] is not None:
            toast("Bu o'yinchi allaqachon tanlangan")
            return False
        p["group"] = g["id"]
        self.d["turn"] += 1
        finished = not self.free_players()
        if finished:
            self.d["is_draft_open"] = False
        ok = self.store.save()
        self.refresh_all()
        if ok:
            toast("Draft yakunlandi va yopildi (Locked)" if finished else "Tanlandi")
        return ok

    # ---------------- GURUHLAR oynasi ----------------
    def refresh_groups(self):
        box = self.b_groups
        box.clear_widgets()
        for g in self.d["groups"]:
            ms = self.members(g["id"])
            gi = self.d["groups"].index(g)
            box.add_widget(self.band(
                f"[b]{g['name']}[/b]  (kapitan: {self.captain_name(g)}) - {len(ms)} ta | "
                f"TOKEN: {g['ptokens']}",
                GROUP_COLORS[gi % len(GROUP_COLORS)], group=g))
            for p in ms:
                star = "  (K)" if self.is_captain(p["id"]) else ""
                st = self.player_stats(p["id"])
                y_now, susp = self.card_status(p["id"])
                sec = (f"O:{st['apps']} (asosiy {st['starts']}, zaxira {st['sub_in']}) | "
                       f"G:{st['goals']} A:{st['assists']} | "
                       f"S:{st['yellow']} Q:{st['red']} | MOTM:{st['motm']} | Ball: {st['points']}")
                if susp:
                    sec += " | JARIMADA"
                box.add_widget(TwoLineListItem(
                    text=(f"{('#' + str(p['number']) + '  ') if p.get('number') else ''}"
                          f"{p['name']}{star} | {p.get('pos') or '-'} | OVR {self.player_ovr(p['id'])[0]}"),
                    secondary_text=sec,
                    on_release=lambda x, pid=p["id"]: self.player_card(pid)))

    # ---------------- TARKIB (boshlang'ich 6) oynasi ----------------
    def refresh_lineup(self):
        box = self.b_lineup
        box.clear_widgets()
        if not self.ADMIN_APP:
            box.add_widget(MDRaisedButton(text="Kapitan: boshlang'ich 6 ni belgilash",
                                          size_hint_x=1,
                                          on_release=lambda *a: self.captain_lineup_start()))
            box.add_widget(MDRaisedButton(text="Kapitan: guruh logosini yuklash",
                                          size_hint_x=1,
                                          on_release=lambda *a: self.captain_logo_upload()))
        if self.REFEREE_APP:
            box.add_widget(MDRaisedButton(text="Hakam: gol kiritish (muallif + assist)",
                                          size_hint_x=1,
                                          on_release=lambda *a: self.goal_add()))
            box.add_widget(MDRaisedButton(text="Hakam: golni o'chirish",
                                          size_hint_x=1,
                                          on_release=lambda *a: self.goal_remove()))
        box.add_widget(self.note(
            "Tarkib draft yopilgandan so'ng, kapitan PIN kodi bilan kiritiladi. "
            "Sariq/qizil kartochkalarni faqat admin belgilaydi."))
        if not self.d["matches"]:
            box.add_widget(MDLabel(text="O'yinlar hali yaratilmagan.",
                                   size_hint_y=None, height=dp(40)))
        for m in self.d["matches"]:
            state = "natija kiritilgan" if m["hs"] is not None else (
                "tarkib QULFLANGAN" if m["lineup_locked"] else "tarkib ochiq")
            box.add_widget(self.band(
                f"[b]{self.gname(m['home'])} - {self.gname(m['away'])}[/b]  ({state})",
                BLUE, text_color=(0.95, 0.76, 0.19, 1)))
            box.add_widget(MDRaisedButton(
                text="O'yin jurnali", size_hint_x=1,
                on_release=lambda *a, mm=m: self.match_journal(mm)))
            for gid in (m["home"], m["away"]):
                ids = m["lineups"].get(str(gid), [])
                names = ", ".join(self.pname(i) for i in ids) if ids else "kiritilmagan"
                box.add_widget(TwoLineListItem(
                    text=f"{self.gname(gid)}: {len(ids)}/{LINEUP_SIZE}",
                    secondary_text=names, disabled=True))
                if ids:
                    box.add_widget(self.header(f"[b]{self.gname(gid)} — maydonda[/b]", h=26))
                    box.add_widget(self.pitch_widget(m, gid))
            for sb in m["subs"]:
                box.add_widget(OneLineListItem(
                    text=(f"Almashtirish ({self.gname(sb['team'])}): "
                          f"{self.pname(sb['out'])} chiqdi, {self.pname(sb['in'])} kirdi"),
                    disabled=True))
            for gl in m["goals"]:
                ast = f" (assist: {self.pname(gl['assist'])})" if gl.get("assist") else ""
                box.add_widget(OneLineListItem(
                    text=f"Gol ({self.gname(gl['team'])}): {self.pname(gl['scorer'])}{ast}",
                    disabled=True))
            top_pid, mode, tied = self.motm(m)
            if mode in ("auto", "admin"):
                r = self.match_points(m, top_pid)
                tag = "admin tanlovi" if mode == "admin" else "avtomatik"
                it = OneLineIconListItem(
                    text=f"Player of the Match: {self.pname(top_pid)} - {r[0]} ball ({tag})",
                    on_release=lambda x, pid=top_pid: self.player_card(pid))
                it.add_widget(IconLeftWidget(icon="trophy", theme_text_color="Custom",
                                             text_color=(0.78, 0.57, 0, 1)))
                box.add_widget(it)
            elif mode == "tie":
                box.add_widget(OneLineListItem(
                    text="Player of the Match: ballar teng ("
                         + ", ".join(self.pname(i) for i in tied) + ") - admin tanlaydi",
                    disabled=True))
            if m["cards"]:
                cs = ", ".join(f"{self.pname(c['pid'])} ({'qizil' if c['type'] == 'red' else 'sariq'})"
                               for c in m["cards"])
                box.add_widget(OneLineListItem(text="Kartochkalar: " + cs, disabled=True))

    def best_six(self, gid, mid):
        """Eng kuchli 6 taklif: jarima/token taqiqlanmaganlar OVR bo'yicha."""
        elig = []
        for p in self.members(gid):
            pid = p["id"]
            if self.token_banned(pid) or self.card_status(pid, mid)[1]:
                continue
            elig.append((self.player_ovr(pid)[0], -pid, p))
        elig.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [p["id"] for _, _, p in elig[:LINEUP_SIZE]]

    def pitch_widget(self, m, gid):
        """Boshlang'ich 6 ni maydon ustida pozitsiyalar bo'yicha joylashtirish."""
        ids = m["lineups"].get(str(gid), [])
        pitch = MDFloatLayout(size_hint_y=None, height=dp(300), md_bg_color=(0.13, 0.42, 0.20, 1))
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
                node = MDBoxLayout(orientation="vertical", size_hint=(None, None),
                                   size=(dp(86), dp(54)),
                                   pos_hint={"center_x": cx, "center_y": cy})
                node.add_widget(MDLabel(text=f"[b]#{p.get('number') or '-'}[/b]", markup=True,
                                        font_style="Caption", halign="center", size_hint_y=None,
                                        height=dp(18), theme_text_color="Custom",
                                        text_color=GOLD))
                nm = p["name"].split()[0]
                node.add_widget(MDLabel(text=f"[b]{nm}[/b]", markup=True, font_style="Caption",
                                        halign="center", size_hint_y=None, height=dp(18),
                                        theme_text_color="Custom", text_color=(1, 1, 1, 1)))
                node.add_widget(MDLabel(text=f"OVR {ovr}", font_style="Caption", halign="center",
                                        size_hint_y=None, height=dp(16),
                                        theme_text_color="Custom", text_color=(1, 1, 1, 0.7)))
                pitch.add_widget(node)
        return pitch

    def match_journal(self, m):
        """O'yin jurnali: gol/almashtirish/kartochka voqealari vaqt tartibida."""
        events = []
        for gl in m["goals"]:
            ast = f" (assist: {self.pname(gl['assist'])})" if gl.get("assist") else ""
            events.append((gl.get("ts"), f"GOL — {self.gname(gl['team'])}: "
                                         f"{self.pname(gl['scorer'])}{ast}"))
        for sb in m["subs"]:
            events.append((sb.get("ts"), f"Almashtirish — {self.gname(sb['team'])}: "
                                         f"{self.pname(sb['out'])} chiqdi, "
                                         f"{self.pname(sb['in'])} kirdi"))
        for c in m["cards"]:
            kind = "QIZIL" if c["type"] == "red" else "SARIQ"
            events.append((c.get("ts"), f"{kind} kartochka — {self.pname(c['pid'])}"))
        events.sort(key=lambda e: e[0] or 0)
        items = [TwoLineListItem(text=txt, secondary_text=self._fmt_ts(ts), disabled=True)
                 for ts, txt in events]
        if not items:
            items = [OneLineListItem(text="Hozircha voqea yo'q", disabled=True)]
        title = f"Jurnal: {self.gname(m['home'])} — {self.gname(m['away'])}"
        self.show_dialog(title, items=items)

    def check_pin(self, gid, pin):
        g = self.group(gid)
        if not g or not g.get("pin_hash"):
            toast("Bu guruh uchun PIN o'rnatilmagan. Admin PIN o'rnatsin.")
            return False
        if self.pin_hash(pin, gid) != g["pin_hash"]:
            toast("PIN noto'g'ri")
            return False
        return True

    def captain_lineup_start(self):
        if self.d["is_draft_open"]:
            toast("Tarkib faqat draft yopilgandan keyin kiritiladi")
            return
        opts = [(f"{g['name']} (kapitan: {self.captain_name(g)})", g["id"])
                for g in self.d["groups"]]

        def got_group(gid):
            def got_pin(pin):
                if not self.check_pin(gid, pin):
                    return
                mopts = []
                for m in self.d["matches"]:
                    if gid in (m["home"], m["away"]) and m["hs"] is None and not m["lineup_locked"]:
                        mopts.append((f"{self.gname(m['home'])} — {self.gname(m['away'])}", m["id"]))
                self.choose_dialog("Qaysi o'yin?", mopts,
                                   lambda mid: self.lineup_dialog(gid, mid))
            self.input_dialog("Kapitan PIN", "PIN", got_pin, password=True, digits=True)
        self.choose_dialog("Qaysi guruh?", opts, got_group)

    def lineup_dialog(self, gid, mid):
        m = self.match(mid)
        if not m:
            return
        sel = set(m["lineups"].get(str(gid), []))
        items = []
        togglers = []          # (item_widget, pid, name)

        def render():
            for it, pid, name in togglers:
                it.text = ("[+] " if pid in sel else "[  ] ") + name

        for p in self.members(gid):
            pid, name = p["id"], p["name"]
            y, susp = self.card_status(pid, mid)
            if susp:
                sel.discard(pid)
                items.append(OneLineListItem(text=f"{name} — jarimada (o'ynay olmaydi)",
                                             disabled=True))
                continue
            if self.token_banned(pid):
                sel.discard(pid)
                items.append(OneLineListItem(text=f"{name} — APEX TOKEN 0 (o'ynay olmaydi)",
                                             disabled=True))
                continue
            it = OneLineListItem(text=("[+] " if pid in sel else "[  ] ") + name)

            def toggle(item, pid=pid, name=name):
                if pid in sel:
                    sel.discard(pid)
                else:
                    if len(sel) >= LINEUP_SIZE:
                        toast(f"Faqat {LINEUP_SIZE} ta tanlanadi")
                        return
                    sel.add(pid)
                item.text = ("[+] " if pid in sel else "[  ] ") + name
                toast(f"Tanlandi: {len(sel)}/{LINEUP_SIZE}")
            it.bind(on_release=toggle)
            items.append(it)
            togglers.append((it, pid, name))

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
        if self.d["is_draft_open"]:
            toast("Draft ochiq: tarkib kiritib bo'lmaydi")
            return False
        if not m or gid not in (m["home"], m["away"]):
            toast("O'yin topilmadi")
            return False
        if m["hs"] is not None or m["lineup_locked"]:
            toast("Bu o'yin tarkibi qulflangan")
            return False
        if len(set(pids)) != LINEUP_SIZE:
            toast(f"Aynan {LINEUP_SIZE} ta o'yinchi tanlang")
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
        rows = {g["id"]: dict(gid=g["id"], name=g["name"], P=0, W=0, D=0, L=0, GF=0, GA=0, PTS=0)
                for g in self.d["groups"] if ids is None or g["id"] in ids}
        for m in self.d["matches"]:
            if m.get("stage", "group") != stage or m["hs"] is None:
                continue
            if m["home"] not in rows or m["away"] not in rows:
                continue
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
        return sorted(rows.values(),
                      key=lambda r: (-r["PTS"], -(r["GF"] - r["GA"]), -r["GF"], r["name"]))

    def _table_rows(self, box, rows, top_mark=1):
        for i, r in enumerate(rows, 1):
            box.add_widget(TwoLineListItem(
                text=f"{i}. {r['name']} — {r['PTS']} ochko",
                bg_color=(0.42, 0.33, 0.06, 1) if (i <= top_mark and r["PTS"] > 0) else CARD,
                secondary_text=(f"O'yin {r['P']} | G {r['W']} D {r['D']} M {r['L']} | "
                                f"To'plar {r['GF']}-{r['GA']}"),
                disabled=True))

    def refresh_table(self):
        box = self.b_table
        box.clear_widgets()
        box.add_widget(self.hero("Turnir jadvali va statistika"))
        halves = self.stage_groups()
        if halves:
            for i, h in enumerate(halves, 1):
                box.add_widget(self.header(f"[b]{i}-guruh jadvali (guruh bosqichi)[/b]"))
                self._table_rows(box, self.standings(grp=h), top_mark=1)
            box.add_widget(self.note("Har ikki guruh g'olibi FINAL da o'ynaydi.", 30))
        else:
            box.add_widget(self.header("[b]Turnir jadvali[/b]"))
            self._table_rows(box, self.standings(), top_mark=2)
        fin = self.final_match()
        if fin:
            box.add_widget(self.header("[b]FINAL[/b]"))
            score = "—" if fin["hs"] is None else f"{fin['hs']} : {fin['as']}"
            box.add_widget(TwoLineListItem(
                text=f"{self.gname(fin['home'])}  {score}  {self.gname(fin['away'])}",
                secondary_text="Chempionlik o'yini", disabled=True))
            if fin["hs"] is not None and fin["hs"] != fin["as"]:
                w = fin["home"] if fin["hs"] > fin["as"] else fin["away"]
                box.add_widget(self.band(f"[b]CHEMPION: {self.gname(w)}[/b]  "
                                         f"(+{TEAM_WIN_TOKENS} APEX PRO TOKEN)",
                                         GOLD, text_color=NAVY, group=self.group(w)))
            box.add_widget(self.note("3-o'rin va undan past jamoalar musobaqani yakunlagan.", 30))
        elif self.group_stage_complete():
            c = self.final_candidates()
            if len(c) == 2:
                box.add_widget(self.band(
                    f"[b]FINAL juftligi: {self.gname(c[0])} — {self.gname(c[1])}[/b]  "
                    "(admin FINAL o'yinini yaratadi)", GOLD, text_color=NAVY))
            rest = [r for r in self.standings() if not halves][2:] if not halves else []
            if rest:
                box.add_widget(self.note("3-o'rin va undan past jamoalar musobaqani yakunlagan.", 30))
        box.add_widget(self.header("[b]O'yinlar[/b]"))
        if not self.d["matches"]:
            box.add_widget(MDLabel(text="Hozircha o'yinlar yo'q.", size_hint_y=None, height=dp(40)))
        for m in self.d["matches"]:
            score = "—" if m["hs"] is None else f"{m['hs']} : {m['as']}"
            tag = "  [FINAL]" if m.get("stage") == "final" else ""
            box.add_widget(OneLineListItem(
                text=f"{self.gname(m['home'])}  {score}  {self.gname(m['away'])}{tag}",
                disabled=True))
        self.build_stats_table(box)
        self.build_leaderboards(box)

    # ---------------- MARKET oynasi ----------------
    def refresh_market(self):
        box = self.b_market
        box.clear_widgets()
        box.add_widget(self.hero("Market — APEX PRO TOKEN"))
        gids = self.captain_groups()
        if gids:
            for gid in gids:
                g = self.group(gid)
                if g:
                    box.add_widget(self.band(
                        f"[b]{g['name']}[/b]  |  balans: [b]{g['ptokens']}[/b] token",
                        GOLD, text_color=NAVY, group=g))
        else:
            box.add_widget(self.note(
                "Marketdan faqat jamoa kapitanlari foydalanadi. "
                "Kapitan sifatida tasdiqlash uchun PIN kiriting.", 44))
            box.add_widget(MDRaisedButton(
                text="Kapitan PIN kirish", size_hint_x=1,
                on_release=lambda *a: self.choose_dialog(
                    "Qaysi guruh kapitani?", [(g["name"], g["id"]) for g in self.d["groups"]],
                    lambda gid: self.captain_auth(gid, self.refresh_all))))
        items = [it for it in self.d["market"] if it["qty"] > 0]
        box.add_widget(self.header(f"[b]Sotuvda: {len(items)}[/b]"))
        if not items:
            box.add_widget(MDLabel(text="Hozircha sotuvda narsa yo'q. Admin qo'shadi.",
                                   size_hint_y=None, height=dp(40)))
        for it in items:
            card = adaptive_card(orientation="horizontal", radius=[12], md_bg_color=CARD,
                                 padding=dp(8), spacing=dp(8))
            if it.get("img"):
                card.add_widget(Image(source=b64_to_path(f"m{it['id']}", it["img"]),
                                      size_hint_x=None, width=dp(72)))
            col = MDBoxLayout(orientation="vertical", size_hint_x=1)
            col.add_widget(MDLabel(text=f"[b]{it['name']}[/b]", markup=True))
            if it.get("desc"):
                col.add_widget(MDLabel(text=it["desc"], font_style="Caption"))
            col.add_widget(MDLabel(text=f"Narx: [b]{it['price']}[/b] token  |  Qolgan: {it['qty']}",
                                   markup=True, font_style="Caption"))
            card.add_widget(col)
            if gids:
                card.add_widget(MDRaisedButton(
                    text="Olish",
                    on_release=lambda *a, iid=it["id"]: self.market_buy_ask(iid, gids)))
            box.add_widget(card)
        listed = [p for p in self.d["players"] if p.get("tstatus") == "listed"]
        box.add_widget(self.header(f"[b]Transfer list: {len(listed)}[/b]"))
        for p in listed:
            t = self.transfer_of(p["id"])
            sec = f"{self.player_line(p)} | jamoa: {self.gname(p['group'])}"
            if t and t["status"] == "offer":
                sec += f" | taklif: {t['amount']} token ({self.gname(t['buyer_gid'])})"
            row = TwoLineListItem(text=p["name"], secondary_text=sec, disabled=True)
            box.add_widget(row)
            if gids:
                box.add_widget(MDRaisedButton(
                    text=f"{p['name']} uchun taklif yuborish", size_hint_x=1,
                    on_release=lambda *a, pid=p["id"]: self.offer_dialog(pid)))
        if gids:
            box.add_widget(MDRaisedButton(
                text="Transfer so'rovlarim va muzokaralar", size_hint_x=1,
                on_release=lambda *a: self.captain_transfers()))

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
