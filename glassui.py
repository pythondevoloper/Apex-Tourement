# -*- coding: utf-8 -*-
"""
Glass UI vidjetlari — main.py prototipidagi saf-Kivy (canvas asosidagi) dizayn tili.
Firebase / admin mantiqidan butunlay mustaqil: barcha tugmalar callback orqali ulanadi.
AdminApp (admin.py) va LeagueApp (common.py — o'yinchi/hakam) shu vidjetlardan foydalanadi.
"""
import os

from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex as hx
from kivymd import fonts_path
from kivymd.icon_definitions import md_icons

# ----------------------------------------------------------------- ranglar
WHITE = (1, 1, 1, 1)
MUTED = hx("#C3C8F5")
BLUE = hx("#3B82F6")
CYAN = hx("#22D3EE")
GREEN = hx("#10B981")
PURPLE = hx("#6D5BFF")
YELLOW = hx("#FACC15")
INDIGO = hx("#5B4BD8")
GLASS = (1, 1, 1, 0.08)
BORDER = (0.63, 0.67, 1, 0.30)

ICON_FONT = os.path.join(fonts_path, "materialdesignicons-webfont.ttf")


# ----------------------------------------------------------- asosiy vidjetlar
class Icon(Label):
    """Material Design Icons glifi."""

    def __init__(self, name, size=22, color=WHITE, **kw):
        super().__init__(
            text=md_icons.get(name, md_icons["circle"]),
            font_name=ICON_FONT,
            font_size=sp(size),
            color=color,
            size_hint=(None, None),
            size=(dp(size + 6), dp(size + 6)),
            **kw,
        )


class TL(Label):
    """Matn yorlig'i (halign ishlashi uchun text_size bog'langan)."""

    def __init__(self, text="", size=14, color=WHITE, bold=False,
                 align="left", shorten=True, valign="middle", **kw):
        super().__init__(
            text=text, font_size=sp(size), color=color, bold=bold,
            halign=align, valign=valign, markup=True,
            shorten=shorten, shorten_from="right", **kw,
        )
        self.bind(size=lambda w, s: setattr(w, "text_size", s))


class Glass(BoxLayout):
    """Shaffof 'glass' karta: yarim shaffof fon + yorqin chegara."""

    def __init__(self, radius=18, fill=GLASS, border=BORDER, **kw):
        super().__init__(**kw)
        self.rad = dp(radius)
        with self.canvas.before:
            self._fill = Color(*fill)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.rad])
            self._bcol = Color(*border)
            self._ln = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self.rad), width=1)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, self.rad)

    def set_style(self, fill=None, border=None):
        if fill is not None:
            self._fill.rgba = fill
        if border is not None:
            self._bcol.rgba = border


class GlassButton(ButtonBehavior, Glass):
    pass


class Badge(FloatLayout):
    """Aylana: ichida ikonka, bosh harflar yoki rasm (jamoa logosi / avatar)."""

    def __init__(self, color, size=40, icon=None, text=None, image=None, **kw):
        super().__init__(size_hint=(None, None), size=(dp(size), dp(size)), **kw)
        with self.canvas.before:
            Color(color[0], color[1], color[2], 0.35)
            self._e = Ellipse(pos=self.pos, size=self.size)
            Color(color[0], color[1], color[2], 0.9)
            self._l = Line(circle=(0, 0, 0), width=1.3)
        if image:
            try:
                tex = CoreImage(image).texture
                pad = dp(size * 0.12)
                with self.canvas.before:
                    Color(1, 1, 1, 1)
                    self._img = Rectangle(texture=tex, pos=(self.x + pad, self.y + pad),
                                          size=(self.width - pad * 2, self.height - pad * 2))
                self.bind(pos=self._img_upd, size=self._img_upd)
            except Exception:
                image = None
        if icon:
            ic = Icon(icon, size * 0.5, WHITE, pos_hint={"center_x": .5, "center_y": .5})
            self.add_widget(ic)
        if text:
            self.add_widget(TL(text, size * 0.34, bold=True, align="center",
                               pos_hint={"center_x": .5, "center_y": .5}))
        self.bind(pos=self._upd, size=self._upd)

    def _img_upd(self, *_):
        pad = dp(self.width * 0.12)
        self._img.pos = (self.x + pad, self.y + pad)
        self._img.size = (self.width - pad * 2, self.height - pad * 2)

    def _upd(self, *_):
        self._e.pos, self._e.size = self.pos, self.size
        self._l.circle = (self.center_x, self.center_y, self.width / 2)


