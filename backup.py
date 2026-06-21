"""
FuizTime Backup tizimi
- Har kuni 00:00 da keshni JSON fayl qilib backup topicga yuboradi
- Har 4 ta DB o'zgarishidan keyin ham avtomatik backup yuboradi (db.py orqali)
- Har bir backup yuborilganda xabar PIN qilinadi (eskisi yechiladi)
- /export buyrug'i bilan qo'lda ham yuborish mumkin
- /import buyrug'i bilan faylni botga berib qo'lda restore qilish mumkin
- Bot bo'sh boshlansa — PIN qilingan oxirgi backup'dan AVTOMATIK restore qiladi
- Avtomatik restore ishlamasa — superadmin/adminlarga qo'lda /import so'rab xabar beradi
"""
import json
import logging
import os
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
from config import DB_GROUP_ID, TOPIC_IDS, SUPERADMIN, ADMIN_IDS

log = logging.getLogger("FuizBackup")

BACKUP_TOPIC = TOPIC_IDS.get("backup", 384)

async def export_backup(bot: Bot, bot_data: dict) -> bool:
    """Keshni JSON fayl qilib backup topicga yuboradi."""
    try:
        cache    = bot_data.get("cache", {})
        settings = bot_data.get("settings", {})
        features = bot_data.get("features", {})
        extra_admins = bot_data.get("extra_admins", [])

        payload = {
            "version":     "2.1",
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cache":       cache,
            "settings":    settings,
            "features":    features,
            "extra_admins": extra_admins,
            "about_text":  bot_data.get("about_text", ""),
            "about_msg_id": bot_data.get("about_msg_id"),
        }

        # Statistika
        total = sum(len(v) for v in cache.values())
        users = len(cache.get("users", []))

        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

        # Fayl nomi
        fname = f"fuiztime_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"

        # Vaqtinchalik fayl
        tmp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
        with open(tmp_path, "wb") as f:
            f.write(json_bytes)

        # Backup topicga yuborish
        with open(tmp_path, "rb") as f:
            sent_msg = await bot.send_document(
                chat_id=DB_GROUP_ID,
                message_thread_id=BACKUP_TOPIC,
                document=f,
                filename=fname,
                caption=(
                    f"📦 <b>Avtomatik backup</b>\n"
                    f"🗓 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"👥 Userlar: {users}\n"
                    f"📊 Jami yozuvlar: {total}"
                ),
                parse_mode="HTML"
            )

        # Vaqtinchalik faylni o'chirish
        os.remove(tmp_path)

        # ── Yangi backup'ni qadash, eskisini yechish ──
        try:
            old_pin_id = bot_data.get("last_backup_msg_id")
            if old_pin_id and str(old_pin_id) != str(sent_msg.message_id):
                try:
                    await bot.unpin_chat_message(chat_id=DB_GROUP_ID, message_id=int(old_pin_id))
                except TelegramError:
                    pass
            await bot.pin_chat_message(
                chat_id=DB_GROUP_ID,
                message_id=sent_msg.message_id,
                disable_notification=True
            )
            bot_data["last_backup_msg_id"] = str(sent_msg.message_id)
        except TelegramError as e:
            log.warning(f"Backup'ni pin qilishda xato (bot 'can_pin_messages' huquqiga ega emasmi?): {e}")

        log.info(f"Backup muvaffaqiyatli yuborildi: {fname} ({total} yozuv)")
        return True

    except Exception as e:
        log.error(f"Backup xato: {e}")
        return False


def import_backup(bot_data: dict, json_data: bytes) -> tuple[bool, str]:
    """JSON fayldan keshni restore qiladi."""
    try:
        payload = json.loads(json_data.decode("utf-8"))

        version = payload.get("version", "?")
        exported_at = payload.get("exported_at", "?")

        # Restore
        if "cache" in payload:
            bot_data["cache"] = payload["cache"]
        if "settings" in payload:
            bot_data["settings"] = payload["settings"]
        if "features" in payload:
            bot_data["features"] = payload["features"]
        if "extra_admins" in payload:
            bot_data["extra_admins"] = payload["extra_admins"]
        if payload.get("about_text"):
            bot_data["about_text"] = payload["about_text"]
        if payload.get("about_msg_id"):
            bot_data["about_msg_id"] = payload["about_msg_id"]

        cache = bot_data.get("cache", {})
        total = sum(len(v) for v in cache.values())
        users = len(cache.get("users", []))

        log.info(f"Restore muvaffaqiyatli: v{version}, {exported_at}, {total} yozuv")
        return True, (
            f"✅ <b>Restore muvaffaqiyatli!</b>\n\n"
            f"📦 Versiya: {version}\n"
            f"🗓 Backup sanasi: {exported_at}\n"
            f"👥 Userlar: {users}\n"
            f"📊 Jami yozuvlar: {total}"
        )

    except json.JSONDecodeError:
        return False, "❌ Fayl noto'g'ri format! JSON bo'lishi kerak."
    except Exception as e:
        return False, f"❌ Restore xato: {e}"


