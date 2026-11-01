# Apex Pro League: ikkita ilova + umumiy baza

Endi **ikkita alohida ilova** bor va ikkalasi **bitta bulutli bazani** (Firebase) ko'radi:

| Ilova | Kimga | Nima qila oladi |
|---|---|---|
| **Apex Tournament** | O'yinchilar, kapitanlar | Ro'yxatdan o'tish (raqam, pozitsiya, davlat), draft, boshlang'ich 6, jadval, statistika, APEX TOKEN, transfer so'rovi, Market (kapitan) |
| **Apex Admin** | Faqat admin | Hammasi: sozlash, draft ochish/yopish, gol, assist, kartochka, almashtirish, MOTM, natija, o'yinchi/guruh/logo tahriri, tokenlar, jarimalar, hakamlar, Market, FINAL |
| **Apex Referee** | Admin tayinlagan hakam | Gol va assistlarni kiritish, bayonnomani ko'rish |

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
common.py  cloud.py  config.py  player.py  admin.py  referee.py
buildozer_player.spec  buildozer_admin.spec  buildozer_referee.spec
version.json  requirements.txt
trophy.png  icon.png  icon_admin.png  presplash.png  logo_1.png ... logo_12.png
.github/workflows/build.yml      <- build.yml faylining ichi
```

Yuklagach **Actions** da uchta build ishlaydi. Tugagach **Artifacts** dan APK larni yuklab oling:
`apex-player-apk` (o'yinchilarga), `apex-admin-apk` (faqat o'zingizda) va `apex-referee-apk` (hakamlarga).

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
- **Yumshoq:** transfer/muzokara, Market xaridi, xabarnomalar va hakam gollari ham PIN darajasida himoyalangan
  (qoidalar faqat maydonlarning buzilmasligini tekshiradi, kimligini emas). Hakam PIN i ham shu turdagi himoya.
- Baza hamma uchun **o'qishga ochiq** (ismlar, natijalar). Maxfiy ma'lumot kiritmang.

## APEX TOKEN (o'yinchi valyutasi)

- Har bir o'yinchi ro'yxatdan o'tganda **500 APEX TOKEN** oladi; admin istalgan o'yinchiga token
  qo'shadi yoki ayiradi (Admin panel -> "O'yinchiga APEX TOKEN qo'shish / ayirish").
- Jarimalar (admin belgilaydi, Admin panel -> "Davomat jarimalari"):
  | Holat | Token |
  |---|---|
  | O'yinga kech qolish | -100 |
  | O'yinga kelmaslik (zaxirada) | -200 |
  | O'yinga kelmaslik (asosiy tarkibda) | -300 |
  | Qizil kartochka (avtomatik) | -50 |
- Token **0** bo'lsa: o'yinchi asosiy tarkibga qo'yilmaydi va OVR har 2 kunda 1 ballga pasayadi
  (token qayta musbat bo'lsa pasayish to'xtaydi).

## Transfer list va muzokara (APEX PRO TOKEN)

1. O'yinchi o'z kartochkasidan ("Profil" -> kartochka -> "Transfer listga so'rov") so'rov yuboradi:
   o'yinchiga "so'rovingiz tez orada ko'rib chiqiladi", kapitaniga "<ism> transfer listga qo'shilish
   uchun so'rov yubordi" xabari boradi.
2. Kapitan (Market oynasi -> "Transfer so'rovlarim va muzokaralar") qabul qilsa o'yinchiga
   "so'rovingiz qabul qilindi va transfer listga qo'shildingiz", rad etsa "so'rovingiz rad etildi" xabari boradi.
3. Boshqa jamoa kapitani transfer listdagi o'yinchi uchun **taklif** yuboradi: sotuvchi kapitaniga
   "biz sizning <ism> jamoadoshingizni sotib olishga qaror qildik" xabari va **Muzokara** tugmasi keladi.
4. Muzokarada kapitanlar taklif / qarshi taklif beradi yoki "Kelishdim" bosadi. Kelishilgan token
   xaridor jamoa hisobidan sotuvchi jamoa hisobiga o'tadi, o'yinchi yangi jamoaga ko'chadi.
5. Har bir jamoaning **APEX PRO TOKEN** balansi boshida 0; turnir (FINAL) g'olibi **+200** oladi.

## Market (faqat kapitanlar)

Admin "Market: narsa qo'shish / o'chirish" orqali rasm (telefondan), narx va sonini qo'yadi.
Kapitanlar Market oynasida o'z jamoasi balansidagi APEX PRO TOKEN evaziga sotib oladi.

## Guruh logosi

Kapitan "Bayonnoma" oynasidagi "Kapitan: guruh logosini yuklash" tugmasi orqali 12 ta tayyor
logodan tanlaydi yoki **telefondan o'z rasmini yuklaydi** (rasm siqilib bazada saqlanadi).

## Turnir formati

- **8 yoki kamroq jamoa:** bitta guruh, har bir juftlik 2 marta (uy va mehmonda) o'ynaydi
  (3 jamoa bo'lsa har jamoa 4 tadan o'yin). Jadval (ochko, G/D/M, to'plar nisbati) avtomatik.
- Guruh o'yinlari tugagach 1- va 2-o'rin **FINAL** ga chiqadi (admin "FINAL o'yinini yaratish"),
  3-o'rin va undan past jamoalar musobaqani yakunlaydi.
- **8 tadan ko'p jamoa:** avtomatik guruh bosqichi (2 guruh), har guruhda bir davra,
  so'ng ikki guruh g'olibi FINAL da o'ynaydi.

## Hakam ilovasi

Admin "Hakamlar boshqaruvi" da hakam (ism + PIN) qo'shadi. Hakam **Apex Referee** ilovasida
ism va PIN bilan kirib, gol va assistlarni kiritadi (hisob avtomatik hisoblanadi).
Hakam jamoa kapitani yoki boshqa shaxs bo'lishi mumkin.

## Ilova yangilanishi

1. Kodni o'zgartirib `common.py` dagi `VERSION_CODE` ni oshiring va `version.json` da
   `version` ni yangilang (izoh va link ham shu yerda).
2. Repo ga `v2`, `v3` ko'rinishidagi **teg** bilan push qiling: Actions uchta APK ni qurib
   **GitHub Release** ga yuklaydi.
3. Har bir foydalanuvchi ilovani ochganda yangi versiya xabarini ko'radi ("Yuklab olish" tugmasi
   release sahifasini ochadi). Barcha ma'lumotlar Firebase bazasida qoladi — yangilanish ularni o'zgartirmaydi.

## Android 10 va planshetlar

Uchala ilova ham Android 5.0 (API 21) dan yuqori, shu jumladan **Android 10** va planshetlarda
ishlaydi: `orientation = all` (portret + landshaft), minapi 21. Planshetda landshaft rejimda
ochish mumkin.

## Cheklovlar

- Logo: 12 ta tayyor logo yoki telefondan yuklangan rasm (siqilgan holda bazada saqlanadi).
- Internet yo'q bo'lsa ilova oxirgi yuklangan ma'lumotni ko'rsatadi (OFLAYN belgisi bilan), lekin o'zgartirish saqlanmaydi.
- Eski (bitta telefonli) versiyadagi ma'lumotlar ko'chmaydi: admin ilovasida turnirni qaytadan sozlaysiz.
