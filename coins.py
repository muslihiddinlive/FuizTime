"""FuizCoin tizimi."""
import logging
from datetime import datetime, date
from telegram import Bot
from db import (save, update, delete, cache_find, cache_find_all, cache_get)

log = logging.getLogger("FuizCoins")

DEFAULT_SETTINGS = {
    "coin_per_referral":   2,
    "coin_per_group":      0,
    "stars_per_100fc":     15,
    "contact_daily_free":  2,
    "contact_paid_cost":   20,
    "contact_paid_count":  10,
    "admin_max_coin":      1000,  # Admin bir marta bera oladigan max FC
}

COIN_PER_REFERRAL  = 2
COIN_PER_GROUP_ADD = 0

def get_setting(bot_data: dict, key: str):
    return bot_data.get("settings", {}).get(key, DEFAULT_SETTINGS.get(key))

def set_setting(bot_data: dict, key: str, value):
    bot_data.setdefault("settings", {})[key] = value

# ── BALANS ─────────────────────────────────────────────────

def get_balance(bot_data: dict, uid: int) -> int:
    r = cache_find(bot_data, "coins", uid=str(uid))
    return int(r.get("balance", 0)) if r else 0

async def set_balance(bot: Bot, bot_data: dict, uid: int, amount: int, username: str = "") -> int:
    r = cache_find(bot_data, "coins", uid=str(uid))
    if r:
        r["balance"]  = str(max(0, amount))
        r["username"] = username or r.get("username", "")
        await update(bot, bot_data, "coins", r)
    else:
        r = {"uid": str(uid), "balance": str(max(0, amount)), "username": username}
        await save(bot, bot_data, "coins", r)
    return max(0, amount)

async def add_coins(bot: Bot, bot_data: dict, uid: int, amount: int,
                    reason: str = "", username: str = "") -> int:
    cur = get_balance(bot_data, uid)
    new = cur + amount
    await set_balance(bot, bot_data, uid, new, username)
    await log_coin(bot, bot_data, uid, amount, reason)
    return new

async def sub_coins(bot: Bot, bot_data: dict, uid: int, amount: int,
                    reason: str = "") -> tuple[bool, int]:
    cur = get_balance(bot_data, uid)
    if cur < amount:
        return False, cur
    new = cur - amount
    await set_balance(bot, bot_data, uid, new)
    await log_coin(bot, bot_data, uid, -amount, reason)
    return True, new

async def transfer_coins(bot: Bot, bot_data: dict,
                         from_uid: int, to_uid: int, amount: int) -> tuple[bool, str]:
    ok, _ = await sub_coins(bot, bot_data, from_uid, amount, f"transfer→{to_uid}")
    if not ok:
        return False, "Balansingiz yetarli emas!"
    await add_coins(bot, bot_data, to_uid, amount, f"transfer←{from_uid}")
    return True, "ok"

# ── COIN TARIXI ────────────────────────────────────────────

async def log_coin(bot: Bot, bot_data: dict, uid: int, amount: int, reason: str):
    await save(bot, bot_data, "coin_history", {
        "uid":    str(uid),
        "amount": str(amount),
        "reason": reason,
        "date":   datetime.now().strftime("%Y-%m-%d %H:%M"),
    })

def get_history(bot_data: dict, uid: int, limit=10) -> list:
    all_h = cache_find_all(bot_data, "coin_history", uid=str(uid))
    return all_h[-limit:]

# ── MUROJAAT LIMITI ────────────────────────────────────────

def get_today_str() -> str:
    return date.today().isoformat()

def get_contact_usage(bot_data: dict, uid: int) -> dict:
    key   = f"contact_{uid}_{get_today_str()}"
    usage = bot_data.get("contact_usage", {})
    return usage.get(key, {"free": 0, "paid": 0, "paid_left": 0})

def inc_contact_usage(bot_data: dict, uid: int, is_paid: bool = False):
    key   = f"contact_{uid}_{get_today_str()}"
    usage = bot_data.setdefault("contact_usage", {})
    rec   = usage.get(key, {"free": 0, "paid": 0, "paid_left": 0})
    if is_paid:
        rec["paid"]     += 1
        rec["paid_left"] = max(0, rec["paid_left"] - 1)
    else:
        rec["free"] += 1
    usage[key] = rec

