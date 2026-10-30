# -*- coding: utf-8 -*-
"""
Apex Tournament - Apex Pro League (Android, KivyMD 1.1.1)

Qoidalar:
- O'yinchi telefondan o'zi ro'yxatdan o'tadi -> Draft ro'yxatida ko'rinadi
- Kapitanlar navbatma-navbat o'yinchi tanlaydi (Draft). Yopilgach faqat Admin ochadi
- Har o'yin uchun kapitan o'z PIN kodi bilan BOSHLANG'ICH 6 TALIK tarkibni belgilaydi
- Sariq/Qizil kartochkalarni FAQAT ADMIN belgilaydi
    * Qizil karta  -> keyingi o'yinda o'ynay olmaydi
    * 2 ta sariq   -> keyingi o'yinda o'ynay olmaydi (sariqlar nolga tushadi)
  Jarimadagi o'yinchini kapitan 6 taga qo'sha olmaydi
- Bayonnoma: asosiy tarkib / zaxiradan kirish (sub in) / chiqish (sub out)
- Har bir gol: muallif + assist
- Ball: Gol +3, Assist +2, G'alaba +3, Sariq -1, Qizil -3
- Player of the Match (MOTM): o'yinda eng ko'p ball yig'gan (avtomatik) yoki admin tanlovi
- Ma'lumotlar JSON faylda lokal saqlanadi
"""
import os
import json
import hashlib
import itertools

from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.uix.behaviors import ButtonBehavior

from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel, MDIcon
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import OneLineListItem, TwoLineListItem, OneLineIconListItem, IconLeftWidget
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.card import MDCard

DEFAULT_PASSWORD = "admin123"
LINEUP_SIZE = 6

# Ball tizimi
POINTS = {"goal": 3, "assist": 2, "win": 3, "yellow": -1, "red": -3}


class StatRow(ButtonBehavior, MDBoxLayout):
    """Statistika jadvalidagi bosiladigan qator."""
    pass


