# -*- coding: utf-8 -*-
"""
Firebase Realtime Database (REST) mijozi va umumiy ma'lumot ombori.

Ma'lumotlar bazadagi tuzilishi (hammasi id bo'yicha alohida tugunlar):
  /meta      {setup_done, is_draft_open, turn}
  /groups    /<gid>  {id, name, captain_id, pin_hash}
  /players   /<pid>  {id, name, group, self_registered}
  /matches   /<mid>  {id, home, away, hs, as, lineup_locked, motm_admin, goals[], subs[], cards[]}
  /lineups   /<mid>/<gid>  [pid, ...]

Xotirada (ilova ichida) esa avvalgidek oddiy ro'yxatlar ishlatiladi: store.data
"""
import copy
import json
import os
import random
import ssl
import time
import urllib.error
import urllib.request

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # certifi yo'q bo'lsa tizim sertifikatlari
    _CTX = ssl.create_default_context()

META_KEYS = ("setup_done", "is_draft_open", "turn")
COLLECTIONS = ("groups", "players", "matches", "notifs", "transfers", "market", "refs")
EXTRA = ("notifs", "transfers", "market", "refs")

# APEX TOKEN: har bir o'yinchi ro'yxatdan o'tganda shuncha token oladi
TOKEN_START = 500


class CloudError(Exception):
    def __init__(self, kind, msg=""):
        super().__init__(msg or kind)
        self.kind = kind          # network | denied | auth | other
        self.msg = msg

    def human(self):
        if self.kind == "network":
            return "Internet yo'q yoki server javob bermadi."
        if self.kind == "denied":
            return "Ruxsat berilmadi: boshqa foydalanuvchi oldin o'zgartirgan yoki qoida taqiqlaydi."
        if self.kind == "auth":
            return "Email yoki parol noto'g'ri."
        return "Xato: " + self.msg[:90]


# --------------------------------------------------------------------------
#  Firebase REST
# --------------------------------------------------------------------------
class Firebase:
    def __init__(self, db_url, api_key):
        self.db = db_url.rstrip("/")
        self.api_key = api_key
        self.id_token = None
        self.expires = 0
        self.email = None
        self._password = None      # faqat xotirada, diskka yozilmaydi

    # ---- past darajadagi so'rov ----
    def _http(self, method, url, body=None, headers=None, timeout=10):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs = {"Content-Type": "application/json"}
        hdrs.update(headers or {})
        req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                raw = r.read().decode("utf-8")
                h = {k.lower(): v for k, v in r.headers.items()}
                return r.status, h, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return 304, {k.lower(): v for k, v in e.headers.items()}, None
            try:
                txt = e.read().decode("utf-8", errors="ignore")
            except Exception:
                txt = ""
            kind = "denied" if e.code in (401, 403) else "other"
            raise CloudError(kind, f"HTTP {e.code} {txt[:160]}")
        except (urllib.error.URLError, OSError) as e:
            raise CloudError("network", str(e))
        except ValueError as e:
            raise CloudError("other", "JSON xato: " + str(e))

    # ---- admin autentifikatsiyasi ----
    def sign_in(self, email, password):
        url = ("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key="
               + self.api_key)
        try:
            _, _, res = self._http("POST", url, {"email": email, "password": password,
                                                 "returnSecureToken": True})
        except CloudError as e:
            if e.kind == "other" and any(w in e.msg.upper() for w in
                                         ("INVALID", "EMAIL", "PASSWORD", "CREDENTIAL", "USER")):
                raise CloudError("auth", e.msg)
            if e.kind == "denied":
                raise CloudError("auth", e.msg)
            raise
        self.id_token = res["idToken"]
        self.expires = time.time() + int(res.get("expiresIn", "3600")) - 120
        self.email, self._password = email, password

    def sign_out(self):
        self.id_token, self._password, self.expires = None, None, 0

    def is_admin(self):
        return bool(self.id_token)

    def change_password(self, new_password):
        url = "https://identitytoolkit.googleapis.com/v1/accounts:update?key=" + self.api_key
        _, _, res = self._http("POST", url, {"idToken": self._token(), "password": new_password,
                                             "returnSecureToken": True})
        self.id_token = res.get("idToken", self.id_token)
        self.expires = time.time() + int(res.get("expiresIn", "3600")) - 120
        self._password = new_password

    def _token(self):
        if self.id_token and time.time() >= self.expires:
            if not self._password:
                raise CloudError("auth", "sessiya tugagan")
            self.sign_in(self.email, self._password)
        return self.id_token

    # ---- ma'lumotlar bazasi ----
    def get_all(self, etag=None):
        """Hammasini o'qish. O'zgarmagan bo'lsa None, aks holda (data, etag)."""
        headers = {"X-Firebase-ETag": "true"}
        if etag:
            headers["If-None-Match"] = etag
        status, h, body = self._http("GET", self.db + "/.json", headers=headers)
        if status == 304:
            return None
        return body, h.get("etag")

    def patch(self, updates):
        """Ko'p yo'lli atomik yozish: {"players/12": {...}, "meta/turn": 3, "x/y": None}"""
        url = self.db + "/.json"
        tok = self._token()
        if tok:
            url += "?auth=" + tok
        self._http("PATCH", url, updates, timeout=12)


