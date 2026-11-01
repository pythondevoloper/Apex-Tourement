# -*- coding: utf-8 -*-
"""Apex Admin - ADMIN ilovasi. Faqat admin (Firebase Auth) kira oladi va o'zgartira oladi."""
from common import *


class SetupScreen(MDScreen):
    """Turnirni boshlash. Guruhlar soni so'ralmaydi: guruhlar keyin, Admin paneldan qo'shiladi."""

    def __init__(self, **kw):
        super().__init__(**kw)
        body = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(14))
        body.add_widget(Widget())
        body.add_widget(Image(source=TROPHY, size_hint_y=None, height=dp(150)))
        body.add_widget(MDLabel(text="Apex Pro League", font_style="H4", halign="center",
                                theme_text_color="Custom", text_color=GOLD,
                                size_hint_y=None, height=dp(48)))
        body.add_widget(MDLabel(
            text="Turnirni boshlaganingizdan so'ng o'yinchilar ro'yxatdan o'ta oladi.\n"
                 "Guruhlar (jamoa) soni cheklanmagan: ularni Admin paneldan istalgan payt "
                 "qo'shasiz, kapitanlar ro'yxatdan o'tgan o'yinchilar orasidan tanlanadi.",
            halign="center", font_style="Caption", theme_text_color="Secondary",
            size_hint_y=None, height=dp(90)))
        body.add_widget(MDRaisedButton(text="Turnirni boshlash", size_hint_x=1,
                                       on_release=lambda *a: MDApp.get_running_app().start_tournament()))
        body.add_widget(Widget())
        self.add_widget(body)


