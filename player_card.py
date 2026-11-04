# -*- coding: utf-8 -*-
"""O'yinchi kartasi — foydalanuvchi bergan `player_card.py` dizayni (qalqon shakli).

Kartaning o'zi (qalqon konturi, gradient, nur chiziqlari, statistika bandlari)
canvas'da chiziladi: rasm fayli yoki AI kerak emas, APK hajmi oshmaydi.

Farqlar (bizning ilovaga moslash):
  * Kivy 2.2.1: `fit_mode` yo'q — `allow_stretch`/`keep_ratio` ishlatiladi.
  * Vidjetlar `main.py` emas, `glassui.py` dan olinadi.
  * Bayroq fayl bo'lmaydi — O'zbekiston bayrog'i kod bilan chiziladi (UzbFlag).
  * Quyi qator (`strip`) ro'yxat orqali beriladi: Apex kartalarida daraja,
    MOTM, token va OVR ko'rsatiladi.
"""
from kivy.core.window import Window
from kivy.graphics import Color, Line, Mesh, Quad, Rectangle, StencilPop, \
    StencilPush, StencilUnUse, StencilUse
from kivy.graphics.tesselator import TYPE_POLYGONS, WINDING_ODD, Tesselator
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.modalview import ModalView
from kivy.utils import get_color_from_hex as hx
from kivymd.icon_definitions import md_icons

from glassui import ICON_FONT, WHITE, Glass, Icon, TL, UzbFlag

ASPECT = 1280 / 900  # karta balandligi / eni

# Qalqon konturi: (x, y) - kartaning ulushlari, y tepadan hisoblanadi
SHIELD = [(.06, .13), (.30, .11), (.38, .065), (.50, .045), (.62, .065), (.70, .11),
          (.94, .13), (.97, .20), (.97, .72), (.93, .83), (.78, .89), (.50, .93),
          (.22, .89), (.07, .83), (.03, .72), (.03, .20)]

THEMES = {
    "purple": dict(grad=("#4B2A84", "#2B1B86", "#15114F"), edge="#B9A8FF", pill="#6B3A9E",
                   panel=(0.27, 0.10, 0.42, 0.88), s1=(0.88, 0.25, 0.98), s2=(0.25, 0.77, 1.0),
                   glow=(0.8, 0.4, 1, 0.35)),
    "gold": dict(grad=("#8A6A12", "#5A430A", "#2E2204"), edge="#F6D87A", pill="#9A7B1E",
                 panel=(0.25, 0.17, 0.03, 0.88), s1=(1, 0.88, 0.5), s2=(1, 0.7, 0.1),
                 glow=(1, 0.8, 0.3, 0.35)),
    "blue": dict(grad=("#1D4ED8", "#12308F", "#0A1A55"), edge="#9CC9FF", pill="#2F5DC0",
                 panel=(0.05, 0.12, 0.35, 0.88), s1=(0.4, 0.9, 1), s2=(1, 1, 1),
                 glow=(0.3, 0.6, 1, 0.35)),
}


def _icon_markup(name):
    return "[font=%s]%s[/font]" % (ICON_FONT, md_icons[name])