class IconBtn(ButtonBehavior, Badge):
    """Sarlavhadagi dumaloq tugma (ixtiyoriy bildirishnoma nuqtasi bilan)."""

    def __init__(self, icon, dot=False, **kw):
        super().__init__(color=WHITE, size=44, icon=icon, **kw)
        with self.canvas.after:
            self._dcol = Color(0.85, 0.4, 1, 1 if dot else 0)
            self._dot = Ellipse(size=(dp(9), dp(9)))
        self.bind(pos=self._dot_upd, size=self._dot_upd)
        self._dot_upd()

    def _dot_upd(self, *_):
        self._dot.pos = (self.right - dp(14), self.top - dp(14))

    def set_dot(self, on):
        self._dcol.rgba = (0.85, 0.4, 1, 1 if on else 0)


class Toggle(ButtonBehavior, Widget):
    """ON/OFF switch. on_toggle(yangi_holat) qo'ng'iroq qilinadi."""

    def __init__(self, active=True, on_toggle=None, **kw):
        super().__init__(size_hint=(None, None), size=(dp(46), dp(26)), **kw)
        self.active = active
        self.on_toggle = on_toggle
        self.bind(pos=self.draw, size=self.draw)
        self.draw()

    def on_release(self):
        self.active = not self.active
        self.draw()
        if self.on_toggle:
            self.on_toggle(self.active)

    def set_active(self, on):
        self.active = bool(on)
        self.draw()

    def draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*(BLUE if self.active else (1, 1, 1, 0.2)))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(13)])
            Color(1, 1, 1, 1)
            x = self.right - dp(23) if self.active else self.x + dp(3)
            Ellipse(pos=(x, self.y + dp(3)), size=(dp(20), dp(20)))


class Background(Widget):
    """Binafsha -> to'q ko'k vertikal gradient (Texture, silliq)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        tex = Texture.create(size=(1, 3), colorfmt="rgba")
        stops = (hx("#14196B"), hx("#1D1A6E"), hx("#4A2FB8"))  # pastdan tepaga
        buf = bytes(int(v * 255) for c in stops for v in c)
        tex.blit_buffer(buf, colorfmt="rgba", bufferfmt="ubyte")
        tex.mag_filter = tex.min_filter = "linear"
        with self.canvas:
            Color(1, 1, 1, 1)
            self._r = Rectangle(texture=tex, pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._r.pos, self._r.size = self.pos, self.size


class ChipBar(BoxLayout):
    """Gorizontal filtr chiplari. select(names[0]) qurilishda bir marta cb chaqiradi."""

    def __init__(self, names, callback, chip_w=84, **kw):
        super().__init__(size_hint_y=None, height=dp(40), spacing=dp(8), **kw)
        self.cb, self.chips = callback, {}
        for n in names:
            c = GlassButton(size_hint_x=None, width=dp(chip_w), radius=12)
            c.add_widget(TL(n, 13, align="center"))
            c.bind(on_release=lambda w, n=n: self.select(n))
            self.chips[n] = c
            self.add_widget(c)
        self.add_widget(Widget())
        self.current = None
        if names:
            self.select(names[0])

    def select(self, name):
        for n, c in self.chips.items():
            on = n == name
            c.set_style(BLUE if on else GLASS, CYAN if on else BORDER)
        self.current = name
        if self.cb:
            self.cb(name)

    def reselect(self, name):
        for n, c in self.chips.items():
            on = n == name
            c.set_style(BLUE if on else GLASS, CYAN if on else BORDER)
        self.current = name


def scroll_page(pad=(dp(12), dp(4), dp(12), dp(12)), spacing=dp(12)):
    sv = ScrollView(bar_width=0)
    box = BoxLayout(orientation="vertical", size_hint_y=None, padding=pad, spacing=dp(spacing))
    box.bind(minimum_height=box.setter("height"))
    sv.add_widget(box)
    return sv, box


def divider():
    w = Widget(size_hint_y=None, height=dp(1))
    with w.canvas:
        Color(0.63, 0.67, 1, 0.2)
        r = Rectangle(pos=w.pos, size=w.size)
    w.bind(pos=lambda *_: setattr(r, "pos", w.pos), size=lambda *_: setattr(r, "size", w.size))
    return w


def section_label(text):
    return TL(text, 11, MUTED, size_hint_y=None, height=dp(18), padding=(dp(6), 0))


def initials(name):
    return "".join(w[0] for w in str(name).split()[:2]).upper() or "?"


class ButtonRow(ButtonBehavior, BoxLayout):
    pass


def solid_button(text, cb=None, w=None, h=44, fill=BLUE, size=13):
    """To'q rangli tugma (butun kenglik yoki berilgan kenglikda)."""
    b = GlassButton(size_hint=(None, None) if w else (1, None), height=dp(h), radius=14,
                    fill=fill, border=(1, 1, 1, 0.15))
    if w:
        b.width = dp(w)
    b.lbl = TL(text, size, bold=True, align="center")
    b.add_widget(b.lbl)
    if cb:
        b.bind(on_release=lambda *a: cb())
    return b


