# -*- coding: utf-8 -*-
"""APK ikonalarini foydalanuvchi bergan oltin kubok rasminidan yig'adi.

    python scripts/make_icons.py <manba.jpg|png> [band|plaque]

`band`   — ikonaning pastiga to'q ko'mir fonli oltin yozuvli lenta (standart)
`plaque` — yozuv kubokning o'zidagi granit postamentdagi bo'sh taxtacha ustiga

Chiqadi: icon.png (o'yinchi — yozuvsiz), icon_admin.png, icon_captain.png,
icon_referee.png (512x512 PNG).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
APEX = os.path.dirname(HERE)

SIZE = 512
NAVY = (11, 20, 55)          # ilova palitrasidagi #0B1437
GOLD = (232, 195, 106)
ENGRAVED = (58, 42, 8)
WHITE_MIN = 236              # bu yorqlikdagi fon toq oqga aylantiriladi
FONTS = ("georgiab.ttf", "timesbd.ttf", "arialbd.ttf")

# (fayl, yozuv) — yozuv bo'sh bo'lsa ikonada yozuv bo'lmaydi
ICONS = [("icon.png", ""),
         ("icon_admin.png", "ADMIN"),
         ("icon_captain.png", "CAPTAIN"),
         ("icon_referee.png", "REFEREE")]

# Berilgan rasmda kubok egan maydon (manba o'lchami REF_W x REF_H deb o'lchangan)
REF_W, REF_H = 1408, 768
TROPHY_BOX = (334, 16, 1074, 756)
# Postamentdagi bo'sh oltin taxtacha (manba koordinatalari)
PLAQUE_BOX = (625, 655, 785, 705)


def font(size):
    for name in FONTS:
        path = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def square_crop(src):
    """Kubokni yon tomonlari kesilmagan kvadratga sig'diradi, fonni oqartiradi."""
    fx, fy = src.width / float(REF_W), src.height / float(REF_H)
    x0, y0, x1, y1 = TROPHY_BOX
    crop = src.crop((int(x0 * fx), int(y0 * fy), int(x1 * fx), int(y1 * fy)))
    side = min(crop.size)
    left = (crop.width - side) // 2
    top = (crop.height - side) // 2
    crop = crop.crop((left, top, left + side, top + side)).resize((SIZE, SIZE), Image.LANCZOS)
    arr = np.asarray(crop).copy()
    arr[arr.min(axis=2) >= WHITE_MIN] = 255      # gradient fon => toq oq
    return Image.fromarray(arr)


def draw_band(img, word):
    """Pastga oltin yozuvli lenta qo'shadi, kubokni yuqoriga siqib joylaydi."""
    pad, band_h = 18, 76
    trophy = img.resize((int(SIZE * 0.82), int(SIZE * 0.82)), Image.LANCZOS)
    out = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
    out.paste(trophy, ((SIZE - trophy.width) // 2, 4))
    d = ImageDraw.Draw(out)
    top = SIZE - band_h - pad
    d.rounded_rectangle([pad, top, SIZE - pad, SIZE - pad], radius=20, fill=NAVY)
    size = 44
    f = font(size)
    while size > 20 and d.textlength(word, font=f) > SIZE - 2 * (pad + 14):
        size -= 2
        f = font(size)
    w = d.textlength(word, font=f)
    box = d.textbbox((0, 0), word, font=f)
    d.text(((SIZE - w) / 2.0, top + (band_h - (box[3] - box[1])) / 2.0 - box[1]),
           word, font=f, fill=GOLD)
    return out


def draw_plaque(img, word):
    """Yozuvni rasmning o'zidagi taxtacha ustiga yozadi (juda mayda bo'ladi)."""
    k = SIZE / float(TROPHY_BOX[3] - TROPHY_BOX[1])
    x0 = int((PLAQUE_BOX[0] - TROPHY_BOX[0]) * k)
    x1 = int((PLAQUE_BOX[2] - TROPHY_BOX[0]) * k)
    y0 = int((PLAQUE_BOX[1] - TROPHY_BOX[1]) * k)
    y1 = int((PLAQUE_BOX[3] - TROPHY_BOX[1]) * k)
    d = ImageDraw.Draw(img)
    size = min(26, max(10, (y1 - y0) - 6))
    f = font(size)
    while size > 8 and d.textlength(word, font=f) > (x1 - x0) - 6:
        size -= 1
        f = font(size)
    w = d.textlength(word, font=f)
    d.text(((x0 + x1 - w) / 2.0, (y0 + y1 - size) / 2.0), word, font=f, fill=ENGRAVED)
    return img


def main():
    src_path = sys.argv[1]
    variant = sys.argv[2] if len(sys.argv) > 2 else "band"
    out_dir = sys.argv[3] if len(sys.argv) > 3 else APEX
    src = Image.open(src_path).convert("RGB")
    for name, word in ICONS:
        img = square_crop(src)
        if word:
            img = draw_band(img, word) if variant == "band" else draw_plaque(img, word)
        path = os.path.join(out_dir, name)
        img.save(path)
        print("  %s  (%dx%d, %s)" % (path, SIZE, SIZE, word or "yozuvsiz"))


if __name__ == "__main__":
    main()
