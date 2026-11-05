# -*- coding: utf-8 -*-
"""Ish stolidagi render-tekshiruv: to'rtala ilovaning tab'lari soxta ma'lumot bilan
quriladi va traceback bo'lmasa bo'ldi (vizual tekst emas, qurilish tekshiruv).

Ishga tushirish (apex/ papkasidan):
    python scripts/render_check.py [player|referee|captain|admin]
"""
import os
import sys
import copy
import json
import time
import tempfile
import traceback
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gemini
from common import OneLineListItem, LeagueApp      # glass dialog qatori + kapitan hash'i
from kivy.app import App
from kivy.clock import Clock

G1, G2 = 1, 2
CAP_PW = "kapiton123"          # soxta ma'lumotdagi kapitan paroli (faqat sinov uchun)


def player(pid, name, num, gid, pos, base=62):
    """Soxta o'yinchi. `base` boshlang'ich OVR — kartaning daraja rangi
    (bronza/kumush/oltin/ikonik) shunga qarab turli bo'lsin uchun turlicha."""
    a = dict(gemini.DEFAULT_ATTRS)
    for i, k in enumerate(a):
        a[k] = max(45, min(99, base - 10 + (pid * 7 + i * 11) % 13))
    return {"id": pid, "name": name, "first": name.split()[0], "last": name.split()[-1],
            "number": num, "group": gid, "pos": pos, "country": "O'zbekiston",
            "tokens": 300, "token_zero_since": None,
            "attrs": a, "base_ovr": base, "ovr": base,
            "photo_b64": None, "card_b64": None, "tstatus": None,
            "thist": [{"ts": 1730000000 - 86400, "delta": -100, "reason": "O'yinga kech qolish",
                       "bal": 200},
                      {"ts": 1730000000, "delta": 50, "reason": "G'alaba bonusi", "bal": 250}]}


def fake_data():
    def grp(gid, name, cap, ptok, logo, login):
        return {"id": gid, "name": name, "captain_id": cap, "ptokens": ptok, "logo": logo,
                "logo_img": None, "cap_login": login,
                "cap_pass_hash": LeagueApp.cap_hash(CAP_PW, gid)}
    return {
        "setup_done": True, "is_draft_open": False, "turn": 1,
        "groups": [grp(G1, "Guruh A", 101, 250, 1, "guruh-a-1"),
                   grp(G2, "Guruh B", 201, 150, 2, "guruh-b-2")],
        "players": [player(101, "Ali Valiyev", 10, G1, "FW", 88),
                    player(102, "Bekzot Karimov", 5, G1, "DF", 76),
                    player(103, "Sardor Tursunov", 1, G1, "GK", 66),
                    player(201, "Javohir Eshonqulov", 9, G2, "MF", 71),
                    player(202, "Otabek Rustamov", 7, G2, "FW", 84),
                    player(301, "No Group Player", 11, None, "MF", 58),
                    # so'rov (guruhsiz) havuzasi: kvota bo'lishi shu ro'yxatda tekshiriladi
                    player(401, "Rustam Choriyev", 12, None, "GK", 70),
                    player(402, "Dilnoza Qurbonova", 13, None, "DF", 74),
                    player(403, "Shoxrux Barotov", 14, None, "DF", 69),
                    player(404, "Aziz Nasarov", 15, None, "DF", 80),
                    player(405, "Malik Yo'ldoshev", 16, None, "FW", 79),
                    player(406, "Nodira Ismoilova", 17, None, "FW", 65),
                    player(407, "Bekzod Alimov", 18, None, "MF", 73)],
        "matches": [{"id": 1, "home": G1, "away": G2, "hs": 2, "as": 1, "round": 1,
                     "stage": "group", "date": 1730000000, "kick": 1730000000,
                     "lineup_locked": True,
                     "lineups": {str(G1): [101, 102, 103], str(G2): [201, 202]},
                     "subs": [{"team": G1, "out": 103, "in": 102, "ts": 1730001000}],
                     "goals": [{"team": G1, "scorer": 101, "assist": 201, "ts": 1730000500}],
                     "cards": [{"pid": 202, "type": "yellow", "ts": 1730000800}]},
                    {"id": 2, "home": G2, "away": G1, "hs": None, "as": None, "round": 2,
                     "stage": "final", "date": 1730100000, "lineup_locked": False,
                     "kick": int(time.time()) + 30 * 60,
                     "lineups": {}, "subs": [], "goals": [], "cards": []}],
        "notifs": [{"id": 1, "to": "all", "text": "Sinov xabarnomasi",
                    "ts": 1730000000, "read": {}}],
        "transfers": [{"id": 5, "pid": 202, "status": "offer", "amount": 40,
                       "seller_gid": G2, "buyer_gid": G1, "side": "buyer",
                       "ts": 1730000000}],
        "market": [{"id": 1, "name": "Uy formasi", "desc": "Rasmiy forma",
                    "price": 120, "qty": 4, "img": None},
                   {"id": 2, "name": "Pro butslar", "desc": "", "price": 200,
                    "qty": 0, "img": None}],
        "refs": [{"id": 9, "name": "Hakam", "pin_hash": None}],
        "assistants": [],
    }


TABS = {"player": ("groups", "lineup", "table", "market"),
        "referee": ("groups", "lineup", "table"),
        "captain": ("lineup", "groups", "transfer", "market"),
        "admin": ("dash", "matches", "players", "settings")}