def note(text, size=11, h=None):
    """Izmat matn: h berilsa o'lcham beriladi, aksi holda uzunlikka qarab o'sadi."""
    lab = TL(text, size, MUTED, align="left", valign="top", shorten=False,
             size_hint_y=None, padding=(dp(6), 0))
    if h:
        lab.height = dp(h)
    else:
        lab.bind(texture_size=lambda i, v: setattr(i, "height", v[1]))
    return lab


class Band(GlassButton):
    """Rangli shisha tasma: logo/nişan + matn + o'ngda qo'shimcha chip."""

    def __init__(self, text, color, logo=None, name=None, chip=None, h=46,
                 text_color=WHITE, cb=None, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(h),
                         padding=(dp(10), 0), spacing=dp(8), radius=14,
                         fill=(color[0], color[1], color[2], 0.42),
                         border=(color[0], color[1], color[2], 0.85), **kw)
        b = Badge(color, h - dp(10), image=logo if logo and os.path.exists(logo) else None,
                  text=initials(name) if not (logo and os.path.exists(logo)) else None)
        b.pos_hint = {"center_y": .5}
        self.add_widget(b)
        self.add_widget(TL(text, 12.5, text_color, bold=True))
        if chip:
            c = Glass(size_hint=(None, None), size=(dp(84), dp(24)), radius=12,
                      fill=(0, 0, 0, 0.25), border=(1, 1, 1, 0.18),
                      pos_hint={"center_y": .5})
            c.add_widget(TL(chip, 10, bold=True, align="center"))
            self.add_widget(c)
        if cb:
            self.bind(on_release=lambda *a: cb())


def cell(text, w, size=12.5, color=WHITE, bold=False):
    """Jadval uchun o'lchami belgilangan markazlashgan katak."""
    return TL(str(text), size, color, bold, align="center",
              size_hint_x=None, width=dp(w))


def table_row(cells, widths, header=False, cb=None, hl=False, h=40, name=None,
              name_w=None, badge=None, pts=None, pts_w=34):
    """Shisha jadval qatori: [nom] + kataklar (+ oxirgi ustun urg'ulangan).

    cells: ko'rsatiladigan qiymatlar ro'yxati (widths bilan bir xil uzunlikda).
    """
    fill = (0.23, 0.51, 0.96, 0.28) if hl else (GLASS if not header else (0, 0, 0, 0))
    border = (BORDER if not header else (0, 0, 0, 0))
    r = GlassButton(orientation="horizontal", size_hint_y=None, height=dp(h),
                    padding=(dp(8), 0), spacing=dp(4), radius=12, fill=fill, border=border)
    col = MUTED if header else WHITE
    if name is not None:
        if badge is not None:
            b = Badge(badge, h - dp(12), text=initials(name))
            b.pos_hint = {"center_y": .5}
            r.add_widget(b)
        kw = {"size_hint_x": None, "width": dp(name_w)} if name_w else {"size_hint_x": 1}
        r.add_widget(TL(name, 11 if header else 12.5, col, bold=not header, **kw))
    for v, w in zip(cells, widths):
        r.add_widget(cell(v, w, 11 if header else 12.5, col, header is False))
    if pts is not None:
        r.add_widget(cell(pts, pts_w, 15, CYAN, True))
    if cb:
        r.bind(on_release=lambda *a: cb())
    return r


