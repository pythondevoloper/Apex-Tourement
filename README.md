# Apex Pro League: to'rtta ilova + umumiy baza

**To'rtta alohida ilova** bor va to'rtalasi **bitta bulutli bazani** (Firebase) ko'radi:

| Ilova | Kimga | Nima qila oladi |
|---|---|---|
| **Apex Tournament** | O'yinchilar | O'zi ro'yxatdan o'tish (ism, familiya, raqam, pozitsiya), guruhga biriktirilgach: o'z kartasi va statistikasi, jadval, APEX TOKEN, xabarnomalar, Market/narxlar (o'qish uchun) |
| **Apex Captain** | Har bir jamoa kapitani | **Login + parol** bilan kiradi (login/parolni faqat admin beradi): boshlang'ich 6 ni belgilash, jamoasi, transfer so'rovlari va muzokaralar, Market xaridlari, guruh logosi |
| **Apex Admin** | Faqat admin | Hammasi: sozlash, kvota bo'lishi/tozalash, gol, assist, kartochka, almashtirish, MOTM, natija, o'yinchi/guruh/logo tahriri, kapitan loginlari, o'yinchini to'liq o'chirish, tokenlar, jarimalar, hakamlar, Market, FINAL |
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

> Gemini AI kaliti `config.py` da EMAS — u `.gitignore` dagi `gemini_secret.py` faylida turadi
> (qarang: 5.2 bo'lim). Shuning uchun kalit GitHub ga tushmaydi.

## 3. GitHub

Repozitoriy ildizida shu fayllar bo'lsin (eski `main.py` va `buildozer.spec` ni **o'chiring**):

```
common.py  cloud.py  config.py  gemini.py  push.py  glassui.py  player_card.py
player.py  admin.py  referee.py  captain.py
buildozer_player.spec  buildozer_admin.spec  buildozer_referee.spec  buildozer_captain.spec
version.json  requirements.txt  database.rules.json
trophy.png  icon.png  icon_admin.png  icon_captain.png  icon_referee.png
presplash.png  logo_1.png ... logo_12.png
.github/workflows/build.yaml
```

Ikonalar bitta oltin kubok rasminidan yig'iladi (`scripts/make_icons.py`):

```
python scripts/make_icons.py <kubok.jpg> band
```

`icon.png` — o'yinchi uchun yozuvsiz; qolgan uchta ikonaning pastida ko'mir rangli
lentada **ADMIN / CAPTAIN / REFEREE** yozuvi. CI `icon_<app>.png` ni olib `icon.png`
qilib qo'yadi, fayl bo'lmasa `icon.png` ga qaytadi.