# Dialoglarni ochadigan usullar (har bir ilova uchun). Maqsad: glass dialog
# qatlimi real ma'lumot bilan quriladi, xatosiz va o'lchamli bo'ladimi.
# Har bir yozuv: (usul_ismi, app -> argumentlar, [nom: surat fayli uchun]).
DIALOGS = {
    # Player ilovasida kapitan amallari qolmadi — ular faqat "captain" ro'yxatida.
    "player": [("profile_dialog", lambda a: ()), ("show_notifs", lambda a: ()),
               ("search_dialog", lambda a: ()), ("market_dialog", lambda a: ()),
               ("player_card", lambda a: (101,), "card_88"),
               ("player_card", lambda a: (102,), "card_76"),
               ("player_card", lambda a: (103,), "card_66"),
               ("player_card", lambda a: (301,), "card_58"),
               ("token_history", lambda a: (101,)), ("share_table_image", lambda a: ()),
               ("_number_check", lambda a: ()), ("_h2h_check", lambda a: ())],
    "referee": [("show_notifs", lambda a: ()), ("player_card", lambda a: (101,)),
                ("lineup_dialog", lambda a: (G1, 1)), ("match_journal", lambda a: (a.match(1),)),
                ("clock_dialog", lambda a: ()), ("share_table_image", lambda a: ()),
                ("_clock_check", lambda a: ()), ("_number_check", lambda a: ()),
                ("_h2h_check", lambda a: ())],
    "captain": [("profile_dialog", lambda a: ()), ("show_notifs", lambda a: ()),
                ("lineup_dialog", lambda a: (G1, 1)), ("captain_transfers", lambda a: ()),
                ("negotiate_dialog", lambda a: (5,)), ("offer_dialog", lambda a: (202,)),
                ("market_dialog", lambda a: ()), ("player_card", lambda a: (101,), "card_88"),
                ("_cap_login_check", lambda a: ()), ("_lock_check", lambda a: ()),
                ("_number_check", lambda a: ())],
    "admin": [("admin_groups_menu", lambda a: ()), ("admin_goal_menu", lambda a: ()),
              ("admin_card_menu", lambda a: ()), ("admin_refs_menu", lambda a: ()),
              ("admin_market_menu", lambda a: ()), ("admin_enter_result", lambda a: ()),
              ("admin_wipe_all", lambda a: ()), ("admin_cap_logins", lambda a: ()),
              ("admin_remove_player", lambda a: ()),
              ("admin_lineup_manage", lambda a: ()), ("admin_backup_menu", lambda a: ()),
              ("shape_gap_dialog", lambda a: ()),
              ("_number_check", lambda a: ()), ("_split_check", lambda a: ()),
              ("_png_check", lambda a: ()),
              ("_lock_check", lambda a: ()), ("_h2h_check", lambda a: ()),
              ("_backup_check", lambda a: ()), ("_clock_check", lambda a: ()),
              # oxirida: bu ikkisi guruh/o'yinlarni o'chirib tashlaydi
              ("_remove_check", lambda a: ())],
}

# Umumiy dialog funnel'i (uchala ilovada ham bor)
GENERIC = [("confirm_dialog", lambda a: ("Sarlavha", "Matn\nikki qator", lambda: None)),
           ("input_dialog", lambda a: ("Sarlavha", "Maydon", lambda v: None)),
           ("choose_dialog", lambda a: ("Sarlavha", [("Bir", 1), ("Ikki", 2)], lambda v: None)),
           ("show_dialog", lambda a: ("Faqat ro'yxat", None,
                                      [OneLineListItem(text="qator %d" % i,
                                                       secondary_text="izoh " * 20)
                                       for i in range(30)])),
           ("_show_crash", lambda a: ("traceback namunasi\n" * 40,))]


def check_dialogs(app, kind, errors, done):
    """Dialoglarni bittadan ochadi, o'lchamini tekshiradi va yopadi.

    Har qadam keyingi kadrda: Kivy o'lchamlari shundan keyin aniq bo'ladi.
    """
    import glassui as G
    from kivy.metrics import dp
    from kivy.core.window import Window

    shots = os.environ.get("APEX_SHOTS")       # berilsa: har dialog png'iga tushadi
    if shots:
        os.makedirs(shots, exist_ok=True)

    if kind == "admin":
        app.require_admin = lambda: True      # parol so'ramasdan menyu dialoglarini ochish
    plan = list(GENERIC) + DIALOGS[kind]

    def open_one(name, args, label=None):
        """Ochiq dialogni qaytaradi (tashqarida yopish va keyingi qadam kechiktirilsin)."""
        label = label or name
        fn = getattr(app, name, None)
        if fn is None:
            errors.append("dialog yo'q: %s" % name)
            return None
        try:
            fn(*args)
        except Exception as e:
            errors.append("dialog %s: %r" % (label, e))
            traceback.print_exc()
            return None
        d = getattr(app, "dialog", None)
        if d is None:
            print("  [%s] dialog %-20s (ochilmadi - ruxsat/ma'lumot yo'q)" % (kind, label))
            return None
        if not isinstance(d, G.Dialog):
            errors.append("dialog %s glass emas: %s" % (label, type(d).__name__))
            return None
        if d.card.height < dp(100) or not d.card.children:
            errors.append("dialog %s bo'sh: h=%s" % (label, d.card.height))
        print("  [%s] dialog %-20s card=%dx%d qatorlar=%s" %
              (kind, label, int(d.card.width), int(d.card.height), len(d.card.children)))
        return d

    def step(i):
        if i >= len(plan):
            done()
            return
        entry = plan[i]
        name, make_args = entry[0], entry[1]
        if name in SENTINELS:
            # dialog emas: o'zi tekshiruv bo'lib, tashqarida qurilishni buzmasligi kerak
            try:
                SENTINELS[name](app, errors)
            except Exception as e:
                errors.append("sentinel %s: %r" % (name, e))
                traceback.print_exc()
            check_screens(kind, errors)
            Clock.schedule_once(lambda *a: step(i + 1), 0.12)
            return
        label = entry[2] if len(entry) > 2 else name
        d = open_one(name, make_args(app), label)
        if d is not None and shots:
            # Dialog bir necha kadrdan keyin to'liq joylashadi. Window.screenshot
            # framebuffer'dan oladi va siljiigan (shear) surat beradi, shuning uchun
            # vidjetning o'zini FBO orqali rasmga tushiramiz.
            png = os.path.join(shots, "%s_%s.png" % (kind, label))
            Clock.schedule_once(lambda *a: d.export_to_png(png), 0.3)
            Clock.schedule_once(lambda *a: app.close_dialog(), 0.6)
            Clock.schedule_once(lambda *a: step(i + 1), 0.9)
            print("      shot -> %s" % png)
            return
        if d is not None:
            try:
                app.close_dialog()
            except Exception as e:
                errors.append("close_dialog %s: %r" % (label, e))
        Clock.schedule_once(lambda *a: step(i + 1), 0.12)

    step(0)