class Pitch(FloatLayout):
    """Yashnoq maydon: halqalar va chizig'lar bilan (tarkib joylashuvi uchun)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(0.09, 0.45, 0.28, 0.55)
            self._bg = RoundedRectangle(radius=[dp(18)])
            Color(0.63, 0.67, 1, 0.35)
            self._ln = Line(width=1.1)
            self._c1 = Line(circle=(0, 0, 0), width=1.1)
            self._c2 = Line(rounded_rectangle=(0, 0, 0, 0, dp(10)), width=1.1)
        self.bind(pos=self._upd, size=self._upd)
        self._upd()

    def _upd(self, *_):
        w, h = self.width, self.height
        if w <= 1 or h <= 1:
            return
        self._bg.pos, self._bg.size = self.pos, self.size
        self._ln.points = [self.x, self.center_y, self.right, self.center_y]
        r = min(w, h) * 0.16
        self._c1.circle = (self.center_x, self.center_y, r)
        bw, bh = w * 0.22, h * 0.24
        self._c2.rounded_rectangle = (self.x, self.center_y - bh / 2, bw, bh, dp(10))


class Banner(Glass):
    """Yuqori shisha banner: kubok + sarlavha + tavsif."""

    def __init__(self, title, sub, h=118, image=None, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(h),
                         padding=dp(14), spacing=dp(12), radius=22,
                         fill=(0.45, 0.35, 1, 0.25), **kw)
        if image and os.path.exists(image):
            ic = Image(source=image, size_hint=(None, None), size=(dp(h - 30), dp(h - 30)),
                       allow_stretch=True, keep_ratio=True)
            ic.pos_hint = {"center_y": .5}
            self.add_widget(ic)
        else:
            b = Badge(CYAN, h - 34, icon="trophy-outline")
            b.pos_hint = {"center_y": .5}
            self.add_widget(b)
        col = BoxLayout(orientation="vertical", spacing=dp(3))
        col.add_widget(TL(title, 22, bold=True))
        col.add_widget(TL(sub, 11, MUTED, shorten=False))
        self.add_widget(col)


# ---------------------------------------------------------------- kartalar
class MenuCard(GlassButton):
    """Dashboard menyu-to'ri kartasi: ikonka-halqa + sarlavha + tavsif. cb() bosilganda."""

    def __init__(self, icon, title, sub, color, cb, **kw):
        super().__init__(orientation="horizontal", padding=dp(10), spacing=dp(8), radius=18, **kw)
        b = Badge(color, 36, icon=icon)
        b.pos_hint = {"center_y": .5}
        col = BoxLayout(orientation="vertical", spacing=dp(2))
        col.add_widget(TL(title, 12.5, bold=True))
        col.add_widget(TL(sub, 10, MUTED, shorten=False))
        self.add_widget(b)
        self.add_widget(col)
        self.bind(on_release=lambda *a: cb())


class MatchCard(GlassButton):
    """O'yin kartasi: uy badge+nom | hisob chipi | mehmon nom+badge, pastda bosqich + status."""

    def __init__(self, home, home_col, score, away, away_col, stage, done, cb, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(98),
                         padding=(dp(12), dp(8)), spacing=dp(4), radius=18, **kw)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        left = BoxLayout(spacing=dp(6))
        lb = Badge(home_col, 38, text=initials(home))
        lb.pos_hint = {"center_y": .5}
        left.add_widget(lb)
        left.add_widget(TL(home, 12.5, bold=True))
        box = Glass(size_hint=(None, None), size=(dp(66), dp(40)), radius=12,
                    fill=(0.1, 0.25, 0.4, 0.6), pos_hint={"center_y": .5})
        box.add_widget(TL(score, 20, bold=True, align="center"))
        right = BoxLayout(spacing=dp(6))
        right.add_widget(TL(away, 12.5, bold=True, align="right"))
        rb = Badge(away_col, 38, text=initials(away))
        rb.pos_hint = {"center_y": .5}
        right.add_widget(rb)
        row.add_widget(left)
        row.add_widget(box)
        row.add_widget(right)
        self.add_widget(row)

        info = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(4))
        info.add_widget(TL(stage, 11, MUTED))
        info.add_widget(Widget())
        chip = Glass(size_hint=(None, None), size=(dp(92), dp(26)), radius=13,
                     fill=GREEN if done else INDIGO, border=(1, 1, 1, 0.15),
                     pos_hint={"center_y": .5})
        chip.add_widget(TL("Yakunlangan" if done else "Rejada", 10.5, bold=True, align="center"))
        info.add_widget(chip)
        self.add_widget(info)
        self.bind(on_release=lambda *a: cb())


class PlayerRow(GlassButton):
    """O'yinchi qatori: avatar-halqa + ism/(jamoa · pozitsiya) + gol + karta."""

    def __init__(self, name, sub, color, goals, cards, cb, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(64),
                         padding=dp(10), spacing=dp(10), radius=18, **kw)
        av = Badge(color, 44, text=initials(name))
        av.pos_hint = {"center_y": .5}
        self.add_widget(av)
        col = BoxLayout(orientation="vertical")
        col.add_widget(TL(name, 14, bold=True))
        col.add_widget(TL(sub, 11, MUTED))
        self.add_widget(col)
        g = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(38))
        g.add_widget(TL(str(goals), 15, bold=True, align="center"))
        g.add_widget(TL("gol", 10, MUTED, align="center"))
        self.add_widget(g)
        c = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(40))
        c.add_widget(TL(str(cards), 15, YELLOW, bold=True, align="center"))
        c.add_widget(TL("karta", 10, MUTED, align="center"))
        self.add_widget(c)
        self.bind(on_release=lambda *a: cb())