Yuklagach **Actions** da to'rtta build ishlaydi. Tugagach **Artifacts** dan APK larni yuklab oling:
`apex-player-apk` (o'yinchilarga), `apex-captain-apk` (kapitanlarga), `apex-admin-apk` (faqat
o'zingizda) va `apex-referee-apk` (hakamlarga).

## 4. Birinchi ishga tushirish

1. **Apex Admin** ni oching. Kirish ekranida 1-qadamda yaratgan **email va parolingizni** kiriting.
2. Kirgach **Turnirni boshlash** tugmasini bosing. Guruhlar soni so'ralmaydi — guruhlar keyin,
   Admin paneldan istalgan payt qo'shiladi. Bu paytdan boshlab o'yinchilar ro'yxatdan o'ta oladi.
3. O'yinchilar **Apex Tournament** da o'zlari ro'yxatdan o'tadi: **Ism**, **Familiya**,
   **o'yindagi raqami** (1-99) va **pozitsiyasi** (GK / DF / MF / FW) kiritiladi va bazaga saqlanadi.
   Pozitsiya tanlanmasa ro'yxatdan o'tish qabul qilinmaydi. So'ng o'yinchida
   *"Kuting — admin sizni guruhga biriktirgach ilova to'liq ishga tushadi"* xabari ko'rinadi.
4. Admin guruh qo'shadi va ro'yxatdan o'tgan o'yinchilar orasidan **kapitanni tanlaydi**. Guruh
   qo'shishda va kapitanni almashtirishda admin **kapitan logini va parolini** o'zi belgilaydi
   (masalan `guruh-a-17`, parol kamida 6 belgi) — shu ma'lumotni kapitan **Apex Captain** ilovasiga
   kirish uchun beradi. Keyin **«Kvota bo'lishi»** tugmasi bilan barcha so'rov (tanlanmagan)
   o'yinchilarni **ikki bosqichda** taqsimlaydi:
   1. **Avval har guruhning asosiy 6 tasi** to'ldiriladi — **1 darvozabon, 2 himoyachi,
      1 yarim himoyachi, 2 hujumchi** (kapitanlar hisobga olinadi, MF va FW bir-birining o'rnini
      bosadi). Kam topiladigan pozitsiyadan boshlanadi va eng kuchli o'yinchi ko'p joyi bo'lgan
      guruhga beriladi.
   2. **So'ng ortib qolgan o'yinchilar** jamoalar **soni teng** bo'ladigan qilib beriladi
      (har guruhda maksimum **8 o'rin**). Sig'maganlar so'rov holatida qoladi va soni xabarda
      aytiladi.

   Asosiy 6 tasi to'lmagan guruh qolsa, bo'lishdan so'ng **«Asosiy 6 to'lmagan jamoalar»**
   oynasi chiqadi (kimda nima yetishmaydi va nima qilish mumkin). Tugmani yangi so'rov kelganda
   qayta bosish mumkin, «Taqsimni tozalash» bilan hammasini so'rov holatiga qaytarish mumkin.
   Shundan
   keyin o'yinchilar ilovadan to'liq foydalana oladi. Admin o'yinlar jadvalini yaratadi,
   gol/assist/kartochka kiritadi.
   (Admin o'yinchi **yaratmaydi** — o'yinchilar faqat o'zlari ro'yxatdan o'tadi.)

## Apex Captain (kapitanlar uchun alohida ilova)

Kapitanlik amallari **Apex Tournament** ilovasidan olib tashlandi — endi ular faqat **Apex Captain**
ilovasida va **login + parol** bilan:

- Login va parolni **faqat admin** beradi: Admin → **Sozlamalar → Kapitan loginlari**.
- Har guruhning o'z logini bor (`guruh-a-17` ko'rinishida), parol kamida 6 belgi.
- Admin shu oynada **parolni tiklaydi** yoki **loginni almashtiradi** — kapitan parolini unutsa
  admin yangi parol yozadi, bazadagi eski parol ishlamay qoladi.
- Parol bazada **PBKDF2-HMAC-SHA256 (120 000 davr)** hash ko'rinishida turadi, oddiy sha256 emas:
  telefon CPU'sida tekshirish ~0.1 soniya, shuning uchun login tugmasi boshqa oqimda ishlaydi.
- 3 marta xato kirish shu **qurilmada** 60 soniyalik kutishni beradi.
- Kapitan bu ilovada: **Tarkib** (boshlang'ich 6 + guruh logosi), **Jamoam** (faqat o'z jamoasi),
  **Transfer** (so'rovlar va muzokaralar), **Market** (APEX PRO TOKEN xaridlari).
- Chiqish: Profil → **Chiqish** (sessiya o'chadi, login bazadagi hisobga zarar yetkazmaydi).

## Jamoa shakli (tarkib qoidasi)

Kapitan har o'yin uchun **6 ta** asosiy tarkib tanlaydi va shakl majburiy:
**1 darvozabon (GK), 2 himoyachi (DF), 1 yarim himoyachi (MF), 2 hujumchi (FW)**.
**MF va FW o'rnini almashtirish mumkin** — yarim himoyachi hujumda, hujumchi yarim himoyada
o'ynaydi (shuning uchun MF+FW birga 3 ta deb sanaladi). **GK va DF boshqa pozitsiyada
o'ynamaydi.** Tarkib oynasida har qator pozitsiyasi bilan ko'rsatiladi va tepada jonli
sanog' («Darvozabon 1/1 · Himoyachi 1/2 · MF+FW 3/3») boradi; «Eng yaxshi 6» shaklni buzmasdan
eng yuqori OVR yig'adi. Saqlashda qoida qayta tekshiriladi — shakl buzilgan bo'lsa saqlanmaydi.

**Futbolka raqami — har jamoada 1 raqam = 1 o'yinchi.** Raqam 1 dan 99 gacha, o'yinchi ro'yxatdan
o'tganda kiritadi. Bir raqam turli jamoalarda bo'lishi mumkin, lekin **bitta jamoada ikki kishida
bo'lmaydi**. Kimningdir raqamini biz bilmasdan o'zgartirmaymiz:
- **Kvota bo'lishi** («Tasodifiy bo'lish») bir jamoaga takror raqam tushirsa, bo'lish tugadi-da,
  admin ga **«Raqam takrorlari»** oynasi chiqadi: guruh, raqam va kimlarda ekani ko'rsatiladi.
- **Transfer**dan keyin ham shunday: raqamlar o'zgarmaydi, sotuvchi/xaridor kapitanlari va
  o'yinchiga «bu jamoada N raqami ikki o'yinchida — kelishib o'zgartiring» degan xabarnoma boradi.
- Admin o'yinchilar bilan kelishgach **O'yinchilar → O'zgartirish → Futbolka raqami** da raqamni
  o'zi beradi. Oynada **bo'sh raqamlar maslahati** yozilgan bo'ladi; band raqam kiritilsa
  rad etiladi («10 raqami Guruh A jamoida Ali Valiyev da band»).
- Doimiy nazorat: **Boshqaruv** dagi «Raqam takrorlari» kartasi va **Sozlamalar → Raqam
  takrorlari** qatori sonini ko'rsatib turadi («yo'q» bo'lsa hamma narsa tartibda).

**Ma'lumotni noldan boshlash:** Admin → **Sozlamalar → Guruh va o'yinchilarni o'chirish** — barcha
guruhlar, o'yinchilar va ularga bog'liq o'yinlar/tarkiblar/transferlar/xabarnomalar bazadan o'chadi
(hakamlar, yordamchilar va Market tovarlari qoladi). Turnir `setup_done` holatida qoladi, ya'ni
o'yinchilar darhol qayta ro'yxatdan o'ta oladi. Bu amal **qaytarilmaydi**.

**Bitta o'yinchini o'chirish:** Admin → **O'yinchilar → O'yinchini o'chirish**. Tasdiq oynasi
ko'rsatadi-ki, o'yinchi ketganda birga nima o'chadi (tarkib qatorlari, gollar/assists, almashinuvlar,
kartochkalar, davomat, MOTM, transferlar, xabarnomalar, token tarixi). Bu **qattiq o'chirish**: izlar
bazadan tozalanadi, gol ochlari shunga qayta hisoblanadi va amal **ortga qaytarilmaydi**. O'yinchi telefonida uning profili avtomatik tozalanadi.

**Kapitanni o'chirish:** kapitan ham shu ro'yxatdan o'chiriladi, lekin tasdiq oynasi boshqacha —
u ketganda **guruh ham birga o'chadi** (kapitan logini/paroli, guruhning barcha o'yinlari
natijalari bilan). A'zolar o'chmaydi, ular **tanlanmaganlar** ro'yxatiga qaytadi. Guruh soni
cheklanmaydi: kerak bo'lsa bitta guruhgacha (yoki hech qaysi guruh qolmaguncha) o'chirsa bo'ladi.
Shu amal **Boshqaruv → Guruhlar → Kapitanni guruh bilan o'chirish** orqali ham bajariladi.

## Ilova yopilib qolsa

Ilovada kutilmagan xato bo'lsa, u endi yopilmaydi: ekranda **"Xatolik yuz berdi"** oynasi chiqadi. Shu oynaning
skrinshotini yuboring. Xato matni telefonda `crash.log` fayliga ham yoziladi.

## OVR qanday hisoblanadi

`OVR = boshlang'ich reyting (standart 60, admin o'zgartiradi) + jami ball / 3 + 2 x Player of the Match`, 40 dan 99 gacha.

## Xavfsizlik: nima qat'iy, nima yumshoq

- **Qat'iy:** admin amallari (gol, kartochka, natija, o'chirish, guruh/logo/OVR) faqat Firebase hisobi bilan kirgan adminga ruxsat etilgan.
  O'yinchi ilovasi buni qila olmaydi, hatto kod o'zgartirilsa ham: qoidalarni server tekshiradi.