def check_split(app, errors):
    """Kvota bo'lishi: avval har jamoaning asosiy 6 tasi, so'ng ortiqchalar teng son qilib."""
    from common import POS_QUOTA
    jobs, real = [], app.confirm_dialog
    app.confirm_dialog = lambda title, msg, cb, *a, **k: jobs.append(cb)
    try:
        app.admin_random_split()
    finally:
        app.confirm_dialog = real
    if not jobs:
        errors.append("kvota bo'lishi: tasdiq dialog ochilmadi")
        return
    jobs[0]()
    if app.free_players():
        errors.append("kvota bo'lishi: %d o'yinchi guruhsiz qoldi" % len(app.free_players()))
    if app.shape_gaps():
        errors.append("asosiy 6: %d jamoda shakl to'lmadi (%s)"
                      % (len(app.shape_gaps()), [(app.gname(g), m) for g, m in app.shape_gaps()]))
    sizes = [len(app.members(g["id"])) for g in app.d["groups"]]
    if max(sizes) - min(sizes) > 1:
        errors.append("teng son: jamoalar soni farqi %s (1 dan ko'p bo'lmasligi kerak)" % sizes)
    for g in app.d["groups"]:
        c = app.pos_counts([p["id"] for p in app.members(g["id"])])
        print("  [admin] asosiy 6 %-8s %s jami=%d" %
              (g["name"], " ".join("%s%d" % (k, c.get(k, 0)) for k in POS_QUOTA),
               len(app.members(g["id"]))))
    # asosiy 6 to'lmagan jamo ham aniqlanadi va ogohlantirish oynasi quriladi
    gap_snap = _snap(app)
    real_show = app.show_dialog
    try:
        gk = next(p for p in app.members(G1) if (p.get("pos") or "").upper() == "GK")
        gk["pos"] = "MF"
        gaps = app.shape_gaps()
        if not any(g == G1 and "GK" in m for g, m in gaps):
            errors.append("asosiy 6: darvozabonsiz jamo topilmadi (%s)" % gaps)
        # MF va FW bir-birini bosadi: ularning yig'indisi 3 dan kam bo'lsa "FX" chiqadi
        if any(g == G1 and "FX" in m for g, m in gaps):
            errors.append("asosiy 6: MF/FW almashinuvi hisobga olinmadi (%s)" % gaps)
        shown = []
        app.show_dialog = lambda title, *a, **k: shown.append(title)
        app.shape_gap_dialog()
        if not shown or "Asosiy 6" not in shown[0]:
            errors.append("asosiy 6: ogohlantirish oynasi ochilmadi (%s)" % shown)
        print("  [admin] asosiy 6 yetishmovchiligi: %s, oyna=%s" %
              (gaps[0][1] if gaps else {}, shown and shown[0]))
    finally:
        app.show_dialog = real_show
        _restore(app, gap_snap)


def check_cap_login(app, errors):
    """Kapitan kirishi: parol tekshiruvi, login normallashtirish va urinishlar bloki."""
    if app.captain_login("guruh-a-1", CAP_PW) != G1:
        errors.append("kapitan login: to'g'ri parol guruhni topmadi")
    if app.captain_login("  GURUH-A-1 ", CAP_PW) != G1:
        errors.append("kapitan login: kattalik/oraliq belgi qabul qilinmadi")
    if app.captain_login("guruh-a-1", "notogri") is not None:
        errors.append("kapitan login: xato parol o'tdi")
    if app.captain_login("yoq-bunday", CAP_PW) is not None:
        errors.append("kapitan login: noma'lum login o'tdi")
    if app.login_taken("guruh-b-2", ignore_gid=G1) is not True:
        errors.append("kapitan login: band login aniqlanmadi")
    if app.login_taken("guruh-a-1", ignore_gid=G1):
        errors.append("kapitan login: o'z logini 'band' deb chiqdi")
    app.cap_reset_fails()
    for _ in range(app.CAP_MAX_FAILS):
        app.cap_fail()
    if not app.cap_wait():
        errors.append("kapitan login: %d xatodan keyin bloklanmadi" % app.CAP_MAX_FAILS)
    app.cap_reset_fails()
    if app.cap_wait():
        errors.append("kapitan login: blokdan keyin tozalanmadi")
    print("  [captain] login tekshiruvi: OK (%d urinish/%d s blok)" %
          (app.CAP_MAX_FAILS, app.CAP_LOCK_SECONDS))


def check_remove(app, errors):
    """D-1: o'yinchini o'chirish baza bo'ylab barcha izlarini tozalaydi."""
    pid = 202
    # me.json ga tegilmasin: o'chirilgan o'yinchi bizning sessiyamiz emas
    app.load_me = lambda: {"pid": 101}
    app._save_me = lambda me: None
    app._remove_player(pid)
    if app.player(pid):
        errors.append("o'chirish: o'yinchi qolib ketdi")
    for m in app.d["matches"]:
        if any(pid in ids for ids in m["lineups"].values()):
            errors.append("o'chirish: %s tarkibida qoldi" % m["id"])
        if any(c["pid"] == pid for c in m["cards"]):
            errors.append("o'chirish: %s kartochkasida qoldi" % m["id"])
        if any(pid in (s["in"], s["out"]) for s in m["subs"]):
            errors.append("o'chirish: %s almashinuvida qoldi" % m["id"])
    if any(t["pid"] == pid for t in app.d["transfers"]):
        errors.append("o'chirish: transferi qolib ketdi")
    if any(n["to"] == "p%d" % pid for n in app.d["notifs"]):
        errors.append("o'chirish: xabarnomalari qolib ketdi")
    if app.player_refs(pid):
        errors.append("o'chirish: player_refs hali iz topmoqda")
    if not app.is_captain(101):
        errors.append("o'chirish: 101 kapitanligi buzildi")
    print("  [admin] o'chirish kaskadi: qoldiq iz yo'q, hisob %s:%s" %
          (app.match(1)["hs"], app.match(1)["as"]))
    check_cap_group_remove(app, errors)