# --------------------------------------------------------------------------
#  Xotira (ro'yxatlar)  <->  Baza (id bo'yicha tugunlar) o'tkazgichlari
# --------------------------------------------------------------------------
def empty_data():
    return {"setup_done": False, "is_draft_open": False, "turn": 0,
            "groups": [], "players": [], "matches": [],
            "notifs": [], "transfers": [], "market": [], "refs": []}


def _clean(d, skip=()):
    out = {}
    for k, v in d.items():
        if k in skip or v is None or (isinstance(v, list) and not v):
            continue
        out[k] = copy.deepcopy(v)
    return out


def to_remote(data):
    meta = {k: data[k] for k in META_KEYS if data.get(k) is not None}
    groups = {str(g["id"]): _clean(g) for g in data["groups"]}
    players = {str(p["id"]): _clean(p) for p in data["players"]}
    matches, lineups = {}, {}
    for m in data["matches"]:
        matches[str(m["id"])] = _clean(m, skip=("lineups",))
        for gid, ids in m.get("lineups", {}).items():
            if ids:
                lineups.setdefault(str(m["id"]), {})[str(gid)] = list(ids)
    return dict({"meta": meta, "groups": groups, "players": players,
                 "matches": matches, "lineups": lineups},
                **{c: {str(x["id"]): _clean(x) for x in data[c]} for c in EXTRA})


def _values(node):
    if isinstance(node, dict):
        return [v for v in node.values() if isinstance(v, dict)]
    if isinstance(node, list):
        return [v for v in node if isinstance(v, dict)]
    return []


def _i(v):
    """Id qiymatini butun songa keltiradi (Firebase float qaytarsa ham)."""
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v


def _norm_ids(m):
    for k in ("home", "away", "motm_admin"):
        if k in m:
            m[k] = _i(m[k])
    for g in m.get("goals", []):
        for k in ("scorer", "assist", "team"):
            if k in g:
                g[k] = _i(g[k])
    for s in m.get("subs", []):
        for k in ("team", "out", "in"):
            if k in s:
                s[k] = _i(s[k])
    for c in m.get("cards", []):
        if "pid" in c:
            c["pid"] = _i(c["pid"])
    for a in m.get("attendance", []):
        if "pid" in a:
            a["pid"] = _i(a["pid"])