# ------------------------------------------------------- Header va navigatsiya
class Header(Glass):
    def __init__(self, on_bell, on_user, title="APEX [b]ADMIN[/b]",
                 sub="Turnirni boshqaring", on_search=None,
                 icon="shield-star-outline", **kw):
        super().__init__(size_hint_y=None, height=dp(72), padding=(dp(14), 0),
                         spacing=dp(10), radius=22, **kw)
        lg = Icon(icon, 36, WHITE)
        lg.pos_hint = {"center_y": .5}
        col = BoxLayout(orientation="vertical", padding=(0, dp(14)))
        self.title_lbl = TL(title, 18)
        self.sub_lbl = TL(sub, 11, MUTED)
        col.add_widget(self.title_lbl)
        col.add_widget(self.sub_lbl)
        self.bell = IconBtn("bell-outline")
        self.bell.pos_hint = {"center_y": .5}
        self.bell.bind(on_release=lambda *a: on_bell())
        widgets = [lg, col, self.bell]
        if on_search:
            srch = IconBtn("magnify")
            srch.pos_hint = {"center_y": .5}
            srch.bind(on_release=lambda *a: on_search())
            widgets.append(srch)
        usr = IconBtn("account-outline")
        usr.pos_hint = {"center_y": .5}
        usr.bind(on_release=lambda *a: on_user())
        widgets.append(usr)
        for w in widgets:
            self.add_widget(w)

    def set_sub(self, text):
        self.sub_lbl.text = text

    def set_dot(self, on):
        self.bell.set_dot(on)


class NavItem(ButtonBehavior, BoxLayout):
    def __init__(self, key, icon, label, **kw):
        super().__init__(orientation="vertical", padding=dp(5), spacing=dp(2), **kw)
        self.key = key
        with self.canvas.before:
            self._c = Color(0, 0, 0, 0)
            self._r = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)])
        self.icon = Icon(icon, 24, MUTED, pos_hint={"center_x": .5})
        self.lbl = TL(label, 11, MUTED, align="center", size_hint_y=None, height=dp(16))
        self.add_widget(self.icon)
        self.add_widget(self.lbl)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._r.pos, self._r.size = self.pos, self.size

    def set_active(self, on):
        self._c.rgba = (0.23, 0.51, 0.96, 0.35) if on else (0, 0, 0, 0)
        self.icon.color = self.lbl.color = WHITE if on else MUTED


class NavBar(Glass):
    def __init__(self, on_go, tabs, **kw):
        super().__init__(size_hint_y=None, height=dp(76), padding=dp(6), spacing=dp(4),
                         radius=26, fill=(0.12, 0.12, 0.47, 0.65), **kw)
        self.items = {}
        for key, ic, lab in tabs:
            it = NavItem(key, ic, lab)
            it.bind(on_release=lambda w, k=key: on_go(k))
            self.items[key] = it
            self.add_widget(it)

    def activate(self, key):
        for k, it in self.items.items():
            it.set_active(k == key)


# ------------------------------------------------------------- dialog qatlami
class Wrap(TL):
    """O'raladigan, balandligi matniga qarab o'zgaradigan yorliq.

    TL o'z ichida text_size'ni size'ga bog'laydi: shunda texture_size balandligi
    yorliqning joriy balandligiga teng bo'lib qoladi va avto-balandlik ishlamaydi.
    Bu sinf har o'lchov/matn o'zgarishida text_size=(width, None) qo'yib,
    balandlikni qayta hisoblaydi. Bog'lamalar TL'dan KEYIN quriladi — Kivy'da
    oxirgi bog'langan handler g'olib bo'ladi.

    Matn bo'sh bo'lsa balandlik 0: aks holda Kivy'dagi 100dp standart balandlik
    dialog qatorlarini bo'sh joy bilan shishiradi.
    """

    def __init__(self, text="", size=14, color=WHITE, bold=False, align="left", **kw):
        kw.setdefault("size_hint_y", None)
        super().__init__(text, size, color, bold=bold, align=align, shorten=False,
                         valign="top", **kw)
        self.bind(width=self._remeasure, height=self._remeasure, text=self._remeasure)
        self._remeasure()

    def _remeasure(self, *_):
        self.text_size = (max(self.width, 1), None)
        if not self.text:
            self.height = 0
            return
        self.texture_update()
        h = self.texture_size[1]
        if abs(h - self.height) > 0.5:
            self.height = h