class LoginScreen(MDScreen):
    """Admin kirishi: email + parol. Kirgandan keyin turnir sozlanmagan bo'lsa, sozlash ochiladi."""

    def __init__(self, **kw):
        super().__init__(**kw)
        sv = ScrollView()
        box = MDBoxLayout(orientation="vertical", adaptive_height=True, padding=dp(24),
                          spacing=dp(12))
        box.add_widget(Image(source=TROPHY, size_hint_y=None, height=dp(140)))
        box.add_widget(MDLabel(text="Apex Admin", font_style="H4", halign="center",
                               theme_text_color="Custom", text_color=GOLD,
                               size_hint_y=None, height=dp(48)))
        box.add_widget(MDLabel(text="Administrator hisobi bilan kiring", halign="center",
                               font_style="Caption", theme_text_color="Secondary",
                               size_hint_y=None, height=dp(24)))
        card = adaptive_card(orientation="vertical", radius=[16], md_bg_color=CARD,
                             padding=dp(14), spacing=dp(6))
        self.email = MDTextField(hint_text="Email", text=config.ADMIN_EMAIL, icon_left="email-outline")
        self.pw = MDTextField(hint_text="Parol", password=True, icon_left="lock-outline")
        card.add_widget(self.email)
        card.add_widget(self.pw)
        self.btn = MDRaisedButton(text="Kirish", size_hint_x=1, on_release=self.go)
        card.add_widget(Widget(size_hint_y=None, height=dp(6)))
        card.add_widget(self.btn)
        box.add_widget(card)
        box.add_widget(MDLabel(
            text="Hisob Firebase Authentication da yaratilgan bo'ladi (README 1-qadam).",
            halign="center", font_style="Caption", theme_text_color="Secondary",
            size_hint_y=None, height=dp(44)))
        sv.add_widget(box)
        self.add_widget(sv)

    def busy(self, flag):
        self.btn.disabled = flag
        self.btn.text = "Kirilmoqda..." if flag else "Kirish"

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
        self.d["is_draft_open"] = True
        self.d["turn"] = 0
        self.store.snapshot["meta"].pop("turn", None)   # turn bazaga albatta yozilsin
        if not self.store.save():
            return
        self.route()
        toast("Turnir boshlandi. O'yinchilar ro'yxatdan o'tadi, guruhlar keyin qo'shiladi.")

    # ---------------- Admin oynasi ----------------
    def refresh_admin(self):
        box = self.b_admin
        box.clear_widgets()
        box.add_widget(self.note(
            f"Kirgan hisob: {self.fb.email or '-'}. Barcha o'zgarishlar darhol hamma telefonlarda ko'rinadi.", 44))
        row = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
        row.add_widget(MDLabel(text="Draft ochiq / yopiq"))
        sw = MDSwitch(active=self.d["is_draft_open"], pos_hint={"center_y": 0.5})
        sw.bind(active=self.on_toggle_draft)
        row.add_widget(sw)
        box.add_widget(row)

        def btn(text, cb):
            box.add_widget(MDRaisedButton(text=text, on_release=lambda *a: cb(), size_hint_x=1))
        btn("O'yinchi qo'shish", self.admin_add_player)
        btn("O'yinchi ma'lumotlarini tahrirlash (raqam, pozitsiya, davlat, OVR)", self.admin_edit_player)
        btn("O'yinchiga APEX TOKEN qo'shish / ayirish", self.admin_tokens)
        btn("Davomat jarimalari (kech qolish / kelmaslik)", self.admin_penalty)
        btn("O'yinchini o'chirish", self.admin_remove_player)
        btn("O'yinchini guruhga ko'chirish", self.admin_move_player)
        btn("Guruhlar va kapitanlarni boshqarish", self.admin_groups_menu)
        btn("O'yinlar jadvalini yaratish", self.admin_make_fixtures)
        btn("FINAL o'yinini yaratish", self.admin_make_final)
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
        btn("Hakamlar boshqaruvi", self.admin_refs_menu)
        btn("Market: narsa qo'shish / o'chirish", self.admin_market_menu)
        btn("Draftni noldan boshlash", self.admin_reset_draft)
        btn("Admin parolini o'zgartirish", self.admin_change_pw)
        btn("Chiqish", self.logout)

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

    def on_toggle_draft(self, sw, value):
        if not self.require_admin():
            return
        self.d["is_draft_open"] = bool(value)
        self.store.save()
        toast("Draft ochildi" if value else "Draft yopildi (Locked)")
        self.refresh_all()

    def admin_add_player(self):
        if not self.require_admin():
            return

        def cb(name):
            if not name:
                return
            if self.name_exists(name):
                toast("Bunday ism mavjud")
                return
            def create(info):
                if not self.require_admin():
                    return
                p = {"id": self.store.new_id(), "name": name, "group": None,
                     "tokens": TOKEN_START, "token_zero_since": None}
                p.update(info)
                self.d["players"].append(p)
                if self.store.save():
                    toast("Qo'shildi")
                self.refresh_all()
            self.collect_player_info(create)
        self.input_dialog("Yangi o'yinchi", "Ismi", cb)

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

    def admin_groups_menu(self):
        if not self.require_admin():
            return
        opts = [("Guruh qo'shish", self.admin_add_group),
                ("Guruh nomini o'zgartirish", self.admin_rename_group),
                ("Guruh logosini o'zgartirish", self.admin_set_logo),
                ("Kapitanni almashtirish", self.admin_change_captain),
                ("Guruhni o'chirish", self.admin_delete_group)]
        self.choose_dialog("Guruhlar", opts, lambda fn: fn())

    def admin_add_group(self):
        def cb(name):
            if not name or not self.require_admin():
                return

            def cb2(logo):
                def cb3(pid):
                    def cb4(pin):
                        if not self.require_admin():
                            return
                        if not self.valid_pin(pin):
                            toast("PIN kamida 4 raqam bo'lsin")
                            return
                        gid = self.store.new_id()
                        if pid is None:
                            pid = self.store.new_id()
                            self.d["players"].append(
                                {"id": pid, "name": name + " kapitani", "group": gid,
                                 "number": DEFAULT_NUMBER, "pos": DEFAULT_POS,
                                 "country": DEFAULT_COUNTRY, "tokens": TOKEN_START,
                                 "token_zero_since": None})
                        else:
                            self.player(pid)["group"] = gid
                        g = {"id": gid, "name": name, "captain_id": pid,
                             "pin_hash": self.pin_hash(pin, gid), "ptokens": 0}
                        self.apply_logo(g, logo)
                        self.d["groups"].append(g)
                        self.store.save()
                        self.refresh_all()
                        toast("Guruh qo'shildi")
                    if pid is not None and self.is_captain(pid):
                        toast("Bu o'yinchi allaqachon kapitan")
                        return
                    self.input_dialog("Kapitan PIN", "PIN (4+ raqam)", cb4,
                                      password=True, digits=True)
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
                def cb(t):
                    if not (t.isdigit() and 1 <= int(t) <= 99):
                        toast("Raqam 1 dan 99 gacha bo'lsin")
                        return
                    p["number"] = int(t)
                    done()
                self.input_dialog("Futbolka raqami", "1-99", cb,
                                  text=str(p.get("number") or ""), digits=True)

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
                def cb2(pin):
                    if not self.require_admin():
                        return
                    if not self.valid_pin(pin):
                        toast("PIN kamida 4 raqam bo'lsin")
                        return
                    p = self.player(pid)
                    if not p:
                        return
                    p["group"] = gid
                    g = self.group(gid)
                    g["captain_id"] = pid
                    g["pin_hash"] = self.pin_hash(pin, gid)
                    self.store.save()
                    self.refresh_all()
                    toast("Kapitan almashtirildi")
                self.input_dialog("Yangi kapitan PIN", "PIN (4+ raqam)", cb2,
                                  password=True, digits=True)
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
                self.award_final(m)
                self.close_dialog()
                self.store.save()
                self.refresh_all()
            self.show_dialog("Natija", content=content, buttons=[
                MDFlatButton(text="Bekor", on_release=self.close_dialog),
                MDRaisedButton(text="Saqlash", on_release=save)])
        self.choose_dialog("Qaysi o'yin?", opts, chosen)

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
                    m["cards"].append({"pid": pid, "type": t})
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

    def build_extra_screens(self):
        self.sm.add_widget(LoginScreen(name="login", md_bg_color=NAVY))
        self.setup_screen = SetupScreen(name="setup", md_bg_color=NAVY)
        self.sm.add_widget(self.setup_screen)

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