class PlayerCard(FloatLayout):
    STAT_ORDER = ("PAC", "SHO", "PAS", "DRI", "DEF", "PHY")

    def __init__(self, name, rating, position, stats, alt_positions=(), extra="++",
                 photo=None, flag=None, league=None, club=None, card_type="R",
                 skill=4, weak=4, score="87.5", theme="purple", width=dp(280),
                 strip=None, **kw):
        super().__init__(size_hint=(None, None), size=(width, width * ASPECT), **kw)
        self.theme_name, self._fs = theme, []
        self._tex = None

        # --- surat: yuklangan foto/AI rasmi bo'lmasa ikonka
        if photo:
            im = Image(source=photo, allow_stretch=True, keep_ratio=True,
                       size_hint=(.64, .43), pos_hint={"center_x": .52, "top": .81})
            self.add_widget(im)
        else:
            self._icon("account", .30, (.64, .43), {"center_x": .5, "top": .81},
                       (1, 1, 1, 0.25))

        self._icon("soccer", .06, (.1, .06), {"center_x": .5, "center_y": .83})

        self._t(str(rating), .15, {"x": .12, "top": .79}, (.27, .10))
        self._t(position, .062, {"x": .12, "top": .70}, (.27, .05))
        self._t(extra, .05, {"x": .12, "top": .655}, (.27, .04))

        # o'ng tomondagi muqobil pozitsiyalar
        col = BoxLayout(orientation="vertical", spacing=dp(1), size_hint=(.125, .235),
                        pos_hint={"right": .975, "top": .74})
        for p in alt_positions[:4]:
            g = Glass(radius=3, fill=hx(THEMES[theme]["pill"]), border=(1, 1, 1, 0.45))
            g.add_widget(self._lbl(p, .038, align="center"))
            col.add_widget(g)
        self.alt_col = col
        self.add_widget(col)

        # chap tomondagi uslub belgisi (romb ichida ikonka)
        self._icon("strategy", .05, (.1, .06), {"center_x": .105, "center_y": .455})

        # ism
        self._t(name, .085, {"center_x": .5, "center_y": .335}, (.8, .09))

        # statistika: 6 ustun
        row = BoxLayout(size_hint=(.78, .12), pos_hint={"center_x": .5, "center_y": .26})
        for key in self.STAT_ORDER:
            c = BoxLayout(orientation="vertical")
            c.add_widget(self._lbl(key, .04, bold=False, align="center"))
            c.add_widget(self._lbl(str(stats.get(key, "-")), .075, align="center"))
            row.add_widget(c)
        self.add_widget(row)

        # bayroq / liga / klub
        icons = BoxLayout(size_hint=(.34, .07), pos_hint={"center_x": .5, "center_y": .175},
                          spacing=dp(6))
        for src, fb in ((flag, "flag"), (league, "trophy-variant-outline"),
                        (club, "shield-half-full")):
            if src:
                icons.add_widget(Image(source=src, allow_stretch=True, keep_ratio=True))
            elif fb == "flag":
                # davlat har doim O'zbekiston: bayroq fayl emas, kod bilan chiziladi
                fl = UzbFlag()
                fl.size_hint = (1, None)
                fl.bind(width=lambda i, w: setattr(i, "height", w * 0.625))
                icons.add_widget(fl)
            else:
                ic = Icon(fb, 10, WHITE)
                ic.size_hint = (1, 1)
                self._reg(ic, .07)
                icons.add_widget(ic)
        self.add_widget(icons)

        # pastki chiziq: 4 planšet (dizayn bo'yicha standart yoki `strip` bilan)
        if strip is None:
            strip = ((card_type, .9, False), ("%d%s" % (skill, _icon_markup("star")), 1.2, False),
                     ("%d%s" % (weak, _icon_markup("shoe-sneaker")), 1.2, False),
                     (str(score), 1.4, True))
        strip_row = BoxLayout(size_hint=(.58, .055), pos_hint={"center_x": .5, "center_y": .09},
                              spacing=dp(1))
        self.strip_cells = []
        for txt, w, green in strip:
            g = Glass(radius=4, size_hint_x=w, border=(1, 1, 1, 0.5),
                      fill=hx("#4FCFA2") if green else hx(THEMES[theme]["pill"]))
            g.add_widget(self._lbl(txt, .04, color=hx("#0B2B20") if green else WHITE,
                                   align="center"))
            self.strip_cells.append((g, green))
            strip_row.add_widget(g)
        self.add_widget(strip_row)

        self.bind(pos=self._draw, size=self._upd)
        self._upd()

    # ---------------------------------------------------------- yordamchilar
    def _reg(self, widget, frac):
        self._fs.append((widget, frac))

    def _lbl(self, text, frac, color=WHITE, bold=True, align="center"):
        lab = TL(text, 10, color, bold, align=align, shorten=False)
        self._reg(lab, frac)
        return lab

    def _icon(self, name, frac, size, pos, color=WHITE):
        ic = Icon(name, 10, color)
        ic.size_hint, ic.pos_hint = size, pos
        self._reg(ic, frac)
        self.add_widget(ic)
        return ic

    def _t(self, text, frac, pos, size, **kw):
        lab = self._lbl(text, frac, **kw)
        lab.size_hint, lab.pos_hint = size, pos
        self.add_widget(lab)
        return lab

    def _pts(self, inset=0.0):
        pts = []
        for fx, fy in SHIELD:
            fx = .5 + (fx - .5) * (1 - inset)
            fy = .5 + (fy - .5) * (1 - inset)
            pts += [self.x + fx * self.width, self.y + (1 - fy) * self.height]
        return pts

    @staticmethod
    def _mesh(points):
        tess = Tesselator()
        tess.add_contour(points)
        if not tess.tesselate(WINDING_ODD, TYPE_POLYGONS):
            return
        for verts, idx in tess.meshes:
            Mesh(vertices=verts, indices=idx, mode="triangle_fan")

    def _texture(self):
        if self._tex is None:
            th = THEMES[self.theme_name]
            tex = Texture.create(size=(1, 3), colorfmt="rgba")
            buf = bytes(int(v * 255) for c in th["grad"] for v in hx(c))
            tex.blit_buffer(buf, colorfmt="rgba", bufferfmt="ubyte")
            tex.mag_filter = tex.min_filter = "linear"
            self._tex = tex
        return self._tex

    # ----------------------------------------------------------------- chizish
    def _upd(self, *_):
        for w, frac in self._fs:
            w.font_size = frac * self.width
        self._draw()

    def _draw(self, *_):
        th = THEMES[self.theme_name]
        c, x, y, w, h = self.canvas.before, self.x, self.y, self.width, self.height
        c.clear()
        outer, inner = self._pts(0), self._pts(0.03)
        with c:
            Color(*th["glow"])
            Line(points=outer, close=True, width=dp(5))
            Color(*hx(th["edge"]))
            self._mesh(outer)
            # ichki qism: qalqon bo'yicha qirqilgan
            StencilPush()
            self._mesh(inner)
            StencilUse()
            Color(1, 1, 1, 1)
            Rectangle(texture=self._texture(), pos=(x, y), size=(w, h))
            for col, a, k in ((th["s1"], .6, 0), (th["s2"], .5, 1), (th["s1"], .35, 2)):
                Color(col[0], col[1], col[2], a)
                Line(bezier=[x - .05 * w, y + (.45 + .08 * k) * h,
                             x + .35 * w, y + (.62 + .05 * k) * h,
                             x + .7 * w, y + (.55 + .12 * k) * h,
                             x + 1.05 * w, y + (.85 - .05 * k) * h], width=dp(2.5 - .5 * k))
            Color(*th["panel"])
            Rectangle(pos=(x, y + .14 * h), size=(w, .24 * h))
            StencilUnUse()
            self._mesh(inner)
            StencilPop()
            # ichki chegara
            Color(1, 1, 1, 0.35)
            Line(points=inner, close=True, width=1)
            # uslub romb belgisi
            cx, cy, rx, ry = x + .105 * w, y + .455 * h, .06 * w, .05 * h
            Color(*hx(th["pill"]))
            Quad(points=[cx - rx, cy, cx, cy + ry, cx + rx, cy, cx, cy - ry])
            Color(1, 1, 1, 0.9)
            Line(points=[cx - rx, cy, cx, cy + ry, cx + rx, cy, cx, cy - ry], close=True,
                 width=1.2)

    def set_theme(self, name):
        self.theme_name = name
        self._tex = None
        for g in self.alt_col.children:
            g.set_style(fill=hx(THEMES[name]["pill"]))
        for g, green in self.strip_cells:
            if not green:
                g.set_style(fill=hx(THEMES[name]["pill"]))
        self._draw()


