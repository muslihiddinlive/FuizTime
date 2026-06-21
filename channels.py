"""Majburiy kanal/guruh tizimi va broadcast."""
import logging
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from db import save, delete, cache_find, cache_get

log = logging.getLogger("FuizChannels")

# ── MAJBURIY KANALLAR ──────────────────────────────────────────────────────

async def check_subscription(bot: Bot, uid: int, bot_data: dict) -> list:
    """Foydalanuvchi obuna bo'lmagan kanallarni qaytaradi."""
    channels = cache_get(bot_data, "channels")
    not_subbed = []
    for ch in channels:
        ch_id = ch.get("ch_id")
        if not ch_id:
            continue
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=uid)
            if member.status in ("left", "kicked", "restricted"):
                not_subbed.append(ch)
        except TelegramError:
            not_subbed.append(ch)
    return not_subbed

def subscription_kb(not_subbed: list, back_data="main") -> InlineKeyboardMarkup:
    rows = []
    for ch in not_subbed:
        name = ch.get("name", "Kanal")
        link = ch.get("invite_link") or ch.get("ch_id")
        if link and not str(link).startswith("http"):
            link = f"https://t.me/{str(link).lstrip('@')}"
        if link:
            rows.append([InlineKeyboardButton(f"📢 {name}", url=link)])
    rows.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(rows)

async def add_channel(bot: Bot, bot_data: dict,
                      ch_id: str, name: str,
                      invite_link: str = "",
                      is_referral: bool = False) -> dict | str:
    """Majburiy kanal qo'shish."""
    existing = cache_find(bot_data, "channels", ch_id=str(ch_id))
    if existing:
        return "Bu kanal/guruh allaqachon qo'shilgan!"
    r = await save(bot, bot_data, "channels", {
        "ch_id":       str(ch_id),
        "name":        name,
        "invite_link": invite_link,
        "is_referral": "1" if is_referral else "0",
        "type":        "channel",
    })
    return r

async def add_group(bot: Bot, bot_data: dict,
                    gr_id: str, name: str,
                    invite_link: str = "",
                    is_referral: bool = False) -> dict | str:
    existing = cache_find(bot_data, "channels", ch_id=str(gr_id))
    if existing:
        return "Bu guruh allaqachon qo'shilgan!"
    r = await save(bot, bot_data, "channels", {
        "ch_id":       str(gr_id),
        "name":        name,
        "invite_link": invite_link,
        "is_referral": "1" if is_referral else "0",
        "type":        "group",
    })
    return r

async def remove_channel(bot: Bot, bot_data: dict, msg_id: str) -> bool:
    return await delete(bot, bot_data, "channels", msg_id)

# ── BROADCAST ──────────────────────────────────────────────────────────────

async def broadcast_to_users(bot: Bot, bot_data: dict,
                              text: str, parse_mode="HTML") -> dict:
    """Barcha userlarga xabar yuborish."""
    users   = cache_get(bot_data, "users")
    sent    = 0
    failed  = 0
    blocked = 0
    for u in users:
        uid = u.get("uid")
        if not uid:
            continue
        try:
            await bot.send_message(
                chat_id=int(uid),
                text=text,
                parse_mode=parse_mode
            )
            sent += 1
        except TelegramError as e:
            err = str(e).lower()
            if "blocked" in err or "deactivated" in err:
                blocked += 1
            else:
                failed += 1
        await asyncio.sleep(0.05)  # flood limit
    await save(bot, bot_data, "broadcasts", {
        "type":    "users",
        "sent":    str(sent),
        "failed":  str(failed),
        "blocked": str(blocked),
        "text":    text[:200],
    })
    return {"sent": sent, "failed": failed, "blocked": blocked}

async def broadcast_to_channels(bot: Bot, bot_data: dict,
                                 text: str, parse_mode="HTML") -> dict:
    """Admin bo'lgan kanallarga xabar yuborish."""
    channels = cache_get(bot_data, "channels")
    sent = 0
    failed = 0
    for ch in channels:
        ch_id = ch.get("ch_id")
        if not ch_id:
            continue
        try:
            await bot.send_message(
                chat_id=ch_id,
                text=text,
                parse_mode=parse_mode
            )
            sent += 1
        except TelegramError as e:
            log.warning(f"broadcast channel {ch_id}: {e}")
            failed += 1
        await asyncio.sleep(0.1)
    await save(bot, bot_data, "broadcasts", {
        "type":   "channels",
        "sent":   str(sent),
        "failed": str(failed),
        "text":   text[:200],
    })
    return {"sent": sent, "failed": failed}

async def broadcast_to_groups(bot: Bot, bot_data: dict,
                               text: str, parse_mode="HTML") -> dict:
    """Bot admin bo'lgan guruhlarga xabar yuborish."""
    groups = cache_get(bot_data, "targets")
    sent = 0
    failed = 0
    for g in groups:
        gr_id = g.get("gr_id")
        if not gr_id:
            continue
        try:
            await bot.send_message(
                chat_id=int(gr_id),
                text=text,
                parse_mode=parse_mode
            )
            sent += 1
        except TelegramError as e:
            log.warning(f"broadcast group {gr_id}: {e}")
            failed += 1
        await asyncio.sleep(0.1)
    await save(bot, bot_data, "broadcasts", {
        "type":   "groups",
        "sent":   str(sent),
        "failed": str(failed),
        "text":   text[:200],
    })
    return {"sent": sent, "failed": failed}

async def broadcast_to_all(bot: Bot, bot_data: dict,
                            text: str, parse_mode="HTML") -> dict:
    """Hammaga: users + channels + groups."""
    r1 = await broadcast_to_users(bot, bot_data, text, parse_mode)
    r2 = await broadcast_to_channels(bot, bot_data, text, parse_mode)
    r3 = await broadcast_to_groups(bot, bot_data, text, parse_mode)
    return {
        "users":    r1,
        "channels": r2,
        "groups":   r3,
    }