async def auto_restore_if_empty(bot: Bot, bot_data: dict) -> bool:
    """
    Bot xotirasi bo'sh boshlangan bo'lsa (masalan Render disk tozalanib,
    cache.json yo'qolgan holatda), backup topicda PIN qilingan oxirgi JSON
    faylni avtomatik topib, yuklab oladi va restore qiladi.

    Eslatma: Telegram Bot API orqali bot eski xabarlarni "qidirib" topa
    olmaydi — faqat PIN qilingan xabarni getChat() orqali ko'ra oladi.
    Shu sababli bu funksiya pin'ga tayanadi. Agar pin topilmasa yoki xato
    chiqsa, False qaytaradi va chaqiruvchi tomon /import so'rab xabar beradi.
    """
    cache = bot_data.get("cache", {})
    total = sum(len(v) for v in cache.values())
    if total > 0:
        return False  # Bo'sh emas — restorega ehtiyoj yo'q

    try:
        chat = await bot.get_chat(DB_GROUP_ID)
        pinned = chat.pinned_message
        if not pinned or not pinned.document:
            log.warning("Avtomatik restore: pin qilingan backup fayl topilmadi.")
            return False
        if not (pinned.document.file_name or "").endswith(".json"):
            log.warning("Avtomatik restore: pin qilingan fayl .json emas.")
            return False

        tg_file = await bot.get_file(pinned.document.file_id)
        content_bytes = await tg_file.download_as_bytearray()
        ok, _ = import_backup(bot_data, bytes(content_bytes))
        bot_data["last_backup_msg_id"] = str(pinned.message_id)

        if ok:
            log.info("✅ Avtomatik restore muvaffaqiyatli (pin qilingan backup orqali).")
        else:
            log.error("Avtomatik restore: backup fayl formatida xato.")
        return ok

    except TelegramError as e:
        log.error(f"Avtomatik restore xato (Telegram API): {e}")
        return False
    except Exception as e:
        log.error(f"Avtomatik restore xato: {e}")
        return False


async def check_empty_and_notify(bot: Bot, bot_data: dict, auto_restored: bool = False):
    """Bot bo'sh boshlanganda (yoki avtomatik restore qilingandan keyin)
    superadmin va adminlarga xabar beradi."""
    cache = bot_data.get("cache", {})
    total = sum(len(v) for v in cache.values())
    all_admins = [SUPERADMIN] + ADMIN_IDS + bot_data.get("extra_admins", [])

    if auto_restored:
        msg = (
            "✅ <b>Avtomatik restore muvaffaqiyatli!</b>\n\n"
            "Bot ma'lumotlari yo'qolgan edi (Render disk tozalandi), "
            "lekin backup topicdagi PIN qilingan oxirgi JSON fayldan "
            "<b>o'zi avtomatik qayta tikladi</b>. Qo'lda hech narsa qilish shart emas.\n\n"
            f"📊 Tiklangan yozuvlar: {total}"
        )
        for aid in set(all_admins):
            try:
                await bot.send_message(aid, msg, parse_mode="HTML")
            except TelegramError:
                pass
        log.info("Bot bo'sh boshlandi, avtomatik restore muvaffaqiyatli bo'ldi.")
        return

    if total == 0:
        msg = (
            "⚠️ <b>Bot ma'lumotlari tozalandi!</b>\n\n"
            "Render disk tozalash natijasida <b>cache.json</b> o'chirildi, "
            "avtomatik restore esa muvaffaqiyatsiz bo'ldi "
            "(backup topicda PIN qilingan fayl topilmadi yoki xatolik bo'ldi).\n\n"
            "Qo'lda restore qilish uchun:\n"
            "1. Backup topicdan oxirgi JSON faylni yuklab oling\n"
            "2. /import buyrug'ini yuboring va faylni attach qiling\n\n"
            "<i>Bot hozir bo'sh holda ishlayapti.</i>"
        )
        for aid in set(all_admins):
            try:
                await bot.send_message(aid, msg, parse_mode="HTML")
            except TelegramError:
                pass
        log.warning("Bot bo'sh boshlandi — avtomatik restore muvaffaqiyatsiz, adminlarga xabar yuborildi")