def show_card(width=dp(300), **card_kw):
    """Kartani qorong'i fonda popup sifatida ko'rsatadi (tashqariga bossangiz yopiladi)."""
    card = PlayerCard(width=width, **card_kw)
    mv = ModalView(size_hint=(None, None), size=card.size, background="",
                   background_color=(0, 0, 0, 0), overlay_color=(0, 0, 0, 0.75))
    mv.add_widget(card)
    mv.open()
    return mv


if __name__ == "__main__":
    from kivy.app import App

    COLE = dict(name="Cole", rating=87, position="RW", extra="++",
                alt_positions=("RM", "LM", "CAM", "LW"),
                stats=dict(PAC=88, SHO=84, PAS=86, DRI=90, DEF=51, PHY=72))

    class Demo(App):
        def build(self):
            Window.size = (390, 800)
            root = FloatLayout()
            self.card = PlayerCard(width=dp(300), pos_hint={"center_x": .5, "center_y": .5},
                                   **COLE)
            self.names, self.i = list(THEMES), 0
            self.card.bind(on_touch_down=self.cycle)
            root.add_widget(self.card)
            return root

        def cycle(self, card, touch):
            if card.collide_point(*touch.pos):
                self.i = (self.i + 1) % len(self.names)
                card.set_theme(self.names[self.i])

    Demo().run()