def check_cap_group_remove(app, errors):
    """Kapitanni o'chirish — guruh, o'yinlari va izlari birga ketadi."""
    g3 = {"id": 3, "name": "Guruh C", "captain_id": 301, "ptokens": 50, "logo": 3,
          "logo_img": None, "cap_login": "guruh-c-3",
          "cap_pass_hash": app.cap_hash("parol12", 3)}
    app.d["groups"].append(g3)
    app.player(301)["group"] = 3
    app.d["matches"].append({"id": 99, "home": 3, "away": G1, "hs": 1, "as": 0, "round": 3,
                             "stage": "group", "date": 1730200000, "lineup_locked": True,
                             "lineups": {"3": [301], "1": [101]}, "subs": [],
                             "goals": [], "cards": []})
    txt = app.cap_delete_text(301, g3)
    if "Guruh C" not in txt or "kapitan" not in txt:
        errors.append("kapitan o'chirish: ogohlantirish matni noto'g'ri")
    app._delete_captain_with_group(301)
    if app.group(3):
        errors.append("kapitan o'chirish: guruh qoldi")
    if app.player(301):
        errors.append("kapitan o'chirish: o'yinchi qoldi")
    if app.match(99):
        errors.append("kapitan o'chirish: guruhning o'yini qoldi")
    if not app.match(1):
        errors.append("kapitan o'chirish: begona o'yin ham o'chdi")
    if len(app.d["groups"]) != 2:
        errors.append("kapitan o'chirish: guruh soni %d bo'ldi" % len(app.d["groups"]))
    # guruh soni endi cheklanmagan: keyingi kapitan ham guruh bilan ketadi
    app._delete_captain_with_group(201)
    if app.group(G2) or app.player(201):
        errors.append("kapitan o'chirish: guruh soni to'shib qo'ydi")
    if app.match(1) or app.match(2):
        errors.append("kapitan o'chirish: o'sha guruhning o'yini qoldi")
    if len(app.d["groups"]) != 1:
        errors.append("kapitan o'chirish: guruhlar soni %d bo'ldi" % len(app.d["groups"]))
    print("  [admin] kapitan+guruh o'chirish: guruh/o'yin/izlar ketdi, 1 guruh qoldi")


# ---------------- yangi funksiyalar uchun o'z-tekshiruvlar ----------------
def _snap(app):
    return copy.deepcopy(app.d)


def _restore(app, snap):
    # nusxa bilan qaytaradi: aks holda app.d snap ichidagi obyektlarga alias bo'lib,
    # keyingi o'zgarishlar snap ni buzadi (ikki marta restore qilish imkonsiz bo'lardi)
    app.d.clear()
    app.d.update(copy.deepcopy(snap))


def _need_match(app, mid):
    """Oldingi tekshiruvlar (o'chirish kaskadi) o'yinni olib tashlasa: soxtani qayta qo'yamiz."""
    if app.match(mid) is None:
        _restore(app, fake_data())


def check_h2h(app, errors):
    """O'zaro uchrashuv: teng balli klasterda umumiy to'plar farqini yengadi."""
    snap = _snap(app)
    A, B, C, D, E, F = 11, 12, 13, 14, 15, 16
    names = {A: "Alfa", B: "Beta", C: "Gamma", D: "Delta", E: "Epsilon", F: "Fukron"}

    def mt(i, h, a, hs, as_):
        return {"id": i, "home": h, "away": a, "hs": hs, "as": as_, "round": 1,
                "stage": "group", "lineup_locked": True, "lineups": {},
                "subs": [], "goals": [], "cards": []}

    def grp(gid):
        return {"id": gid, "name": names[gid], "captain_id": None, "ptokens": 0,
                "logo": 1, "logo_img": None, "cap_login": None, "cap_pass_hash": None}

    def order(rows):
        return [r["name"] for r in rows]

    try:
        # 1) Alfa-Beta va Gamma-Delta teng ballar; o'zaro natija umumiy farqni yengadi
        app.d["groups"] = [grp(g) for g in (A, B, C, D)]
        app.d["matches"] = [mt(1, A, B, 1, 0), mt(2, C, A, 3, 0), mt(3, D, A, 3, 0),
                            mt(4, B, C, 8, 0), mt(5, D, B, 3, 0), mt(6, C, D, 1, 0)]
        rows = app.standings()
        if order(rows) != ["Gamma", "Delta", "Alfa", "Beta"]:
            errors.append("o'zaro uchrashuv: tartib %s (kutilgan Gamma, Delta, Alfa, Beta)"
                          % order(rows))
        by = {r["name"]: r for r in rows}
        if by["Alfa"]["PTS"] != 3 or by["Beta"]["PTS"] != 3:
            errors.append("o'zaro uchrashuv: ballar kutilgandek emas %s" %
                          [(r["name"], r["PTS"]) for r in rows])
        if by["Alfa"]["HPTS"] != 3 or by["Gamma"]["HPTS"] != 3 or by["Delta"]["HGD"] != -1:
            errors.append("o'zaro uchrashuv: mini-jadval ballari noto'g'ri %s" %
                          [(r["name"], r["HPTS"], r["HGD"]) for r in rows])
        note = app.h2h_note(rows)
        if not note or "Alfa" not in note or "o'zaro uchrashuv" not in note:
            errors.append("o'zaro uchrashuv: izoh chiqmadi (%r)" % note)

        # 2) klaster to'liq o'ynalmagan bo'lsa o'zaro uchrashuv QO'LLANILMAIDI
        app.d["groups"] = [grp(g) for g in (A, B, C, D, E, F)]
        app.d["matches"].append(mt(7, E, F, 1, 0))
        rows = app.standings()
        if order(rows) != ["Gamma", "Delta", "Beta", "Epsilon", "Alfa", "Fukron"]:
            errors.append("tugallanmagan klaster: tartib %s (o'zaro qulf ishlatilmasligi "
                          "kerak edi)" % order(rows))
        by = {r["name"]: r for r in rows}
        if by["Alfa"]["HPTS"] or by["Epsilon"]["HPTS"]:
            errors.append("tugallanmagan klaster: baribir o'zaro ball qo'llandi")
        print("  [table] o'zaro uchrashuv: %s | izoh: %s" %
              (order(app.standings()), "bor" if app.h2h_note(app.standings()) else "yo'q"))
    finally:
        _restore(app, snap)


