# -*- coding: utf-8 -*-
"""Apex Referee - HAKAM ilovasi. Admin tayinlagan hakam gol va assistlarni kiritadi."""
from common import *


class RefLoginScreen(MDScreen):
    """Hakam kirishi: admin bergan ism + PIN."""

    def __init__(self, **kw):
        super().__init__(**kw)
        sv = ScrollView()
        box = MDBoxLayout(orientation="vertical", adaptive_height=True, padding=dp(24),
                          spacing=dp(12))
        box.add_widget(Image(source=TROPHY, size_hint_y=None, height=dp(140)))
        box.add_widget(MDLabel(text="Apex Referee", font_style="H4", halign="center",
                               theme_text_color="Custom", text_color=GOLD,
                               size_hint_y=None, height=dp(48)))
        box.add_widget(MDLabel(text="Hakam hisobi bilan kiring (ism va PIN ni admin beradi)",
                               halign="center", font_style="Caption",
                               theme_text_color="Secondary", size_hint_y=None, height=dp(24)))
        card = adaptive_card(orientation="vertical", radius=[16], md_bg_color=CARD,
                             padding=dp(14), spacing=dp(6))
        self.name = MDTextField(hint_text="Hakam ismi", icon_left="whistle")
        self.pw = MDTextField(hint_text="PIN", password=True, input_filter="int",
                              icon_left="lock-outline")
        card.add_widget(self.name)
        card.add_widget(self.pw)
        self.btn = MDRaisedButton(text="Kirish", size_hint_x=1, on_release=self.go)
        card.add_widget(Widget(size_hint_y=None, height=dp(6)))
        card.add_widget(self.btn)
        box.add_widget(card)
        sv.add_widget(box)
        self.add_widget(sv)

    def busy(self, flag):
        self.btn.disabled = flag
        self.btn.text = "Kirilmoqda..." if flag else "Kirish"

    def go(self, *a):
        MDApp.get_running_app().ref_login(self.name.text, self.pw.text)


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
        r = next((x for x in self.d["refs"] if x["id"] == self.ref_id), None)
        self.toolbar.title = (self.TOOLBAR_NAME + (f" | {r['name']}" if r else "")
                              + ("" if self.store.online else " | OFLAYN"))
        bell = "bell-badge-outline" if self.unread_notifs() else "bell-outline"
        self.toolbar.right_action_items = [
            [bell, lambda x: self.show_notifs()],
            ["account-circle-outline", lambda x: self.profile_dialog()]]


if __name__ == "__main__":
    RefereeApp().run()