def relayout(widget, passes=3):
    """Butun daraxtni qo'lda joylashtiradi.

    Kivy o'z-o'zidan joylashtirishni faqat ota-vidjet bolasi o'lchami
    o'zgarganda qo'zg'atadi: Window'ga bevosita qo'shilgan overlay'da bu
    zanjir uziladi (dialog ichi bo'sh qolishi shundan). Bir necha marta:
    ota kenglik beradi -> bola balandligini o'lchaydi -> ota yig'adi.
    """
    for _ in range(passes):
        stack = [widget]
        while stack:
            node = stack.pop()
            tu = getattr(node, "texture_update", None)
            if tu is not None:
                tu()                        # Label teksturasi shu yerda hisoblanadi
            do = getattr(node, "do_layout", None)
            if do is not None:
                do()
            stack.extend(getattr(node, "children", []))


class Btn(ButtonBehavior, Glass):
    """Matnli shisha tugma: KivyMD tugmalari o'rniga (text= va on_release=).

    fill=None bo'lsa "ghost" (shaffof, firuza chegarali), aks holda to'la rangli.
    Kenglik matn bo'yicha avtomatik; size_hint_x berilsa shunga bo'ysunadi.
    """

    def __init__(self, text="", fill=None, text_color=WHITE, size=14, h=46, **kw):
        kw.pop("md_bg_color", None)                  # eski KivyMD chaqiruvlari bardoshli bo'lsin
        kw.pop("theme_text_color", None)
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(h))
        rad = kw.pop("radius", 14)
        sx = kw.pop("size_hint_x", None)
        if fill is None:
            super().__init__(radius=rad, **kw)
            self._bcol.rgba = (CYAN[0], CYAN[1], CYAN[2], .55)
            self._base = GLASS
        else:
            super().__init__(radius=rad, fill=fill, border=(1, 1, 1, .16), **kw)
            self._base = fill
        self.lbl = TL(text, size, text_color, bold=True, align="center")
        self.add_widget(self.lbl)
        if sx is None:
            self.size_hint_x = None
            self.width = self._nat = min(dp(240), dp(30) + dp(8.4) * len(text or ""))
        else:
            self.size_hint_x = sx
            self._nat = None
        self.bind(state=self._press)

    def _press(self, *_):
        self._fill.rgba = (1, 1, 1, .26) if self.state == "down" else self._base

    @property
    def text(self):
        return self.lbl.text

    @text.setter
    def text(self, val):
        self.lbl.text = val
        if self._nat is not None:
            self._nat = self.width = min(dp(240), dp(30) + dp(8.4) * len(val or ""))


class MenuItem(ButtonBehavior, Glass):
    """Dialog ro'yxat qatori: sarlavha + (ixtiyoriy) qo'shimcha matn."""

    def __init__(self, text="", secondary_text="", **kw):
        for k in ("bg_color", "theme_text_color", "text_color",
                  "secondary_theme_text_color", "secondary_text_color"):
            kw.pop(k, None)
        kw.setdefault("size_hint_y", None)
        super().__init__(orientation="vertical", radius=14, spacing=dp(2),
                         padding=(dp(12), dp(8)), **kw)
        self._base = self._fill.rgba
        self.lbl = Wrap(text, 14, WHITE, bold=True, align="left")
        self.sub = Wrap(secondary_text, 11.5, MUTED, align="left")
        self.add_widget(self.lbl)
        self.add_widget(self.sub)
        self.bind(minimum_height=self.setter("height"))
        self.text = text
        self.secondary_text = secondary_text
        self.bind(state=self._press)

    def _press(self, *_):
        self._fill.rgba = (1, 1, 1, .20) if self.state == "down" else self._base

    @property
    def text(self):
        return self.lbl.text

    @text.setter
    def text(self, val):
        self.lbl.text = val

    @property
    def secondary_text(self):
        return self.sub.text

    @secondary_text.setter
    def secondary_text(self, val):
        self.sub.text = val
        self.sub.opacity = 1 if val else 0


