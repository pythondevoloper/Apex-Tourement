# -*- coding: utf-8 -*-
"""Apex Captain - JAMOA KAPITANLARI uchun alohida ilova.

Login va parolni faqat admin beradi (Admin -> Kapitan loginlari). Kapitan shu
ilovada: boshlang'ich 6 ni belgilaydi (shakl: 1 GK / 2 DF / 1 MF / 2 FW, MF va FW
o'rin almashadi), jamoasini ko'radi, transfer so'rovlarini yuritadi va Market'dan
jamoa APEX PRO TOKEN'i bilan xarid qiladi.
"""
from common import *
import glassui as G


class CaptainLoginScreen(MDScreen):
    """Kapitan kirishi: login + parol. Xato 3 marta -> 60 soniya kutish."""

    def __init__(self, **kw):
        super().__init__(**kw)
        root = FloatLayout()
        root.add_widget(G.Background())
        ui = G.BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(16), dp(24)))
        ui.add_widget(G.TL("APEX [b]CAPTAIN[/b]", 22, align="center",
                           size_hint_y=None, height=dp(36)))
        ui.add_widget(G.note("Login va parolni admin beradi", size=11.5))

        card = G.Glass(orientation="vertical", size_hint_y=None, spacing=dp(10),
                       padding=(dp(16), dp(16)), radius=22)
        card.bind(minimum_height=card.setter("height"))
        self.login = glass_field("Login", max_len=32)
        self.pw = glass_field("Parol", password=True, max_len=40)
        card.add_widget(self.login)
        card.add_widget(self.pw)
        ui.add_widget(card)

        self.btn = G.solid_button("Kirish", self.go, h=52, fill=G.GREEN, size=15)
        ui.add_widget(self.btn)
        self.msg = G.TL("", 11.5, RED, align="center", size_hint_y=None, height=dp(20))
        ui.add_widget(self.msg)
        ui.add_widget(G.note("Tarkib, transfer va Market endi shu ilovada — "
                             "o'yinchining Apex Tournament ilovasi faqat o'z ma'lumoti uchun.",
                             size=10.5))
        ui.add_widget(Widget())
        root.add_widget(ui)
        self.add_widget(root)

    def busy(self, flag):
        self.btn.disabled = flag
        self.btn.lbl.text = "Tekshirilmoqda..." if flag else "Kirish"

    def error(self, text):
        self.msg.text = text or ""

    def go(self, *a):
        MDApp.get_running_app().cap_do_login(self.login.text, self.pw.text)


class CaptainApp(LeagueApp):
    ADMIN_APP = False
    REFEREE_APP = False
    CAPTAIN_APP = True
    APP_TITLE = "Apex Captain"
    TOOLBAR_NAME = "Apex Captain"
    CACHE_NAME = "apex_captain_cache.json"

    # ---------------- ekranlar va yo'nalish ----------------
    def build_extra_screens(self):
        self.sm.add_widget(CaptainLoginScreen(name="caplogin", md_bg_color=NAVY))

    def first_screen(self):
        return "caplogin"

    def route(self):
        """Turnir boshlanmagan -> kuting; hisob saqlangan -> panel; aks holda -> kirish."""
        if not self.d["setup_done"]:
            self.status_screen.set(
                "Turnir hali boshlanmagan.\nAdmin turnirni boshlagach kapitan hisoblari "
                "ochiladi.", True)
            self.sm.current = "status"
            return
        gid = self.saved_cap_gid()
        if gid is None:
            self.sm.current = "caplogin"
            return
        self.my_cap_gid = gid
        self.sm.current = "main"
        self.refresh_all()
        self.sync_push()

    # ---------------- kirish / chiqish ----------------
    def cap_do_login(self, login, password):
        scr = self.sm.get_screen("caplogin")
        wait = self.cap_wait()
        if wait:
            scr.error(f"Juda ko'p urinish — {wait} soniyadan keyin qayta urinib ko'ring")
            return
        if not (login or "").strip() or not (password or ""):
            scr.error("Login va parolni to'ldiring")
            return
        scr.busy(True)
        scr.error("")

        def work():
            # PBKDF2 (~120k davr) ~0.1 s: UI qotib qolmasligi uchun boshqa oqimda
            gid = self.captain_login(login, password)
            Clock.schedule_once(lambda dt: self._cap_login_done(gid, scr), 0)
        threading.Thread(target=work, daemon=True).start()

    def _cap_login_done(self, gid, scr):
        scr.busy(False)
        if gid is None:
            wait = self.cap_wait()
            left = self.CAP_MAX_FAILS - int(self.load_me().get("cap_fails") or 0)
            scr.error(f"{wait} soniya kuting" if wait else
                      f"Login yoki parol xato (yana {max(left, 0)} urinish)")
            return
        self.cap_reset_fails()
        self.set_cap_session(gid)
        scr.login.text = ""
        scr.pw.text = ""
        self.route()

    def cap_logout(self):
        self.clear_cap_session()
        self.sm.current = "caplogin"

    def profile_dialog(self):
        g = self.group(self.my_cap_gid) if self.my_cap_gid else None
        if not g:
            self.cap_logout()
            return
        items = [
            OneLineListItem(text=f"Jamoa: {g['name']}", disabled=True),
            OneLineListItem(text=f"Login: {g.get('cap_login') or '-'}", disabled=True),
            OneLineListItem(text=f"APEX PRO TOKEN: {g['ptokens']}", disabled=True),
            OneLineListItem(text="Chiqish",
                            on_release=lambda *a: (self.close_dialog(), self.cap_logout())),
        ]
        self.show_dialog("Kapitan hisobi", items=items)

    def update_toolbar(self):
        h = getattr(self, "pl_header", None)
        if h is None:
            return
        g = self.group(self.my_cap_gid) if self.my_cap_gid else None
        on = "" if self.store.online else "  ·  OFLAYN"
        h.set_sub(f"{g['name'] if g else 'Kapitan'}{on}")
        try:
            h.set_dot(bool(self.unread_notifs()))
        except Exception:
            pass

    # ---------------- "Jamoam" tab'i: faqat o'z guruhi ----------------
    def refresh_groups(self):
        box = self.b_groups
        box.clear_widgets()
        g = self.group(self.my_cap_gid) if self.my_cap_gid else None
        if not g:
            box.add_widget(self.note("Kapitan hisobi topilmadi — Chiqish qilib qayta kiring."))
            return
        ms = self.members(g["id"])
        col = self._grp_color(g["id"])
        box.add_widget(G.Band(f"[b]{g['name']}[/b]  ·  kapitan: {self.captain_name(g)}",
                              col, logo=self.logo_source(g), name=g["name"],
                              chip=f"{len(ms)} o'yinchi"))
        box.add_widget(G.section_label(f"APEX PRO TOKEN: {g['ptokens']}"))
        box.add_widget(self.panel(
            G.TL(self.shape_summary([p["id"] for p in ms]), 12, G.CYAN, shorten=False),
            title="JAMOA SHAKLI (1 GK / 2 DF / 1 MF / 2 FW)"))
        if not ms:
            box.add_widget(self.note("Jamoangizda hali o'yinchi yo'q — admin bo'lgach chiqadi."))
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


if __name__ == "__main__":
    CaptainApp().run()
