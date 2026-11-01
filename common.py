# -*- coding: utf-8 -*-
"""
Apex Pro League - umumiy qism (o'yinchi va admin ilovalari uchun).
Ma'lumotlar Firebase Realtime Database da saqlanadi (cloud.py), ikkala ilova bir xil
bazani ko'radi. O'zgartirishlar faqat admin ilovasida (Firebase Auth + qoidalar).
"""
import os
import json
import hashlib
import itertools
import threading
import traceback

from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
from kivy.uix.gridlayout import GridLayout

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
from cloud import Firebase, RemoteStore, CloudError

LINEUP_SIZE = 6

# Ball tizimi
POINTS = {"goal": 3, "assist": 2, "win": 3, "yellow": -1, "red": -3}

# O'yinchi kartochkasi
POSITIONS = [("Darvozabon", "GK"), ("Himoyachi", "DF"),
             ("Yarim himoyachi", "MF"), ("Hujumchi", "FW")]
POS_NAME = {c: n for n, c in POSITIONS}
COUNTRIES = ["O'zbekiston", "Qozog'iston", "Qirg'iziston", "Tojikiston", "Turkmaniston",
             "Rossiya", "Turkiya", "Ozarbayjon", "Braziliya", "Argentina", "Portugaliya", "Ispaniya"]
DEFAULT_COUNTRY, DEFAULT_NUMBER, DEFAULT_POS = "O'zbekiston", 10, "MF"
BASE_OVR = 60          # admin o'zgartirmasa, boshlang'ich reyting
LOGO_COUNT = 12        # logo_1.png ... logo_12.png


# ---------------- Ranglar (Apex Pro League uslubi) ----------------
NAVY = (0.043, 0.078, 0.216, 1)      # asosiy fon
NAVY2 = (0.07, 0.12, 0.30, 1)        # dialog foni
BLUE = (0.10, 0.20, 0.52, 1)         # toolbar / sarlavhalar
CARD = (0.09, 0.16, 0.38, 1)         # ro'yxat qatorlari
CARD2 = (0.07, 0.13, 0.32, 1)        # navbatma-navbat qator
GOLD = (0.95, 0.76, 0.19, 1)
GOLD_HEX = "F2C230"
GREEN = (0.06, 0.45, 0.28, 1)        # draft ochiq
RED = (0.55, 0.12, 0.14, 1)          # draft yopiq
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


def adaptive_card(**kw):
    """Ichidagi elementlarga qarab balandligi o'zgaradigan kartochka (MDCard da adaptive_height yo'q)."""
    card = MDCard(size_hint_y=None, **kw)
    card.bind(minimum_height=card.setter("height"))
    return card


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
        self.value = value
        self.label = MDLabel(text=text, halign="center", theme_text_color="Custom",
                             text_color=(1, 1, 1, 1))
        self.add_widget(self.label)

    def set_on(self, on):
        self.md_bg_color = GOLD if on else CARD
        self.label.text_color = NAVY if on else (1, 1, 1, 1)


