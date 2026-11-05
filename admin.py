# -*- coding: utf-8 -*-
"""Apex Admin - ADMIN ilovasi. Faqat admin (Firebase Auth) kira oladi va o'zgartira oladi."""
from kivy.core.window import Window
from kivy.utils import platform, get_color_from_hex as hx
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen
from common import *
from common import _glass_border  # pastqi belgi: `import *` uni olib kirmaydi
import glassui as G  # main.py prototipidagi glass dizayn vidjetlari (saf Kivy canvas)

MAX_GROUP = 8        # har bir jamoada (kapitan bilan) maksimum o'yinchi soni


def _dup_hint(dups):
    """Dashboard kartasidagi qisqa holat matni: raqam takrorlari bormi."""
    if not dups:
        return "Barcha jamoalarda noyob"
    return "%d jamoada takror — kelishib tuzating" % len({g for g, _, _ in dups})


class SetupScreen(MDScreen):
    """Turnirni boshlash. Guruhlar soni so'ralmaydi: guruhlar keyin, Admin paneldan qo'shiladi."""

    def __init__(self, **kw):
        super().__init__(**kw)
        root = FloatLayout()
        root.add_widget(G.Background())
        body = G.BoxLayout(orientation="vertical", padding=(dp(24), dp(24)), spacing=dp(14))
        body.add_widget(Widget())
        badge = G.Badge(G.CYAN, 120, image=TROPHY if os.path.exists(TROPHY) else None,
                        icon=None if os.path.exists(TROPHY) else "trophy-outline")
        badge.pos_hint = {"center_x": .5}
        body.add_widget(badge)
        body.add_widget(G.TL("APEX [b]PRO LEAGUE[/b]", 22, align="center",
                             size_hint_y=None, height=dp(40)))
        body.add_widget(G.note(
            "Turnirni boshlaganingizdan so'ng o'yinchilar ro'yxatdan o'ta oladi.\n"
            "Guruhlar (jamoa) soni cheklanmagan: ularni Admin paneldan istalgan payt "
            "qo'shasiz, kapitanlar ro'yxatdan o'tgan o'yinchilar orasidan tanlanadi.",
            size=12))
        body.add_widget(Widget())
        body.add_widget(G.solid_button(
            "Turnirni boshlash",
            lambda: MDApp.get_running_app().start_tournament(), h=54, fill=G.GREEN, size=15))
        root.add_widget(body)
        self.add_widget(root)


class LoginScreen(MDScreen):
    """Admin kirishi: email + parol. Kirgandan keyin turnir sozlanmagan bo'lsa, sozlash ochiladi."""

    def __init__(self, **kw):
        super().__init__(**kw)
        root = FloatLayout()
        root.add_widget(G.Background())
        ui = G.BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(16), dp(20)))
        ui.add_widget(G.TL("APEX [b]ADMIN[/b]", 20, align="center",
                           size_hint_y=None, height=dp(34)))
        ui.add_widget(G.note("Administrator hisobi bilan kiring", size=11.5))
        card = G.Glass(orientation="vertical", size_hint_y=None, spacing=dp(10),
                       padding=(dp(16), dp(16)), radius=22)
        card.bind(minimum_height=card.setter("height"))
        self.email = glass_field("Email", text=config.ADMIN_EMAIL)
        self.pw = glass_field("Parol", password=True)
        card.add_widget(self.email)
        card.add_widget(self.pw)
        ui.add_widget(card)
        self.btn = G.solid_button("Kirish", self.go, h=52, fill=G.GREEN, size=15)
        ui.add_widget(self.btn)
        ui.add_widget(G.note("Hisob Firebase Authentication da yaratilgan bo'ladi "
                             "(README 1-qadam).", size=10.5))
        ui.add_widget(Widget())
        root.add_widget(ui)
        self.add_widget(root)

    def busy(self, flag):
        self.btn.disabled = flag
        self.btn.lbl.text = "Kirilmoqda..." if flag else "Kirish"

    def go(self, *a):
        MDApp.get_running_app().do_login(self.email.text, self.pw.text)