- **Qat'iy:** o'yinchi faqat turnir boshlangan (`setup_done`) bo'lsa ro'yxatdan o'ta oladi; guruhga biriktirishni faqat admin qiladi
  («Kvota bo'lishi»), server qoidalari o'yinchi/kapitan buni rad etadi.
- **Yumshoq:** kapitan paroli bazada PBKDF2 hash ko'rinishida ochiq turadi (120 000 davr). Uni singdirish
  oddiy PIN ga qaraganda ancha qiyin, lekin bazani o'qiy olgan texnik bilimli o'yinchi nazariy jihatdan
  boshqa kapitan nomidan tarkib kiritishi yoki navbat tartibini buzishi mumkin. Do'stlar ligasi uchun
  yetarli; qat'iy himoya uchun Firebase Authentication + Cloud Functions kerak (pullik reja).
- **Yumshoq:** transfer/muzokara, Market xaridi va xabarnomalar ham shu darajada himoyalangan
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
2. Kapitan (**Apex Captain → Transfer**) qabul qilsa o'yinchiga
   "so'rovingiz qabul qilindi va transfer listga qo'shildingiz", rad etsa "so'rovingiz rad etildi" xabari boradi.
3. Boshqa jamoa kapitani transfer listdagi o'yinchi uchun **taklif** yuboradi: sotuvchi kapitaniga
   "biz sizning <ism> jamoadoshingizni sotib olishga qaror qildik" xabari va **Muzokara** tugmasi keladi.
4. Muzokarada kapitanlar taklif / qarshi taklif beradi yoki "Kelishdim" bosadi. Kelishilgan token
   xaridor jamoa hisobidan sotuvchi jamoa hisobiga o'tadi, o'yinchi yangi jamoaga ko'chadi.
5. Har bir jamoaning **APEX PRO TOKEN** balansi boshida 0; turnir (FINAL) g'olibi **+200** oladi.

## Market (faqat kapitanlar)

Admin "Market: narsa qo'shish / o'chirish" orqali rasm (telefondan), narx va sonini qo'yadi.
Kapitanlar **Apex Captain → Market** oynasida o'z jamoasi balansidagi APEX PRO TOKEN evaziga sotib oladi.
**Apex Tournament** ilovasida o'yinchilar narxlarni faqat o'qiydi (xarid tugmasi yo'q).

## Guruh logosi

Kapitan **Apex Captain → Tarkib** oynasidagi "Guruh logosini yuklash" tugmasi orqali 12 ta tayyor
logodan tanlaydi yoki **telefondan o'z rasmini yuklaydi** (rasm siqilib bazada saqlanadi).

## Turnir formati

- **8 yoki kamroq jamoa:** bitta guruh, har bir juftlik 2 marta (uy va mehmonda) o'ynaydi
  (3 jamoa bo'lsa har jamoa 4 tadan o'yin). Jadval (ochko, G/D/M, to'plar nisbati) avtomatik.
- Guruh o'yinlari tugagach 1- va 2-o'rin **FINAL** ga chiqadi (admin "FINAL o'yinini yaratish"),
  3-o'rin va undan past jamoalar musobaqani yakunlaydi.
- **8 tadan ko'p jamoa:** avtomatik guruh bosqichi (2 guruh), har guruhda bir davra,
  so'ng ikki guruh g'olibi FINAL da o'ynaydi.
- **Ballar teng bo'lsa** avval **o'zaro uchrashuv** qaraladi: teng jamoalar o'zaro HAMMA
  juftliklarni o'ynab bo'lgan bo'lsa, o'sha mini-jadvaldagi ball → to'plar farqi → to'plar
  hisobga olinadi. Biror uchrashuv hali o'ynalmagan bo'lsa o'zaro qoida **qo'llanilmaydi**
  (umumiy to'plar farqi asosiy bo'lib qoladi). Jadval ostida qaysi jamoalar shu qoida bilan
  ajratilgani yozib chiqadi.

## Hakam ilovasi

Admin "Hakamlar boshqaruvi" da hakam (ism + PIN) qo'shadi. Hakam **Apex Referee** ilovasida
ism va PIN bilan kirib, gol va assistlarni kiritadi (hisob avtomatik hisoblanadi).
Hakam jamoa kapitani yoki boshqa shaxs bo'lishi mumkin.

**Sekundomer** (Hakam → Tarkib → "Hakam sekundomeri"): o'yin uchun jonli `mm:ss` soat,
Boshlash/Pauza, bo'limi (1-/2-bo'lim, `CLOCK_HALF_MIN = 20` daqiqa) va "Nolga" tugmalari.
Gol, almashinuv va kartochka kiritilganda soatning daqiqasi yozga `min` sifatida qo'shiladi,
shuning uchun o'yin jurnali `12' · GOL — ...` ko'rinishida chiqadi. Soat **faqat shu
telefonning `clock.json` faylida** yuradi — baza yozish huquqi hakamda yo'q, daqiqa esa
gol yozivi bilan bazaga tushadi.

## Ilova yangilanishi

1. Kodni o'zgartirib `common.py` dagi `VERSION_CODE` ni oshiring va `version.json` da
   `version` ni yangilang (izoh va link ham shu yerda).
2. Repo ga `v2`, `v3` ko'rinishidagi **teg** bilan push qiling: Actions to'rtta APK ni qurib
   **GitHub Release** ga yuklaydi.
3. Har bir foydalanuvchi ilovani ochganda yangi versiya xabarini ko'radi ("Yuklab olish" tugmasi
   release sahifasini ochadi). Barcha ma'lumotlar Firebase bazasida qoladi — yangilanish ularni o'zgartirmaydi.

## Android 10 va planshetlar

To'rtala ilova ham Android 5.0 (API 21) dan yuqori, shu jumladan **Android 10** va planshetlarda
ishlaydi: `orientation = all` (portret + landshaft), minapi 21. Planshetda landshaft rejimda
ochish mumkin.

## Cheklovlar

- Logo: 12 ta tayyor logo yoki telefondan yuklangan rasm (siqilgan holda bazada saqlanadi).
- Internet yo'q bo'lsa ilova oxirgi yuklangan ma'lumotni ko'rsatadi (OFLAYN belgisi bilan), lekin o'zgartirish saqlanmaydi.
- Eski (bitta telefonli) versiyadagi ma'lumotlar ko'chmaydi: admin ilovasida turnirni qaytadan sozlaysiz.

## Push bildirishnoma (FCM) — bepul GitHub Actions

Push yuborish uchun Firebase **server kaliti** kerak, uni APK ichiga joylab bo'lmaydi. Shuning uchun
push server tomonida yuboriladi. Bizda ikkita yo'l bor — **bepul** (GitHub Actions cron, tavsiya etiladi)
va pulli (Cloud Functions). Quyida bepul yo'l asosiy qilib berilgan.

**Qanday ishlaydi (topic-based):** ilova o'z auditoriyalariga obuna bo'ladi — `all`, `p{pid}`, `g{gid}`
(bular `common.py` dagi `my_audiences()` bilan aynan mos). Admin/hakam xabarnoma yozganda u `/notifs/{id}`
ga tushadi. Server shu yozuvlarni ko'rib, `to` topiciga FCM push yuboradi. Serverda qurilma tokenlarini
saqlash shart emas. FCM ning o'zi har doim **bepul**.

### Bepul yo'l: GitHub Actions cron (tavsiya)

`.github/workflows/push.yaml` har ~5 daqiqada `scripts/fcm_push.py` ni ishga tushiradi. Skript
`/notifs` ni o'qiydi, `push_state/last_id` kursori bilan takroriy yozuvlarni chiqarib tashlaydi va
yangi xabarnomalarni topic'ga yuboradi. Ommaviy (public) repo uchun GitHub Actions **bepul**.
Yagona kechikish: cron tufayli push ~5–15 daqiqada yetib boradi (real-time emas).

**Bir martalik sozlash:**

1. Firebase konsoli > **Project settings** > **Service accounts** > **Generate new private key** —
   JSON kalit faylini yuklab oling (bu bepul, Blaze/karta talab qilinmaydi).
2. Yuklab olingan JSON ning **butun matnini** GitHub repo kaliti sifatida saqlang:
   repo > **Settings** > **Secrets and variables** > **Actions** > **New repository secret**
   - Name: `FIREBASE_SERVICE_ACCOUNT`
   - Secret: JSON faylning to'liq mazmuni (bir qatorda, nuqtali vergul bilan ajratilgan).
3. `database.rules.json` dagi `ADMIN_UID_SHU_YERGA` ni o'z admin UID ingiz bilan almashtiring
   (qoidalar bazaga yozishni himoya qiladi).
4. Tayyor — har ~5 daqiqada workflow avtomatik ishlaydi. Darhol sinash uchun GitHub repo
   > **Actions** > **FCM Push (cron)** > **Run workflow** ni bosing.

> Kalit faylini **hech qachon** repo'ga commit qilmang — u faqat GitHub Secret'da turadi.

### Pulli (ixtiyoriy) yo'l: Cloud Functions

`functions/` papkasidagi `pushOnNotif` real-time ishlaydi (kechikishsiz), lekin **Blaze**
(pay-as-you-go) rejani va `firebase deploy` ni talab qiladi. Pul to'lashni xohlamasangiz bu yo'lni
o'tkazib yuboring — yuqoridagi bepul cron ham xuddi shu ishni bajaradi.

### Mijoz tomoni (Android/Kivy) — allaqachon qo'shilgan

`push.py` moduli:

- `google-services.json` dan FCM identifikatorlarini o'qib, `FirebaseApp` ni **qo'lda** ishga tushiradi
  (google-services gradle plugin talab qilinmaydi — buildozer uchun bu ishonchliroq).
- Ilova `route()`/`set_my_pid`/kapitan PIN dan keyin `sync_push()` chaqiriladi: `my_audiences()` dagi
  topiclarga (`all`, `p{pid}`, `g{gid}`) obuna bo'ladi, ortiqchalarini bekor qiladi.
- Android 13+ da ishga tushganda bir marta `POST_NOTIFICATIONS` ruxsatini so'raydi.
- Server `notification` payload yuborgani uchun xabarni tizim trayi avtomatik ko'rsatadi —
  alohida Java service kerak emas.
- Desktop'da yoki SDK/`google-services.json` topilmasa `push.py` **jim no-op** qiladi: ilova yiqilmaydi,
  faqat in-app xabarnomalar (qo'ng'iroq belgisi) ishlaydi.

**Mijozni yoqish uchun:**

1. Firebase konsoli > Project settings > **Your apps** > Android ilova qo'shing
   (package name: `org.apex.apextournament`, `org.apex.apexcaptain`, `org.apex.apexadmin`,
   `org.apex.apexreferee`).
2. **google-services.json** ni yuklab oling va `apex/` papkasiga qo'ying
   (`google-services.json.example` — namuna). CI uni avtomatik APK ga nusxalaydi.
3. To'rtala `buildozer_*.spec` da allaqachon `firebase-messaging` bog'liqligi va `POST_NOTIFICATIONS`
   ruxsati yoqilgan. APK ni qayta quring (teg bilan push qiling).

> Eslatma: har ilova (player/captain/admin/referee) uchun alohida Android app ro'yxatdan o'tkazing —
> `google-services.json` bitta package name ga bog'lanadi. Oddiy yechim: to'rtalasini bitta
> `google-services.json` ichida to'rtta `client` sifatida qo'shing yoki har build uchun almashtiring.
> Barcha client'lar bitta `project_number`/sender_id ni bo'lishgani uchun topic push baribir ishlaydi.

## v3 — Glassmorphism, oltin karta, AI (Gemini), mashq tahlili, yordamchilar

### Dizayn
Butun interfeys **glassmorphism** uslubiga o'tdi: binafsha→ko'k gradient fon, yarim shaffof
shisha kartalar va ochiq chegara chiziqlari. **Apex Admin** endi butunlay **mustaqil ilova**:
pastki navigatsiya **Dashboard / O'yinlar / O'yinchilar / Boshqaruv**.

### Oltin o'yinchi kartasi + AI rasm
Har bir o'yinchi kartasida **FC Mobile uslubidagi oltin karta** ko'rsatiladi: OVR, pozitsiya,
familiya va 6 ta atribut — **TEZ(pac), ZAR(sho), PAS(pas), DRB(dri), HIM(def), JIS(phy)**.
Yangi ro'yxatdan o'tgan o'yinchining atributlari **45-55** atrofidan boshlanadi, OVR shu
atributlarning o'rtachasidan hisoblanadi.

O'yinchi (yoki admin) kartada **Rasm yuklash** tugmasi bilan telefon rasmini tanlaydi. Agar
Gemini kaliti kiritilgan bo'lsa, rasm AI orqali qayta ishlanadi: orqa fon olib tashlanadi,
oltin karta foniga joylanadi va tiniqlashtiriladi (natija `card_b64` da saqlanadi). Kalit
bo'lmasa oddiy rasm saqlanadi.

### Gemini API (ixtiyoriy, lekin bepul)
1. https://aistudio.google.com — **bepul** API kalit oling.
2. `apex/` papkasida **`gemini_secret.py`** faylini yarating (`.gitignore` da — push bo'lmaydi):
   ```python
   GEMINI_API_KEY = "sizning_kalitingiz"
   ```
   `config.py` uni avtomatik o'qiydi. **Kalitni `config.py` ga yozmang** — GitHub secret
   scanning uni bloklaydi va tarixda qoladi.
3. Model nomlari kerak bo'lsa `config.py` da `GEMINI_MODEL_IMAGE` / `GEMINI_MODEL_VIDEO`
   bilan sozlanadi (standart: `gemini-2.5-flash-image`, `gemini-2.5-flash`).
4. `gemini_secret.py` bo'lmasa yoki bo'sh bo'lsa barcha AI funksiyalari **jim no-op** — ilova yiqilmaydi.


### Mashq videosi + gibrid OVR
Admin > **O'yinchilar** > o'yinchi kartasi > **AI / Mashq**:
- **Mashq videosi tahlili (AI)**: atributni tanlaysiz → qisqa video (<18MB) yuklaysiz →
  Gemini 45-99 oralig'ida taklif beradi → admin **Tasdiqlash** yoki **Qo'lda** o'zgartiradi.
- **Atributni qo'lda kiritish**: AI'siz to'g'ridan-to'g'ri 45-99 son kiritasiz.
Video tahlili taxminiy va bepul kvota cheklangan — natijani har doim admin tasdiqlaydi.

### Yordamchi (assistant) — admin huquqi
Admin > **Boshqaruv** > **Yordamchilar (admin assistant)** > **Yordamchi yaratish**: ism, email,
parol. Ilova Firebase Auth da yangi hisob yaratadi va uni `/assistants` ro'yxatiga qo'shadi.
Yordamchi shu email/parol bilan **Apex Admin** ilovasiga kiradi va hamma narsani boshqara oladi.

**Majburiy bitta qadam** (bitta marta): yangilangan `database.rules.json` ni Firebase ga
deploy qiling yoki konsolda Realtime Database **Rules** da ildiz `.write` ni shunga almashtiring:

```
".write": "auth != null && (auth.uid === 'ADMIN_UID_SHU_YERGA' || root.child('assistants').child(auth.uid).exists())"
```

Bu `ADMIN_UID_SHU_YERGA` o'rniga o'z admin UID ingiz, yordamchi UID lari esa `/assistants` da
avtomatik paydo bo'ladi. Yordamchini o'chirsangiz huquqi darhol bekor bo'ladi.

### v3 release
`VERSION_CODE = 3`, `version.json` > `"version": 3`, uchtala spec `version = 3.0`. APK qurish va
reliz: teg push qiling — `git tag v3 && git push origin v3`. GitHub Actions APK larni yig'adi va
**Releases** ga chiqaradi; ilova ichida yangilanish xabari avtomatik ko'rinadi.

## v4/v5 — Apex Captain, jamoa shakli kvotasi, qattiq o'chirish

- **Apex Captain** — to'rtinchi alohida ilova (`captain.py`, `buildozer_captain.spec`,
  `org.apex.apexcaptain`). Kapitanlik amallari endi shu yerda va **login + parol** bilan
  (PBKDF2 120 000 davr, 3 xatodan keyin 60 s kutish). Loginlarni admin beradi:
  **Sozlamalar → Kapitan loginlari**.
- **Apex Tournament** endi faqat shaxsiy ilova: ro'yxatdan o'tish, o'z kartasi/statistikasi,
  tokenlar, xabarnomalar, jadval va Market/narxlarni **o'qish** uchun. Tarkib, transfer
  muzokarasi va xarid qilmaydi.
- **Jamoa shakli**: `POS_QUOTA` (1 GK / 2 DF / 1 MF / 2 FW) endi uch joyda bitta qoida —
  «Kvota bo'lishi» (v6 da bosqichlarga bo'lindi, quyida), «Eng yaxshi 6» taklifi va tarkibni
  saqlash. MF va FW o'rin almashadi.
- **O'yinchini o'chirish** (Admin → O'yinchilar): tasdiq oynasi qancha iz o'chishini sanab
  beradi, keyin tarkib/gol/assist/almashinuv/kartochka/davomat/MOTM/transfer/xabarnoma/token
  tarixi tozalanadi va gol ochlari qayta hisoblanadi. **Kapitan** bo'lsa, u o'chirilganda
  **guruhi ham birga ketadi** (logini, o'yinlari bilan); a'zolari tanlanmaganlarga qaytadi.
- **CI**: `build.yaml` artiq **to'rtta** APK quradi va `glassui.py`, `player_card.py` ni ham
  build papkasiga nusxalaydi (avval tushirib qoldirilgan — APK importda yiqilardi).

**Majburiy qadam:** `database.rules.json` yangilandi — `/groups/$gid` yozish qoidasi endi
`pin_hash` o'rniga `cap_login` va `cap_pass_hash` o'zgarishini tekshiradi. Uni Firebase konsolida
**Rules** ga qo'ying (yoki `firebase deploy --only database`), aks holda kapitan logosini yuklay
olmaydi. Eski guruhlar `cap_login` siz qoladi — admin **Kapitan loginlari** da login/parol yozgach
ishlaydi.

### Release
`VERSION_CODE = 5`, `version.json` > `"version": 5`, to'rtala spec `version = 3.4`.
Teg push qiling: `git tag v5 && git push origin v5`.

## v6 — zaxira, o'zaro uchrashuv, avtomatik qulf, sekundomer, jadval rasmi

- **Turnir zaxirasi (eksport / tiklash).** Admin panel → **Zaxira / tiklash** (yoki
  Sozlamalar → TIZIM → "Turnir zaxirasi"). Butun turnir `to_remote()` ko'rinishida
  `<user_data_dir>/backups/apex_YYYYmmdd_HHMMSS_<yorliq>.json` fayliga yoziladi, faylni
  **yuborish** (Telegram/Drive) `content://` URI orqali, **tiklash** esa fayl tanlanadi.
  Eng yangi 20 ta zaxira saqlanadi (`BACKUP_KEEP`). Xavfli amallar oldidan
  (to'liq tozalash, guruh/kapitan/o'yinchi o'chirish, taqsimni tozalash, tiklash)
  **avtomatik zaxira** yaratiladi — u amalni to'xtatmaydi, faqat xabar qiladi.
  Tiklashda hozirgi ma'lumot to'liq almashtiriladi, `store.save()` differensial PATCH
  bo'lgani uchun bazada faylda yo'q tugunlar o'chadi.
- **O'zaro uchrashuv** endi jadvalda uchinchi ustun emas, ballar tenglashganda
  avtomatik ishlaydigan qoida (yuqoridagi "Turnir formati" ga qarang).
- **Tarkibning avtomatik qulfi.** Admin → **Tarkib qulfi** da o'yinga boshlanish vaqti
  (`05.11 18:30`) qo'yiladi, bazada `matches/$mid/kick` (epoch sekund). Vaqt yetganda
  (`LINEUP_LOCK_MIN = 15` daqiqa oldin) tarkib **barcha telefonlarda** yopiladi: kapitan
  tugmasi ko'rinmaydi, `set_lineup()` rad etadi, holat `tarkib QULFLANGAN (avtomatik)`.
  Admin ilovasi qulfni bazaga ham yozadi (`lineup_locked = true`, har 60 soniyada tekshiradi),
  shunda server qoidalari ham boshqa qurilmalarning yozuvini qaytaradi. Vaqt o'chirilsa
  qulf faqat qo'lab yoki natija orqali bo'ladi.
- **Hakam sekundomeri** — "Hakam ilovasi" bo'limiga qarang.
- **Kvota bo'lishi endi ikki bosqichda.** Avval **hamma** guruhning asosiy 6 tasi to'ldiriladi,
  keyin ortiqchalar **teng son** qilib beriladi (max 8 o'rin). Sig'maganlar so'rovda qoladi va
  sanaladi. `common.py` da `shape_gaps()` — asosiy 6 tasi to'lmagan guruhlar ro'yxati
  (MF+FW birga 3 ta, shuning uchun «hujumchi yetishmaydi» deb asossiz qo'rqitmaydi), admin
  panelida **«Asosiy 6 to'lmagan jamoalar»** oynasi bo'lishdan keyin avtomatik chiqadi.
- **Jadvalni PNG qilib ulashish.** Jadval tab'ining boshidagi tugma jadvalni
  (guruhlar, o'zaro uchrashuv izohi, chempion, bombardirlar) shisha panelga yig'adi,
  ko'rib chiqish oynasini ochadi va **"PNG yuborish"** bilan 2× aniqlikdagi rasmga
  aylantiradi (`export_to_png(scale=2)` → MediaStore → ACTION_SEND).

**Xavfsizlik:** zaxira fayli bazadagi hamma narsani olib chiqadi — shu jumladan kapitan
`cap_pass_hash` va hakam `pin_hash` lari. Ular Realtime Database'da allaqachon hamma
uchun o'qiladigan (`rules: ".read": true`), ya'ni fayl yangi sir qo'shmaydi; lekin
buni begonalarga yubormang.

**Majburiy qadam:** `database.rules.json` o'zgarmadi — `kick` maydoni `matches` tugunida
va uni faqat admin yozadi. Faqat `matches/$mid/goals` ga hakam yozoladi, shuning uchun
sekundomer bazaga yozilmaydi.

### Tekshiruv
`python -u scripts/render_check.py all` endi bularni ham sinaydi: o'zaro uchrashuv tartibi
(tugallanmagan klasterda qoida ishlatilmasligi bilan), avtomatik qulf (`kick` holatlari va
bazaga yozish), sekundomer (bo'limlar, daqiqa, `clock.json`, panel), zaxira (yozish, o'qish,
tiklash), jadval PNG faylini va futbolka raqami qoidasini (bo'sh raqam topish, takror ro'yxati,
band raqam rad etilishi, taqsim/transfer raqamlarni o'zgartirmasligi). Kvota bo'lishi sinovi ham
ikki bosqichni tekshiradi: hech kim so'rovda qolmaydi, hamma guruhda asosiy 6 ta to'liq
(`shape_gaps()` bo'sh) va jamoalar soni 1 tadan ortiq farq qilmaydi; sun'iy ravishda darvozabonni
MF ga o'zgartirib, «Asosiy 6» oynasining chiqishini ham sinaydi.

