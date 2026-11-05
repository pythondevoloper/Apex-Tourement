# -*- coding: utf-8 -*-
"""
Ish stoli (Windows) uchun .exe yasash — PyInstaller.

    python scripts/build_exe.py              # to'rtala ilova
    python scripts/build_exe.py admin        # bittasi (player|admin|referee|captain)

Chiqadi: dist/ApexAdmin.exe, dist/ApexTournament.exe, dist/ApexReferee.exe,
          dist/ApexCaptain.exe

Bepul: PyInstaller + hooks-contrib (GPL, pul talab qilmaydi).
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPDIR = os.path.join(ROOT, "dist")
WORKDIR = os.path.join(ROOT, "build")
ICO_DIR = os.path.join(ROOT, "build", "ico")

APPS = {
    "player": ("player.py", "ApexTournament", "icon.png"),
    "admin": ("admin.py", "ApexAdmin", "icon_admin.png"),
    "referee": ("referee.py", "ApexReferee", "icon_referee.png"),
    "captain": ("captain.py", "ApexCaptain", "icon_captain.png"),
}

# common.py HERE ga qo'yadigan fayllar (trophy.png, logo_1..12.png) — exe ichida
# shu papkada bo'lishi kerak, aks holda logo/troph ko'rinmaydi.
DATA = ["trophy.png"] + ["logo_%d.png" % n for n in range(1, 13)]


def make_ico(png_name, ico_name):
    """PNG -> .ico (PyInstaller Windows'da faqat .ico qabul qiladi)."""
    from PIL import Image
    src = os.path.join(ROOT, png_name)
    if not os.path.exists(src):
        return None
    out = os.path.join(ICO_DIR, ico_name)
    im = Image.open(src).convert("RGBA").resize((256, 256), Image.LANCZOS)
    im.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return out


def build(kind):
    entry, name, icon_png = APPS[kind]
    ico = make_ico(icon_png, name + ".ico")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", name,
        "--distpath", APPDIR,
        "--workpath", os.path.join(WORKDIR, name),
        "--specpath", WORKDIR,
        "--collect-all", "kivymd",
        "--collect-data", "kivy",
        "--exclude-module", "gemini_secret",
    ]
    if ico:
        cmd += ["--icon", ico]
    for d in DATA:
        p = os.path.join(ROOT, d)
        if os.path.exists(p):
            cmd += ["--add-data", p + os.pathsep + "."]
    cmd.append(os.path.join(ROOT, entry))
    print("\n=== %s (%s) ===" % (name, entry))
    r = subprocess.run(cmd, cwd=ROOT)
    exe = os.path.join(APPDIR, name + ".exe")
    if r.returncode == 0 and os.path.exists(exe):
        print("  TAYYOR: %s  (%.1f MB)" % (exe, os.path.getsize(exe) / 1048576.0))
        return True
    print("  XATO: %s yigilmadi (chiqish kodi %s)" % (name, r.returncode))
    return False


def main():
    if sys.platform != "win32":
        print(".exe faqat Windows'da yig'iladi (bu yer: %s)" % sys.platform)
        return 1
    os.makedirs(ICO_DIR, exist_ok=True)
    want = sys.argv[1:] or list(APPS)
    bad = [w for w in want if w not in APPS]
    if bad:
        print("Noma'lum ilova: %s  (player|admin|referee|captain)" % ", ".join(bad))
        return 1
    ok = all(build(k) for k in want)
    print("\n%d ta exe: %s" % (len(want), "hammasi tayyor" if ok else "ba'rilari xatoli"))
    print("Ishga tushganda ma'lumot: %APPDATA%\\<IlovaNomi>\\ (cache, crash.log)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
