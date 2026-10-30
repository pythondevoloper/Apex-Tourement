[app]
title = Apex Tournament
package.name = apextournament
package.domain = org.apex
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0

# KivyMD 1.1.1 + Kivy 2.2.1 barqaror kombinatsiya
requirements = python3,kivy==2.2.1,kivymd==1.1.1,pillow

# Barqaror python-for-android versiyasi (master Python 3.14 ishlatadi va Kivy 2.2.1 bilan mos emas)
p4a.branch = v2024.01.21

orientation = portrait
fullscreen = 0

# Internet yoki xotira ruxsatlari kerak emas (ma'lumot app ichki papkasida saqlanadi)
android.permissions =

android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a, x86_64
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
