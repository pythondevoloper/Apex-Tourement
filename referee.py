# -*- coding: utf-8 -*-
"""Apex Referee - HAKAM ilovasi. Admin tayinlagan hakam gol va assistlarni kiritadi."""
from common import *


class RefLoginScreen(MDScreen):
    """Hakam kirishi: admin bergan ism + PIN (glass prototip uslubi)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        root = FloatLayout()
        root.add_widget(G.Background())
        ui = G.BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(16), dp(20)))
        ui.add_widget(G.TL("APEX [b]HAKAM[/b]", 20, align="center",
                           size_hint_y=None, height=dp(34)))
        ui.add_widget(G.note("Hakam hisobi bilan kiring (ism va PIN ni admin beradi).",
                             size=11.5))
        card = G.Glass(orientation="vertical", size_hint_y=None, spacing=dp(10),
                       padding=(dp(16), dp(16)), radius=22)
        card.bind(minimum_height=card.setter("height"))
        self.ref_name = glass_field("Hakam ismi", max_len=30)
        self.pw = glass_field("PIN", max_len=6, digits=True, password=True)
        card.add_widget(self.ref_name)
        card.add_widget(self.pw)
        ui.add_widget(card)
        ui.add_widget(Widget())
        self.btn = G.solid_button("Kirish", self.go, h=52, fill=G.GREEN, size=15)
        ui.add_widget(self.btn)
        root.add_widget(ui)
        self.add_widget(root)

    def busy(self, flag):
        self.btn.disabled = flag
        self.btn.lbl.text = "Kirilmoqda..." if flag else "Kirish"

    def go(self, *a):
        MDApp.get_running_app().ref_login(self.ref_name.text, self.pw.text)


class RefereeApp(LeagueApp):
    REFEREE_APP = True
    APP_TITLE = "Apex Referee"
    TOOLBAR_NAME = "Apex Hakam"
    CACHE_NAME = "apex_ref_cache.json"
    ref_id = None

    def build_extra_screens(self):
        self.sm.add_widget(RefLoginScreen(name="login", md_bg_color=NAVY))

    def first_screen(self):
        return "login"

    def route(self):
        if self.ref_id is None:
            self.sm.current = "login"
        elif self.d["setup_done"]:
            self.sm.current = "main"
            self.refresh_all()
        else:
            self.status_screen.set("Turnir hali sozlanmagan.", True)
            self.sm.current = "status"

    def ref_login(self, name, pin):
        name = (name or "").strip()
        r = next((x for x in self.d["refs"] if x["name"].lower() == name.lower()), None)
        if not r or not r.get("pin_hash") or self.ref_hash(pin, r["id"]) != r["pin_hash"]:
            toast("Ism yoki PIN noto'g'ri")
            return
        self.ref_id = r["id"]
        self.route()
        toast(f"Xush kelibsiz, {r['name']}")

    def update_toolbar(self):
        """Header pastdagi qator: hakam ismi + oflayn belgisi + yangi xabar nuqtasi."""
        h = getattr(self, "pl_header", None)
        if h is None:
            return
        r = next((x for x in self.d["refs"] if x["id"] == self.ref_id), None)
        on = "" if self.store.online else "  ·  OFLAYN"
        h.set_sub("%s%s" % (r["name"] if r else "Hisob kiritilmagan", on))
        try:
            h.set_dot(bool(self.unread_notifs()))
        except Exception:
            pass


if __name__ == "__main__":
    RefereeApp().run()
