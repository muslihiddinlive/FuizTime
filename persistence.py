"""
FuizTime Persistence — restart da keshni saqlash/yuklash.
bot_data ni lokal JSON ga yozadi, restart da qayta yuklaydi.
Telegram supergroup = asosiy DB (ground truth)
JSON = tezkor kesh (restart safe)
"""
import json
import os
import logging
from datetime import datetime

log = logging.getLogger("FuizPersist")
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.json")

def save_cache(bot_data: dict):
    """bot_data keshini faylga saqlash."""
    try:
        payload = {
            "cache":         bot_data.get("cache", {}),
            "extra_admins":  bot_data.get("extra_admins", []),
            "about_text":    bot_data.get("about_text", ""),
            "about_msg_id":  bot_data.get("about_msg_id"),
            "settings":      bot_data.get("settings", {}),
            "contact_usage": bot_data.get("contact_usage", {}),
            "saved_at":      datetime.now().isoformat(),
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        log.info(f"Kesh saqlandi: {CACHE_FILE}")
    except Exception as e:
        log.error(f"Kesh saqlashda xato: {e}")

def load_cache() -> dict:
    """Fayldan keshni yuklash."""
    if not os.path.exists(CACHE_FILE):
        log.info("Kesh fayli yo'q, bo'sh kesh.")
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        saved_at = payload.get("saved_at", "")
        log.info(f"Kesh yuklandi (saqlangan: {saved_at})")
        return payload
    except Exception as e:
        log.error(f"Kesh yuklashda xato: {e}")
        return {}

def restore_bot_data(bot_data: dict):
    """Yuklangan keshni bot_data ga o'rnatish."""
    payload = load_cache()
    if not payload:
        return
    bot_data["cache"]         = payload.get("cache", {})
    bot_data["extra_admins"]  = payload.get("extra_admins", [])
    bot_data["about_text"]    = payload.get("about_text", "")
    bot_data["settings"]      = payload.get("settings", {})
    bot_data["contact_usage"] = payload.get("contact_usage", {})
    if payload.get("about_msg_id"):
        bot_data["about_msg_id"] = payload["about_msg_id"]
    log.info("bot_data restored from cache.")