def from_remote(raw):
    raw = raw or {}
    meta = raw.get("meta") or {}
    data = empty_data()
    data["setup_done"] = bool(meta.get("setup_done", False))
    data["is_draft_open"] = bool(meta.get("is_draft_open", False))
    data["turn"] = int(meta.get("turn", 0) or 0)

    for v in _values(raw.get("groups")):
        g = dict(v)
        g["id"] = int(g["id"])
        g["captain_id"] = _i(g.get("captain_id"))
        g.setdefault("pin_hash", None)
        g["logo"] = _i(g.get("logo"))
        g.setdefault("logo_img", None)
        g["ptokens"] = int(g.get("ptokens", 0) or 0)
        data["groups"].append(g)
    for v in _values(raw.get("players")):
        p = dict(v)
        p["id"] = int(p["id"])
        p["group"] = _i(p.get("group"))
        p.setdefault("group", None)
        for k in ("number", "pos", "country", "base_ovr"):
            p.setdefault(k, None)
        p["number"] = _i(p["number"])
        p["base_ovr"] = _i(p["base_ovr"])
        p["tokens"] = int(p.get("tokens", TOKEN_START) or 0)
        p["token_zero_since"] = _i(p.get("token_zero_since"))
        p.setdefault("tstatus", None)     # None | "pending" | "listed"
        data["players"].append(p)
    lin_all = raw.get("lineups") or {}
    for v in _values(raw.get("matches")):
        m = dict(v)
        m["id"] = int(m["id"])
        m.setdefault("hs", None)
        m.setdefault("as", None)
        m.setdefault("lineup_locked", False)
        m.setdefault("motm_admin", None)
        m.setdefault("stage", "group")     # "group" | "final"
        m["grp"] = _i(m.get("grp"))        # guruh bosqichidagi guruh id si (>8 jamoa)
        if not isinstance(m.get("attendance"), list):
            m["attendance"] = []
        for k in ("goals", "subs", "cards"):
            if not isinstance(m.get(k), list):
                m[k] = []
        lin = lin_all.get(str(m["id"])) if isinstance(lin_all, dict) else None
        if not isinstance(lin, dict):
            lin = {}
        m["lineups"] = {str(k): [_i(v) for v in x] for k, x in lin.items() if isinstance(x, list)}
        _norm_ids(m)
        data["matches"].append(m)
    for v in _values(raw.get("notifs")):
        n = dict(v)
        n["id"] = int(n["id"])
        n.setdefault("to", "all")
        n.setdefault("text", "")
        n["ts"] = int(n.get("ts", 0) or 0)
        n["read"] = n.get("read") if isinstance(n.get("read"), dict) else {}
        data["notifs"].append(n)
    for v in _values(raw.get("transfers")):
        t = dict(v)
        t["id"] = int(t["id"])
        t["pid"] = _i(t.get("pid"))
        t.setdefault("status", "pending")   # pending|listed|offer|done|rejected
        t["seller_gid"] = _i(t.get("seller_gid"))
        t["buyer_gid"] = _i(t.get("buyer_gid"))
        t["amount"] = int(t.get("amount", 0) or 0)
        t["ts"] = int(t.get("ts", 0) or 0)
        t.setdefault("msg", "")
        data["transfers"].append(t)
    for v in _values(raw.get("market")):
        it = dict(v)
        it["id"] = int(it["id"])
        it.setdefault("name", "")
        it.setdefault("desc", "")
        it["price"] = int(it.get("price", 0) or 0)
        it["qty"] = int(it.get("qty", 0) or 0)
        it.setdefault("img", None)
        data["market"].append(it)
    for v in _values(raw.get("refs")):
        r = dict(v)
        r["id"] = int(r["id"])
        r.setdefault("name", "")
        r.setdefault("pin_hash", None)
        data["refs"].append(r)
    for c in COLLECTIONS:
        data[c].sort(key=lambda x: x["id"])
    return data


def merge_into(cur, new):
    """Yangi ma'lumotni MAVJUD obyektlar ichiga joyida qo'shadi (ochiq dialoglar eskirmasin)."""
    for k in META_KEYS:
        cur[k] = new[k]
    for coll in COLLECTIONS:
        by_id = {x["id"]: x for x in cur[coll]}
        out = []
        for n in new[coll]:
            x = by_id.get(n["id"])
            if x is None:
                out.append(n)
            else:
                x.clear()
                x.update(n)
                out.append(x)
        cur[coll][:] = out