def check_lock(app, errors):
    """Tarkib avtomatik qulfi: boshlanish vaqtidan LINEUP_LOCK_MIN oldin yopiladi."""
    from common import LINEUP_LOCK_MIN
    snap = _snap(app)
    _need_match(app, 2)
    now = int(time.time())
    m = app.match(2)
    real_save = app.store.save
    try:
        m["lineup_locked"] = False
        m["kick"] = None
        if app.lineup_closed(m) or app.lock_note(m) != "tarkib ochiq":
            errors.append("qulf: vaqt qo'ylmagan o'yin yopiq chiqdi (%s)" % app.lock_note(m))
        m["kick"] = now + (LINEUP_LOCK_MIN - 5) * 60
        if not app.auto_locked(m) or not app.lineup_closed(m):
            errors.append("qulf: %d daq. oldin avtomatik yopilishi kerak edi" % LINEUP_LOCK_MIN)
        if "avtomatik" not in app.lock_note(m):
            errors.append("qulf: matnda avtomatik deyilmadi (%s)" % app.lock_note(m))
        if app.set_lineup(m["home"], m["id"], [101, 102, 103]) is not False:
            errors.append("qulf: avtomatik yopilgan o'yinga tarkib qabul qilindi")
        m["kick"] = now + 120 * 60
        if app.lineup_closed(m) or "daq. keyin" not in app.lock_note(m):
            errors.append("qulf: 2 soatlik o'yin ochiq + hisoblagich bo'lishi kerak (%s)"
                          % app.lock_note(m))
        if not app.lineup_closed(app.match(1)):
            errors.append("qulf: natija kiritilgan o'yin yopiq emas")
        # admin qulfni bazaga ham yozadi (boshqa telefonlar ham rad etilishi uchun)
        if hasattr(app, "auto_lock_persist"):
            app.fb.is_admin = lambda: True
            writes = []
            app.store.save = lambda *a: (writes.append(1), True)[1]
            m["kick"] = now - 60
            app.auto_lock_persist()
            if not m["lineup_locked"] or not writes:
                errors.append("qulf: auto_lock_persist bazaga yozmadi (writes=%s)" % writes)
            if "QULFLANGAN" not in app.lock_note(m):
                errors.append("qulf: yozilgandan keyin matn %s" % app.lock_note(m))
            # ikkinchi marta: allaqachon qulflangan -> yozuv takrorlanmasligi kerak
            first = len(writes)
            writes[:] = []
            app.auto_lock_persist()
            if writes:
                errors.append("qulf: avtomatik qulf takror yozdi")
            print("  [admin] avtomatik qulf: yozuvlar=%d/%d (takrorlanmasligi kerak), holat=%s"
                  % (first, len(writes), app.lock_note(m)))
        else:
            m["kick"] = now - 60
            if not app.lineup_closed(m) or "avtomatik" not in app.lock_note(m):
                errors.append("qulf: bazaga yozmasdan ham mijozda yopiq turishi kerak")
            print("  [%s] avtomatik qulf (faqat mijozda): %s" %
                  (app.__class__.__name__, app.lock_note(m)))
    finally:
        app.store.save = real_save
        _restore(app, snap)


def check_clock(app, errors):
    """Hakam sekundomeri: bo'limlar, daqiqa hisobi, faylga saqlash va panel qurilishi."""
    import glassui as G
    from common import CLOCK_HALF_MIN, RefClockPanel
    tmp = tempfile.mkdtemp(prefix="apex_clock_")
    app._clock_path = lambda: os.path.join(tmp, "clock.json")
    app._clocks = {}
    mid = 2
    _need_match(app, mid)
    panel = None
    try:
        app.clock_reset(mid)
        if app.clock_minute(mid) is not None:
            errors.append("soat: ishlamagan holatda daqiqa None bo'lmadi")
        st = app.clock_state(mid)
        st["acc"] = 300
        app.clock_save(st)
        if app.clock_minute(mid) != 300 // 60 + 1:
            errors.append("soat: 1-bo'lim 05:00 -> %r daqiqa" % app.clock_minute(mid))
        app.clock_next_half(mid)
        st = app.clock_state(mid)
        if st["half"] != 2 or st["acc"] != 0 or app.clock_minute(mid) is not None:
            errors.append("soat: 2-bo'limga o'tish noto'g'ri (%r)" % st)
        st["acc"] = 60
        app.clock_save(st)
        want = CLOCK_HALF_MIN + 1 + 1
        if app.clock_minute(mid) != want:
            errors.append("soat: 2-bo'lim 01:00 -> %r (kutilgan %d)"
                          % (app.clock_minute(mid), want))
        # holat faylga yozilganmi (keshni o'chirib qayta o'qiymiz)
        app._clocks = None
        if app.clock_minute(mid) != want:
            errors.append("soat: holat clock.json ga yozilmadi")
        # jonli soat: panel va yurish matni
        st = app.clock_state(mid)
        st["acc"] = 125
        st["since"] = int(time.time())
        app.clock_save(st)
        if not app.clock_running_text(mid).startswith("  ·  \u23f1"):
            errors.append("soat: yugurayotgan matn chiqmadi (%r)" % app.clock_running_text(mid))
        panel = RefClockPanel(mid)
        if ":" not in panel.time_lbl.text or "2-bo'lim" not in panel.half_lbl.text:
            errors.append("soat: panel matni %r / %r" % (panel.time_lbl.text, panel.half_lbl.text))
        if panel.run_btn.lbl.text != "Pauza":
            errors.append("soat: yurganda tugma %r" % panel.run_btn.lbl.text)
        panel.toggle()
        if app.clock_state(mid)["since"] is not None or panel.run_btn.lbl.text != "Boshlash":
            errors.append("soat: pauza ishlamadi")
        # dialog orqali ham ochiladi (hakam menyusi shu yo'l bilan kiradi)
        app.clock_dialog()
        d = getattr(app, "dialog", None)
        if not isinstance(d, G.Dialog):
            errors.append("soat: clock_dialog ochilmadi")
        else:
            app.close_dialog()
        print("  [clock] %s daqiqa, panel=%s, fayl=%s" %
              (want, panel.time_lbl.text, os.path.basename(app._clock_path())))
    finally:
        if panel is not None and panel._ev is not None:
            panel._ev.cancel()