class AdminMixin:
    """Admin funksiyalari. Har bir o'zgartirish Firebase qoidalari orqali ham tekshiriladi."""

    # ---------------- kirish / chiqish ----------------
    def require_admin(self):
        if not self.fb.is_admin():
            toast("Admin sifatida kiring")
            self.sm.current = "login"
            return False
        return True

    def do_login(self, email, password):
        """Email + parol bilan kirish (fon oqimida). Muvaffaqiyatli bo'lsa route() ekranni tanlaydi."""
        if not self.config_ok():
            toast("config.py to'ldirilmagan")
            return
        email = (email or "").strip()
        if not email or not password:
            toast("Email va parolni kiriting")
            return
        screen = self.sm.get_screen("login")
        screen.busy(True)

        def work():
            res = err = None
            try:
                self.fb.sign_in(email, password)
                self.store.etag = None
                res = self.store.fetch()
            except CloudError as e:
                err = e
            Clock.schedule_once(lambda dt: self._login_done(res, err))
        threading.Thread(target=work, daemon=True).start()

    def _login_done(self, res, err):
        screen = self.sm.get_screen("login")
        screen.busy(False)
        if err is not None:
            self.fb.sign_out()
            toast(err.human())
            return
        screen.pw.text = ""
        if res:
            self.store.apply(res)
        self.route()

    def logout(self):
        self.fb.sign_out()
        self.sm.current = "login"

    # ---------------- boshlang'ich sozlash ----------------
    def start_tournament(self):
        """Guruhlar soni so'ralmaydi: turnir ochiladi, guruhlar keyin qo'shiladi."""
        if not self.require_admin():
            return
        self.d["setup_done"] = True
        self.d["turn"] = 0
        self.store.snapshot["meta"].pop("turn", None)   # turn bazaga albatta yozilsin
        if not self.store.save():
            return
        self.route()
        toast("Turnir boshlandi. O'yinchilar ro'yxatdan o'tadi, guruhlar keyin qo'shiladi.")

    # ---------------- Admin oynasi ----------------
    # ---------------- Admin ekranlari (glass prototip uslubi) ----------------
    # ---------------- kartalar / dialoglar ----------------
    def open_player(self, pid):
        p = self.player(pid)
        if not p:
            return
        st = self.player_stats(pid)
        lines = [self.player_line(p), "",
                 "Gollar: %d    Assist: %d" % (st["goals"], st["assists"]),
                 "Sariq: %d    Qizil: %d" % (st["yellow"], st["red"]),
                 "O'yin: %d    G'alaba: %d" % (st["apps"], st["wins"]),
                 "Ball: %d" % st["points"]]
        self.show_dialog(self.pname(pid), text="\n".join(lines))

    def open_match(self, mid):
        m = self.match(mid)
        if not m:
            return
        lines = [self.match_label(m), ""]
        for g in m["goals"]:
            who = "%s (%s)" % (self.pname(g["scorer"]), self.gname(g["team"]))
            if g.get("assist"):
                who += " — assist: " + self.pname(g["assist"])
            lines.append("Gol: " + who)
        for c in m["cards"]:
            t = "Qizil" if c["type"] == "red" else "Sariq"
            lines.append("%s kartochka: %s" % (t, self.pname(c["pid"])))
        if not m["goals"] and not m["cards"]:
            lines.append("Hali gol va kartochka kiritilmagan.")
        self.show_dialog(self.match_label(m), text="\n".join(lines))

    # ---------------- Tab: Dashboard ----------------
    def refresh_dash(self):
        box = self.b_dash
        box.clear_widgets()

        card = G.Glass(orientation="vertical", size_hint_y=None, height=dp(178),
                       padding=dp(14), spacing=dp(10), radius=22)
        top = G.BoxLayout(size_hint_y=None, height=dp(62))
        left = G.BoxLayout(orientation="vertical")
        left.add_widget(G.TL("TURNIR", 11, G.MUTED))
        left.add_widget(G.TL("Turnir boshqaruvi", 22, bold=True))
        left.add_widget(G.TL("Barcha jarayonlar nazoratingizda", 11.5, G.MUTED))
        unassigned = len(self.free_players())
        pill = G.Glass(size_hint=(None, None), size=(dp(128), dp(44)), padding=(dp(10), 0),
                       spacing=dp(6), radius=16, pos_hint={"center_y": .5})
        pi = G.Icon("account-plus-outline", 20, G.CYAN)
        pi.pos_hint = {"center_y": .5}
        pill.add_widget(pi)
        pill.add_widget(G.TL("So'rov: %d" % unassigned, 13, bold=True, valign="center"))
        top.add_widget(left)
        top.add_widget(pill)
        card.add_widget(top)

        stats = G.Glass(size_hint_y=None, height=dp(62), padding=dp(8), radius=16)
        for ic, num, lab in (("account-group", len(self.d["groups"]), "jamoa"),
                             ("account-multiple", len(self.d["players"]), "o'yinchi"),
                             ("soccer", len(self.d["matches"]), "o'yin")):
            cell = G.BoxLayout(spacing=dp(4))
            i = G.Icon(ic, 22, G.MUTED)
            i.pos_hint = {"center_y": .5}
            col = G.BoxLayout(orientation="vertical")
            col.add_widget(G.TL(str(num), 18, bold=True))
            col.add_widget(G.TL(lab, 11, G.MUTED))
            cell.add_widget(i)
            cell.add_widget(col)
            stats.add_widget(cell)
        card.add_widget(stats)
        box.add_widget(card)

        menu = [
            ("account-group", "Guruhlar", "Jamoalarni boshqarish", hx("#7C5CFF"), self.admin_groups_menu),
            ("calendar-month", "Jadval yaratish", "O'yinlar jadvalini tuzish", hx("#3B82F6"), self.admin_make_fixtures),
            ("note-edit-outline", "Natija kiritish", "O'yin natijalarini kiritish", hx("#14B8A6"), self.admin_enter_result),
            ("soccer", "Gollar", "Gollar statistikasi", hx("#6366F1"), self.admin_goal_menu),
            ("card", "Kartochkalar", "Sariq va qizil kartochkalar", hx("#FACC15"), self.admin_card_menu),
            ("database", "Token", "Tokenlarni boshqarish", hx("#22D3EE"), self.admin_tokens),
            ("whistle", "Hakamlar", "Hakamlar va tayinlovlar", hx("#EC4899"), self.admin_refs_menu),
            ("cart-outline", "Market", "Sovrinlar va buyumlar", hx("#6D5BFF"), self.admin_market_menu),
            ("shuffle", "Kvota bo'lishi", "1 GK / 2 DF / 1 MF / 2 FW", hx("#0EA5E9"),
             self.admin_random_split),
            ("numeric", "Raqam takrorlari", _dup_hint(self.dup_numbers()),
             hx("#F59E0B"), self.number_clash_dialog),
            ("restore", "Taqsimni tozalash", "Qayta bo'lish uchun", hx("#EF4444"), self.admin_reset_split),
            ("delete-forever-outline", "O'yinchini o'chirish", "Baza bo'ylab izlari bilan",
             hx("#F87171"), self.admin_remove_player),
            ("shield-half-full", "Kapitan loginlari", "Login berish / parolni tiklash",
             hx("#22D3EE"), self.admin_cap_logins),
            ("lock-check", "Tarkib qulfi", "Boshlanish vaqti va avtomatik qulf", hx("#7C5CFF"),
             self.admin_lineup_manage),
            ("content-save-settings-outline", "Zaxira / tiklash", "Turnirni JSON ga eksport qilish",
             hx("#14B8A6"), self.admin_backup_menu),
        ]
        grid = G.GridLayout(cols=2, spacing=dp(12), size_hint_y=None,
                            row_default_height=dp(76), row_force_default=True)
        rows = (len(menu) + 1) // 2
        grid.height = rows * dp(76) + (rows - 1) * dp(12)
        for icon, t1, t2, col, cb in menu:
            grid.add_widget(G.MenuCard(icon, t1, t2, col, cb))
        box.add_widget(grid)

        banner = G.Glass(size_hint_y=None, height=dp(70), padding=dp(16), spacing=dp(12), radius=18)
        tr = G.Icon("trophy-outline", 34, hx("#8B7BFF"))
        tr.pos_hint = {"center_y": .5}
        banner.add_widget(tr)
        banner.add_widget(G.TL("Adolatli boshqaruv - katta o'yinlar garovi!", 14, bold=True, shorten=False))
        ch = G.Icon("chart-bar", 26, hx("#5B6CFF"))
        ch.pos_hint = {"center_y": .5}
        banner.add_widget(ch)
        box.add_widget(banner)

    # ---------------- Tab: O'yinlar ----------------
    def refresh_matches(self):
        self._matches_list()

    def _set_mfilter(self, name):
        self._m_filter = name
        self._matches_list()

    def _matches_list(self):
        lb = getattr(self, "_m_list", None)
        if lb is None:
            return
        lb.clear_widgets()
        if getattr(self, "_m_sub", None):
            self._m_sub.text = "%d ta o'yin" % len(self.d["matches"])
        f = getattr(self, "_m_filter", "Barchasi")
        shown = 0
        for m in self.d["matches"]:
            stage = m.get("stage", "group")
            if f == "Guruh" and stage != "group":
                continue
            if f == "FINAL" and stage != "final":
                continue
            score = "-:-" if m["hs"] is None else "%d:%d" % (m["hs"], m["as"])
            lb.add_widget(G.MatchCard(
                self.gname(m["home"]), self._grp_color(m["home"]), score,
                self.gname(m["away"]), self._grp_color(m["away"]),
                "FINAL" if stage == "final" else "Bosh guruh", m["hs"] is not None,
                lambda q=m["id"]: self.open_match(q)))
            shown += 1
        if not shown:
            lb.add_widget(G.TL("O'yin topilmadi. Dashboard'dagi 'Jadval yaratish' orqali boshlang.",
                               12, G.MUTED, shorten=False))

    # ---------------- Tab: O'yinchilar ----------------
    def refresh_players(self):
        self._players_list()

    def _set_ppos(self, name):
        self._p_pos = name
        self._players_list()

    def _players_list(self):
        lb = getattr(self, "_p_list", None)
        if lb is None:
            return
        lb.clear_widgets()
        if getattr(self, "_p_sub", None):
            self._p_sub.text = "%d ta o'yinchi" % len(self.d["players"])
        q = (self.p_search.text or "").strip().lower() if getattr(self, "p_search", None) else ""
        pos = getattr(self, "_p_pos", "Barchasi")
        shown = 0
        for p in self.d["players"]:
            if pos != "Barchasi" and p.get("pos") != pos:
                continue
            team = self.gname(p["group"]) if p["group"] else "Tanlanmagan"
            if q and q not in p["name"].lower() and q not in team.lower():
                continue
            st = self.player_stats(p["id"])
            color = self._grp_color(p["group"]) if p["group"] else G.PURPLE
            sub = "%s · %s" % (team, POS_NAME.get(p.get("pos"), "—"))
            lb.add_widget(G.PlayerRow(
                p["name"], sub, color, st["goals"], st["yellow"] + st["red"],
                lambda q2=p["id"]: self.open_player(q2)))
            shown += 1
        if not shown:
            lb.add_widget(G.TL("O'yinchi topilmadi.", 12, G.MUTED))

    # ---------------- Tab: Sozlamalar ----------------
    def refresh_settings(self):
        box = self.b_settings
        box.clear_widgets()
        box.add_widget(G.TL("Sozlamalar", 28, bold=True, size_hint_y=None, height=dp(40)))

        prof = G.Glass(size_hint_y=None, height=dp(80), padding=dp(14), spacing=dp(14), radius=20)
        av = G.Badge(G.PURPLE, 54, text="AD")
        av.pos_hint = {"center_y": .5}
        col = G.BoxLayout(orientation="vertical")
        col.add_widget(G.TL("Administrator", 17, bold=True))
        em = getattr(self.fb, "email", None) or getattr(config, "ADMIN_EMAIL", "")
        col.add_widget(G.TL(str(em), 12, G.MUTED))
        prof.add_widget(av)
        prof.add_widget(col)
        box.add_widget(prof)

        box.add_widget(G.section_label("TURNIR"))
        box.add_widget(self._set_group([
            self._link_row("Guruhlar", str(len(self.d["groups"])), self.admin_groups_menu),
            self._link_row("Kvota bo'lishi", str(len(self.free_players())) + " so'rov", self.admin_random_split),
            self._link_row("Taqsimni tozalash", "", self.admin_reset_split),
            self._link_row("Kapitan loginlari", "", self.admin_cap_logins),
            self._link_row("FINAL o'yini", "", self.admin_make_final),
        ]))
        box.add_widget(G.section_label("MA'LUMOTLAR"))
        box.add_widget(self._set_group([
            self._link_row("O'yin jadvali", "tuzish", self.admin_make_fixtures),
            self._link_row("Tarkib qulfi va vaqti",
                           str(sum(1 for m in self.d["matches"] if self.lineup_closed(m)))
                           + "/" + str(len(self.d["matches"])) + " qulflangan",
                           self.admin_lineup_manage),
            self._link_row("Raqam takrorlari",
                           "yo'q" if not self.dup_numbers() else "%d ta" % len(self.dup_numbers()),
                           self.number_clash_dialog),
            self._link_row("Hakamlar", str(len(self.d["refs"])), self.admin_refs_menu),
            self._link_row("Yordamchilar", str(len(self.d["assistants"])), self.admin_assistants_menu),
            self._link_row("Market", str(len(self.d["market"])), self.admin_market_menu),
            self._link_row("Guruh va o'yinchilarni o'chirish",
                           "%d + %d" % (len(self.d["groups"]), len(self.d["players"])),
                           self.admin_wipe_all),
            self._link_row("O'yinchini o'chirish",
                           str(len(self.d["players"])) + " o'yinchi",
                           self.admin_remove_player),
        ]))
        box.add_widget(G.section_label("TIZIM"))
        box.add_widget(self._set_group([
            self._link_row("Token boshqaruvi", "", self.admin_tokens),
            self._link_row("Turnir zaxirasi (backup)",
                           str(len(self.backup_files())) + " fayl", self.admin_backup_menu),
            self._link_row("Davomat jarimalari", "", self.admin_penalty),
            self._link_row("Parolni o'zgartirish", "", self.admin_change_pw),
            self._link_row("Til", "O'zbekcha", None),
            self._link_row("Versiya", "v%d" % VERSION_CODE, None),
        ]))

        out = G.GlassButton(size_hint_y=None, height=dp(50), radius=16,
                            fill=(0.94, 0.27, 0.27, 0.18), border=(0.97, 0.44, 0.44, 0.5))
        out.add_widget(G.TL("Chiqish", 15, hx("#FECACA"), bold=True, align="center"))
        out.bind(on_release=lambda *_: self.logout())
        box.add_widget(out)

    @staticmethod
    def _set_group(rows):
        g = G.Glass(orientation="vertical", size_hint_y=None, radius=18)
        g.bind(minimum_height=g.setter("height"))
        for i, r in enumerate(rows):
            if i:
                g.add_widget(G.divider())
            g.add_widget(r)
        return g

    def _link_row(self, title, value, cb):
        r = G.ButtonRow(size_hint_y=None, height=dp(52), padding=(dp(16), 0), spacing=dp(6))
        r.add_widget(G.TL(title, 14.5, bold=True))
        if value:
            r.add_widget(G.TL(value, 12, G.MUTED, align="right", size_hint_x=None, width=dp(120)))
        ch = G.Icon("chevron-right", 18, G.MUTED)
        ch.pos_hint = {"center_y": .5}
        r.add_widget(ch)
        if cb:
            r.bind(on_release=lambda *a: cb())
        return r


    def admin_change_pw(self):
        if not self.require_admin():
            return

        def cb(pw):
            if len(pw) < 6:
                toast("Parol kamida 6 belgi bo'lsin")
                return
            try:
                self.fb.change_password(pw)
                toast("Parol o'zgartirildi")
            except CloudError as e:
                toast(e.human())
        self.input_dialog("Yangi parol", "Parol (kamida 6 belgi)", cb, password=True)

    def player_refs(self, pid):
        """O'yinchi bazada qayerlarda q iz qoldirganini sanaydi (o'chirish oldidan ko'rsatish uchun)."""
        g = lambda n, label: [(label, n)] if n else []
        out = []
        out += g(sum(ids.count(pid) for m in self.d["matches"]
                     for ids in m["lineups"].values()), "tarkib qatori")
        out += g(sum(1 for m in self.d["matches"] for x in m["goals"]
                     if pid in (x["scorer"], x.get("assist"))), "gol/assist")
        out += g(sum(1 for m in self.d["matches"] for s in m["subs"]
                     if pid in (s["in"], s["out"])), "almashinuv")
        out += g(sum(1 for m in self.d["matches"] for c in m["cards"]
                     if c["pid"] == pid), "kartochka")
        out += g(sum(1 for m in self.d["matches"] for a in m.get("attendance", [])
                     if a["pid"] == pid), "davomat")
        out += g(sum(1 for m in self.d["matches"] if m.get("motm_admin") == pid), "MOTM")
        out += g(sum(1 for t in self.d["transfers"] if t["pid"] == pid), "transfer")
        out += g(sum(1 for n in self.d["notifs"] if n["to"] == f"p{pid}"), "xabarnoma")
        out += g(len(self.player(pid).get("thist", [])) if self.player(pid) else 0, "token tarixi")
        return out

    def admin_remove_player(self):
        if not self.require_admin():
            return
        opts = [(self.player_label(p), p["id"]) for p in self.d["players"]]

        def chosen(pid):
            g = self.captain_group(pid)
            if g:
                self.confirm_dialog("Kapitanni guruh bilan o'chirish",
                                    self.cap_delete_text(pid, g),
                                    lambda: self._delete_captain_with_group(pid))
                return
            refs = self.player_refs(pid)
            if refs:
                text = ("«%s» o'chirilsinmi? Birga o'chadi:\n%s\n\nBu amall ortga qaytarilmaydi." %
                        (self.pname(pid),
                         "\n".join("  • %d %s" % (count, label) for label, count in refs)))
            else:
                text = "«%s» o'chirilsinmi? Statistikasi yo'q." % self.pname(pid)
            self.confirm_dialog("O'yinchini o'chirish", text,
                                lambda: self._remove_player(pid))
        self.choose_dialog("Qaysi o'yinchi?", opts, chosen)

    def cap_delete_text(self, pid, g):
        gid = g["id"]
        refs = self.player_refs(pid)
        members = len([p for p in self.members(gid) if p["id"] != pid])
        games = sum(1 for m in self.d["matches"] if gid in (m["home"], m["away"]))
        lines = [f"«{self.pname(pid)}» kapitan — «{g['name']}» guruh ham birga o'chadi.",
                 "",
                 "  • guruh: %s (login: %s) — kapitan logini bilan yo'q bo'ladi" %
                 (g["name"], g.get("cap_login") or "yo'q")]
        if members > 0:
            lines.append(f"  • {members} a'zo: tanlanmaganlar ro'yxatiga qaytadi")
        if games:
            lines.append(f"  • {games} o'yin: natijalari bilan o'chadi")
        lines += ["  • %d %s" % (count, label) for label, count in refs]
        lines += ["", "Bu amall ortga qaytarilmaydi."]
        return "\n".join(lines)

    def _delete_captain_with_group(self, pid):
        if not self.require_admin():
            return
        self.auto_backup("kapitan o'chirish")
        g = self.captain_group(pid)
        if g:
            self._purge_group(g["id"])
        self.purge_player(pid)
        self.d["players"] = [p for p in self.d["players"] if p["id"] != pid]
        if self.load_me().get("pid") == pid:
            self.clear_me()
        self.store.save()
        self.refresh_all()
        toast("Kapitan va guruh barcha izlari bilan o'chirildi")

    def _remove_player(self, pid):
        if not self.require_admin():
            return
        self.auto_backup("o'yinchi o'chirish")
        self.purge_player(pid)
        self.d["players"] = [p for p in self.d["players"] if p["id"] != pid]
        if self.load_me().get("pid") == pid:
            self.clear_me()
        self.store.save()
        self.refresh_all()
        toast("O'yinchi va barcha izlari o'chirildi")

    def purge_player(self, pid):
        """Baza bo'ylab o'yinchi izlarini to'liq tozalaydi (D-1: qattiq o'chirish)."""
        for m in self.d["matches"]:
            for k in list(m["lineups"].keys()):
                m["lineups"][k] = [x for x in m["lineups"][k] if x != pid]
            goals = [g for g in m["goals"] if pid not in (g["scorer"], g.get("assist"))]
            subs = [s for s in m["subs"] if pid not in (s["in"], s["out"])]
            cards = [c for c in m["cards"] if c["pid"] != pid]
            if len(goals) != len(m["goals"]):
                m["goals"] = goals
                self.recompute_score(m)
            m["cards"] = cards
            m["subs"] = subs
            if "attendance" in m:
                m["attendance"] = [a for a in m["attendance"] if a["pid"] != pid]
            if m.get("motm_admin") == pid:
                m["motm_admin"] = None
        self.d["transfers"] = [t for t in self.d["transfers"] if t["pid"] != pid]
        self.d["notifs"] = [n for n in self.d["notifs"] if n["to"] != f"p{pid}"]

    def admin_groups_menu(self):
        if not self.require_admin():
            return
        opts = [("Kvota bo'lishi", self.admin_random_split),
                ("Taqsimni tozalash", self.admin_reset_split),
                ("Guruh qo'shish", self.admin_add_group),
                ("Guruh nomini o'zgartirish", self.admin_rename_group),
                ("Guruh logosini o'zgartirish", self.admin_set_logo),
                ("Kapitanni almashtirish", self.admin_change_captain),
                ("Kapitanni guruh bilan o'chirish", self.admin_delete_captain),
                ("Guruhni o'chirish", self.admin_delete_group)]
        self.choose_dialog("Guruhlar", opts, lambda fn: fn())

    def admin_delete_captain(self):
        if not self.require_admin():
            return
        opts = [("%s  —  %s" % (g["name"], self.captain_name(g)), g["captain_id"])
                for g in self.d["groups"] if g.get("captain_id") is not None
                and self.player(g["captain_id"])]

        def chosen(pid):
            g = self.captain_group(pid)
            if not g:
                toast("Bu guruhning kapitani topilmadi")
                return
            self.confirm_dialog("Kapitanni guruh bilan o'chirish",
                                self.cap_delete_text(pid, g),
                                lambda: self._delete_captain_with_group(pid))
        if not opts:
            toast("Hech bir guruhda kapitan yo'q")
            return
        self.choose_dialog("Qaysi kapitan?", opts, chosen)

    def admin_add_group(self):
        def cb(name):
            if not name or not self.require_admin():
                return

            def cb2(logo):
                def cb3(pid):
                    if pid is not None and self.is_captain(pid):
                        toast("Bu o'yinchi allaqachon kapitan")
                        return
                    gid = self.store.new_id()

                    def got(login, pw):
                        if not self.require_admin():
                            return
                        cap_id = pid
                        if cap_id is None:
                            cap_id = self.store.new_id()
                            self.d["players"].append(
                                {"id": cap_id, "name": name + " kapitani", "group": gid,
                                 "number": DEFAULT_NUMBER, "pos": DEFAULT_POS,
                                 "country": DEFAULT_COUNTRY, "tokens": TOKEN_START,
                                 "token_zero_since": None})
                        else:
                            self.player(cap_id)["group"] = gid
                        g = {"id": gid, "name": name, "captain_id": cap_id,
                             "cap_login": login, "cap_pass_hash": self.cap_hash(pw, gid),
                             "ptokens": 0}
                        self.apply_logo(g, logo)
                        self.d["groups"].append(g)
                        self.store.save()
                        self.refresh_all()
                        toast("Guruh qo'shildi — kapitan logini: %s" % login)
                    self.ask_cap_credentials(gid, name, got)
                opts = [(self.player_label(p), p["id"]) for p in self.d["players"]
                        if not self.is_captain(p["id"])]
                opts.append(("— Yangi o'yinchi yaratish", None))
                self.choose_dialog("Kapitan (ro'yxatdan o'tganlar)", opts, cb3)
            self.logo_picker(cb2)
        self.input_dialog("Yangi guruh nomi", "Nomi", cb)

    def admin_set_logo(self):
        opts = [(g["name"], g["id"]) for g in self.d["groups"]]

        def chosen(gid):
            def got(value):
                if self.require_admin():
                    self.apply_logo(self.group(gid), value)
                    self.store.save()
                    self.refresh_all()
            self.logo_picker(got)
        self.choose_dialog("Qaysi guruh?", opts, chosen)

    def admin_edit_player(self):
        """Raqam, pozitsiya, davlat va boshlang'ich OVR ni o'zgartirish."""
        if not self.require_admin():
            return
        opts = [(f"{p['name']}  ({self.player_line(p)})", p["id"]) for p in self.d["players"]]

        def chosen(pid):
            p = self.player(pid)

            def done():
                if self.require_admin() and self.store.save():
                    toast("Saqlandi")
                self.refresh_all()

            def set_number():
                self.ask_number(pid)

            def set_pos():
                def cb(code):
                    p["pos"] = code
                    done()
                self.choose_dialog("Pozitsiya", [(f"{n} ({c})", c) for n, c in POSITIONS], cb)

            def set_country():
                def cb(t):
                    if not 2 <= len(t) <= 30:
                        toast("Davlat nomi 2-30 belgi bo'lsin")
                        return
                    p["country"] = t
                    done()
                self.input_dialog("Davlat", "Davlat nomi", cb, text=p.get("country") or "")

            def set_ovr():
                def cb(t):
                    if not (t.isdigit() and 40 <= int(t) <= 90):
                        toast("Boshlang'ich OVR 40 dan 90 gacha bo'lsin")
                        return
                    p["base_ovr"] = int(t)
                    done()
                self.input_dialog("Boshlang'ich OVR", "40-90", cb,
                                  text=str(p.get("base_ovr") or BASE_OVR), digits=True)
            self.choose_dialog("Nimani o'zgartiramiz?", [
                ("Futbolka raqami", set_number), ("Pozitsiya", set_pos),
                ("Davlat", set_country), ("Boshlang'ich OVR", set_ovr)], lambda fn: fn())
        self.choose_dialog("Qaysi o'yinchi?", opts, chosen)

    def ask_number(self, pid):
        """Futbolka raqami: jamoada band bo'lsa rad etiladi (1 raqam = 1 o'yinchi)."""
        p = self.player(pid)
        if not p or not self.require_admin():
            return

        def cb(t):
            if not (t.isdigit() and 1 <= int(t) <= MAX_NUMBER):
                toast("Raqam 1 dan %d gacha bo'lsin" % MAX_NUMBER)
                return
            clash = self.number_holder(p["group"], int(t), pid)
            if clash:
                toast("%d raqami %s jamoida %s da band — avval uning raqamini "
                      "boshqaga o'zgartiring" % (int(t), self.gname(p["group"]), clash["name"]))
                return
            p["number"] = int(t)
            if self.require_admin() and self.store.save():
                toast("Saqlandi")
            self.refresh_all()
            rest = self.dup_numbers(p["group"])
            if rest:
                self.number_clash_dialog(rest)

        free = ", ".join(str(n) for n in self.free_numbers(p["group"], 4, pid))
        self.input_dialog("%s  ·  raqam" % p["name"],
                          "1-%d, jamoada noyob bo'lsin. Bo'sh: %s" % (MAX_NUMBER, free), cb,
                          text=str(p.get("number") or ""), digits=True)

    def number_clash_dialog(self, dups=None):
        """Takror raqamlar ro'yxati: qatorni bossa o'sha o'yinchining raqamini o'zgartiramiz."""
        dups = self.dup_numbers() if dups is None else dups
        if not dups:
            self.show_dialog("Raqam takrorlari",
                             text="Har jamoada barcha raqamlar noyob — tuzatish shart emas.")
            return

        def pick(item):
            gid, num, ps = item
            self.choose_dialog("%s  ·  %d raqami" % (self.gname(gid), num),
                               [(f"{p['name']}  ({self.player_line(p)})", p["id"]) for p in ps],
                               self.ask_number)

        opts = [("%s  ·  %d raqami  ·  %s" %
                 (self.gname(gid), num, " va ".join(x["name"].split()[0] for x in ps)),
                 (gid, num, ps)) for gid, num, ps in dups]
        self.choose_dialog(
            "Raqam takrorlari: %d" % len(dups), opts, pick)

    def shape_gap_dialog(self, gaps=None):
        """Asosiy 6 tasi to'lmagan jamoalar: bo'lishdan keyin admin ko'radi (hech narsa to'xtamaydi)."""
        gaps = self.shape_gaps() if gaps is None else gaps
        if not gaps:
            self.show_dialog("Asosiy tarkib shakli",
                             text="Hamma jamoada asosiy 6 ta (1 GK / 2 DF / 1 MF / 2 FW) to'lgan.")
            return
        lines = []
        for gid, miss in gaps:
            lines.append("%s (%d kishi): %s" % (
                self.gname(gid), len(self.members(gid)),
                ", ".join("%s %d ta yetishmaydi" % (SHAPE_LABEL.get(k, k), v)
                          for k, v in miss.items())))
        self.show_dialog(
            "Asosiy 6 to'lmagan jamoalar",
            text="\n".join(lines) +
                 "\n\nYechim: havuzada shu pozitsiyada o'yinchi bo'lsa «Kvota bo'lishi»ni "
                 "qayta bosing, yoki O'yinchilar → O'zgartirish → Pozitsiya dan pozitsiyani "
                 "o'zgartiring (MF va FW bir-birining o'rnini bosadi, GK va DF — yo'q).")

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
            def cb(pid):
                def got(login, pw):
                    if not self.require_admin():
                        return
                    p = self.player(pid)
                    if not p:
                        return
                    p["group"] = gid
                    g = self.group(gid)
                    g["captain_id"] = pid
                    g["cap_login"] = login
                    g["cap_pass_hash"] = self.cap_hash(pw, gid)
                    self.store.save()
                    self.refresh_all()
                    toast("Kapitan almashtirildi — login: %s" % login)
                    if self.dup_numbers(gid):
                        self.number_clash_dialog(self.dup_numbers(gid))
                self.ask_cap_credentials(gid, self.gname(gid), got)
            popts = [(self.player_label(p), p["id"]) for p in self.d["players"]
                     if not self.is_captain(p["id"])]
            if not popts:
                toast("Avval o'yinchilar ro'yxatdan o'tsin")
                return
            self.choose_dialog("Yangi kapitan (ro'yxatdan o'tganlar)", popts, cb)
        self.choose_dialog("Qaysi guruh?", opts, chosen)

    def admin_delete_group(self):
        opts = [(g["name"], g["id"]) for g in self.d["groups"]]

        def chosen(gid):
            cap = self.group(gid).get("captain_id")
            extra = (f" Kapitan «{self.pname(cap)}» oddiy o'yinchi bo'lib qoladi."
                     if cap and self.player(cap) else "")
            self.confirm_dialog("Guruhni o'chirish",
                                f"«{self.gname(gid)}» o'chirilsinmi? A'zolari tanlanmaganlarga o'tadi.{extra}",
                                lambda: self._delete_group(gid))
        self.choose_dialog("Qaysi guruh?", opts, chosen)

    def _delete_group(self, gid):
        if not self.require_admin():
            return
        self.auto_backup("guruh o'chirish")
        self._purge_group(gid)
        self.store.save()
        self.refresh_all()

    def _purge_group(self, gid):
        for p in self.d["players"]:
            if p["group"] == gid:
                p["group"] = None
        self.d["groups"] = [g for g in self.d["groups"] if g["id"] != gid]
        self.d["matches"] = [m for m in self.d["matches"] if gid not in (m["home"], m["away"])]
        self.d["turn"] = 0

    def ask_cap_credentials(self, gid, gname, cb):
        """Kapitan uchun login + parol so'rash (faqat admin beradi)."""
        sug = self.suggest_login(gname, gid)

        def got_pw(pw):
            if not self.require_admin():
                return
            if not self.valid_password(pw):
                toast("Parol kamida 6 belgi bo'lsin")
                return
            cb(self.norm_login(got_login.lg), pw.strip())

        def got_login(login):
            if not self.require_admin():
                return
            lg = self.norm_login(login)
            if len(lg) < 4:
                toast("Login kamida 4 ta lotin harf/raqam bo'lsin")
                return
            if self.login_taken(lg, ignore_gid=gid):
                toast(f"Bu login band — masalan: {sug}")
                return
            got_login.lg = lg
            self.input_dialog("Kapitan paroli", "Parol (kamida 6 belgi)", got_pw, password=True)
        got_login.lg = ""
        self.input_dialog("Kapitan logini", f"Login (masalan: {sug})", got_login)

    def admin_cap_logins(self):
        """Kapitan loginlari: loginni ko'rish, parolni tiklash yoki loginni almashtirish."""
        if not self.require_admin():
            return
        opts = [(f"{g['name']}  —  {g.get('cap_login') or 'loginsiz'}", g["id"])
                for g in self.d["groups"]]

        def change_login(g):
            def cb(login):
                if not self.require_admin():
                    return
                lg = self.norm_login(login)
                if len(lg) < 4:
                    toast("Login kamida 4 ta lotin harf/raqam bo'lsin")
                    return
                if self.login_taken(lg, ignore_gid=g["id"]):
                    toast("Bu login band")
                    return
                g["cap_login"] = lg
                self.store.save()
                toast("Login o'zgartirildi: %s" % lg)
            self.input_dialog("Loginni almashtirish",
                              f"Hozir: {g.get('cap_login')} (masalan: {self.suggest_login(g['name'], g['id'])})",
                              cb)

        def reset_password(g):
            def cb(pw):
                if not self.require_admin():
                    return
                if not self.valid_password(pw):
                    toast("Parol kamida 6 belgi bo'lsin")
                    return
                g["cap_pass_hash"] = self.cap_hash(pw.strip(), g["id"])
                self.store.save()
                toast("Parol yangilandi")
            self.input_dialog("Parolni tiklash",
                              f"{g.get('cap_login')} uchun yangi parol (6+ belgi)",
                              cb, password=True)

        def chosen(gid):
            g = self.group(gid)
            if g.get("cap_login"):
                acts = [("Parolni tiklash", lambda: reset_password(g)),
                        ("Loginni almashtirish", lambda: change_login(g))]
            else:
                def issue():
                    self.ask_cap_credentials(g["id"], g["name"],
                                             lambda lg, pw: self._set_cap_cred(g, lg, pw))
                acts = [("Login va parol berish", issue)]
            self.choose_dialog(g["name"], [(t, fn) for t, fn in acts], lambda fn: fn())

        self.choose_dialog("Kapitan loginlari", opts, chosen)

    def _set_cap_cred(self, g, login, pw):
        if not self.require_admin():
            return
        g["cap_login"] = login
        g["cap_pass_hash"] = self.cap_hash(pw, g["id"])
        self.store.save()
        toast("Kapitan yuklandi — login: %s" % login)

    def admin_make_fixtures(self):
        if not self.require_admin():
            return
        halves = self.stage_groups()
        scopes = halves if halves else [[g["id"] for g in self.d["groups"]]]
        if not self.d["groups"]:
            toast("Avval guruh qo'shing")
            return
        have = {(m["home"], m["away"], m.get("stage", "group"), m.get("grp"))
                for m in self.d["matches"]}
        added = 0
        for si, scope in enumerate(scopes):
            grp = si if halves else None
            for a, b in self.planned_pairs(scope, halves is None):
                if (a, b, "group", grp) in have:
                    continue
                self.d["matches"].append({"id": self.store.new_id(), "home": a, "away": b,
                                          "hs": None, "as": None, "lineups": {},
                                          "lineup_locked": False, "cards": [],
                                          "goals": [], "subs": [], "motm_admin": None,
                                          "stage": "group", "grp": grp, "attendance": []})
                added += 1
        self.store.save()
        self.refresh_all()
        kind = "guruh bosqichi" if halves else "2 davrali (uy-mehmon)"
        toast(f"{added} ta o'yin qo'shildi ({kind})")

    def admin_make_final(self):
        if not self.require_admin():
            return
        if self.final_match():
            toast("FINAL allaqachon yaratilgan")
            return
        if not self.group_stage_complete():
            toast("Guruh o'yinlari hali to'liq tugamagan")
            return
        c = self.final_candidates()
        if len(c) != 2:
            toast("Final juftligini aniqlab bo'lmadi")
            return
        self.d["matches"].append({"id": self.store.new_id(), "home": c[0], "away": c[1],
                                  "hs": None, "as": None, "lineups": {},
                                  "lineup_locked": False, "cards": [],
                                  "goals": [], "subs": [], "motm_admin": None,
                                  "stage": "final", "grp": None, "attendance": []})
        self.store.save()
        self.refresh_all()
        toast(f"FINAL yaratildi: {self.gname(c[0])} — {self.gname(c[1])}")

    def admin_enter_result(self):
        if not self.require_admin():
            return
        opts = [(self.match_label(m), m["id"]) for m in self.d["matches"]]

        def chosen(mid):
            m = self.match(mid)
            if m["goals"]:
                toast("Hisob gollardan avtomatik hisoblanadi. Gollarni o'zgartiring.")
                return
            f1 = glass_field(self.gname(m["home"]), digits=True,
                             text="" if m["hs"] is None else str(m["hs"]))
            f2 = glass_field(self.gname(m["away"]), digits=True,
                             text="" if m["as"] is None else str(m["as"]))
            content = BoxLayout(orientation="vertical", spacing=dp(10))
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
                self.award_final(m)
                self.close_dialog()
                self.store.save()
                self.refresh_all()
            self.show_dialog("Natija", content=content, buttons=[
                MDFlatButton(text="Bekor", on_release=self.close_dialog),
                MDRaisedButton(text="Saqlash", on_release=save)])
        self.choose_dialog("Qaysi o'yin?", opts, chosen)

    def admin_goal_menu(self):
        if not self.require_admin():
            return
        self.choose_dialog("Gollar", [("Gol qo'shish (muallif + assist)", self.admin_add_goal),
                                      ("Golni o'chirish", self.admin_remove_goal)],
                           lambda fn: fn())

    def admin_card_menu(self):
        if not self.require_admin():
            return
        self.choose_dialog("Kartochkalar", [("Sariq / Qizil qo'shish", self.admin_add_card),
                                            ("Kartochkani bekor qilish", self.admin_remove_card)],
                           lambda fn: fn())

    def admin_add_goal(self):
        if not self.require_admin():
            return
        self.goal_add()

    def admin_remove_goal(self):
        if not self.require_admin():
            return
        self.goal_remove()

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
                        s = {"team": gid, "out": oid, "in": iid, "ts": now_ts()}
                        mn = self.clock_minute(mid)
                        if mn:
                            s["min"] = mn
                        m["subs"].append(s)
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
                    c = {"pid": pid, "type": t, "ts": now_ts()}
                    mn = self.clock_minute(mid)
                    if mn:
                        c["min"] = mn
                    m["cards"].append(c)
                    if t == "red":
                        self.add_tokens(pid, -RED_PENALTY, "Qizil kartochka")
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
                c = m["cards"][idx]
                m["cards"].pop(idx)
                if c["type"] == "red":
                    self.add_tokens(c["pid"], RED_PENALTY, "Qizil kartochka bekor qilindi")
                self.store.save()
                self.refresh_all()
                toast("Kartochka bekor qilindi")
        self.choose_dialog("Qaysi kartochka?", opts, chosen)

    def admin_lineup_manage(self):
        """O'yin boshlanish vaqti va tarkib qulfi (avtomatik qulf shu vaqtdan kelib chiqadi)."""
        if not self.require_admin():
            return
        opts = [(f"{self.match_label(m)}  [{self.lock_note(m)}]", m["id"])
                for m in self.d["matches"]]

        def chosen(mid):
            m = self.match(mid)
            kick = self.kick_ts(m)

            def toggle_lock():
                m["lineup_locked"] = not m["lineup_locked"]
                self.store.save()
                self.refresh_all()
                if m["lineup_locked"]:
                    toast("Qulflandi")
                elif self.auto_locked(m):
                    toast("Ochildi, lekin boshlanish vaqti o'tgan — avtomatik qulf yopib turadi. "
                          "Vaqtga o'zgartirish kiriting.")
                else:
                    toast("Ochildi")

            def clear(gid):
                m["lineups"][str(gid)] = []
                self.store.save()
                self.refresh_all()
                toast("Tozalandi")

            acts = [("Qulflash / Ochish", toggle_lock),
                    ("Boshlanish vaqtini belgilash",
                     lambda: self.input_dialog(
                         "Boshlanish vaqti (kun.oy soat:daq)",
                         "05.11 18:30", lambda txt, mm=m: self._set_kick(mm, txt),
                         text=time.strftime("%d.%m %H:%M", time.localtime(kick)) if kick else ""))]
            if kick:
                acts.append(("Boshlanish vaqtini o'chirish", lambda: self._set_kick(m, None)))
            acts += [(f"{self.gname(m['home'])} tarkibini tozalash", lambda: clear(m["home"])),
                     (f"{self.gname(m['away'])} tarkibini tozalash", lambda: clear(m["away"]))]
            self.choose_dialog("Amal", acts, lambda fn: fn())
        self.choose_dialog("Qaysi o'yin?", opts, chosen)

    def _set_kick(self, m, txt):
        """Boshlanish vaqtini saqlaydi (None — o'chirish). Tarkib qulfi shu vaqtdan hisoblanadi."""
        if txt is None:
            m["kick"] = None
            self.store.save()
            self.refresh_all()
            toast("Boshlanish vaqti o'chirildi — endi tarkib faqat qo'lab qulflanadi")
            return
        t = None
        for fmt in ("%d.%m %H:%M", "%d.%m.%Y %H:%M"):
            try:
                t = time.strptime((txt or "").strip(), fmt)
                break
            except ValueError:
                continue
        if not t:
            toast("Format: 05.11 18:30 (kun.oy soat:daqiqa)")
            return
        year = t.tm_year if t.tm_year != 1900 else time.localtime().tm_year
        ts = int(time.mktime((year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, 0, 0, 0, -1)))
        m["kick"] = ts
        if self.store.save():
            self.refresh_all()
            toast("Boshlanishi %s — tarkib %s gacha ochiq"
                  % (time.strftime("%d.%m %H:%M", time.localtime(ts)),
                     time.strftime("%d.%m %H:%M", time.localtime(self.lock_at(m)))))

    def auto_lock_persist(self, *a):
        """Boshlanishiga LINEUP_LOCK_MIN daqiqa qolganda qulfni bazaga ham yozadi (barcha telefonlar uchun)."""
        if not self.fb.is_admin():
            return
        due = [m for m in self.d["matches"]
               if m["hs"] is None and not m["lineup_locked"] and self.auto_locked(m)]
        if not due:
            return
        for m in due:
            m["lineup_locked"] = True
        if self.store.save():
            self.refresh_all()
            toast("Tarkib avtomatik qulflandi: %s"
                  % ", ".join(self.match_label(m) for m in due[:3]))

    def admin_random_split(self):
        if not self.require_admin():
            return
        groups = self.d["groups"]
        if not groups:
            toast("Avval kamida bitta guruh yarating va kapitan tanlang")
            return
        pool = [p for p in self.free_players() if not self.is_captain(p["id"])]
        if not pool:
            toast("Tanlanmagan (so'rov) o'yinchi yo'q")
            return

        sizes = {g["id"]: len(self.members(g["id"])) for g in groups}
        if all(n >= MAX_GROUP for n in sizes.values()):
            toast("Barcha guruhlar to'lgan (har biri max %d). Yangi guruh qo'shing." % MAX_GROUP)
            return

        def do():
            if not self.require_admin():
                return
            sz = {g["id"]: len(self.members(g["id"])) for g in groups}
            # har guruhning asosiy 6 talik shakl qoldig'i: 1 GK, 2 DF, 1 MF, 2 FW (kapitan ham hisobda)
            need = {g["id"]: {k: POS_QUOTA[k] - self.pos_counts(
                        [p["id"] for p in self.members(g["id"])]).get(k, 0)
                    for k in POS_QUOTA} for g in groups}
            pos_of = lambda p: (p.get("pos") or "MF").upper()
            ovr_of = lambda p: self.player_ovr(p["id"])[0]
            # kam uchraydigan pozitsiyadan boshlaymiz: shakl avval to'lsin
            scarce = sorted(POS_QUOTA, key=lambda k: sum(1 for p in pool if pos_of(p) == k))
            placed, extra = 0, []

            # --- 1-bosqich: avval HAMA jamoaning asosiy 6 tasi to'ldiriladi ---
            for pos in scarce:
                xs = sorted([p for p in pool if pos_of(p) == pos], key=ovr_of, reverse=True)
                for p in xs:
                    want = [gid for gid in sz
                            if sz[gid] < MAX_GROUP and need[gid].get(pos, 0) > 0]
                    if not want:
                        extra.append(p)
                        continue
                    # eng muhtaj guruh; teng bo'lsa soni eng kam jamoa
                    gid = min(want, key=lambda k: (-need[k][pos], sz[k]))
                    p["group"] = gid
                    need[gid][pos] -= 1
                    sz[gid] += 1
                    placed += 1
            # --- 2-bosqich: ortib qolganlar jamoalar SONI Teng bo'lishi uchun beriladi ---
            for p in sorted(extra, key=ovr_of, reverse=True):
                room = [gid for gid in sz if sz[gid] < MAX_GROUP]
                if not room:
                    break
                gid = min(room, key=lambda k: (sz[k], -max(need[k].values())))
                p["group"] = gid
                sz[gid] += 1
                placed += 1
            self.store.save()
            self.refresh_all()
            left = len(pool) - placed
            msg = ("%d o'yinchi bo'lindi: avval har jamoaga asosiy 6 ta (1 GK / 2 DF / 1 MF / "
                   "2 FW), so'ng ortiqchalar teng son qilib" % placed)
            if left:
                msg += ". %d tasi sig'madi (har guruh max %d)" % (left, MAX_GROUP)
            toast(msg)
            if self.shape_gaps():
                self.shape_gap_dialog()
            dups = self.dup_numbers()
            if dups:
                self.number_clash_dialog(dups)
        self.confirm_dialog(
            "Kvota bo'yicha bo'lish",
            "%d ta so'rov ikki bosqichda bo'linsinmi?\n\n"
            "1) Avval har guruhning ASOSIY 6 tasi to'ldiriladi: 1 darvozabon, 2 himoyachi, "
            "1 yarim himoyachi, 2 hujumchi (MF va FW bir-birining o'rnini bosadi).\n"
            "2) So'ng ortib qolgan o'yinchilar soni teng bo'ladigan qilib jamoalarga "
            "beriladi (max %d o'rin).\n\n"
            "Guruhlarga tushgan o'yinchilar joyida qoladi, kapitanlar aralashmaydi. "
            "Eslatma: bir jamoaga takror futbolka raqami tushsa, ro'yxati ko'rsatiladi — "
            "o'yinchilar bilan kelishib raqamni o'zingiz o'zgartirasiz."
            % (len(pool), MAX_GROUP), do)

    def admin_reset_split(self):
        if not self.require_admin():
            return

        def do():
            if not self.require_admin():
                return
            self.auto_backup("taqsimni tozalash")
            for p in self.d["players"]:
                if not self.is_captain(p["id"]):
                    p["group"] = None
                    self.purge_from_lineups(p["id"])
            self.store.save()
            self.refresh_all()
            toast("Barcha so'rovlar tanlanmaganlarga qaytarildi")
        self.confirm_dialog(
            "Taqsimni tozalash",
            "Kapitanlardan boshqa hamma o'yinchilar tanlanmaganlar (so'rov) ro'yxatiga qaytadi.",
            do)


    # ---------------- Jonli ma'lumotni tozalash ----------------
    def admin_wipe_all(self):
        """Guruhlar va o'yinchilarni butunlay o'chirish (hakamlar qoladi)."""
        if not self.require_admin():
            return
        if not self.d["groups"] and not self.d["players"]:
            toast("O'chiradigan guruh yoki o'yinchi yo'q")
            return
        g, p = len(self.d["groups"]), len(self.d["players"])
        self.confirm_dialog(
            "Guruh va o'yinchilarni o'chirish",
            "%d guruh va %d o'yinchi butunlay o'chadi. Ularga bog'liq o'yinlar, tarkiblar, "
            "transferlar va xabarnomalar ham tozalanadi. Hakamlar ro'yxati qoladi.\n\n"
            "Bu amal qaytarilmaydi!" % (g, p),
            self._wipe_all)

    def _wipe_all(self):
        if not self.require_admin():
            return
        self.auto_backup("to'liq tozalash")
        self.d["groups"] = []
        self.d["players"] = []
        self.d["matches"] = []
        self.d["transfers"] = []
        self.d["notifs"] = []
        self.d["turn"] = 0
        self.store.save()
        self.refresh_all()
        toast("Guruhlar va o'yinchilar o'chirildi")

    # ---------------- ZAXIRA: eksport / tiklash ----------------
    BACKUP_KEEP = 20      # shu qadar eng yangi zaxira qurilmada saqlanadi

    def backup_dir(self):
        d = os.path.join(self.user_data_dir, "backups")
        os.makedirs(d, exist_ok=True)
        return d

    def backup_files(self):
        """Shu qurilmadagi zaxira fayllar (yangidan eskiga tartibda)."""
        try:
            return sorted([f for f in os.listdir(self.backup_dir())
                           if f.startswith("apex_") and f.endswith(".json")], reverse=True)
        except Exception:
            return []

    def backup_now(self, tag="qo'lab"):
        """Butun turnir snapshot'ini JSON ga yozadi; eski zaxiralar siqib chiqariladi."""
        slug = "".join(c for c in (tag or "").lower() if c.isalnum() or c in "-_")[:28] or "backup"
        name = "apex_%s_%s.json" % (time.strftime("%Y%m%d_%H%M%S"), slug)
        try:
            payload = to_remote(self.d)
            payload["_apex"] = {"ts": now_ts(), "tag": tag, "ver": VERSION_CODE}
            with open(os.path.join(self.backup_dir(), name), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            for old in self.backup_files()[self.BACKUP_KEEP:]:
                try:
                    os.remove(os.path.join(self.backup_dir(), old))
                except Exception:
                    pass
            return os.path.join(self.backup_dir(), name)
        except Exception as e:
            toast("Zaxira yozilmadi: " + str(e)[:70])
            return None

    def auto_backup(self, why):
        """Xavfli amaldan oldin. Fayl xatosi amalni to'xtatmasligi kerak."""
        if self.backup_now("avto: " + why):
            toast("Zaxira yaratildi (%s)" % why)

    def backup_read(self, path):
        """Zaxira faylni tekshirib store.data ko'rinishida qaytaradi (xato bo'lsa None)."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            toast("Fayl o'qilmadi: " + str(e)[:70])
            return None
        if not isinstance(raw, dict) or not isinstance(raw.get("groups"), dict) \
                or not isinstance(raw.get("players"), dict):
            toast("Bu APEX zaxira fayli emas")
            return None
        return from_remote(raw)

    def restore_counts(self, data):
        return "%d guruh, %d o'yinchi, %d o'yin" % (
            len(data["groups"]), len(data["players"]), len(data["matches"]))

    def admin_restore(self, data, label):
        def do():
            self.auto_backup("tiklashdan oldin")
            merge_into(self.d, data)
            if self.store.save():
                toast("Turnir tiklandi")
            self.refresh_all()
        self.confirm_dialog(
            "Zaxiradan tiklash",
            "%s\n\nTiklanadi: %s.\n\nHozirgi ma'lumot (%s) fayldagisi bilan to'liq almashtiriladi "
            "va bazaga yoziladi. Tiklashdan oldin avtomatik zaxira yaratiladi."
            % (label, self.restore_counts(data), self.restore_counts(self.d)),
            do)

    def admin_backup_menu(self):
        if not self.require_admin():
            return
        files = self.backup_files()

        def create():
            if self.backup_now("qo'lab"):
                self.refresh_settings()

        def send():
            if not files:
                toast("Avval zaxira yarating")
                return
            share_file(os.path.join(self.backup_dir(), files[0]), "application/json",
                       "Zaxira faylni yuborish")

        def from_file():
            def got(path):
                data = self.backup_read(path)
                if data:
                    self.admin_restore(data, "Tanlangan fayl: " + os.path.basename(path))
            pick_media_file("application/json", "json", "APEX zaxirasi", got)

        def from_app(name):
            data = self.backup_read(os.path.join(self.backup_dir(), name))
            if data:
                self.admin_restore(data, "Qurilmadagi zaxira: " + name)

        opts = [("Zaxira yaratish (JSON fayl)", create),
                ("Zaxira faylni yuborish", send),
                ("Fayldan tiklash", from_file)]
        if files:
            opts.append(("Shu qurilmadagi zaxiralar (%d)" % len(files),
                         lambda: self.choose_dialog("Zaxiralar", [(f, f) for f in files],
                                                   from_app)))
        self.choose_dialog("Turnir zaxirasi", opts, lambda fn: fn())

    # ---------------- APEX TOKEN: admin qo'shadi / ayiradi ----------------
    def admin_tokens(self):
        if not self.require_admin():
            return
        opts = [(f"{p['name']}  ({p.get('tokens', TOKEN_START)} token)", p["id"])
                for p in self.d["players"]]

        def chosen(pid):
            def cb(txt):
                if not self.require_admin():
                    return
                try:
                    delta = int(txt)
                except ValueError:
                    toast("Son kiriting (masalan 100 yoki -50)")
                    return
                if delta == 0:
                    return
                self.add_tokens(pid, delta, "Admin tomonidan")
                if self.store.save():
                    toast(f"Balans: {self.player(pid)['tokens']}")
                self.refresh_all()
            self.input_dialog(f"{self.pname(pid)}: APEX TOKEN",
                              "Qo'shish uchun musbat, ayirish uchun manfiy son", cb,
                              text="100")
        self.choose_dialog("Qaysi o'yinchi?", opts, chosen)

    # ---------------- davomat jarimalari ----------------
    def admin_penalty(self):
        if not self.require_admin():
            return
        opts = [(self.match_label(m), m["id"]) for m in self.d["matches"]]
        if not opts:
            toast("Avval o'yinlar yaratilsin")
            return

        def got_match(mid):
            m = self.match(mid)
            if not m:
                return
            pids = set()
            for gid in (m["home"], m["away"]):
                pids |= set(m["lineups"].get(str(gid), [])) | set(self.team_appeared(m, gid))
            popts = [(self.pname(pid), pid) for pid in sorted(pids)]
            if not popts:
                toast("Bu o'yinda tarkib kiritilmagan")
                return

            def got_player(pid):
                def got_kind(code):
                    if not self.require_admin():
                        return
                    if self.apply_penalty(pid, mid, code):
                        if self.store.save():
                            toast("Jarima belgilandi")
                        self.refresh_all()
                self.choose_dialog("Jarima turi", [(n, c) for c, n, _ in PENALTIES], got_kind)
            self.choose_dialog("Qaysi o'yinchi?", popts, got_player)
        self.choose_dialog("Qaysi o'yin?", opts, got_match)

    # ---------------- hakamlar ----------------
    def admin_refs_menu(self):
        if not self.require_admin():
            return
        opts = [("Hakam qo'shish", self.admin_ref_add),
                ("Hakamni o'chirish", self.admin_ref_del)]
        self.choose_dialog("Hakamlar", opts, lambda fn: fn())

    def admin_ref_add(self):
        if not self.require_admin():
            return

        def cb(name):
            if not name or not self.require_admin():
                return
            if any(r["name"].lower() == name.lower() for r in self.d["refs"]):
                toast("Bunday hakam mavjud")
                return

            def cb2(pin):
                if not self.require_admin():
                    return
                if not self.valid_pin(pin):
                    toast("PIN kamida 4 raqam bo'lsin")
                    return
                rid = self.store.new_id()
                self.d["refs"].append({"id": rid, "name": name,
                                       "pin_hash": self.ref_hash(pin, rid)})
                if self.store.save():
                    toast("Hakam qo'shildi")
                self.refresh_all()
            self.input_dialog("Hakam PIN", "PIN (4+ raqam)", cb2, password=True, digits=True)
        self.input_dialog("Yangi hakam", "Ismi", cb)

    def admin_ref_del(self):
        if not self.require_admin():
            return
        opts = [(r["name"], r["id"]) for r in self.d["refs"]]

        def chosen(rid):
            self.d["refs"] = [r for r in self.d["refs"] if r["id"] != rid]
            if self.store.save():
                toast("Hakam o'chirildi")
            self.refresh_all()
        self.choose_dialog("Qaysi hakam?", opts, chosen)

    # ---------------- yordamchilar (admin assistant) ----------------
    def admin_assistants_menu(self):
        if not self.require_admin():
            return
        opts = [("Yordamchi yaratish", self.admin_assist_add),
                ("Yordamchini o'chirish", self.admin_assist_del)]
        self.choose_dialog("Yordamchilar", opts, lambda fn: fn())

    def admin_assist_add(self):
        """Admin o'ziga yordamchi hisob yaratadi: ism + email + parol.
        Yordamchi shu email/parol bilan APEX ADMIN ilovasiga kiradi va hammasini boshqara oladi."""
        if not self.require_admin():
            return

        def got_name(name):
            if not name or not self.require_admin():
                return

            def got_email(email):
                email = (email or "").strip().lower()
                if "@" not in email:
                    toast("To'g'ri email kiriting")
                    return

                def got_pw(pw):
                    if len(pw) < 6:
                        toast("Parol kamida 6 belgi bo'lsin")
                        return
                    self._assist_create_async(name, email, pw)
                self.input_dialog("Parol", "Kamida 6 belgi (yordamchiga berasiz)",
                                  got_pw, password=True)
            self.input_dialog("Yordamchi email", "email@example.com", got_email)
        self.input_dialog("Yordamchi ismi", "Ismi", got_name)

    def _assist_create_async(self, name, email, pw):
        toast("Hisob yaratilmoqda...")

        def work():
            try:
                uid = self.fb.create_email_user(email, pw)
            except CloudError as e:
                Clock.schedule_once(lambda dt: toast("Xato: " + e.human()))
                return
            if not uid:
                Clock.schedule_once(lambda dt: toast("Hisob yaratilmadi"))
                return

            def done(*a):
                if not self.require_admin():
                    return
                if any(x["id"] == uid for x in self.d["assistants"]):
                    toast("Bu hisob allaqachon bor")
                    return
                self.d["assistants"].append({"id": uid, "name": name, "email": email})
                if self.store.save():
                    toast("Yordamchi yaratildi. Endi u shu email/parol bilan Admin ilovasiga kirsin.")
                self.refresh_all()
            Clock.schedule_once(done, 0)
        threading.Thread(target=work, daemon=True).start()

    def admin_assist_del(self):
        if not self.require_admin():
            return
        opts = [(f"{a['name']}  ({a.get('email', '')})", a["id"]) for a in self.d["assistants"]]
        if not opts:
            toast("Yordamchi yo'q")
            return

        def chosen(uid):
            self.confirm_dialog(
                "Yordamchini o'chirish",
                "Huquq bekor qilinadi va Firebase Auth hisobi o'chiriladi. Davom?",
                lambda: self._assist_delete(uid))
        self.choose_dialog("Qaysi yordamchi?", opts, chosen)

    def _assist_delete(self, uid):
        if not self.require_admin():
            return
        self.d["assistants"] = [a for a in self.d["assistants"] if a["id"] != uid]
        self.store.save()
        self.refresh_all()

        def work():
            try:
                self.fb.delete_email_user(uid)
            except Exception:
                pass
            Clock.schedule_once(lambda dt: toast("Yordamchi o'chirildi"))
        threading.Thread(target=work, daemon=True).start()

    # ---------------- market boshqaruvi (admin) ----------------
    def admin_market_menu(self):
        if not self.require_admin():
            return
        opts = [("Narsa qo'shish", self.admin_market_add),
                ("Narsani o'chirish", self.admin_market_del)]
        self.choose_dialog("Market", opts, lambda fn: fn())

    def admin_market_add(self):
        if not self.require_admin():
            return

        def got_name(name):
            if not name or not self.require_admin():
                return

            def got_price(pt):
                try:
                    price = int(pt)
                except ValueError:
                    toast("Narxni son ko'rinishida kiriting")
                    return
                if price <= 0:
                    toast("Narx musbat bo'lsin")
                    return

                def got_qty(qt):
                    try:
                        qty = int(qt)
                    except ValueError:
                        toast("Sonini son ko'rinishida kiriting")
                        return
                    if qty <= 0:
                        toast("Son musbat bo'lsin")
                        return

                    def got_img(with_img):
                        def create(img):
                            self.d["market"].append({"id": self.store.new_id(), "name": name,
                                                     "desc": "", "price": price, "qty": qty,
                                                     "img": img})
                            if self.store.save():
                                toast("Marketga qo'shildi")
                            self.refresh_all()
                        if with_img:
                            def got(path):
                                try:
                                    create(image_to_b64(path, size=128))
                                except Exception:
                                    toast("Rasmni o'qib bo'lmadi")
                            pick_image_file(got)
                        else:
                            create(None)
                    self.choose_dialog("Rasm", [("Telefondan yuklash", True),
                                                ("Rasmsiz", False)], got_img)
                self.input_dialog("Necha dona?", "Son", got_qty, text="1", digits=True)
            self.input_dialog("Narx (APEX PRO TOKEN)", "Narx", got_price, digits=True)
        self.input_dialog("Narsa nomi", "Nomi", got_name)

    def admin_market_del(self):
        if not self.require_admin():
            return
        opts = [(f"{it['name']} ({it['price']} token, {it['qty']} ta)", it["id"])
                for it in self.d["market"]]

        def chosen(iid):
            self.d["market"] = [it for it in self.d["market"] if it["id"] != iid]
            if self.store.save():
                toast("O'chirildi")
            self.refresh_all()
        self.choose_dialog("Qaysi narsa?", opts, chosen)


class AdminApp(AdminMixin, LeagueApp):
    ADMIN_APP = True
    APP_TITLE = "Apex Admin"
    TOOLBAR_NAME = "Apex Admin"
    CACHE_NAME = "apex_admin_cache.json"

    def build_main(self):
        """Admin — main.py prototipi uslubidagi glass interfeys: gradient fon,
        maxsus Header, ichki ScreenManager va tag NavBar. Ma'lumot real Firebase'dan."""
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

        self.adm_header = G.Header(on_bell=lambda: self.show_notifs(),
                                   on_user=lambda: self.profile_dialog())
        ui.add_widget(self.adm_header)

        self._content_sm = ScreenManager()   # NoTransition: pastki FBO/stencil talab qilmaydi (arzon telefon GPU'lari uchun xavfsiz)
        self._content_sm.add_widget(self._build_dash_tab())
        self._content_sm.add_widget(self._build_matches_tab())
        self._content_sm.add_widget(self._build_players_tab())
        self._content_sm.add_widget(self._build_settings_tab())
        ui.add_widget(self._content_sm)

        self._nav = G.NavBar(on_go=lambda k: self.go_tab(k), tabs=(
            ("dash", "view-dashboard-outline", "Dashboard"),
            ("matches", "soccer", "O'yinlar"),
            ("players", "account-group-outline", "O'yinchilar"),
            ("settings", "cog-outline", "Sozlamalar")))
        ui.add_widget(self._nav)

        root.add_widget(ui)
        scr.add_widget(root)
        self._content_sm.current = "dash"
        self._nav.activate("dash")
        return scr

    # ---------------- tab chrome'lari (bir marta quriladi) ----------------
    def _build_dash_tab(self):
        s = Screen(name="dash")
        sv, box = G.scroll_page()
        self.b_dash = box
        s.add_widget(sv)
        return s

    def _build_settings_tab(self):
        s = Screen(name="settings")
        sv, box = G.scroll_page(pad=(dp(12), dp(4), dp(12), dp(12)))
        self.b_settings = box
        s.add_widget(sv)
        return s

    def _build_matches_tab(self):
        s = Screen(name="matches")
        root = G.BoxLayout(orientation="vertical", spacing=dp(10),
                           padding=(dp(12), 0, dp(12), 0))
        title = G.BoxLayout(size_hint_y=None, height=dp(40))
        title.add_widget(G.TL("O'yinlar", 28, bold=True))
        self._m_sub = G.TL("", 11, G.MUTED, align="right")
        title.add_widget(self._m_sub)
        root.add_widget(title)
        sv, self._m_list = G.scroll_page(pad=(0, 0, 0, dp(8)))
        self._m_chips = G.ChipBar(["Barchasi", "Guruh", "FINAL"], self._set_mfilter, chip_w=92)
        root.add_widget(self._m_chips)
        root.add_widget(sv)
        s.add_widget(root)
        return s

    def _build_players_tab(self):
        s = Screen(name="players")
        root = G.BoxLayout(orientation="vertical", spacing=dp(10),
                           padding=(dp(12), 0, dp(12), 0))
        title = G.BoxLayout(size_hint_y=None, height=dp(40))
        title.add_widget(G.TL("O'yinchilar", 28, bold=True))
        self._p_sub = G.TL("", 11, G.MUTED, align="right")
        title.add_widget(self._p_sub)
        root.add_widget(title)

        search = G.Glass(size_hint_y=None, height=dp(46), padding=(dp(14), 0), radius=16)
        mg = G.Icon("magnify", 20, G.MUTED)
        mg.pos_hint = {"center_y": .5}
        self.p_search = TextInput(hint_text="Ism yoki jamoa bo'yicha qidirish...",
                                  multiline=False, background_color=(0, 0, 0, 0),
                                  foreground_color=(1, 1, 1, 1), hint_text_color=G.MUTED,
                                  cursor_color=G.CYAN, padding=(dp(8), dp(14), 0, 0),
                                  font_size=dp(14))
        self.p_search.bind(text=lambda *_: self._players_list())
        search.add_widget(mg)
        search.add_widget(self.p_search)
        root.add_widget(search)

        sv, self._p_list = G.scroll_page(pad=(0, 0, 0, dp(8)))
        self._p_chips = G.ChipBar(["Barchasi", "GK", "DF", "MF", "FW"], self._set_ppos, chip_w=78)
        root.add_widget(self._p_chips)
        root.add_widget(sv)
        s.add_widget(root)
        return s

    def update_toolbar(self):
        h = getattr(self, "adm_header", None)
        if h is None:
            return
        on = "" if self.store.online else "  ·  OFLAYN"
        h.set_sub("So'rov: %d ta%s" % (len(self.free_players()), on))
        try:
            h.set_dot(bool(self.unread_notifs()))
        except Exception:
            pass

    def refresh_all(self):
        self.update_toolbar()
        for fn in (self.refresh_dash, self.refresh_matches,
                   self.refresh_players, self.refresh_settings):
            try:
                fn()
            except Exception as e:
                traceback.print_exc()
                toast("%s xato: %r" % (getattr(fn, "__name__", "?"), e))

    def build_extra_screens(self):
        self.sm.add_widget(LoginScreen(name="login", md_bg_color=NAVY))
        self.setup_screen = SetupScreen(name="setup", md_bg_color=NAVY)
        self.sm.add_widget(self.setup_screen)
        # boshlanishiga LINEUP_LOCK_MIN daqiqa qolganda qulfni bazaga ham yozadi
        Clock.schedule_interval(self.auto_lock_persist, 60)

    def first_screen(self):
        return "login"

    def route(self):
        if not self.fb.is_admin():
            self.sm.current = "login"
        elif self.d["setup_done"]:
            self.sm.current = "main"
            self.refresh_all()
        else:
            self.sm.current = "setup"


if __name__ == "__main__":
    AdminApp().run()
