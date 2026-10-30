# -*- coding: utf-8 -*-
"""Apex Admin - ADMIN ilovasi. Faqat admin (Firebase Auth) kira oladi va o'zgartira oladi."""
from common import *


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
        b.add_widget(Image(source=TROPHY, size_hint_y=None, height=dp(150)))
        b.add_widget(MDLabel(text="Apex Pro League", font_style="H4", halign="center",
                             theme_text_color="Custom", text_color=GOLD,
                             size_hint_y=None, height=dp(48)))
        b.add_widget(MDLabel(text="Apex Tournament: dastlabki sozlash", halign="center",
                             size_hint_y=None, height=dp(30)))
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
        self.name_fields, self.cap_fields, self.pin_fields, self.logos = [], [], [], []
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
            self.logos.append(i % LOGO_COUNT + 1)
            row = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
            prev = LogoButton(source=logo_path(self.logos[i]), size_hint_x=None, width=dp(48))
            row.add_widget(prev)
            row.add_widget(MDRaisedButton(
                text="Guruh logosini tanlash",
                on_release=lambda *a, i=i, prev=prev: self.pick_logo(i, prev)))
            inner.add_widget(row)
        sv.add_widget(inner)
        b.add_widget(sv)
        b.add_widget(MDRaisedButton(text="Saqlash va boshlash", on_release=self.finish))

    def pick_logo(self, i, prev):
        def chosen(n):
            self.logos[i] = n
            prev.source = logo_path(n)
        self.app.logo_picker(chosen)

    def finish(self, *a):
        self.app.finish_setup([f.text.strip() for f in self.name_fields],
                              [f.text.strip() for f in self.cap_fields],
                              [f.text.strip() for f in self.pin_fields],
                              list(self.logos))


class LoginScreen(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        box = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(14))
        box.add_widget(Image(source=TROPHY, size_hint_y=None, height=dp(150)))
        box.add_widget(MDLabel(text="Apex Admin", font_style="H4", halign="center",
                               theme_text_color="Custom", text_color=GOLD,
                               size_hint_y=None, height=dp(48)))
        box.add_widget(MDLabel(text=f"Hisob: {config.ADMIN_EMAIL}", halign="center",
                               font_style="Caption", size_hint_y=None, height=dp(24)))
        self.pw = MDTextField(hint_text="Admin paroli", password=True)
        box.add_widget(self.pw)
        box.add_widget(MDRaisedButton(text="Kirish", on_release=self.go))
        box.add_widget(Widget())
        self.add_widget(box)

    def go(self, *a):
        password = self.pw.text
        self.pw.text = ""
        MDApp.get_running_app().do_login(password)


class AdminMixin:
    """Admin funksiyalari. Har bir o'zgartirish Firebase qoidalari orqali ham tekshiriladi."""

    # ---------------- kirish / chiqish ----------------
    def require_admin(self):
        if not self.fb.is_admin():
            toast("Admin sifatida kiring")
            self.sm.current = "login"
            return False
        return True

    def do_login(self, password):
        if not self.config_ok():
            toast("config.py to'ldirilmagan")
            return
        if not password:
            toast("Parolni kiriting")
            return
        try:
            self.fb.sign_in(config.ADMIN_EMAIL, password)
            self.store.pull(force=True)
        except CloudError as e:
            self.fb.sign_out()
            toast(e.human())
            return
        self.route()

    def logout(self):
        self.fb.sign_out()
        self.sm.current = "login"

    # ---------------- boshlang'ich sozlash ----------------
    def finish_setup(self, names, caps, pins, logos):
        if not self.require_admin():
            return
        if any(not n for n in names) or any(not c for c in caps):
            toast("Barcha guruh va kapitan nomlarini to'ldiring")
            return
        if len({c.lower() for c in caps}) != len(caps):
            toast("Kapitan ismlari takrorlanmasin")
            return
        if any(not self.valid_pin(p) for p in pins):
            toast("Har bir kapitan PIN kodi kamida 4 raqam bo'lsin")
            return
        d = self.d
        d["groups"].clear()
        d["players"].clear()
        d["matches"].clear()
        for n, c, pin, logo in zip(names, caps, pins, logos):
            gid, pid = self.store.new_id(), self.store.new_id()
            d["players"].append({"id": pid, "name": c, "group": gid, "number": DEFAULT_NUMBER,
                                 "pos": DEFAULT_POS, "country": DEFAULT_COUNTRY})
            d["groups"].append({"id": gid, "name": n, "captain_id": pid, "logo": logo,
                                "pin_hash": self.pin_hash(pin, gid)})
        d["turn"] = 0
        d["is_draft_open"] = True
        d["setup_done"] = True
        self.store.snapshot["meta"].pop("turn", None)   # turn bazaga albatta yozilsin
        if not self.store.save():
            return
        self.route()
        toast("Sozlash yakunlandi. O'yinchilar endi ro'yxatdan o'ta oladi.")

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
                p = {"id": self.store.new_id(), "name": name, "group": None}
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

            def cb2(cap, logo):
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
                    self.d["players"].append({"id": pid, "name": cap, "group": gid,
                                              "number": DEFAULT_NUMBER, "pos": DEFAULT_POS,
                                              "country": DEFAULT_COUNTRY})
                    self.d["groups"].append({"id": gid, "name": name, "captain_id": pid,
                                             "logo": logo, "pin_hash": self.pin_hash(pin, gid)})
                    self.store.save()
                    self.refresh_all()
                self.input_dialog("Kapitan PIN", "PIN (4+ raqam)", cb3, password=True, digits=True)
            self.logo_picker(lambda logo: self.input_dialog(
                "Kapitan ismi", "Kapitan", lambda cap: cb2(cap, logo)))
        self.input_dialog("Yangi guruh nomi", "Nomi", cb)

    def admin_set_logo(self):
        opts = [(g["name"], g["id"]) for g in self.d["groups"]]

        def chosen(gid):
            def got(n):
                if self.require_admin():
                    self.group(gid)["logo"] = n
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