class Dialog(FloatLayout):
    """Shisha dialog: butun ekranni qoplaydigan qorargan fon + markazdagi karta.
    MDDialog o'rnini bosadi (open()/dismiss() bor); fon bosilsa yopiladi."""

    def __init__(self, title, body=None, actions=None, text=None, **kw):
        super().__init__(size_hint=(1, 1), **kw)
        with self.canvas.before:
            self._dc = Color(0, 0, 0, .62)
            self._dr = Rectangle(pos=self.pos, size=self.size)
        self.card = Glass(orientation="vertical", size_hint=(None, None), radius=24,
                          padding=(dp(16), dp(14)), spacing=dp(10),
                          fill=(0.09, 0.11, 0.30, .86),
                          border=(CYAN[0], CYAN[1], CYAN[2], .55),
                          pos_hint={"center_x": .5, "center_y": .5})
        head = Wrap(title, 16, CYAN, bold=True, align="center")
        self.card.add_widget(head)
        if text:
            self.card.add_widget(Wrap(text, 12.5, WHITE, align="center"))

        self.sv = self.body = None
        self._sv_pref = 0
        if body is not None:
            if getattr(body, "size_hint_y", None) is None or not hasattr(body, "minimum_height"):
                self.card.add_widget(body)          # kontent o'zi balandligini oladi
                if isinstance(body, ScrollView):    # ega balandligi ekranga sig'masa qisqaradi
                    self.sv = body
                    self._sv_pref = body.height or dp(320)
            else:
                self.body = body
                body.size_hint_y = None
                body.bind(minimum_height=body.setter("height"))
                self.sv = ScrollView(size_hint=(1, None), do_scroll_x=False, bar_width=0)
                self.sv.add_widget(body)
                self.card.add_widget(self.sv)

        self.actions = list(actions or [])
        if self.actions:
            # tugmalar sig'masa siqish o'rniga bir necha qatorga bo'linadi
            self.arows = BoxLayout(size_hint_y=None, height=dp(48),
                                   orientation="vertical", spacing=dp(8))
            self.card.add_widget(self.arows)
        self.add_widget(self.card)
        self._busy = False
        self.bind(pos=self._redraw, size=self._redraw)
        self.card.bind(minimum_height=self._redraw)   # bolalar o'lchangani chekkanda qayta hisobla
        self._redraw()

    def _redraw(self, *_):
        if self._busy:
            return                          # joylashtirish ichidan qayta kirishning oldini oladi
        self._busy = True
        try:
            self._dr.pos, self._dr.size = self.pos, self.size
            self.card.width = min(dp(460), max(dp(220), self.width - dp(24)))
            relayout(self.card)
            self._fit_actions()               # qatorlar soni karta balandligiga ta'sir qiladi
            if self.sv is not None:
                cap = max(dp(160), self.height - dp(220))
                if self.body is not None:
                    # ScrollView bolasining kengligini o'zi bermaydi (MDListdan farqli)
                    self.body.width = self.sv.width
                    relayout(self.body)
                    self.sv.height = min(self.body.minimum_height, cap)
                else:
                    self.sv.height = min(self._sv_pref, cap)
            # sv.height endigina o'zgardi: minimum_height'ni shunga qayta
            # hisoblatmasak karta bir qatorga yetmay qisqadi va oxirgi element
            # kesiladi (profile_dialog'dagi 4-yorliq kabi).
            relayout(self.card)
            self.card.height = min(self.card.minimum_height,
                                   max(dp(120), self.height - dp(32)))
            relayout(self.card)
        finally:
            self._busy = False

    def _fit_actions(self):
        """Tugmalarni karta ichki kengligiga qarab qatorlarga bo'lib joylaydi.

        Ilgari sig'magan tugmalar nisbatan siqilardi va matn 'To...' bo'lib
        kesilar edi; endi ikkinchi (uchinchi) qatorga chiqariladi.
        """
        host = getattr(self, "arows", None)
        if host is None:
            return
        inner = self.card.width - self.card.padding[0] - self.card.padding[2]
        gap = dp(10)
        for b in self.actions:
            nat = getattr(b, "_nat", None)
            if nat is not None:
                b.size_hint_x = None
                b.width = min(nat, inner)
        rows, cur, used = [], [], 0.0
        for b in self.actions:
            w = b.width
            if cur and used + gap + w > inner:
                rows.append(cur)
                cur, used = [], 0.0
            used = w if not cur else used + gap + w
            cur.append(b)
        if cur:
            rows.append(cur)
        host.clear_widgets()
        for b in self.actions:
            if b.parent is not None:
                b.parent.remove_widget(b)     # eski qatorlar tugmani ushlab qolgan bo'ladi
        for r in rows:
            row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
            row.add_widget(Widget())           # chapdagi bo'shliq: tugmalar o'ngga tirkaladi
            for b in r:
                row.add_widget(b)
            host.add_widget(row)
        host.height = dp(46) * len(rows) + dp(8) * (len(rows) - 1)

    def open(self):
        if self.parent is None:
            Window.add_widget(self)
        self._redraw()
        Clock.schedule_once(self._redraw, 0)      # matn o'lchamlari bir kadrdan keyin aniq bo'ladi
        Clock.schedule_once(self._redraw, 0.15)

    def dismiss(self, *a):
        if self.parent is not None:
            self.parent.remove_widget(self)

    def on_touch_down(self, touch):
        if self.card.collide_point(*touch.pos):
            super().on_touch_down(touch)
            return True                     # dialog modali: ostaga tegish o'tmaydi
        self.dismiss()
        return True