def check_number(app, errors):
    """
    Futbolka raqami: har jamoada 1 raqam = 1 o'yinchi.
    Takror o'z-o'zidan o'zgarmaydi — admin ro'yxatni ko'radi, o'yinchilar bilan
    kelishib raqamni o'zi beradi (band raqam esa qabul qilinmaydi).
    """
    from common import MAX_NUMBER
    snap = _snap(app)
    jobs = []
    real_choose, real_input, real_confirm = app.choose_dialog, app.input_dialog, app.confirm_dialog
    try:
        if app.taken_numbers(G1) != {10, 5, 1}:
            errors.append("raqam: band raqamlar %s (10, 5, 1 bo'lishi kerak)"
                          % sorted(app.taken_numbers(G1)))
        if app.free_number(G1) != 2 or app.free_numbers(G1, 4) != [2, 3, 4, 6]:
            errors.append("raqam: bo'sh raqamlar %s / %s"
                          % (app.free_number(G1), app.free_numbers(G1, 4)))
        if not app.number_holder(G1, 10) or app.number_holder(G1, 10, 101):
            errors.append("raqam: 10 raqami Alida — o'zini hisobga olmaganda topilmasligi kerak")
        if app.dup_numbers():
            errors.append("raqam: soxta ma'lumotda takror yo'q edi, %s chiqdi" % app.dup_numbers())
        if not hasattr(app, "number_clash_dialog"):
            print("  [%s] raqam yordamchilari: band=%s, bo'sh=%d" %
                  (app.__class__.__name__, sorted(app.taken_numbers(G1)), app.free_number(G1)))
            return

        # ---- 1) takror yuzaga keldi: hech narsa o'zgarmaydi, admin ga ro'yxat chiqadi ----
        app.player(103)["number"] = 5
        dups = app.dup_numbers(G1)
        if len(dups) != 1 or dups[0][1] != 5 or len(dups[0][2]) != 2:
            errors.append("raqam: takror topilmadi (%s)" % [(g, n, len(p)) for g, n, p in dups])
        app.choose_dialog = lambda title, opts, cb: jobs.append((title, opts, cb))
        app.number_clash_dialog()
        if not jobs or "Raqam takrorlari" not in jobs[0][0]:
            errors.append("raqam: admin ga takror ro'yxati ochilmadi (%s)" % [j[0] for j in jobs])
        else:
            row_title, row_opts, row_cb = jobs[-1]
            if len(row_opts) != 1 or "5 raqami" not in row_opts[0][0]:
                errors.append("raqam: ro'yxat qatori noto'g'ri (%s)" % row_opts)
            row_cb(row_opts[0][1])
            if len(jobs[-1][1]) != 2 or "5 raqami" not in jobs[-1][0]:
                errors.append("raqam: takrorlangan o'yinchilar ro'yxati ochilmadi (%s)"
                              % jobs[-1][0])
            pid = next(v for _, v in jobs[-1][1] if v == 103)
            app.input_dialog = lambda title, hint, cb, *a, **k: jobs.append((title, hint, cb))
            jobs[-1][2](pid)
            ask_title, ask_hint, ask_cb = jobs[-1]
            if "Bo'sh: 1, 2, 3, 4" not in ask_hint:
                errors.append("raqam: bo'sh raqam maslahati yo'q (%s)" % ask_hint)
            ask_cb(str(MAX_NUMBER + 1))
            if app.player(103)["number"] != 5:
                errors.append("raqam: %d (chegaradan tashqari) qabul qilindi" % (MAX_NUMBER + 1))
            ask_cb("10")
            if app.player(103)["number"] != 5:
                errors.append("raqam: band 10 raqami qabul qilindi")
            ask_cb("2")
            if app.player(103)["number"] != 2 or app.dup_numbers():
                errors.append("raqam: bo'sh 2 qabul bo'lmadi yoki takror qoldi")

        # ---- 2) transfer: raqam o'zgarmaydi, faqat xabarnoma bor ----
        app.player(102)["number"] = 9        # 9 raqami G2 da Javohirda
        app.d["transfers"].append({"id": 777, "pid": 102, "status": "offer", "amount": 10,
                                   "seller_gid": G1, "buyer_gid": G2, "side": "seller",
                                   "ts": 1730000000, "msg": ""})
        app.group(G2)["ptokens"] = 100
        n0 = len(app.d["notifs"])
        app.transfer_accept(777)
        p = app.player(102)
        if p["number"] != 9 or p["group"] != G2:
            errors.append("raqam: transfer raqamni o'zgartirdi (%s) yoki jamoaga kirmadi (%s)"
                          % (p["number"], p["group"]))
        if not any("ikki o'yinchida" in x["text"] for x in app.d["notifs"][n0:]):
            errors.append("raqam: transferdan keyin takror haqida xabar yo'q")
        if len(app.dup_numbers(G2)) != 1:
            errors.append("raqam: G2 dagi takror ro'yxatga kirmadi (%s)" % app.dup_numbers())

        # ---- 3) kvota bo'lishi: takror tushsa ham raqamlar o'zgarishi taqiqlanadi ----
        _restore(app, snap)
        for q in app.free_players():
            q["number"] = 10
        jobs[:] = []
        app.confirm_dialog = lambda title, msg, cb, *a, **k: cb()
        app.admin_random_split()
        if not any("Raqam takrorlari" in t for t, o, c in jobs):
            errors.append("raqam: bo'lishdan keyin takror ro'yxati chiqmadi (%s)"
                          % [j[0] for j in jobs])
        if any(app.player(i)["number"] != 10 for i in (401, 402, 403)):
            errors.append("raqam: bo'lish kimningdir raqamini o'zgartirdi")
        print("  [admin] raqam: takror qatorlari=%s, G1 band=%s, G1 bo'sh=%s" %
              ([o[0] for o in jobs[0][1]] if jobs else [],
               sorted(app.taken_numbers(G1)), app.free_numbers(G1, 3)))
    finally:
        app.choose_dialog, app.input_dialog, app.confirm_dialog = real_choose, real_input, real_confirm
        _restore(app, snap)


