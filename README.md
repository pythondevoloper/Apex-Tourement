# Apex Pro League: ikkita ilova + umumiy baza

Endi **ikkita alohida ilova** bor va ikkalasi **bitta bulutli bazani** (Firebase) ko'radi:

| Ilova | Kimga | Nima qila oladi |
|---|---|---|
| **Apex Tournament** | O'yinchilar, kapitanlar | Ro'yxatdan o'tish (raqam, pozitsiya, davlat), draft, boshlang'ich 6, jadval, statistika |
| **Apex Admin** | Faqat admin | Hammasi: sozlash, draft ochish/yopish, gol, assist, kartochka, almashtirish, MOTM, natija, o'yinchi/guruh/logo tahriri |

Har qanday telefondagi o'zgarish 6 soniya ichida boshqa telefonlarda ko'rinadi.

## 1. Firebase sozlash (bir marta, bepul)

1. https://console.firebase.google.com ga kiring, **Add project** (Analytics shart emas).
2. **Build -> Realtime Database -> Create database**. Test emas, **locked mode** tanlang. Tepada chiqqan manzilni
   (`https://....firebaseio.com` yoki `....firebasedatabase.app`) nusxalang.
3. **Build -> Authentication -> Get started -> Email/Password** ni yoqing. **Users -> Add user** bilan admin hisobini yarating
   (email + kamida 6 belgili parol). Yaratilgach shu qatordagi **User UID** ni nusxalang.
4. **Project settings (tishli g'ildirak) -> General -> Web API Key** ni nusxalang.
5. **Realtime Database -> Rules** bo'limiga `database.rules.json` ichini qo'ying. Ichidagi `ADMIN_UID_SHU_YERGA` ni
   3-qadamdagi UID bilan almashtiring va **Publish** bosing.

## 2. config.py ni to'ldirish

```python
FIREBASE_DB_URL = "https://...firebaseio.com"   # 2-qadam
FIREBASE_API_KEY = "AIza..."                     # 4-qadam
ADMIN_EMAIL = "admin@example.com"                # 3-qadamdagi email
```

## 3. GitHub

Repozitoriy ildizida shu fayllar bo'lsin (eski `main.py` va `buildozer.spec` ni **o'chiring**):

```
common.py  cloud.py  config.py  player.py  admin.py
buildozer_player.spec  buildozer_admin.spec
trophy.png  icon.png  icon_admin.png  presplash.png  logo_1.png ... logo_12.png
.github/workflows/build.yml      <- build.yml faylining ichi
```

Yuklagach **Actions** da ikkita build ishlaydi. Tugagach **Artifacts** dan ikkita APK yuklab oling:
`apex-player-apk` (o'yinchilarga tarqating) va `apex-admin-apk` (faqat o'zingizda qolsin).

## 4. Birinchi ishga tushirish

1. **Apex Admin** ni oching. Kirish ekranida 1-qadamda yaratgan **email va parolingizni** kiriting.
2. Kirgach turnir sozlanmagan bo'lsa, **sozlash** ochiladi:
   - 1/2: guruhlar sonini `-` / `+` tugmalari bilan tanlang.
   - 2/2: har bir guruh uchun **nom, kapitan, PIN va logo** kiriting, so'ng **Saqlash va boshlash**.
3. O'yinchilar **Apex Tournament** da **Ro'yxatdan o'tish** ekranini to'ldiradi: ism, raqam, pozitsiya, davlat
   (tepada jonli kartochka ko'rinib turadi).
4. Kapitanlar draftda navbat bilan tanlaydi. Admin keyin o'yinlar jadvalini yaratadi, gol/assist/kartochka kiritadi.

## Ilova yopilib qolsa

Ilovada kutilmagan xato bo'lsa, u endi yopilmaydi: ekranda **"Xatolik yuz berdi"** oynasi chiqadi. Shu oynaning
skrinshotini yuboring. Xato matni telefonda `crash.log` fayliga ham yoziladi.

## OVR qanday hisoblanadi

`OVR = boshlang'ich reyting (standart 60, admin o'zgartiradi) + jami ball / 3 + 2 x Player of the Match`, 40 dan 99 gacha.

## Xavfsizlik: nima qat'iy, nima yumshoq

- **Qat'iy:** admin amallari (gol, kartochka, natija, o'chirish, guruh/logo/OVR) faqat Firebase hisobi bilan kirgan adminga ruxsat etilgan.
  O'yinchi ilovasi buni qila olmaydi, hatto kod o'zgartirilsa ham: qoidalarni server tekshiradi.
- **Qat'iy:** draft yopiq bo'lsa o'yinchi tanlash yoki ro'yxatdan o'tish serverda rad etiladi; bitta o'yinchini ikki kapitan tanlay olmaydi.
- **Yumshoq:** kapitan PIN kodi bazada hash ko'rinishida ochiq turadi. Texnik bilimli o'yinchi uni topib, boshqa kapitan nomidan
  tarkib kiritishi yoki navbat tartibini buzishi mumkin. Do'stlar ligasi uchun yetarli; qat'iy himoya uchun Cloud Functions kerak (pullik reja).
- Baza hamma uchun **o'qishga ochiq** (ismlar, natijalar). Maxfiy ma'lumot kiritmang.

## Cheklovlar

- Logo: 12 ta tayyor logodan tanlanadi. Telefondan o'z rasmingizni yuklash hali yo'q.
- Internet yo'q bo'lsa ilova oxirgi yuklangan ma'lumotni ko'rsatadi (OFLAYN belgisi bilan), lekin o'zgartirish saqlanmaydi.
- Eski (bitta telefonli) versiyadagi ma'lumotlar ko'chmaydi: admin ilovasida turnirni qaytadan sozlaysiz.