# ------------------------------------------------ FC uslubidagi o'yinchi kartasi
# Namuna (EA FC 'flash' kartasi) asosida: qalqon tanasi, daraja rangi, OVR +
# pozitsiya, ism bandi, 6 atribut, bayroq va quyi planšetlar. Kartaning butun
# tanasi piksel-piksel tekstura qilib yig'iladi — rasm fayli yoki AI talab
# qilinmaydi, APK hajmi oshmaydi va oflayn ham ishlaydi.

FC_TIERS = [
    # (min OVR, kod, nom, pastki rang, yuqori rang, chegara, siyoh, yorliq siyohi)
    (85, "IC", "Ikonik", hx("#2A1263"), hx("#8B5CF6"), (0.80, 0.66, 1, .95), WHITE, MUTED),
    (75, "G", "Oltin", hx("#7A5708"), hx("#F0CE68"), (1, .92, .62, .95),
     hx("#2A1D02"), hx("#54400B")),
    (65, "S", "Kumush", hx("#5C6472"), hx("#DCE2EC"), (1, 1, 1, .85),
     hx("#1A1D24"), hx("#3B4250")),
    (0, "B", "Bronza", hx("#4E2A0E"), hx("#C98A50"), (1, .80, .58, .9),
     hx("#241203"), hx("#4A2A0C")),
]

_tex_cache = {}


def fc_tier(ovr):
    return next(t for t in FC_TIERS if ovr >= t[0])


def _uzb_flag_texture():
    """O'zbekiston bayrog'i: ko'k (tepa) / oq / yashil (past) qatorlari, ular orasidagi
    qizil chiziqlar, ko'k qatordagi hilol va yulduzchalar. Buffer'da 0-qator pastda."""
    tex = _tex_cache.get("uzb")
    if tex is not None:
        return tex
    W, H = 96, 60
    blue, white = hx("#0099B5")[:3], (1, 1, 1)
    green, red = hx("#1EB53A")[:3], hx("#CE1126")[:3]
    third = H // 3
    stars = [(x, y) for y in (H - 8, H - 17) for x in
             (range(34, 92, 12) if y == H - 8 else range(40, 88, 12))]

    def pixel(x, y):
        if y < third - 1:
            return green
        if y < third:
            return red
        if y < 2 * third - 1:
            return white
        if y < 2 * third:
            return red
        for sx, sy in stars:
            if abs(x - sx) <= 1 and abs(y - sy) <= 1:
                return white
        d1 = (x - 16) ** 2 + (y - (H - 12)) ** 2
        d2 = (x - 20) ** 2 + (y - (H - 12)) ** 2
        return white if d1 <= 49 and d2 > 49 else blue

    buf = bytearray(W * H * 4)
    for y in range(H):
        row = y * W * 4
        for x in range(W):
            c = pixel(x, y)
            i = row + x * 4
            buf[i] = int(c[0] * 255)
            buf[i + 1] = int(c[1] * 255)
            buf[i + 2] = int(c[2] * 255)
            buf[i + 3] = 255
    tex = Texture.create(size=(W, H), colorfmt="rgba")
    tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    tex.mag_filter = tex.min_filter = "linear"
    _tex_cache["uzb"] = tex
    return tex


class UzbFlag(Widget):
    """Kichik O'zbekiston bayrog'i (fayl yo'q, tekstura kod orqali)."""

    def __init__(self, w=38, **kw):
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("size", (dp(w), dp(w * 0.625)))
        super().__init__(**kw)
        with self.canvas:
            Color(1, 1, 1, 1)
            self._r = Rectangle(texture=_uzb_flag_texture(), pos=self.pos, size=self.size)
            self._b = Color(1, 1, 1, .55)
            self._l = Line(rectangle=(self.x, self.y, self.width, self.height), width=1)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._r.pos, self._r.size = self.pos, self.size
        self._l.rectangle = (self.x, self.y, self.width, self.height)