def hash_pw(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
#  Ma'lumotlar ombori (JSON)
# --------------------------------------------------------------------------
class Store:
    def __init__(self, path):
        self.path = path
        self.data = self._default()
        self.load()

    @staticmethod
    def _default():
        salt = os.urandom(8).hex()
        return {
            "setup_done": False,
            "is_draft_open": False,
            "turn": 0,
            "next_id": 1,
            "salt": salt,
            "admin_hash": hash_pw(DEFAULT_PASSWORD, salt),
            "groups": [],    # {"id","name","captain_id","pin_hash"}
            "players": [],   # {"id","name","group","self_registered"}
            "matches": [],   # {"id","home","away","hs","as","lineups","lineup_locked","cards"}
        }

    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data.update(json.load(f))
        except Exception as e:
            print("Yuklashda xato:", e)
        self.migrate()

    def migrate(self):
        """Eski versiya ma'lumotlarini yangi maydonlar bilan to'ldirish."""
        for g in self.data["groups"]:
            g.setdefault("pin_hash", None)
        for m in self.data["matches"]:
            m.setdefault("lineups", {})
            m.setdefault("lineup_locked", False)
            m.setdefault("cards", [])
            m.setdefault("goals", [])   # {"scorer","assist","team"}
            m.setdefault("subs", [])    # {"team","out","in"}
            m.setdefault("motm_admin", None)   # admin tanlagan Player of the Match

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def new_id(self):
        i = self.data["next_id"]
        self.data["next_id"] = i + 1
        return i


# --------------------------------------------------------------------------
#  Boshlang'ich sozlash ekrani
# --------------------------------------------------------------------------
class SetupScreen(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.app = MDApp.get_running_app()
        self.box = MDBoxLayout(orientation="vertical", padding=dp(20), spacing=dp(14))
        self.add_widget(self.box)
        self.step1()

    def step1(self):
        b = self.box
        b.clear_widgets()
        b.add_widget(MDLabel(text="Apex Tournament: dastlabki sozlash", font_style="H5",
                             size_hint_y=None, height=dp(50)))
        b.add_widget(MDLabel(text="Guruhlar sonini kiriting (2 dan 8 gacha)",
                             size_hint_y=None, height=dp(30)))
        self.count = MDTextField(hint_text="Guruhlar soni", input_filter="int", text="4")
        b.add_widget(self.count)
        b.add_widget(MDRaisedButton(text="Davom etish", on_release=self.step2))
        b.add_widget(Widget())

    def step2(self, *a):
        try:
            n = int(self.count.text)
        except ValueError:
            toast("Son kiriting")
            return
        if n < 2 or n > 8:
            toast("Guruhlar soni 2 dan 8 gacha bo'lsin")
            return
        b = self.box
        b.clear_widgets()
        b.add_widget(MDLabel(text="Guruhlar va kapitanlar", font_style="H5",
                             size_hint_y=None, height=dp(50)))
        sv = ScrollView()
        inner = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(8),
                            padding=(0, 0, 0, dp(20)))
        self.name_fields, self.cap_fields, self.pin_fields = [], [], []
        for i in range(n):
            nf = MDTextField(hint_text=f"{i + 1}-guruh nomi", text=f"Guruh {i + 1}")
            cf = MDTextField(hint_text=f"{i + 1}-guruh kapitani (ism)")
            pf = MDTextField(hint_text=f"{i + 1}-guruh kapitan PIN (kamida 4 raqam)",
                             input_filter="int", password=True)
            self.name_fields.append(nf)
            self.cap_fields.append(cf)
            self.pin_fields.append(pf)
            for w in (nf, cf, pf):
                inner.add_widget(w)
        self.pw = MDTextField(hint_text="Admin paroli (kamida 4 belgi)", password=True)
        inner.add_widget(self.pw)
        sv.add_widget(inner)
        b.add_widget(sv)
        b.add_widget(MDRaisedButton(text="Saqlash va boshlash", on_release=self.finish))

    def finish(self, *a):
        self.app.finish_setup([f.text.strip() for f in self.name_fields],
                              [f.text.strip() for f in self.cap_fields],
                              [f.text.strip() for f in self.pin_fields],
                              self.pw.text)


# --------------------------------------------------------------------------
#  Asosiy ilova
# --------------------------------------------------------------------------
class MiniLigaApp(MDApp):
    dialog = None
    admin_ok = False

    # ---------------- ishga tushirish ----------------
    def build(self):
        self.title = "Apex Tournament"
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = "Light"
        Window.softinput_mode = "below_target"
        self.store = Store(os.path.join(self.user_data_dir, "apex_tournament.json"))

        self.sm = MDScreenManager()
        self.setup_screen = SetupScreen(name="setup")
        self.main_screen = self.build_main()
        self.sm.add_widget(self.setup_screen)
        self.sm.add_widget(self.main_screen)
        if self.store.data["setup_done"]:
            self.sm.current = "main"
            self.refresh_all()
        else:
            self.sm.current = "setup"
        return self.sm

    def on_pause(self):
        self.lock_admin()
        return True

    def on_resume(self):
        pass

    # ---------------- UI qurish ----------------
    def build_main(self):
        scr = MDScreen(name="main")
        root = MDBoxLayout(orientation="vertical")
        self.toolbar = MDTopAppBar(title="Apex Pro League", elevation=2)
        root.add_widget(self.toolbar)
        nav = MDBottomNavigation()
        self.t_draft, self.b_draft = self.make_tab("draft", "Draft", "account-multiple-plus")
        self.t_groups, self.b_groups = self.make_tab("groups", "Guruhlar", "account-group")
        self.t_lineup, self.b_lineup = self.make_tab("lineup", "Bayonnoma", "soccer-field")
        self.t_table, self.b_table = self.make_tab("table", "Jadval", "trophy")
        self.t_admin, self.b_admin = self.make_tab("admin", "Admin", "shield-account")
        for t in (self.t_draft, self.t_groups, self.t_lineup, self.t_table):
            t.bind(on_tab_press=lambda *a: self.lock_admin())
        for t in (self.t_draft, self.t_groups, self.t_lineup, self.t_table, self.t_admin):
            nav.add_widget(t)
        root.add_widget(nav)
        scr.add_widget(root)
        return scr

    def make_tab(self, name, text, icon):
        item = MDBottomNavigationItem(name=name, text=text, icon=icon)
        sv = ScrollView()
        box = MDBoxLayout(orientation="vertical", adaptive_height=True,
                          padding=dp(10), spacing=dp(6))
        sv.add_widget(box)
        item.add_widget(sv)
        return item, box

    @staticmethod
    def header(text, h=40):
        return MDLabel(text=text, markup=True, font_style="Subtitle1",
                       size_hint_y=None, height=dp(h))

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
            kw.update(type="simple", items=items)
        elif content is not None:
            kw.update(type="custom", content_cls=content)
        elif text:
            kw["text"] = text
        kw["buttons"] = buttons or [MDFlatButton(text="Yopish", on_release=self.close_dialog)]
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

    def player_card(self, pid):
        """O'yinchining shaxsiy kartochkasi."""
        p = self.player(pid)
        if not p:
            return
        s = self.player_stats(pid)
        y_now, susp = self.card_status(pid)
        role = " (kapitan)" if self.is_captain(pid) else ""
        lines = [
            f"Guruh: [b]{self.gname(p['group']) if p['group'] else 'tanlanmagan'}[/b]{role}",
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
        inner = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(2))
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
        sv = ScrollView(size_hint_y=None, height=dp(420))
        sv.add_widget(inner)
        self.show_dialog(p["name"], content=sv)

    # --- umumiy statistika jadvali (G va A alohida ustunlarda) ---
    STAT_COLS = [0.07, 0.30, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.15]

    def stat_row(self, cells, header=False, pid=None):
        row = StatRow(size_hint_y=None, height=dp(34))
        for i, (txt, w) in enumerate(zip(cells, self.STAT_COLS)):
            text = f"[b]{txt}[/b]" if header else str(txt)
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
                [i, p["name"][:12], s["apps"], s["goals"], s["assists"],
                 s["yellow"], s["red"],
                 (f"[color=#c79100][b]{s['motm']}[/b][/color]" if s["motm"] else 0),
                 s["points"]], pid=p["id"]))

    # ---------------- boshlang'ich sozlashni yakunlash ----------------
    def finish_setup(self, names, caps, pins, password):
        if any(not n for n in names) or any(not c for c in caps):
            toast("Barcha guruh va kapitan nomlarini to'ldiring")
            return
        if len({c.lower() for c in caps}) != len(caps):
            toast("Kapitan ismlari takrorlanmasin")
            return
        if any(not self.valid_pin(p) for p in pins):
            toast("Har bir kapitan PIN kodi kamida 4 raqam bo'lsin")
            return
        if len(password) < 4:
            toast("Admin paroli kamida 4 belgi bo'lsin")
            return
        d = self.d
        d["groups"], d["players"], d["matches"] = [], [], []
        for n, c, pin in zip(names, caps, pins):
            gid, pid = self.store.new_id(), self.store.new_id()
            d["players"].append({"id": pid, "name": c, "group": gid})
            d["groups"].append({"id": gid, "name": n, "captain_id": pid,
                                "pin_hash": self.pin_hash(pin, gid)})
        d["salt"] = os.urandom(8).hex()
        d["admin_hash"] = hash_pw(password, d["salt"])
        d["turn"] = 0
        d["is_draft_open"] = True
        d["setup_done"] = True
        self.store.save()
        self.sm.current = "main"
        self.refresh_all()
        toast("Sozlash yakunlandi. O'yinchilar ro'yxatdan o'tishi mumkin.")

    # ---------------- yangilash ----------------
    def refresh_all(self):
        self.toolbar.title = "Apex Pro League | Draft: " + (
            "OCHIQ" if self.d["is_draft_open"] else "YOPIQ")
        self.refresh_draft()
        self.refresh_groups()
        self.refresh_lineup()
        self.refresh_table()
        self.refresh_admin()

    # ---------------- DRAFT oynasi ----------------
    def refresh_draft(self):
        box = self.b_draft
        box.clear_widgets()
        is_open = self.d["is_draft_open"]
        card = MDCard(orientation="vertical", padding=dp(12), size_hint_y=None,
                      height=dp(90), radius=[12])
        if is_open:
            g = self.current_group()
            card.add_widget(MDLabel(text="[b]Draft: OCHIQ[/b]", markup=True))
            card.add_widget(MDLabel(
                text=f"Navbat: {g['name']} (kapitan: {self.captain_name(g)})" if g else "Guruh yo'q"))
        else:
            card.add_widget(MDLabel(text="[b]Draft: YOPIQ (Locked)[/b]", markup=True))
            card.add_widget(MDLabel(text="O'zgartirish faqat Admin panelda mumkin."))
        box.add_widget(card)

        if is_open:
            box.add_widget(MDRaisedButton(text="Ro'yxatdan o'tish (men o'ynayman)",
                                          size_hint_x=1,
                                          on_release=lambda *a: self.register_dialog()))
        free = self.free_players()
        box.add_widget(self.header(f"Ro'yxatdan o'tgan, tanlanmagan: {len(free)}"))
        if not free:
            box.add_widget(MDLabel(text="Hamma o'yinchilar guruhlarga taqsimlangan.",
                                   size_hint_y=None, height=dp(40)))
        for p in free:
            if is_open:
                box.add_widget(OneLineListItem(
                    text=p["name"],
                    on_release=lambda x, pid=p["id"]: self.ask_pick(pid)))
            else:
                box.add_widget(OneLineListItem(text=p["name"], disabled=True))

    # --- o'yinchining o'zi ro'yxatdan o'tishi ---
    def register_dialog(self):
        if not self.d["is_draft_open"]:
            toast("Draft yopilgan. Ro'yxatdan o'tish yopiq.")
            return

        def cb(name):
            if not self.d["is_draft_open"]:
                toast("Draft yopilgan")
                return
            if len(name) < 2 or len(name) > 30:
                toast("Ism 2–30 belgi bo'lsin")
                return
            if self.name_exists(name):
                toast("Bu ism allaqachon ro'yxatda")
                return
            self.d["players"].append({"id": self.store.new_id(), "name": name,
                                      "group": None, "self_registered": True})
            self.store.save()
            self.refresh_all()
            toast("Ro'yxatdan o'tdingiz. Draftda ko'rinasiz.")
        self.input_dialog("Ro'yxatdan o'tish", "Ism va familiya", cb)

    def ask_pick(self, pid):
        if not self.d["is_draft_open"]:
            toast("Draft yopilgan")
            return
        g, p = self.current_group(), self.player(pid)
        if not g or not p:
            return
        self.confirm_dialog(
            "Tanlashni tasdiqlang",
            f"{g['name']} ({self.captain_name(g)}) uchun «{p['name']}» tanlansinmi?",
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
        if not self.free_players():
            self.d["is_draft_open"] = False
            toast("Draft yakunlandi va yopildi (Locked)")
        self.store.save()
        self.refresh_all()
        return True

    # ---------------- GURUHLAR oynasi ----------------
    def refresh_groups(self):
        box = self.b_groups
        box.clear_widgets()
        for g in self.d["groups"]:
            ms = self.members(g["id"])
            box.add_widget(self.header(
                f"[b]{g['name']}[/b]  (kapitan: {self.captain_name(g)}) — {len(ms)} ta", 44))
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
                    text=p["name"] + star, secondary_text=sec,
                    on_release=lambda x, pid=p["id"]: self.player_card(pid)))

    # ---------------- TARKIB (boshlang'ich 6) oynasi ----------------
    def refresh_lineup(self):
        box = self.b_lineup
        box.clear_widgets()
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
            box.add_widget(self.header(
                f"[b]{self.gname(m['home'])} — {self.gname(m['away'])}[/b]  ({state})", 44))
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
        self.store.save()
        self.refresh_all()
        toast("Tarkib saqlandi")
        return True

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
        box.add_widget(self.header("[b]Turnir jadvali[/b]"))
        for i, r in enumerate(self.standings(), 1):
            box.add_widget(TwoLineListItem(
                text=f"{i}. {r['name']} — {r['PTS']} ochko",
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
    def lock_admin(self):
        if self.admin_ok:
            self.admin_ok = False
            self.refresh_admin()

    def require_admin(self):
        if not self.admin_ok:
            toast("Faqat admin uchun")
            return False
        return True

    def admin_login(self, *a):
        if hash_pw(self.pw_field.text, self.d["salt"]) == self.d["admin_hash"]:
            self.admin_ok = True
            self.refresh_admin()
        else:
            toast("Parol noto'g'ri")

    def refresh_admin(self):
        box = self.b_admin
        box.clear_widgets()
        if not self.admin_ok:
            box.add_widget(self.header("[b]Admin kirishi[/b]"))
            self.pw_field = MDTextField(hint_text="Admin paroli", password=True)
            box.add_widget(self.pw_field)
            box.add_widget(MDRaisedButton(text="Kirish", on_release=self.admin_login))
            return

        row = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
        row.add_widget(MDLabel(text="Draft ochiq / yopiq"))
        sw = MDSwitch(active=self.d["is_draft_open"], pos_hint={"center_y": 0.5})
        sw.bind(active=self.on_toggle_draft)
        row.add_widget(sw)
        box.add_widget(row)

        def btn(text, cb):
            box.add_widget(MDRaisedButton(text=text, on_release=lambda *a: cb(), size_hint_x=1))
        btn("O'yinchi qo'shish", self.admin_add_player)
        btn("O'yinchini o'chirish", self.admin_remove_player)
        btn("O'yinchini guruhga ko'chirish", self.admin_move_player)
        btn("Guruhlar va kapitanlarni boshqarish", self.admin_groups_menu)
        btn("O'yinlar jadvalini yaratish", self.admin_make_fixtures)
        btn("Natija kiritish", self.admin_enter_result)
        btn("Gol kiritish (muallif + assist)", self.admin_add_goal)
        btn("Golni o'chirish", self.admin_remove_goal)
        btn("Almashtirish (zaxiradan kirish / chiqish)", self.admin_add_sub)
        btn("Almashtirishni bekor qilish", self.admin_remove_sub)
        btn("Player of the Match tanlash", self.admin_set_motm)
        btn("Sariq / Qizil kartochka belgilash", self.admin_add_card)
        btn("Kartochkani bekor qilish", self.admin_remove_card)
        btn("Tarkibni boshqarish (qulf / tozalash)", self.admin_lineup_manage)
        btn("Kapitan PIN o'rnatish", self.admin_set_pin)
        btn("Draftni noldan boshlash", self.admin_reset_draft)
        btn("Parolni o'zgartirish", self.admin_change_pw)
        btn("Admin paneldan chiqish", self.lock_admin)

    def on_toggle_draft(self, sw, value):
        if not self.require_admin():
            return
        self.d["is_draft_open"] = bool(value)
        self.store.save()
        toast("Draft ochildi" if value else "Draft yopildi (Locked)")
        self.refresh_all()

    # --- o'yinchilar ---
    def admin_add_player(self):
        if not self.require_admin():
            return

        def cb(name):
            if not name:
                return
            if self.name_exists(name):
                toast("Bunday ism mavjud")
                return
            self.d["players"].append({"id": self.store.new_id(), "name": name, "group": None})
            self.store.save()
            self.refresh_all()
            toast("Qo'shildi")
        self.input_dialog("Yangi o'yinchi", "Ismi", cb)

    def player_label(self, p):
        return f"{p['name']} [{self.gname(p['group']) if p['group'] else 'tanlanmagan'}]"

    def admin_remove_player(self):
        if not self.require_admin():
            return
        opts = [(self.player_label(p), p["id"]) for p in self.d["players"]]

        def chosen(pid):
            if self.is_captain(pid):
                toast("Avval kapitanni almashtiring")
                return
            if self.has_history(pid):
                toast("Statistikasi bor o'yinchini o'chirib bo'lmaydi")
                return
            self.confirm_dialog("O'chirish", f"«{self.pname(pid)}» o'chirilsinmi?",
                                lambda: self._remove_player(pid))
        self.choose_dialog("Qaysi o'yinchi?", opts, chosen)

    def _remove_player(self, pid):
        if not self.require_admin():
            return
        self.purge_from_lineups(pid)
        self.d["players"] = [p for p in self.d["players"] if p["id"] != pid]
        self.store.save()
        self.refresh_all()

    def admin_move_player(self):
        if not self.require_admin():
            return
        opts = [(self.player_label(p), p["id"]) for p in self.d["players"]
                if not self.is_captain(p["id"])]

        def chosen(pid):
            gopts = [("— Tanlanmaganlar ro'yxatiga", None)] + \
                    [(g["name"], g["id"]) for g in self.d["groups"]]

            def to_group(gid):
                if not self.require_admin():
                    return
                self.purge_from_lineups(pid)
                self.player(pid)["group"] = gid
                self.store.save()
                self.refresh_all()
            self.choose_dialog("Qaysi guruhga?", gopts, to_group)
        self.choose_dialog("Qaysi o'yinchi?", opts, chosen)

    # --- guruhlar / kapitanlar ---
    def admin_groups_menu(self):
        if not self.require_admin():
            return
        opts = [("Guruh qo'shish", self.admin_add_group),
                ("Guruh nomini o'zgartirish", self.admin_rename_group),
                ("Kapitanni almashtirish", self.admin_change_captain),
                ("Guruhni o'chirish", self.admin_delete_group)]
        self.choose_dialog("Guruhlar", opts, lambda fn: fn())

    def admin_add_group(self):
        def cb(name):
            if not name or not self.require_admin():
                return

            def cb2(cap):
                if not cap or not self.require_admin():
                    return
                if self.name_exists(cap):
                    toast("Bunday ism mavjud")
                    return

                def cb3(pin):
                    if not self.require_admin():
                        return
                    if not self.valid_pin(pin):
                        toast("PIN kamida 4 raqam bo'lsin")
                        return
                    gid, pid = self.store.new_id(), self.store.new_id()
                    self.d["players"].append({"id": pid, "name": cap, "group": gid})
                    self.d["groups"].append({"id": gid, "name": name, "captain_id": pid,
                                             "pin_hash": self.pin_hash(pin, gid)})
                    self.store.save()
                    self.refresh_all()
                self.input_dialog("Kapitan PIN", "PIN (4+ raqam)", cb3, password=True, digits=True)
            self.input_dialog("Kapitan ismi", "Kapitan", cb2)
        self.input_dialog("Yangi guruh nomi", "Nomi", cb)

    def admin_rename_group(self):
        opts = [(g["name"], g["id"]) for g in self.d["groups"]]

        def chosen(gid):
            def cb(name):
                if name and self.require_admin():
                    self.group(gid)["name"] = name
                    self.store.save()
                    self.refresh_all()
            self.input_dialog("Yangi nom", "Nomi", cb, text=self.gname(gid))
        self.choose_dialog("Qaysi guruh?", opts, chosen)

    def admin_change_captain(self):
        opts = [(f"{g['name']} (hozir: {self.captain_name(g)})", g["id"])
                for g in self.d["groups"]]

        def chosen(gid):
            def cb(name):
                if not name or not self.require_admin():
                    return
                p = next((x for x in self.d["players"] if x["name"].lower() == name.lower()), None)
                if p:
                    if p["group"] not in (None, gid):
                        toast("Bu o'yinchi boshqa guruhda")
                        return
                    if self.is_captain(p["id"]):
                        toast("U allaqachon kapitan")
                        return

                def cb2(pin):
                    if not self.require_admin():
                        return
                    if not self.valid_pin(pin):
                        toast("PIN kamida 4 raqam bo'lsin")
                        return
                    q = next((x for x in self.d["players"] if x["name"].lower() == name.lower()), None)
                    if q:
                        q["group"] = gid
                        pid = q["id"]
                    else:
                        pid = self.store.new_id()
                        self.d["players"].append({"id": pid, "name": name, "group": gid})
                    g = self.group(gid)
                    g["captain_id"] = pid
                    g["pin_hash"] = self.pin_hash(pin, gid)
                    self.store.save()
                    self.refresh_all()
                self.input_dialog("Yangi kapitan PIN", "PIN (4+ raqam)", cb2,
                                  password=True, digits=True)
            self.input_dialog("Yangi kapitan ismi", "Ism", cb)
        self.choose_dialog("Qaysi guruh?", opts, chosen)

    def admin_delete_group(self):
        opts = [(g["name"], g["id"]) for g in self.d["groups"]]

        def chosen(gid):
            if len(self.d["groups"]) <= 2:
                toast("Kamida 2 ta guruh qolishi kerak")
                return
            self.confirm_dialog("Guruhni o'chirish",
                                f"«{self.gname(gid)}» o'chirilsinmi? A'zolari tanlanmaganlarga o'tadi.",
                                lambda: self._delete_group(gid))
        self.choose_dialog("Qaysi guruh?", opts, chosen)

    def _delete_group(self, gid):
        if not self.require_admin():
            return
        for p in self.d["players"]:
            if p["group"] == gid:
                p["group"] = None
        self.d["groups"] = [g for g in self.d["groups"] if g["id"] != gid]
        self.d["matches"] = [m for m in self.d["matches"] if gid not in (m["home"], m["away"])]
        self.d["turn"] = 0
        self.store.save()
        self.refresh_all()

    def admin_set_pin(self):
        if not self.require_admin():
            return
        opts = [(f"{g['name']} (kapitan: {self.captain_name(g)})", g["id"])
                for g in self.d["groups"]]

        def chosen(gid):
            def cb(pin):
                if not self.require_admin():
                    return
                if not self.valid_pin(pin):
                    toast("PIN kamida 4 raqam bo'lsin")
                    return
                self.group(gid)["pin_hash"] = self.pin_hash(pin, gid)
                self.store.save()
                toast("PIN o'rnatildi")
            self.input_dialog("Yangi PIN", "PIN (4+ raqam)", cb, password=True, digits=True)
        self.choose_dialog("Qaysi guruh?", opts, chosen)

    # --- o'yinlar va natijalar ---
    def admin_make_fixtures(self):
        if not self.require_admin():
            return
        have = {(m["home"], m["away"]) for m in self.d["matches"]}
        added = 0
        for a, b in itertools.combinations([g["id"] for g in self.d["groups"]], 2):
            if (a, b) in have or (b, a) in have:
                continue
            self.d["matches"].append({"id": self.store.new_id(), "home": a, "away": b,
                                      "hs": None, "as": None, "lineups": {},
                                      "lineup_locked": False, "cards": [],
                                      "goals": [], "subs": [], "motm_admin": None})
            added += 1
        self.store.save()
        self.refresh_all()
        toast(f"{added} ta o'yin qo'shildi")

    def match_label(self, m):
        sc = "—" if m["hs"] is None else f"{m['hs']}:{m['as']}"
        return f"{self.gname(m['home'])} {sc} {self.gname(m['away'])}"

    def admin_enter_result(self):
        if not self.require_admin():
            return
        opts = [(self.match_label(m), m["id"]) for m in self.d["matches"]]

        def chosen(mid):
            m = self.match(mid)
            if m["goals"]:
                toast("Hisob gollardan avtomatik hisoblanadi. Gollarni o'zgartiring.")
                return
            f1 = MDTextField(hint_text=self.gname(m["home"]), input_filter="int",
                             text="" if m["hs"] is None else str(m["hs"]))
            f2 = MDTextField(hint_text=self.gname(m["away"]), input_filter="int",
                             text="" if m["as"] is None else str(m["as"]))
            content = MDBoxLayout(orientation="vertical", size_hint_y=None, height=dp(140))
            content.add_widget(f1)
            content.add_widget(f2)

            def save(*a):
                if not self.require_admin():
                    return
                try:
                    m["hs"], m["as"] = int(f1.text), int(f2.text)
                except ValueError:
                    toast("Hisobni to'g'ri kiriting")
                    return
                m["lineup_locked"] = True   # natijadan keyin tarkib qulflanadi
                self.close_dialog()
                self.store.save()
                self.refresh_all()
            self.show_dialog("Natija", content=content, buttons=[
                MDFlatButton(text="Bekor", on_release=self.close_dialog),
                MDRaisedButton(text="Saqlash", on_release=save)])
        self.choose_dialog("Qaysi o'yin?", opts, chosen)

    # --- bayonnoma: gol + assist ---
    def admin_add_goal(self):
        if not self.require_admin():
            return
        opts = [(self.match_label(m), m["id"]) for m in self.d["matches"]]

        def got_match(mid):
            m = self.match(mid)
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
                        if not self.require_admin():
                            return
                        m["goals"].append({"scorer": sid, "assist": aid, "team": gid})
                        self.recompute_score(m)
                        self.store.save()
                        self.refresh_all()
                        toast(f"Gol! Hisob {m['hs']}:{m['as']}")
                    self.choose_dialog("Assist bergan o'yinchi", aopts, got_assist)
                self.choose_dialog("Golni urgan o'yinchi", sopts, got_scorer)
            self.choose_dialog("Qaysi jamoa urdi?", topts, got_team)
        self.choose_dialog("Qaysi o'yin?", opts, got_match)

    def admin_remove_goal(self):
        if not self.require_admin():
            return
        opts = []
        for m in self.d["matches"]:
            for i, g in enumerate(m["goals"]):
                ast = f", assist: {self.pname(g['assist'])}" if g.get("assist") else ""
                opts.append((f"{self.pname(g['scorer'])}{ast} ({self.match_label(m)})", (m["id"], i)))

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

    # --- bayonnoma: almashtirishlar (zaxira) ---
    def admin_add_sub(self):
        if not self.require_admin():
            return
        opts = [(self.match_label(m), m["id"]) for m in self.d["matches"]]

        def got_match(mid):
            m = self.match(mid)
            topts = [(self.gname(m["home"]), m["home"]), (self.gname(m["away"]), m["away"])]

            def got_team(gid):
                if len(self.team_starters(m, gid)) != LINEUP_SIZE:
                    toast("Avval boshlang'ich 6 tarkibi kiritilsin")
                    return
                field = self.team_onfield(m, gid)
                used = set(self.team_appeared(m, gid)) | \
                    {s["out"] for s in m["subs"] if s["team"] == gid}
                bench = [p for p in self.members(gid)
                         if p["id"] not in used and not self.card_status(p["id"], mid)[1]]
                if not bench:
                    toast("Zaxirada o'yinchi yo'q")
                    return

                def got_out(oid):
                    def got_in(iid):
                        if not self.require_admin():
                            return
                        m["subs"].append({"team": gid, "out": oid, "in": iid})
                        m["lineup_locked"] = True
                        self.store.save()
                        self.refresh_all()
                        toast("Almashtirish qayd etildi")
                    self.choose_dialog("Zaxiradan kim kiradi? (sub in)",
                                       [(p["name"], p["id"]) for p in bench], got_in)
                self.choose_dialog("Kim chiqadi? (sub out)",
                                   [(self.pname(i), i) for i in field], got_out)
            self.choose_dialog("Qaysi jamoa?", topts, got_team)
        self.choose_dialog("Qaysi o'yin?", opts, got_match)

    def admin_remove_sub(self):
        if not self.require_admin():
            return
        opts = []
        for m in self.d["matches"]:
            for i, sb in enumerate(m["subs"]):
                opts.append((f"{self.pname(sb['out'])} -> {self.pname(sb['in'])} ({self.match_label(m)})",
                             (m["id"], i)))

        def chosen(v):
            mid, idx = v
            m = self.match(mid)
            if not m or not (0 <= idx < len(m["subs"])):
                return
            sb = m["subs"][idx]
            if any(sb["in"] in (g["scorer"], g.get("assist")) for g in m["goals"]):
                toast("Avval bu o'yinchining gol/assistlarini o'chiring")
                return
            if any(o is not sb and o["out"] == sb["in"] for o in m["subs"]):
                toast("Avval keyingi almashtirishni bekor qiling")
                return
            m["subs"].pop(idx)
            self.store.save()
            self.refresh_all()
            toast("Almashtirish bekor qilindi")
        self.choose_dialog("Qaysi almashtirish?", opts, chosen)

    # --- Player of the Match (admin tanlovi) ---
    def admin_set_motm(self):
        if not self.require_admin():
            return
        opts = [(self.match_label(m), m["id"]) for m in self.d["matches"] if m["hs"] is not None]
        if not opts:
            toast("Avval o'yin natijasi kiritilsin")
            return

        def got_match(mid):
            m = self.match(mid)
            popts = [("Avtomatik (admin tanlovini bekor qilish)", None)]
            for gid in (m["home"], m["away"]):
                for pid in self.team_appeared(m, gid):
                    r = self.match_points(m, pid)
                    popts.append((f"{self.pname(pid)} - {r[0]} ball", pid))

            def got_player(pid):
                if not self.require_admin():
                    return
                m["motm_admin"] = pid
                self.store.save()
                self.refresh_all()
                toast("Admin tanlovi saqlandi" if pid else "Avtomatik rejimga qaytdi")
            self.choose_dialog("Player of the Match", popts, got_player)
        self.choose_dialog("Qaysi o'yin?", opts, got_match)

    # --- kartochkalar (faqat admin) ---
    def admin_add_card(self):
        if not self.require_admin():
            return
        opts = [(self.match_label(m), m["id"]) for m in self.d["matches"] if m["hs"] is not None]
        if not opts:
            toast("Avval o'yin natijasini kiriting")
            return

        def got_match(mid):
            m = self.match(mid)
            plist = [p for gid in (m["home"], m["away"]) for p in self.members(gid)]
            popts = [(f"{p['name']} [{self.gname(p['group'])}]", p["id"]) for p in plist]

            def got_player(pid):
                def got_type(t):
                    if not self.require_admin():
                        return
                    m["cards"].append({"pid": pid, "type": t})
                    self.store.save()
                    self.refresh_all()
                    y, susp = self.card_status(pid)
                    toast("Keyingi o'yinda jarimada" if susp else "Kartochka belgilandi")
                self.choose_dialog("Kartochka turi",
                                   [("Sariq", "yellow"), ("Qizil", "red")], got_type)
            self.choose_dialog("Qaysi o'yinchi?", popts, got_player)
        self.choose_dialog("Qaysi o'yinda?", opts, got_match)

    def admin_remove_card(self):
        if not self.require_admin():
            return
        opts = []
        for m in self.d["matches"]:
            for i, c in enumerate(m["cards"]):
                t = "qizil" if c["type"] == "red" else "sariq"
                opts.append((f"{self.pname(c['pid'])} — {t} ({self.match_label(m)})", (m["id"], i)))

        def chosen(v):
            mid, idx = v
            m = self.match(mid)
            if m and 0 <= idx < len(m["cards"]):
                m["cards"].pop(idx)
                self.store.save()
                self.refresh_all()
                toast("Kartochka bekor qilindi")
        self.choose_dialog("Qaysi kartochka?", opts, chosen)

    # --- tarkibni boshqarish (admin) ---
    def admin_lineup_manage(self):
        if not self.require_admin():
            return
        opts = [(f"{self.match_label(m)}  [{'qulf' if m['lineup_locked'] else 'ochiq'}]", m["id"])
                for m in self.d["matches"]]

        def chosen(mid):
            m = self.match(mid)

            def toggle_lock():
                m["lineup_locked"] = not m["lineup_locked"]
                self.store.save()
                self.refresh_all()
                toast("Qulflandi" if m["lineup_locked"] else "Ochildi")

            def clear(gid):
                m["lineups"][str(gid)] = []
                self.store.save()
                self.refresh_all()
                toast("Tozalandi")
            acts = [("Qulflash / Ochish", toggle_lock),
                    (f"{self.gname(m['home'])} tarkibini tozalash", lambda: clear(m["home"])),
                    (f"{self.gname(m['away'])} tarkibini tozalash", lambda: clear(m["away"]))]
            self.choose_dialog("Amal", acts, lambda fn: fn())
        self.choose_dialog("Qaysi o'yin?", opts, chosen)

    # --- xizmat ---
    def admin_reset_draft(self):
        if not self.require_admin():
            return

        def do():
            for p in self.d["players"]:
                if not self.is_captain(p["id"]):
                    p["group"] = None
                    self.purge_from_lineups(p["id"])
            self.d["turn"] = 0
            self.d["is_draft_open"] = True
            self.store.save()
            self.refresh_all()
        self.confirm_dialog("Draftni noldan boshlash",
                            "Kapitanlardan boshqa hamma o'yinchilar tanlanmaganlarga qaytadi va draft ochiladi.",
                            do)

    def admin_change_pw(self):
        if not self.require_admin():
            return

        def cb(pw):
            if len(pw) < 4:
                toast("Parol kamida 4 belgi bo'lsin")
                return
            self.d["salt"] = os.urandom(8).hex()
            self.d["admin_hash"] = hash_pw(pw, self.d["salt"])
            self.store.save()
            toast("Parol o'zgartirildi")
        self.input_dialog("Yangi parol", "Parol", cb, password=True)


if __name__ == "__main__":
    MiniLigaApp().run()