def check_backup(app, errors):
    """Zaxira: JSON eksport, tekshiruv va tiklash (butun turnir almashtiriladi)."""
    snap = _snap(app)
    _need_match(app, 2)
    tmp = tempfile.mkdtemp(prefix="apex_backup_")
    app.backup_dir = lambda: tmp
    try:
        app.match(2)["kick"] = 1700000000
        path = app.backup_now("sinov")
        if not path or not os.path.exists(path):
            errors.append("zaxira: fayl yozilmadi (%r)" % path)
            return
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for k in ("meta", "groups", "players", "matches", "lineups"):
            if k not in raw:
                errors.append("zaxira: '%s' tuguni yo'q" % k)
        if raw.get("_apex", {}).get("tag") != "sinov":
            errors.append("zaxira: yorliq saqlanmadi (%r)" % raw.get("_apex"))
        if int(raw["matches"]["2"]["kick"]) != 1700000000:
            errors.append("zaxira: boshlanish vaqti tushib qoldi")
        data = app.backup_read(path)
        if not data:
            errors.append("zaxira: o'qib bo'lmadi")
            return
        if [len(data[c]) for c in ("groups", "players", "matches")] != \
           [len(app.d[c]) for c in ("groups", "players", "matches")]:
            errors.append("zaxira: sonlar mos emas %s (hozir %s)" %
                          (app.restore_counts(data), app.restore_counts(app.d)))
        if app.backup_read(os.path.join(tmp, "apex_yoq.json")) is not None:
            errors.append("zaxira: yo'q fayl o'qildi")
        # tiklash: buzib tashlab, fayldan qaytaramiz (tasdiq dialog avtomatik 'ha')
        jobs = []
        real_confirm = app.confirm_dialog
        app.confirm_dialog = lambda title, msg, cb, *a, **k: jobs.append(cb)
        try:
            app.d["groups"] = []
            app.d["matches"] = []
            app.admin_restore(data, "sinov")
        finally:
            app.confirm_dialog = real_confirm
        if not jobs:
            errors.append("tiklash: tasdiq dialog ochilmadi")
            return
        jobs[0]()
        if [len(app.d[c]) for c in ("groups", "players", "matches")] != \
           [len(data[c]) for c in ("groups", "players", "matches")]:
            errors.append("tiklash: fayldagi sonlar qaytmadi (%s)" % app.restore_counts(app.d))
        if app.match(2)["kick"] != 1700000000:
            errors.append("tiklash: boshlanish vaqti tiklanmadi")
        if len(app.backup_files()) < 2:
            errors.append("tiklash: avtomatik zaxira yozilmadi")
        print("  [backup] %s -> %d fayl, tiklandi %s" %
              (os.path.basename(path), len(app.backup_files()), app.restore_counts(app.d)))
    finally:
        _restore(app, snap)


def check_png(app, errors):
    """Jadvalning PNG rasmi: panel quriladi, dialog ochiladi va faylga yoziladi."""
    import glassui as G
    from kivy.clock import Clock
    panel = app.table_image(app.stage_groups(), app.final_match())
    if len(panel.children) < 3:
        errors.append("png: jadval paneli bo'sh (%d vidjet)" % len(panel.children))
    app.share_table_image()
    d = getattr(app, "dialog", None)
    if not isinstance(d, G.Dialog):
        errors.append("png: share_table_image dialog ochmadi")
        return

    def got(path):
        if not path or not os.path.exists(path):
            errors.append("png: fayl yozilmadi (%r)" % path)
        else:
            size = os.path.getsize(path)
            if size < 2000:
                errors.append("png: fayl juda kichik (%d bayt)" % size)
            else:
                print("  [png] jadval rasmi: %d bayt" % size)
            try:
                os.remove(path)
            except OSError:
                pass

    app.export_png(d.card, "rc_jadval", got)
    # dialog export tugagandan keyin yopilsin (lekin orada boshqa dialog ochilgan bo'lsa emas)
    Clock.schedule_once(lambda *a: app.close_dialog()
                        if getattr(app, "dialog", None) is d else None, 0.5)


# Dialog ro'yxatiga aralashgan o'z-tekshiruvlar (ichki jarayonni sinaydi)
SENTINELS = {"_split_check": check_split,
             "_cap_login_check": check_cap_login,
             "_remove_check": check_remove,
             "_h2h_check": check_h2h,
             "_lock_check": check_lock,
             "_clock_check": check_clock,
             "_number_check": check_number,
             "_backup_check": check_backup,
             "_png_check": check_png}