def add_paid_contacts(bot_data: dict, uid: int, count: int):
    key   = f"contact_{uid}_{get_today_str()}"
    usage = bot_data.setdefault("contact_usage", {})
    rec   = usage.get(key, {"free": 0, "paid": 0, "paid_left": 0})
    rec["paid_left"] += count
    usage[key] = rec

def can_send_contact(bot_data: dict, uid: int) -> tuple[bool, str]:
    daily_free = get_setting(bot_data, "contact_daily_free")
    usage      = get_contact_usage(bot_data, uid)
    free_used  = usage.get("free", 0)
    paid_left  = usage.get("paid_left", 0)
    if free_used < daily_free:
        return True, "free"
    if paid_left > 0:
        return True, "paid"
    return False, "limit"

# ── REFERAL ────────────────────────────────────────────────

def get_ref_link(bot_username: str, uid: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{uid}"

def get_channel_ref_link(bot_username: str, uid: int, channel_id: str) -> str:
    return f"https://t.me/{bot_username}?start=cref_{uid}_{channel_id}"

async def process_referral(bot: Bot, bot_data: dict,
                           new_uid: int, ref_uid: int, username: str = "") -> bool:
    existing = cache_find(bot_data, "referrals", new_uid=str(new_uid))
    if existing:
        return False
    coin_amount = get_setting(bot_data, "coin_per_referral")
    await save(bot, bot_data, "referrals", {
        "ref_uid": str(ref_uid),
        "new_uid": str(new_uid),
        "type":    "user",
        "date":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    await add_coins(bot, bot_data, ref_uid, coin_amount,
                    f"referal: {new_uid}", username)
    return True

def get_ref_count(bot_data: dict, uid: int) -> int:
    return len(cache_find_all(bot_data, "referrals", ref_uid=str(uid)))

# ── PROMOKOD ───────────────────────────────────────────────

async def create_promo(bot: Bot, bot_data: dict,
                       code: str, amount: int,
                       total_uses: int, per_user: int) -> dict:
    # Kod katta harfga o'tkazamiz
    code = code.upper().strip()
    existing = cache_find(bot_data, "promocodes", code=code)
    if existing:
        return {"error": "Bu kod allaqachon mavjud!"}
    r = await save(bot, bot_data, "promocodes", {
        "code":       code,
        "amount":     str(amount),
        "total_uses": str(total_uses),
        "per_user":   str(per_user),
        "used":       "0",
        "date":       datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    return r

async def use_promo(bot: Bot, bot_data: dict,
                    uid: int, code: str, username: str = "") -> tuple[bool, str]:
    code  = code.upper().strip()
    promo = cache_find(bot_data, "promocodes", code=code)
    if not promo:
        return False, "❌ Promokod topilmadi!"

    try:
        total_uses = int(promo.get("total_uses") or 0)
        per_user   = int(promo.get("per_user") or 1)
        used       = int(promo.get("used") or 0)
        amount     = int(promo.get("amount") or 0)
    except (ValueError, TypeError):
        return False, "❌ Promokod ma'lumotlari noto'g'ri!"

    if total_uses <= 0:
        return False, "❌ Promokod noto'g'ri (limit 0)!"

    if used >= total_uses:
        return False, f"❌ Promokod limiti tugagan! ({used}/{total_uses})"

    # Bu user necha marta ishlatgan
    all_hist   = cache_get(bot_data, "coin_history")
    user_uses  = [h for h in all_hist
                  if str(h.get("uid")) == str(uid)
                  and h.get("reason") == f"promo:{code}"]

    if len(user_uses) >= per_user:
        return False, f"❌ Siz bu promokodni {per_user} marta ishlatgansiz!"

    # Ishlatish
    promo["used"] = str(used + 1)
    await update(bot, bot_data, "promocodes", promo)
    await add_coins(bot, bot_data, uid, amount, f"promo:{code}", username)
    return True, f"✅ +{amount} FuizCoin! (Balans: {get_balance(bot_data, uid)} FC)"

async def delete_promo(bot: Bot, bot_data: dict, msg_id: str) -> bool:
    return await delete(bot, bot_data, "promocodes", msg_id)
