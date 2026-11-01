[app]
title = Apex Admin
package.name = apexadmin
package.domain = org.apex
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0

# KivyMD 1.1.1 + Kivy 2.2.1 barqaror kombinatsiya
requirements = python3,kivy==2.2.1,kivymd==1.1.1,pillow,openssl,certifi

# Barqaror python-for-android versiyasi (master Python 3.14 ishlatadi va Kivy 2.2.1 bilan mos emas)
p4a.branch = v2024.01.21

icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #0B1437

# Telefon va planshet: portret ham, landshaft ham
orientation = all
fullscreen = 0

# Internet kerak: ma'lumotlar Firebase bazasida saqlanadi
android.permissions = INTERNET,ACCESS_NETWORK_STATE

# Android 5.0 (API 21) dan boshlab, Android 10 (API 29) va planshetlar ham kiradi
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a, x86_64
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