# Admin tab'larining konteyneri b_<tab> emas (Kivy App.__getattr__ proksisi
# boshbiror metodni qaytarib yuboradi) -> obyekt lugsasidan olamiz.
BOX_ATTRS = {"admin": {"matches": "_m_list", "players": "_p_list"}}


def check_screens(kind, errors):
    """Tab tashqarisidagi mustaqil ekranlar (royxatdan otish, kirish) ham qurilsin."""
    try:
        if kind == "player":
            from common import RegisterScreen, StatusScreen
            sc = [RegisterScreen(name="register"), StatusScreen(name="status")]
            sc[0].reset()
            sc[1].set("Sinov: ulanish xatosi", True)
            sc[1].set("Turnir sozlanmagan", False)
        elif kind == "referee":
            from referee import RefLoginScreen
            from common import StatusScreen
            sc = [RefLoginScreen(name="login"), StatusScreen(name="status")]
            sc[0].busy(True)
            sc[0].busy(False)
            sc[1].set("Yuklanmoqda...", True)
        elif kind == "captain":
            from captain import CaptainLoginScreen
            from common import StatusScreen
            sc = [CaptainLoginScreen(name="caplogin"), StatusScreen(name="status")]
            sc[0].busy(True)
            sc[0].busy(False)
            sc[0].error("Login yoki parol xato")
            sc[0].error("")
            sc[1].set("Turnir hali boshlanmagan.", True)
        else:
            from admin import SetupScreen, LoginScreen
            sc = [SetupScreen(name="setup"), LoginScreen(name="login")]
            sc[1].busy(True)
            sc[1].busy(False)
        for s in sc:
            print("  [%s] ekran %-10s widgets=%s" % (kind, s.name, len(s.children)))
    except Exception as e:
        errors.append("ekran: %r" % e)
        traceback.print_exc()


def make_app(kind):
    if kind == "referee":
        from referee import RefereeApp
        app = RefereeApp()
        app.ref_id = 9
        return app
    if kind == "admin":
        from admin import AdminApp
        return AdminApp()
    if kind == "captain":
        from captain import CaptainApp
        app = CaptainApp()
        # me.json ga tegmasdan: sessiyani G1 kapitani qilib qo'yamiz
        me = {"pid": 101, "cap_gid": G1}
        app.load_me = lambda: dict(me)

        def save(m):
            me.clear()
            me.update(m)
        app._save_me = save
        app.my_cap_gid = G1
        return app
    from player import PlayerApp
    app = PlayerApp()
    # Sessiya = G1 kapitani (101): kapitan dialoglari har doim ochilishi uchun.
    # me.json fayliga tegilmaymiz (haqiqiy foydalanuvchi identifikatori buzi'lmasin).
    app.load_me = lambda: {"pid": 101}
    app._save_me = lambda me: None
    return app


class Runner:
    """Har bir ilova uchun: build -> soxta ma'lumot -> barcha tab'larni qurish."""

    def __init__(self, kind):
        self.kind = kind
        self.errors = []
        self.app = make_app(kind)
        self.app.build = self._build          # MDApp.run() shu _build'ni chaqiradi
        # Ilova tarmog'iga chiqmasin: soxta ma'lumot serverni bosib qo'ymasligi va
        # server javobining soxtani buzbemasligi uchun sinxronni o'chiramiz.
        for name in ("poll", "check_update", "start_sync", "_sync_done",
                     "_poll_done", "_update_info"):
            setattr(self.app, name, lambda *a: None)

    def _build(self):
        app = self.app
        # kutilmagan xato yoki crash-dialog ochilib tekshiruvni to'xtatmasin: yozib olamiz
        app.report_crash = lambda exc: self.errors.append("CRASH: %r" % exc)
        sm = type(app).build(app)              # haqiqiy ilova qurilsin
        if sm is not getattr(app, "sm", None):
            # LeagueApp.build xatoni yutib crash-ekran qaytarsa, shu yerda bilanadi.
            self.errors.append("BUILD CRASH: build() crash ekranini qaytardi")
            for w in getattr(sm, "children", []):
                print("  " + str(getattr(w, "text", ""))[-1200:])
        app.store.fetch = lambda *a: None
        app.store.save = lambda *a: False
        app.store.data = fake_data()           # keyin soxta ma'lumot bilan almashtiriladi
        # Sinxron o'chiq => route() ishlamaydi: tekshiruv asosiy ekranda bo'lsin
        app.sm.current = "main"

        def run(*a):
            for key in TABS[self.kind]:
                try:
                    app.go_tab(key)
                except Exception as e:
                    self.errors.append("go_tab %s: %r" % (key, e))
            try:
                app.refresh_all()
            except Exception as e:
                self.errors.append("refresh_all: %r" % e)
            for key in TABS[self.kind]:
                name = BOX_ATTRS.get(self.kind, {}).get(key, "b_" + key)
                box = app.__dict__.get(name)
                print("  [%s] tab %-8s widgets=%s" %
                      (self.kind, key, len(box.children) if box is not None else "-"))
            check_screens(self.kind, self.errors)

            def finish(*a):
                print("  [%s] XATOLAR: %s" % (self.kind, self.errors or "yo'q"))
                app.stop()
            check_dialogs(app, self.kind, self.errors, finish)
        Clock.schedule_once(run, 0)
        return sm


if __name__ == "__main__":
    # Bitta MDApp bir jarayonda faqat bir marta ishga tushadi: har bir ilova
    # alohida ichki jarayonda tekshiriladi.
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    kinds = list(TABS) if arg == "all" else [arg]
    if len(kinds) > 1:
        bad = 0
        for k in kinds:
            print("=== %s ===" % k)
            bad |= subprocess.call([sys.executable, os.path.abspath(__file__), k])
        sys.exit(bad)
    bad = 0
    runner = Runner(kinds[0])
    try:
        runner.app.run()
    except Exception:
        traceback.print_exc()
        bad = 1
    sys.exit(bad if runner.errors else 0)
