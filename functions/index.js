/**
 * Apex Tournament — FCM push server komponenti.
 *
 * Nega bu fayl kerak: push yuborish uchun Firebase server kaliti kerak va uni
 * APK ichiga joylab bo'lmaydi (har kim tortib olib soxta xabar tarqatishi mumkin).
 * Shu sababli push faqat SHU YERDA, server tomonida yuboriladi.
 *
 * Arxitektura (topic-based, token saqlash shart emas):
 *   Mijoz (Android) o'z auditoriyalariga obuna bo'ladi:  "all", "p{pid}", "g{gid}".
 *   Ilovada har xabarnoma /notifs/{nid} ga {to, text} bilan yoziladi.
 *   Quyidagi trigger yangi xabarnomani ko'rib, uni `to` topiciga push qiladi.
 *   `to` qiymatlari common.py dagi my_audiences() bilan aynan mos keladi.
 */

const { setGlobalOptions, onCall, HttpsError } = require("firebase-functions/v2");
const { onValueCreated } = require("firebase-functions/v2/database");
const { onSchedule } = require("firebase-functions/v2/scheduler");
const { initializeApp } = require("firebase-admin/app");
const { getMessaging } = require("firebase-admin/messaging");
const { getDatabase } = require("firebase-admin/database");
const logger = require("firebase-functions/logger");

initializeApp();

// Baza europe-west1 da, funksiyalar ham shu yerda bo'lsin (past kechikish).
setGlobalOptions({ region: "europe-west1", maxInstances: 10 });

const APP_TITLE = "Apex Pro League";
// FCM topic nomi qoidalari: faqat harf/raqam va -_.~% , 1..900 belgi.
const TOPIC_RE = /^[a-zA-Z0-9-_.~%]{1,900}$/;
const NOTIF_TTL_DAYS = 30;

/**
 * Yangi xabarnoma yozilganda uni tegishli topicga push qiladi.
 * Trigger faqat onCreate da ishlaydi, shuning uchun bir xabar ikki marta ketmaydi.
 */
exports.pushOnNotif = onValueCreated("/notifs/{nid}", async (event) => {
  const snap = event.data;
  if (!snap) return;
  const notif = snap.val() || {};
  const to = notif.to;
  const text = (notif.text || "").toString().trim();

  if (!to || !text) {
    logger.info("pushOnNotif: 'to' yoki 'text' yo'q, o'tkazib yuborildi", { nid: event.params.nid });
    return;
  }
  if (!TOPIC_RE.test(to)) {
    logger.warn("pushOnNotif: yaroqsiz topic nomi", { to });
    return;
  }

  const message = {
    topic: to,
    notification: { title: APP_TITLE, body: text.slice(0, 175) },
    data: { nid: String(event.params.nid), to: String(to), click_action: "OPEN_APP" },
    android: {
      priority: to === "all" ? "normal" : "high",
      ttl: 24 * 60 * 60 * 1000,
      collapseKey: `notif-${event.params.nid}`,
    },
  };

  try {
    const mid = await getMessaging().send(message);
    logger.info("push yuborildi", { to, mid });
  } catch (err) {
    // Topic hali bo'sh bo'lishi mumkin (hech kim obuna bo'lmagan) — bu xato emas.
    logger.error("push yuborilmadi", { to, code: err && err.code, msg: err && err.message });
  }
});

/**
 * Eski xabarnomalarni tozalash (baza shishib ketmasligi uchun).
 * Har kuni 03:00 UTC da NOTIF_TTL_DAYS kundan eski yozuvlarni o'chiradi.
 */
exports.cleanupOldNotifs = onSchedule(
  { schedule: "every day 03:00", timeZone: "Etc/UTC" },
  async () => {
    const ref = getDatabase().ref("notifs");
    const cutoff = Math.floor(Date.now() / 1000) - NOTIF_TTL_DAYS * 86400;
    try {
      const snap = await ref.orderByChild("ts").endAt(cutoff).once("value");
      const val = snap.val() || {};
      const keys = Object.keys(val);
      if (!keys.length) {
        logger.info("cleanupOldNotifs: o'chirish uchun eski xabar yo'q");
        return;
      }
      const updates = {};
      for (const k of keys) updates[`notifs/${k}`] = null;
      await getDatabase().ref().update(updates);
      logger.info("cleanupOldNotifs: eski xabarlar o'chirildi", { count: keys.length });
    } catch (err) {
      logger.error("cleanupOldNotifs xatosi", { msg: err && err.message });
    }
  }
);