class RegisterScreen(MDScreen):
    """O'yinchining ro'yxatdan o'tish ekrani: jonli kartochka + tanlanadigan belgilar."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.pos_code = None
        self.country = None
        root = MDBoxLayout(orientation="vertical")

        bar = MDBoxLayout(size_hint_y=None, height=dp(56), md_bg_color=BLUE,
                          padding=(dp(8), 0), spacing=dp(6))
        bar.add_widget(MDIconButton(icon="arrow-left", theme_text_color="Custom", text_color=GOLD,
                                    on_release=lambda *a: self.back()))
        bar.add_widget(MDLabel(text="[b]Ro'yxatdan o'tish[/b]", markup=True, font_style="H6",
                               theme_text_color="Custom", text_color=GOLD))
        root.add_widget(bar)

        sv = ScrollView()
        body = MDBoxLayout(orientation="vertical", adaptive_height=True, padding=dp(14),
                           spacing=dp(10))

        # --- jonli kartochka ---
        self.preview = MDCard(orientation="horizontal", size_hint_y=None, height=dp(116),
                              padding=dp(10), spacing=dp(10), radius=[16],
                              md_bg_color=(0.48, 0.28, 0.12, 1))
        left = MDBoxLayout(orientation="vertical", size_hint_x=None, width=dp(78))
        self.pv_num = MDLabel(text="[b]--[/b]", markup=True, font_style="H3", halign="center")
        self.pv_pos = MDLabel(text="[b]--[/b]", markup=True, halign="center")
        left.add_widget(self.pv_num)
        left.add_widget(self.pv_pos)
        mid = MDBoxLayout(orientation="vertical", spacing=dp(2))
        self.pv_name = MDLabel(text="[b]Ism va familiya[/b]", markup=True, font_style="H6")
        self.pv_posname = MDLabel(text="Pozitsiya tanlanmagan", font_style="Caption")
        self.pv_country = MDLabel(text="Davlat tanlanmagan", font_style="Caption")
        mid.add_widget(self.pv_name)
        mid.add_widget(self.pv_posname)
        mid.add_widget(self.pv_country)
        self.preview.add_widget(left)
        self.preview.add_widget(mid)
        self.preview.add_widget(Image(source=TROPHY, size_hint_x=None, width=dp(60)))
        body.add_widget(self.preview)

        # --- maydonlar ---
        body.add_widget(self._title("1. Ma'lumotlaringiz"))
        self.name_field = MDTextField(hint_text="Ism va familiya", max_text_length=30,
                                      icon_left="account")
        self.num_field = MDTextField(hint_text="Futbolka raqami (1-99)", input_filter="int",
                                     max_text_length=2, icon_left="tshirt-crew")
        self.name_field.bind(text=self.refresh_preview)
        self.num_field.bind(text=self.refresh_preview)
        body.add_widget(self.name_field)
        body.add_widget(self.num_field)

        body.add_widget(self._title("2. Pozitsiya"))
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(2 * 46 + 8))
        self.pos_chips = {}
        for n, code in POSITIONS:
            ch = Chip(f"{code}  {n}", value=code)
            ch.bind(on_release=lambda w, code=code: self.select_pos(code))
            self.pos_chips[code] = ch
            grid.add_widget(ch)
        body.add_widget(grid)

        body.add_widget(self._title("3. Davlat"))
        rows = (len(COUNTRIES) + 1 + 1) // 2
        cgrid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(rows * 46 + (rows - 1) * 8))
        self.country_chips = {}
        for cname in COUNTRIES + [None]:
            ch = Chip(cname or "Boshqa davlat...", value=cname)
            ch.bind(on_release=lambda w, cname=cname: self.select_country(cname))
            self.country_chips[cname] = ch
            cgrid.add_widget(ch)
        body.add_widget(cgrid)
        self.other_field = MDTextField(hint_text="Davlat nomini yozing", max_text_length=30,
                                       icon_left="earth", size_hint_y=None, height=0, opacity=0,
                                       disabled=True)
        self.other_field.bind(text=self.refresh_preview)
        body.add_widget(self.other_field)
        body.add_widget(Widget(size_hint_y=None, height=dp(8)))
        sv.add_widget(body)
        root.add_widget(sv)

        foot = MDBoxLayout(size_hint_y=None, height=dp(74), padding=dp(12), md_bg_color=NAVY2)
        foot.add_widget(MDRaisedButton(text="Ro'yxatdan o'tish", size_hint_x=1,
                                       on_release=lambda *a: self.submit()))
        root.add_widget(foot)
        self.add_widget(root)

    @staticmethod
    def _title(text):
        return MDLabel(text=f"[color=#{GOLD_HEX}][b]{text}[/b][/color]", markup=True,
                       font_style="Subtitle1", size_hint_y=None, height=dp(30))

    def reset(self):
        self.name_field.text = ""
        self.num_field.text = ""
        self.other_field.text = ""
        self.pos_code = None
        self.country = None
        self.country_set = False
        self._apply_chips()
        self.refresh_preview()

    def _apply_chips(self):
        for code, ch in self.pos_chips.items():
            ch.set_on(code == self.pos_code)
        for cname, ch in self.country_chips.items():
            ch.set_on(cname == self.country and self.country_set)
        other = self.country_set and self.country is None
        self.other_field.height = dp(56) if other else 0
        self.other_field.opacity = 1 if other else 0
        self.other_field.disabled = not other

    country_set = False

    def select_pos(self, code):
        self.pos_code = code
        self._apply_chips()
        self.refresh_preview()

    def select_country(self, cname):
        self.country = cname
        self.country_set = True
        self._apply_chips()
        self.refresh_preview()

    def country_value(self):
        if not self.country_set:
            return ""
        return self.country if self.country is not None else self.other_field.text.strip()

    def refresh_preview(self, *a):
        self.pv_num.text = f"[b]{self.num_field.text or '--'}[/b]"
        self.pv_pos.text = f"[b]{self.pos_code or '--'}[/b]"
        self.pv_name.text = f"[b]{self.name_field.text.strip() or 'Ism va familiya'}[/b]"
        self.pv_posname.text = POS_NAME.get(self.pos_code, "Pozitsiya tanlanmagan")
        self.pv_country.text = self.country_value() or "Davlat tanlanmagan"

    def back(self):
        MDApp.get_running_app().sm.current = "main"

    def submit(self):
        MDApp.get_running_app().submit_registration(
            self.name_field.text, self.num_field.text, self.pos_code, self.country_value())


class StatusScreen(MDScreen):
    """Yuklanish / ulanish xatosi / turnir sozlanmagan ekrani."""

    def __init__(self, **kw):
        super().__init__(**kw)
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
        """Android 'Orqaga' tugmasi."""
        if key == 27 and self.sm.current == "register":
            self.sm.current = "main"
            return True
        return False

    def _build_app(self):
        self.title = self.APP_TITLE
        self.theme_cls.primary_palette = "Amber"
        self.theme_cls.accent_palette = "Blue"
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
        Clock.schedule_once(lambda dt: self.start_sync(), 0.3)
        Clock.schedule_interval(self.poll, getattr(config, "POLL_SECONDS", 6))
        return self.sm

    # --- ilovaga xos qismlar (AdminApp o'zgartiradi) ---
    def build_extra_screens(self):
        pass

    def first_screen(self):
        return "status"

    def route(self):
        """Ma'lumot yuklangach qaysi ekranni ko'rsatishni hal qiladi."""
        if self.d["setup_done"]:
            self.sm.current = "main"
            self.refresh_all()
        else:
            self.status_screen.set("Turnir hali sozlanmagan.\nAdmin sozlagach bu yerda paydo bo'ladi.", True)
            self.sm.current = "status"

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

    # ---------------- UI qurish ----------------
    def build_main(self):
        scr = MDScreen(name="main", md_bg_color=NAVY)
        root = MDBoxLayout(orientation="vertical")
        self.toolbar = MDTopAppBar(title="Apex Pro League", elevation=2, md_bg_color=BLUE,
                                   specific_text_color=GOLD,
                                   left_action_items=[["trophy", lambda x: None]])
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
        if self.ADMIN_APP:
            self.t_admin, self.b_admin = self.make_tab("admin", "Admin", "shield-account")
            tabs.append(self.t_admin)
        for t in tabs:
            nav.add_widget(t)
        root.add_widget(nav)
        scr.add_widget(root)
        return scr

    def make_tab(self, name, text, icon):
        item = MDBottomNavigationItem(name=name, text=text, icon=icon)
        sv = MDScrollView(md_bg_color=NAVY)      # tab foni to'q ko'k bo'lsin
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

    def band(self, text, color, text_color=(1, 1, 1, 1), h=44, logo=None):
        """Rangli sarlavha tasmasi (ixtiyoriy logo bilan)."""
        card = MDCard(size_hint_y=None, height=dp(h), padding=(dp(12), dp(4)), radius=[10],
                      md_bg_color=color, spacing=dp(8))
        if logo is not None:
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
        return max(40, min(99, base + bonus)), base, bonus

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

    def collect_player_info(self, done):
        """Raqam -> pozitsiya -> davlat ketma-ket so'raladi. Oxirida done(info) chaqiriladi."""
        def got_number(txt):
            if not txt.isdigit() or not 1 <= int(txt) <= 99:
                toast("Futbolka raqami 1 dan 99 gacha bo'lsin")
                return
            number = int(txt)

            def got_pos(code):
                def finish(country):
                    country = country.strip()
                    if not 2 <= len(country) <= 30:
                        toast("Davlat nomi 2-30 belgi bo'lsin")
                        return
                    done({"number": number, "pos": code, "country": country})

                def got_country(c):
                    if c is None:
                        self.input_dialog("Davlat nomi", "Davlat", finish)
                    else:
                        finish(c)
                self.choose_dialog("Davlat", [(c, c) for c in COUNTRIES] + [("Boshqa (yozaman)", None)],
                                   got_country)
            self.choose_dialog("Pozitsiya", [(f"{n} ({c})", c) for n, c in POSITIONS], got_pos)
        self.input_dialog("Futbolka raqami", "Raqam (1-99)", got_number, digits=True)

    def logo_picker(self, callback):
        """12 ta tayyor logodan birini tanlash. callback(logo_raqami)"""
        rows = (LOGO_COUNT + 3) // 4
        grid = GridLayout(cols=4, spacing=dp(8), padding=dp(4), size_hint_y=None,
                          height=dp(rows * 72 + 8))
        for n in range(1, LOGO_COUNT + 1):
            b = LogoButton(source=logo_path(n), size_hint_y=None, height=dp(64))
            b.bind(on_release=lambda *a, n=n: (self.close_dialog(), callback(n)))
            grid.add_widget(b)
        self.show_dialog("Guruh logosini tanlang", content=grid)

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
            head.add_widget(Image(source=logo_path(g.get("logo")), size_hint_x=None, width=dp(64)))
        inner = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(6))
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
        self.show_dialog(p["name"], content=sv)

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

    # ---------------- boshlang'ich sozlashni yakunlash ----------------

    # ---------------- yangilash ----------------
    def refresh_all(self):
        self.update_toolbar()
        self.refresh_draft()
        self.refresh_groups()
        self.refresh_lineup()
        self.refresh_table()
        if self.ADMIN_APP:
            self.refresh_admin()

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

        if is_open and not self.ADMIN_APP:
            box.add_widget(MDRaisedButton(text="Ro'yxatdan o'tish (men o'ynayman)",
                                          size_hint_x=1,
                                          on_release=lambda *a: self.register_dialog()))
        free = self.free_players()
        box.add_widget(self.header(f"Ro'yxatdan o'tgan, tanlanmagan: {len(free)}"))
        if not free:
            box.add_widget(MDLabel(text="Hamma o'yinchilar guruhlarga taqsimlangan.",
                                   size_hint_y=None, height=dp(40)))
        for p in free:
            pickable = is_open and not self.ADMIN_APP
            box.add_widget(TwoLineListItem(
                text=p["name"], secondary_text=self.player_line(p),
                on_release=(lambda x, pid=p["id"]: self.ask_pick(pid)) if pickable
                else (lambda x, pid=p["id"]: self.player_card(pid))))

    # --- o'yinchining o'zi ro'yxatdan o'tishi ---
    def register_dialog(self):
        """Ro'yxatdan o'tish ekranini ochadi."""
        if not self.d["is_draft_open"]:
            toast("Draft yopilgan. Ro'yxatdan o'tish yopiq.")
            return
        self.register_screen.reset()
        self.sm.current = "register"

    def submit_registration(self, name, number, pos, country):
        if not self.d["is_draft_open"]:
            toast("Draft yopilgan")
            return False
        name = " ".join((name or "").split())
        country = " ".join((country or "").split())
        if not 2 <= len(name) <= 30:
            toast("Ism 2-30 belgi bo'lsin")
            return False
        if self.name_exists(name):
            toast("Bu ism allaqachon ro'yxatda")
            return False
        if not (str(number).isdigit() and 1 <= int(number) <= 99):
            toast("Futbolka raqami 1 dan 99 gacha bo'lsin")
            return False
        if pos not in POS_NAME:
            toast("Pozitsiyani tanlang")
            return False
        if not 2 <= len(country) <= 30:
            toast("Davlatni tanlang yoki yozing")
            return False
        p = {"id": self.store.new_id(), "name": name, "group": None, "self_registered": True,
             "number": int(number), "pos": pos, "country": country}
        self.d["players"].append(p)
        ok = self.store.save()
        self.refresh_all()
        if ok:
            toast("Ro'yxatdan o'tdingiz! Draftda ko'rinasiz.")
            self.sm.current = "main"
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
                f"[b]{g['name']}[/b]  (kapitan: {self.captain_name(g)}) - {len(ms)} ta",
                GROUP_COLORS[gi % len(GROUP_COLORS)], logo=g.get("logo")))
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
            for gid in (m["home"], m["away"]):
                ids = m["lineups"].get(str(gid), [])
                names = ", ".join(self.pname(i) for i in ids) if ids else "kiritilmagan"
                box.add_widget(TwoLineListItem(
                    text=f"{self.gname(gid)}: {len(ids)}/{LINEUP_SIZE}",
                    secondary_text=names, disabled=True))
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
        for p in self.members(gid):
            pid, name = p["id"], p["name"]
            y, susp = self.card_status(pid, mid)
            if susp:
                sel.discard(pid)
                items.append(OneLineListItem(text=f"{name} — jarimada (o'ynay olmaydi)",
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

        def save(*a):
            if self.set_lineup(gid, mid, list(sel)):
                self.close_dialog()
        self.show_dialog(f"Boshlang'ich {LINEUP_SIZE} ta — {self.gname(gid)}", items=items,
                         buttons=[MDFlatButton(text="Bekor", on_release=self.close_dialog),
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
    def standings(self):
        rows = {g["id"]: dict(name=g["name"], P=0, W=0, D=0, L=0, GF=0, GA=0, PTS=0)
                for g in self.d["groups"]}
        for m in self.d["matches"]:
            if m["hs"] is None or m["home"] not in rows or m["away"] not in rows:
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

    def refresh_table(self):
        box = self.b_table
        box.clear_widgets()
        box.add_widget(self.hero("Turnir jadvali va statistika"))
        box.add_widget(self.header("[b]Turnir jadvali[/b]"))
        for i, r in enumerate(self.standings(), 1):
            box.add_widget(TwoLineListItem(
                text=f"{i}. {r['name']} — {r['PTS']} ochko",
                bg_color=(0.42, 0.33, 0.06, 1) if (i == 1 and r["PTS"] > 0) else CARD,
                secondary_text=(f"O'yin {r['P']} | G {r['W']} D {r['D']} M {r['L']} | "
                                f"To'plar {r['GF']}-{r['GA']}"),
                disabled=True))
        box.add_widget(self.header("[b]O'yinlar[/b]"))
        if not self.d["matches"]:
            box.add_widget(MDLabel(text="Hozircha o'yinlar yo'q.", size_hint_y=None, height=dp(40)))
        for m in self.d["matches"]:
            score = "—" if m["hs"] is None else f"{m['hs']} : {m['as']}"
            box.add_widget(OneLineListItem(
                text=f"{self.gname(m['home'])}  {score}  {self.gname(m['away'])}",
                disabled=True))
        self.build_stats_table(box)

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