def diff(old, new):
    """Faqat o'zgargan tugunlar: {"yo'l": yangi_qiymat yoki None(o'chirish)}"""
    ups = {}
    for k in set(old["meta"]) | set(new["meta"]):
        if old["meta"].get(k) != new["meta"].get(k):
            ups["meta/" + k] = new["meta"].get(k)
    for coll in COLLECTIONS:
        o, n = old[coll], new[coll]
        for k in set(o) | set(n):
            if o.get(k) != n.get(k):
                ups[f"{coll}/{k}"] = n.get(k)

    def flat(lin):
        return {f"{mid}/{gid}": ids for mid, gs in lin.items() for gid, ids in gs.items()}
    fo, fn = flat(old["lineups"]), flat(new["lineups"])
    for k in set(fo) | set(fn):
        if fo.get(k) != fn.get(k):
            ups["lineups/" + k] = fn.get(k)
    return ups


# --------------------------------------------------------------------------
#  Ombor
# --------------------------------------------------------------------------
class RemoteStore:
    def __init__(self, fb, cache_path):
        self.fb = fb
        self.cache_path = cache_path
        self.data = empty_data()
        self.snapshot = to_remote(self.data)
        self.etag = None
        self.online = False
        self.rev = 0              # har o'zgarishda oshadi (eskirgan javoblarni tashlash uchun)
        self._last_id = 0
        self.on_error = None      # callback(msg)

    # ---- kesh (oflayn ochilish uchun) ----
    def load_cache(self):
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            merge_into(self.data, from_remote(raw))
            self.snapshot = to_remote(self.data)
        except Exception:
            pass

    def _write_cache(self):
        try:
            tmp = self.cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.snapshot, f, ensure_ascii=False)
            os.replace(tmp, self.cache_path)
        except Exception:
            pass

    def new_id(self):
        used = {x["id"] for c in COLLECTIONS for x in self.data[c]}
        # millisekund * 1000 + tasodifiy: ikki telefon bir vaqtda yaratsa ham to'qnashmaydi
        # (1.8e15 < 2**53, Firebase raqamlari aniq saqlaydi)
        i = int(time.time() * 1000) * 1000 + random.randint(0, 999)
        i = max(i, self._last_id + 1)      # bir qurilmada id'lar qat'iy o'sadi (guruhlar tartibi buzilmasin)
        while i in used:
            i += 1
        self._last_id = i
        return i

    # ---- o'qish ----
    def fetch(self):
        """Tarmoq so'rovi (fon oqimida chaqirilishi mumkin). O'zgarmasa None."""
        rev = self.rev
        try:
            res = self.fb.get_all(self.etag)
        except CloudError:
            self.online = False
            raise
        self.online = True
        if res is None:
            return None
        return res[0], res[1], rev

    def apply(self, res):
        """Asosiy oqimda chaqiriladi. Eskirgan bo'lsa False."""
        raw, etag, rev = res
        if rev != self.rev:
            return False
        merge_into(self.data, from_remote(raw))
        self.snapshot = to_remote(self.data)
        self.etag = etag
        self.rev += 1
        self._write_cache()
        return True

    def pull(self, force=False):
        if force:
            self.etag = None
        res = self.fetch()
        if res:
            self.apply(res)
        return bool(res)

    # ---- yozish ----
    def save(self):
        """O'zgargan qismlarni bazaga yozadi. Muvaffaqiyatsiz bo'lsa mahalliy o'zgarish bekor qilinadi."""
        new = to_remote(self.data)
        ups = diff(self.snapshot, new)
        if not ups:
            return True
        try:
            self.fb.patch(ups)
        except CloudError as e:
            self.online = e.kind != "network"
            merge_into(self.data, from_remote(self.snapshot))     # o'zgarishni qaytarish
            self.rev += 1
            if self.on_error:
                self.on_error(e.human())
            try:
                self.pull(force=True)
            except CloudError:
                pass
            return False
        self.snapshot = new
        self.rev += 1
        self.etag = None
        self.online = True
        self._write_cache()
        return True
