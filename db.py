"""
FuizTime DB layer — Telegram Supergroup Topics as database.
Har bir record = bitta Telegram xabari.
Format: KEY:value satrlari, BODY: dan keyin erkin matn.
"""
import asyncio
import logging
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
from config import DB_GROUP_ID, TOPIC_IDS

log = logging.getLogger("FuizDB")

# ── Serialization ──────────────────────────────────────────────────────────

SKIP_KEYS = {"_msg_id", "_id"}

def _serialize(data: dict) -> str:
    lines = []
    body = data.pop("body", None)
    for k, v in data.items():
        if k in SKIP_KEYS:
            continue
        if v is not None and v != "":
            lines.append(f"{k}:{v}")
    if body:
        lines.append(f"BODY:{body}")
    return "\n".join(lines)

def _deserialize(text: str) -> dict:
    data = {}
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("BODY:"):
            data["body"] = "\n".join(lines[i+1:]) if i+1 < len(lines) else line[5:]
            break
        if ":" in line:
            k, _, v = line.partition(":")
            data[k.strip()] = v.strip()
    return data

# ── Low-level DB ops ───────────────────────────────────────────────────────

async def db_write(bot: Bot, topic: str, data: dict, msg_id: int = None) -> int | None:
    thread_id = TOPIC_IDS.get(topic)
    if not thread_id:
        log.error(f"Unknown topic: {topic}")
        return None
    d = dict(data)
    text = _serialize(d)
    try:
        if msg_id:
            await bot.edit_message_text(
                chat_id=DB_GROUP_ID,
                message_id=msg_id,
                text=text[:4096]
            )
            return msg_id
        else:
            msg = await bot.send_message(
                chat_id=DB_GROUP_ID,
                message_thread_id=thread_id,
                text=text[:4096]
            )
            return msg.message_id
    except TelegramError as e:
        log.error(f"db_write({topic}) error: {e}")
        return None

async def db_delete(bot: Bot, msg_id: int) -> bool:
    try:
        await bot.delete_message(chat_id=DB_GROUP_ID, message_id=msg_id)
        return True
    except TelegramError as e:
        log.warning(f"db_delete({msg_id}) error: {e}")
        return False

# ── Cache helpers ──────────────────────────────────────────────────────────

def cache_get(bot_data: dict, topic: str) -> list:
    return bot_data.setdefault("cache", {}).setdefault(topic, [])

def cache_find(bot_data: dict, topic: str, **kwargs) -> dict | None:
    for r in cache_get(bot_data, topic):
        if all(r.get(k) == str(v) for k, v in kwargs.items()):
            return r
    return None

def cache_find_all(bot_data: dict, topic: str, **kwargs) -> list:
    return [r for r in cache_get(bot_data, topic)
            if all(r.get(k) == str(v) for k, v in kwargs.items())]

def cache_add(bot_data: dict, topic: str, record: dict):
    cache_get(bot_data, topic).append(record)

def cache_update(bot_data: dict, topic: str, msg_id: str | int, updates: dict):
    for r in cache_get(bot_data, topic):
        if str(r.get("_msg_id")) == str(msg_id):
            r.update(updates)
            return

def cache_remove(bot_data: dict, topic: str, msg_id: str | int):
    c = cache_get(bot_data, topic)
    bot_data["cache"][topic] = [r for r in c if str(r.get("_msg_id")) != str(msg_id)]

# ── Debounce backup ────────────────────────────────────────────────────────
# Har o'zgarishda 5 soniya kutadi. Agar 5 soniya ichida yangi o'zgarish
# kelsa — timer qayta boshlanadi. 00:00 daily backup dan mustaqil ishlaydi.

_backup_task: asyncio.Task | None = None

async def _debounce_backup(bot: Bot, bot_data: dict):
    """5 soniya kutib, keyin backup qiladi."""
    await asyncio.sleep(5)
    try:
        import backup as BK
        await BK.export_backup(bot, bot_data)
        log.info("📦 Debounce backup yuborildi (5 soniya harakatsizlikdan keyin).")
    except Exception as e:
        log.error(f"Debounce backup xato: {e}")

async def _track_change(bot: Bot, bot_data: dict):
    """Har bir o'zgarishda debounce backup ni qayta ishga tushiradi."""
    global _backup_task

    # Eski taskni bekor qil
    if _backup_task and not _backup_task.done():
        _backup_task.cancel()

    # Yangi task boshlash
    _backup_task = asyncio.create_task(_debounce_backup(bot, bot_data))

# ── High-level helpers ─────────────────────────────────────────────────────

async def save(bot: Bot, bot_data: dict, topic: str, record: dict) -> dict:
    record.setdefault("_id", datetime.now().strftime("%Y%m%d%H%M%S%f")[:16])
    msg_id = await db_write(bot, topic, record)
    if msg_id:
        record["_msg_id"] = str(msg_id)
        cache_add(bot_data, topic, record)
        await _track_change(bot, bot_data)
    return record

async def update(bot: Bot, bot_data: dict, topic: str, record: dict) -> bool:
    msg_id = record.get("_msg_id")
    if not msg_id:
        return False
    new_msg_id = await db_write(bot, topic, dict(record), int(msg_id))
    if new_msg_id:
        cache_update(bot_data, topic, msg_id, record)
        await _track_change(bot, bot_data)
        return True
    return False

async def delete(bot: Bot, bot_data: dict, topic: str, msg_id: str | int) -> bool:
    ok = await db_delete(bot, int(msg_id))
    cache_remove(bot_data, topic, msg_id)
    if ok:
        await _track_change(bot, bot_data)
    return ok
