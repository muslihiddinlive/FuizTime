#!/usr/bin/env python3
"""FuizTime Bot v2.1 — To'liq tuzatilgan versiya"""

import logging
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ChatMemberHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import BOT_TOKEN, SUPERADMIN, ADMIN_IDS, DB_GROUP_ID, FEATURES
import db as DB
import coins as C
import channels as CH
import persistence as P
import backup as BK

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger("FuizBot")

# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def is_admin(uid: int, bot_data: dict) -> bool:
    extra = bot_data.get("extra_admins", [])
    return uid == SUPERADMIN or uid in ADMIN_IDS or uid in extra

def is_superadmin(uid: int) -> bool:
    return uid == SUPERADMIN

def feature_on(bot_data: dict, name: str) -> bool:
    """Feature yoqilganmi? bot_data dan o'qiydi, yo'q bo'lsa config dan."""
    features = bot_data.get("features", {})
    if name in features:
        return features[name]
    return FEATURES.get(name, True)

def btn(text, data=None, url=None):
    if url:
        return InlineKeyboardButton(text, url=url)
    return InlineKeyboardButton(text, callback_data=data)

def kb(*rows):
    return InlineKeyboardMarkup(list(rows))

def home_btn():
    return kb([btn("🏠 Bosh menyu", "main")])

def back_btn(to="admin"):
    return kb([btn("🔙 Orqaga", to)])

def cancel_btn():
    return kb([btn("❌ Bekor", "cancel")])

def skip_cancel_kb():
    return kb([btn("⏭ O'tkazish", "skip"), btn("❌ Bekor", "cancel")])

def ip_or_link_kb():
    """Server qo'shishda havola yoki IP tanlash."""
    return kb(
        [btn("🔗 Havola bilan", "srv_type:link")],
        [btn("🖥 IP manzil bilan", "srv_type:ip")],
        [btn("❌ Bekor", "cancel")]
    )

# ═══════════════════════════════════════════════════════════
#  SECTIONS CONFIG
# ═══════════════════════════════════════════════════════════

SECTIONS = {
    "versions":  ("📦", "Versiyalar"),
    "news":      ("📰", "Yangiliklar"),
    "gallery":   ("🖼", "Galereya"),
    "mods":      ("🧩", "Modlar"),
    "servers":   ("🌐", "Serverlar"),
    "wiki":      ("📖", "Wiki"),
    "community": ("👥", "Jamiyat"),
    "videos":    ("🎬", "Videolar"),
    "about":     ("ℹ️", "Biz haqimizda"),
    "contact":   ("📞", "Aloqa / Murojaat"),
}

# ADD_STEPS — (key, prompt, optional, accept_file)
# accept_file: "doc" | "photo" | "photo_video" | None
ADD_STEPS = {
    "versions": [
        ("title",   "📌 Versiya nomi (masalan: v1.2.3):", False, None),
        ("desc",    "📝 Tavsif:", False, None),
        ("apk",     "📎 APK faylni yuboring (ixtiyoriy):", True, "doc"),
        ("size",    "📊 Hajm (masalan: 45 MB) (ixtiyoriy):", True, None),
        ("date",    "🗓 Sana (ixtiyoriy):", True, None),
    ],
    "news": [
        ("title",   "📌 Sarlavha:", False, None),
        ("desc",    "📝 Qisqa tavsif:", False, None),
        ("body",    "📄 To'liq matn (ixtiyoriy):", True, None),
        ("link",    "🔗 Havola (ixtiyoriy):", True, None),
        ("media",   "🖼 Rasm yoki video yuboring (ixtiyoriy):", True, "photo_video"),
        ("date",    "🗓 Sana (ixtiyoriy):", True, None),
    ],
    "gallery": [
        ("title",   "📌 Sarlavha:", False, None),
        ("media",   "🖼 Rasm yoki video yuboring:", False, "photo_video"),
        ("desc",    "📝 Tavsif (ixtiyoriy):", True, None),
    ],
    "mods": [
        ("title",   "📌 Mod nomi:", False, None),
        ("desc",    "📝 Tavsif:", False, None),
        ("author",  "👤 Muallif (ixtiyoriy):", True, None),
        ("ver",     "📦 Mod versiyasi (ixtiyoriy):", True, None),
        ("tag",     "🏷 Kategoriya (ixtiyoriy):", True, None),
        ("link",    "🔗 Yuklab olish havolasi (ixtiyoriy):", True, None),
        ("media",   "🖼 Rasm yoki video (ixtiyoriy):", True, "photo_video"),
    ],
    "servers": [
        ("title",   "📌 Server nomi:", False, None),
        # server_type va server_addr — wizard orqali
        ("desc",    "📝 Tavsif (ixtiyoriy):", True, None),
        ("media",   "🖼 Rasm yoki video (ixtiyoriy):", True, "photo_video"),
    ],
    "wiki": [
        ("title",   "📌 Sarlavha:", False, None),
        ("desc",    "📝 Qisqa tavsif:", False, None),
        ("body",    "📄 To'liq matn:", False, None),
        ("tag",     "🏷 Kategoriya (ixtiyoriy):", True, None),
        ("media",   "🖼 Rasm (ixtiyoriy):", True, "photo_video"),
    ],
    "community": [
        ("title",   "📌 Sarlavha:", False, None),
        ("desc",    "📝 Matn:", False, None),
        ("author",  "👤 Muallif (ixtiyoriy):", True, None),
        ("link",    "🔗 Havola (ixtiyoriy):", True, None),
        ("media",   "🖼 Rasm yoki video (ixtiyoriy):", True, "photo_video"),
    ],
    "videos": [
        ("title",   "📌 Sarlavha:", False, None),
        ("link",    "▶️ Video havolasi (YouTube va h.k.):", False, None),
        ("desc",    "📝 Tavsif (ixtiyoriy):", True, None),
    ],
}

# ═══════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════

def get_state(ctx) -> dict:
    uid = ctx.user_data.get("_uid", 0)
    if not uid:
        return {}
    return ctx.bot_data.get("states", {}).get(str(uid), {})

def set_state(ctx, name, data=None):
    uid = ctx.user_data.get("_uid", 0)
    if not uid:
        return
    ctx.bot_data.setdefault("states", {})[str(uid)] = {
        "name": name, "data": data or {}
    }

def clear_state(ctx):
    uid = ctx.user_data.get("_uid", 0)
    if uid:
        ctx.bot_data.get("states", {}).pop(str(uid), None)

def init_user_ctx(ctx, uid: int):
    ctx.user_data["_uid"] = uid

# ═══════════════════════════════════════════════════════════
#  USER REGISTER
# ═══════════════════════════════════════════════════════════

async def register_user(bot, bot_data, uid, username="", fullname=""):
    existing = DB.cache_find(bot_data, "users", uid=str(uid))
    if not existing:
        await DB.save(bot, bot_data, "users", {
            "uid":      str(uid),
            "username": username,
            "fullname": fullname,
            "date":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

# ═══════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════

def main_menu_kb(uid: int, bot_data: dict):
    coins_on  = feature_on(bot_data, "coins")
    refs_on   = feature_on(bot_data, "referrals")
    promos_on = feature_on(bot_data, "promocodes")
    is_sa     = is_superadmin(uid)

    rows = [
        [btn("📦 Versiyalar",  "sec:versions"),
         btn("📰 Yangiliklar", "sec:news")],
        [btn("🖼 Galereya",    "sec:gallery"),
         btn("🧩 Modlar",      "sec:mods")],
        [btn("🌐 Serverlar",   "sec:servers"),
         btn("📖 Wiki",        "sec:wiki")],
        [btn("👥 Jamiyat",     "sec:community"),
         btn("🎬 Videolar",    "sec:videos")],
        [btn("ℹ️ Haqida",      "sec:about"),
         btn("📞 Murojaat",    "sec:contact")],
    ]

    # Coin/referal/promo — faqat yoqilgan bo'lsa yoki superadmin
    coin_row = []
    if coins_on or is_sa:
        coin_row.append(btn("💰 FuizCoin" + ("" if coins_on else " 🔒"), "coin:menu"))
    if refs_on or is_sa:
        coin_row.append(btn("👥 Referal" + ("" if refs_on else " 🔒"), "ref:menu"))
    if coin_row:
        rows.append(coin_row)

    if promos_on or is_sa:
        rows.append([btn("🎁 Promokod" + ("" if promos_on else " 🔒"), "coin:promo")])

    return InlineKeyboardMarkup(rows)

def admin_menu_kb(bot_data: dict = None):
    rows = [
        [btn("📢 Kanallar",        "adm:channels"),
         btn("📣 Reklama",         "adm:broadcast")],
        [btn("➕ Kontent qo'shish","adm:content"),
         btn("🗑 O'chirish",       "adm:delete")],
        [btn("📋 Murojaatlar",     "adm:requests"),
         btn("📊 Statistika",      "adm:stats")],
        [btn("👥 Foydalanuvchilar","adm:users"),
         btn("👤 Adminlar",        "adm:admins")],
    ]
    # FuizCoin tizimi — yoqilgan bo'lsa ko'rinsin
    if bot_data is None or feature_on(bot_data, "coins"):
        rows.append([btn("💰 Coinlar",    "adm:coin:give"),
                     btn("📊 Balanslar",  "adm:coin:balances")])
    if bot_data is None or feature_on(bot_data, "promocodes"):
        rows.append([btn("🎁 Promokodlar", "adm:promos")])
    rows.append([btn("🏠 Bosh menyu", "main")])
    return InlineKeyboardMarkup(rows)

def superadmin_menu_kb(bot_data: dict):
    """Superadmin uchun qo'shimcha panel."""
    coins_on  = feature_on(bot_data, "coins")
    refs_on   = feature_on(bot_data, "referrals")
    promos_on = feature_on(bot_data, "promocodes")
    return kb(
        [btn(f"💰 FuizCoin: {'✅ Yoqiq' if coins_on else '❌ O\'chirilgan'}",
             "sa:toggle:coins")],
        [btn(f"👥 Referal: {'✅ Yoqiq' if refs_on else '❌ O\'chirilgan'}",
             "sa:toggle:referrals")],
        [btn(f"🎁 Promokod: {'✅ Yoqiq' if promos_on else '❌ O\'chirilgan'}",
             "sa:toggle:promocodes")],
        [btn("💰 Coin berish",   "adm:coin:give"),
         btn("📊 Balanslar",     "adm:coin:balances")],
        [btn("🎁 Promokodlar",   "adm:promos")],
        [btn("⚙️ Narxlar/Limitlar", "sa:settings")],
        [btn("📤 Export (backup)", "sa:export"),
         btn("📥 Import (restore)", "sa:import")],
        [btn("🔙 Admin panel",   "admin")],
    )

def content_add_kb():
    rows = []
    for topic, (emoji, name) in SECTIONS.items():
        if topic in ("about", "contact"):
            continue
        rows.append([btn(f"{emoji} {name}", f"adm:add:{topic}")])
    rows.append([btn("✏️ Haqida tahrirlash", "adm:edit:about")])
    rows.append([btn("🔙 Orqaga", "admin")])
    return InlineKeyboardMarkup(rows)

# ═══════════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.forward_origin:
        return
    # Guruhda /start ga javob bermasin
    if update.effective_chat.type != "private":
        return
    uid  = update.effective_user.id
    user = update.effective_user
    init_user_ctx(ctx, uid)
    clear_state(ctx)
    await register_user(
        ctx.bot, ctx.bot_data, uid,
        user.username or "", user.full_name or ""
    )

    # Referal
    args = ctx.args
    if args:
        arg = args[0]
        if arg.startswith("ref_"):
            try:
                ref_uid = int(arg[4:])
                if ref_uid != uid and feature_on(ctx.bot_data, "referrals"):
                    gained = await C.process_referral(
                        ctx.bot, ctx.bot_data, uid, ref_uid, user.username or ""
                    )
                    if gained:
                        try:
                            await ctx.bot.send_message(
                                ref_uid,
                                f"🎉 Yangi referal! <b>{user.full_name}</b> keldi.\n"
                                f"+{C.COIN_PER_REFERRAL} FuizCoin!",
                                parse_mode=ParseMode.HTML
                            )
                        except TelegramError:
                            pass
            except (ValueError, IndexError):
                pass

    # Majburiy kanal tekshiruv
    not_subbed = await CH.check_subscription(ctx.bot, uid, ctx.bot_data)
    if not_subbed:
        await update.message.reply_text(
            "⚠️ Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling:",
            reply_markup=CH.subscription_kb(not_subbed),
            parse_mode=ParseMode.HTML
        )
        return

    await update.message.reply_text(
        "🎮 <b>FuizTime</b> botiga xush kelibsiz!\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=main_menu_kb(uid, ctx.bot_data),
        parse_mode=ParseMode.HTML
    )

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.forward_origin:
        return
    # Guruhda /admin ga javob bermasin
    if update.effective_chat.type != "private":
        return
    uid = update.effective_user.id
    init_user_ctx(ctx, uid)
    if not is_admin(uid, ctx.bot_data):
        await update.message.reply_text("❌ Sizda admin huquqi yo'q.")
        return
    clear_state(ctx)
    await update.message.reply_text(
        "⚙️ <b>Admin paneli</b>",
        reply_markup=admin_menu_kb(ctx.bot_data),
        parse_mode=ParseMode.HTML
    )

async def cmd_sa(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Superadmin panel."""
    uid = update.effective_user.id
    if not is_superadmin(uid):
        return
    clear_state(ctx)
    await update.message.reply_text(
        "👑 <b>Superadmin panel</b>",
        reply_markup=superadmin_menu_kb(ctx.bot_data),
        parse_mode=ParseMode.HTML
    )

async def cmd_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Qo'lda backup yuborish."""""
    uid = update.effective_user.id
    if uid != SUPERADMIN:
        await update.message.reply_text("❌ Faqat superadmin!")
        return
    await update.message.reply_text("⏳ Backup tayyorlanmoqda...")
    ok = await BK.export_backup(ctx.bot, ctx.bot_data)
    if ok:
        ctx.bot_data["change_counter"] = 0
        await update.message.reply_text("✅ Backup backup topicga yuborildi!")
    else:
        await update.message.reply_text("❌ Backup yuborishda xato!")

async def cmd_import(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """JSON fayldan restore qilish."""""
    uid = update.effective_user.id
    if uid != SUPERADMIN:
        await update.message.reply_text("❌ Faqat superadmin!")
        return
    msg = update.message
    if not msg.document:
        await msg.reply_text(
            "📥 <b>Restore qilish</b>\n\n"
            "Backup JSON faylni shu xabarga attach qilib yuboring:\n"
            "<i>/import</i> buyrug'ini yozing va faylni birga yuboring.",
            parse_mode="HTML"
        )
        return
    doc = msg.document
    if not doc.file_name.endswith(".json"):
        await msg.reply_text("❌ Faqat .json fayl qabul qilinadi!")
        return
    await msg.reply_text("⏳ Restore qilinmoqda...")
    tg_file  = await ctx.bot.get_file(doc.file_id)
    content_bytes = await tg_file.download_as_bytearray()
    ok, result = BK.import_backup(ctx.bot_data, bytes(content_bytes))
    if ok:
        P.save_cache(ctx.bot_data)
    await msg.reply_text(result, parse_mode="HTML")

async def cmd_addadmin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPERADMIN:
        return
    args = ctx.args
    if not args or not args[0].lstrip("-").isdigit():
        await update.message.reply_text("Ishlatilishi: /addadmin <user_id>")
        return
    new_id = int(args[0])
    extra  = ctx.bot_data.setdefault("extra_admins", [])
    if new_id not in extra and new_id not in ADMIN_IDS:
        extra.append(new_id)
        await DB.save(ctx.bot, ctx.bot_data, "admins", {
            "uid":  str(new_id),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        await update.message.reply_text(f"✅ {new_id} admin qilindi.")
    else:
        await update.message.reply_text("Bu foydalanuvchi allaqachon admin.")

async def cmd_deladmin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPERADMIN:
        return
    args = ctx.args
    if not args or not args[0].lstrip("-").isdigit():
        await update.message.reply_text("Ishlatilishi: /deladmin <user_id>")
        return
    del_id = int(args[0])
    if del_id == SUPERADMIN:
        await update.message.reply_text("Superadminni o'chirib bo'lmaydi!")
        return
    extra = ctx.bot_data.get("extra_admins", [])
    if del_id in extra:
        extra.remove(del_id)
        await update.message.reply_text(f"✅ {del_id} admin ro'yxatidan o'chirildi.")
    else:
        await update.message.reply_text("Bu foydalanuvchi adminlar ro'yxatida yo'q.")

# ═══════════════════════════════════════════════════════════
#  CONTENT DISPLAY
# ═══════════════════════════════════════════════════════════

def format_item(topic, r):
    title  = r.get("title", "—")
    desc   = r.get("desc", "")
    body   = r.get("body", "")
    link   = r.get("link", "")
    tag    = r.get("tag", "")
    date   = r.get("date", "")
    author = r.get("author", "")
    ver    = r.get("ver", "")
    size   = r.get("size", "")
    server_type = r.get("server_type", "link")
    server_addr = r.get("server_addr", "")

    emoji, name = SECTIONS.get(topic, ("📄", topic))
    lines = [f"<b>{emoji} {title}</b>"]

    if topic == "versions":
        if size:   lines.append(f"📊 Hajm: {size}")
        if date:   lines.append(f"🗓 Sana: {date}")
        if r.get("apk"): lines.append("📎 APK fayl mavjud")
    elif topic == "mods":
        if author: lines.append(f"👤 {author}")
        if ver:    lines.append(f"📦 v{ver}")
        if tag:    lines.append(f"🏷 {tag}")
    elif topic == "servers":
        if server_addr:
            if server_type == "ip":
                lines.append(f"🖥 IP: <code>{server_addr}</code>")
            else:
                lines.append(f"🔗 Havola: {server_addr}")
    elif topic in ("wiki", "community"):
        if tag:    lines.append(f"🏷 {tag}")
        if author: lines.append(f"👤 {author}")

    if desc: lines.append(f"\n{desc}")
    if body: lines.append(f"\n{body}")

    if link and topic not in ("videos", "servers"):
        lines.append(f"\n🔗 <a href='{link}'>Havola</a>")
    if topic == "videos" and link:
        lines.append(f"\n▶️ <a href='{link}'>Ko'rish</a>")

    if date and topic not in ("versions",):
        lines.append(f"🗓 {date}")

    return "\n".join(lines)

async def show_section(query, ctx, topic, page=0):
    uid   = query.from_user.id
    admin = is_admin(uid, ctx.bot_data)
    emoji, name = SECTIONS.get(topic, ("📄", topic))

    if topic == "about":
        text  = ctx.bot_data.get("about_text") or "<i>Hali kiritilmagan.</i>"
        extra = []
        if admin:
            extra.append([btn("✏️ Tahrirlash", "adm:edit:about")])
        extra.append([btn("🏠 Bosh menyu", "main")])
        await query.edit_message_text(
            f"<b>{emoji} {name}</b>\n\n{text}",
            reply_markup=InlineKeyboardMarkup(extra),
            parse_mode=ParseMode.HTML
        )
        return

    # Contact — murojaat yuborish
    if topic == "contact":
        await query.edit_message_text(
            f"<b>{emoji} {name}</b>\n\n"
            f"Adminlarga xabar yuborish uchun quyidagi tugmani bosing.\n"
            f"Xabaringiz barcha adminlarga yetkaziladi.",
            reply_markup=kb(
                [btn("✍️ Xabar yozish", "contact:write")],
                [btn("🏠 Bosh menyu", "main")]
            ),
            parse_mode=ParseMode.HTML
        )
        return

    items   = DB.cache_get(ctx.bot_data, topic)
    per_pg  = 8
    start   = page * per_pg
    end     = start + per_pg
    page_items = items[start:end]

    rows = []
    if admin:
        rows.append([btn("➕ Qo'shish", f"adm:add:{topic}")])
    if not items:
        rows.append([btn("🏠 Bosh menyu", "main")])
        await query.edit_message_text(
            f"<b>{emoji} {name}</b>\n\n<i>Hozircha hech narsa yo'q.</i>",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=ParseMode.HTML
        )
        return

    for r in page_items:
        t = r.get("title") or r.get("server_addr") or "—"
        rows.append([btn(f"▸ {t[:40]}", f"view:{topic}:{r.get('_msg_id')}")])

    nav = []
    if page > 0:         nav.append(btn("◀", f"page:{topic}:{page-1}"))
    if end < len(items): nav.append(btn("▶", f"page:{topic}:{page+1}"))
    if nav: rows.append(nav)
    rows.append([btn("🏠 Bosh menyu", "main")])

    await query.edit_message_text(
        f"<b>{emoji} {name}</b> — {len(items)} ta",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML
    )

async def show_item(query, ctx, topic, msg_id):
    uid   = query.from_user.id
    admin = is_admin(uid, ctx.bot_data)
    items = DB.cache_get(ctx.bot_data, topic)
    r     = next((x for x in items if str(x.get("_msg_id")) == str(msg_id)), None)
    if not r:
        await query.answer("Topilmadi!", show_alert=True)
        return

    text     = format_item(topic, r)
    has_apk  = bool(r.get("apk"))
    media_id = r.get("media_id")
    media_type = r.get("media_type", "photo")  # "photo" | "video"
    server_type = r.get("server_type", "link")
    server_addr = r.get("server_addr", "")

    rows = []
    if has_apk:
        rows.append([btn("📥 APK yuklab olish", f"dl:{topic}:{msg_id}")])
    # Server uchun kirish tugmasi
    if topic == "servers" and server_addr and server_type == "link":
        rows.append([btn("🎮 Serverga kirish", url=server_addr)])
    if admin:
        rows.append([btn("✏️ Tahrirlash", f"adm:edit_item:{topic}:{msg_id}"),
                     btn("🗑 O'chirish",   f"adm:del_item:{topic}:{msg_id}")])
    rows.append([btn("🔙 Orqaga", f"sec:{topic}")])
    view_kb = InlineKeyboardMarkup(rows)

    try:
        if media_id:
            if media_type == "video":
                await query.message.reply_video(
                    video=media_id,
                    caption=text,
                    reply_markup=view_kb,
                    parse_mode=ParseMode.HTML
                )
            else:
                await query.message.reply_photo(
                    photo=media_id,
                    caption=text,
                    reply_markup=view_kb,
                    parse_mode=ParseMode.HTML
                )
            try:
                await query.message.delete()
            except TelegramError:
                pass
        else:
            await query.edit_message_text(
                text,
                reply_markup=view_kb,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
    except TelegramError as e:
        log.warning(f"show_item error: {e}")
        try:
            await query.message.reply_text(
                text, reply_markup=view_kb, parse_mode=ParseMode.HTML
            )
        except TelegramError:
            pass

# ═══════════════════════════════════════════════════════════
#  COIN MENU
# ═══════════════════════════════════════════════════════════

async def show_coin_menu(query, ctx):
    uid = query.from_user.id
    if not feature_on(ctx.bot_data, "coins") and not is_superadmin(uid):
        await query.answer("Bu bo'lim o'chirilgan.", show_alert=True)
        return
    bal         = C.get_balance(ctx.bot_data, uid)
    ref_count   = C.get_ref_count(ctx.bot_data, uid)
    bot_me      = await ctx.bot.get_me()
    ref_link    = C.get_ref_link(bot_me.username, uid)
    ref_price   = C.get_setting(ctx.bot_data, "coin_per_referral")
    stars_price = C.get_setting(ctx.bot_data, "stars_per_100fc")

    rows = []
    if feature_on(ctx.bot_data, "referrals") or is_superadmin(uid):
        rows.append([btn("👥 Referal", "ref:menu")])
    rows.append([btn("📤 Transfer", "coin:transfer"),
                 btn("📜 Tarix",    "coin:history")])
    rows.append([btn("⭐ Stars → FC", "coin:stars")])
    rows.append([btn("🏠 Bosh menyu", "main")])

    await query.edit_message_text(
        f"💰 <b>FuizCoin</b>\n\n"
        f"Balansingiz: <b>{bal} FC</b>\n"
        f"Referallar: <b>{ref_count}</b> ta\n\n"
        f"📊 <b>Narxlar:</b>\n"
        f"• 1 referal = <b>{ref_price} FC</b>\n"
        f"• {stars_price} ⭐ Stars = <b>100 FC</b>\n\n"
        f"🔗 Referal havolangiz:\n<code>{ref_link}</code>",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML
    )

async def show_ref_menu(query, ctx):
    uid = query.from_user.id
    if not feature_on(ctx.bot_data, "referrals") and not is_superadmin(uid):
        await query.answer("Bu bo'lim o'chirilgan.", show_alert=True)
        return
    bot_me    = await ctx.bot.get_me()
    ref_link  = C.get_ref_link(bot_me.username, uid)
    ref_count = C.get_ref_count(ctx.bot_data, uid)
    channels  = DB.cache_get(ctx.bot_data, "channels")
    ref_chs   = [ch for ch in channels if ch.get("is_referral") == "1"]

    text = (
        f"👥 <b>Referal tizimi</b>\n\n"
        f"Har bir referal uchun: <b>{C.COIN_PER_REFERRAL} FC</b>\n"
        f"Bot guruhga qo'shilsa: <b>{C.COIN_PER_GROUP_ADD} FC</b>\n\n"
        f"Sizning referallaringiz: <b>{ref_count}</b>\n\n"
        f"🔗 Havolangiz:\n<code>{ref_link}</code>"
    )
    rows = []
    for ch in ref_chs:
        ch_link = C.get_channel_ref_link(bot_me.username, uid, ch.get("ch_id",""))
        rows.append([btn(f"📢 {ch.get('name','Kanal')}", url=ch_link)])
    rows.append([btn("🔙 Orqaga", "coin:menu")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML
    )

async def show_coin_history(query, ctx):
    uid  = query.from_user.id
    if not feature_on(ctx.bot_data, "coins") and not is_superadmin(uid):
        await query.answer("Bu bo'lim o'chirilgan.", show_alert=True)
        return
    hist = C.get_history(ctx.bot_data, uid, 15)
    if not hist:
        await query.edit_message_text(
            "📜 <b>Coin tarixi</b>\n\n<i>Hozircha hech narsa yo'q.</i>",
            reply_markup=back_btn("coin:menu"),
            parse_mode=ParseMode.HTML
        )
        return
    lines = ["📜 <b>So'nggi amallar:</b>\n"]
    for h in reversed(hist):
        amt  = h.get("amount","0")
        sign = "+" if not str(amt).startswith("-") else ""
        lines.append(f"{sign}{amt} FC — {h.get('reason','')} | {h.get('date','')}")
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=back_btn("coin:menu"),
        parse_mode=ParseMode.HTML
    )

# ═══════════════════════════════════════════════════════════
#  ADMIN — CHANNELS
# ═══════════════════════════════════════════════════════════

async def show_channels_panel(query, ctx):
    channels = DB.cache_get(ctx.bot_data, "channels")
    lines = ["📢 <b>Majburiy kanallar/guruhlar</b>\n"]
    rows  = [
        [btn("➕ Kanal qo'shish", "adm:ch:add:channel"),
         btn("➕ Guruh qo'shish",  "adm:ch:add:group")]
    ]
    for ch in channels:
        t    = "📢" if ch.get("type") == "channel" else "👥"
        ref  = " 🔗" if ch.get("is_referral") == "1" else ""
        name = ch.get("name","—")
        lines.append(f"{t} {name}{ref}")
        rows.append([btn(f"🗑 {name}", f"adm:ch:del:{ch.get('_msg_id')}")])
    rows.append([btn("🔙 Orqaga", "admin")])
    await query.edit_message_text(
        "\n".join(lines) if len(lines) > 1 else "📢 <b>Majburiy kanallar</b>\n\nHozircha yo'q.",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML
    )

async def show_broadcast_panel(query, ctx):
    await query.edit_message_text(
        "📣 <b>Reklama tarqatish</b>\n\nQayerga yuborasiz?",
        reply_markup=kb(
            [btn("👥 Foydalanuvchilarga", "adm:bc:users")],
            [btn("📢 Kanallarga",          "adm:bc:channels")],
            [btn("🏠 Guruhlarga",          "adm:bc:groups")],
            [btn("🌐 Hammaga",             "adm:bc:all")],
            [btn("🔙 Orqaga",             "admin")],
        ),
        parse_mode=ParseMode.HTML
    )

async def show_stats(query, ctx):
    cache  = ctx.bot_data.get("cache", {})
    users  = len(cache.get("users", []))
    admins = len(ctx.bot_data.get("extra_admins", [])) + len(ADMIN_IDS) + 1
    ch_cnt = len(cache.get("channels", []))
    refs   = len(cache.get("referrals", []))
    bcs    = len(cache.get("broadcasts", []))
    reqs   = len(cache.get("requests", []))
    coins_r = cache.get("coins", [])
    total_coins = 0
    for r in coins_r:
        try:
            total_coins += int(r.get("balance", "0"))
        except (TypeError, ValueError):
            continue

    content_lines = []
    for topic, (emoji, name) in SECTIONS.items():
        cnt = len(cache.get(topic, []))
        if cnt:
            content_lines.append(f"  {emoji} {name}: {cnt}")

    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👤 Foydalanuvchilar: <b>{users}</b>\n"
        f"🔑 Adminlar: <b>{admins}</b>\n"
        f"📢 Kanallar/guruhlar: <b>{ch_cnt}</b>\n"
        f"💰 Jami coinlar: <b>{total_coins} FC</b>\n"
        f"👥 Referallar: <b>{refs}</b>\n"
        f"📣 Reklamalar: <b>{bcs}</b>\n"
        f"📋 Murojaatlar: <b>{reqs}</b>\n\n"
        f"<b>Kontent:</b>\n" + "\n".join(content_lines or ["  <i>Bo'sh</i>"])
    )
    try:
        await query.edit_message_text(
            text,
            reply_markup=kb(
                [btn("👥 Userlarni ko'rish", "adm:users")],
                [btn("🔙 Orqaga", "admin")]
            ),
            parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        if "not modified" not in str(e).lower():
            raise


async def show_delete_menu(query, ctx):
    rows = []
    for topic, (emoji, name) in SECTIONS.items():
        cnt = len(DB.cache_get(ctx.bot_data, topic))
        if cnt > 0:
            rows.append([btn(f"{emoji} {name} ({cnt})", f"adm:dellist:{topic}")])
    rows.append([btn("🔙 Orqaga", "admin")])
    await query.edit_message_text(
        "🗑 <b>Nimani o'chirmoqchisiz?</b>",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML
    )

async def show_delete_list(query, ctx, topic):
    emoji, name = SECTIONS.get(topic, ("📄", topic))
    items = DB.cache_get(ctx.bot_data, topic)
    rows  = []
    for r in items:
        t = r.get("title") or r.get("server_addr") or r.get("_msg_id")
        rows.append([btn(f"🗑 {str(t)[:35]}", f"adm:del_item:{topic}:{r.get('_msg_id')}")])
    rows.append([btn("🔙 Orqaga", "adm:delete")])
    await query.edit_message_text(
        f"🗑 <b>{emoji} {name}</b> — o'chiriladigan elementni tanlang:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML
    )

def request_view_text(r: dict) -> str:
    uname = f"@{r.get('username')}" if r.get("username") else ""
    return (
        f"📩 <b>Murojaat</b>\n"
        f"👤 {r.get('name','')} {uname}\n"
        f"🆔 <code>{r.get('uid')}</code>\n"
        f"🗓 {r.get('date','')}\n"
        f"📊 Status: {'🆕 Yangi' if r.get('status')=='new' else '✅ Ko\'rilgan'}\n\n"
        f"{r.get('text','')}"
    )

async def notify_admins_new_request(bot, bot_data, r: dict):
    """Yangi murojaat kelganda barcha adminlarga to'g'ridan-to'g'ri xabar yuboradi."""
    req_mid = r.get("_msg_id")
    uname   = f"@{r.get('username')}" if r.get("username") else ""
    caption = (
        f"📩 <b>Yangi murojaat!</b>\n"
        f"👤 {r.get('name','')} {uname}\n"
        f"🆔 <code>{r.get('uid')}</code>\n"
        f"🗓 {r.get('date','')}\n\n"
        f"{r.get('text','')}"
    )
    markup = kb(
        [btn("💬 Javob berish", f"adm:reply:{r.get('uid')}:{req_mid}")],
        [btn("🗑 O'chirish", f"adm:req_del:{req_mid}")]
    )
    extra = bot_data.get("extra_admins", [])
    all_admins = set([SUPERADMIN] + ADMIN_IDS + extra)
    for aid in all_admins:
        try:
            if r.get("photo_id"):
                await bot.send_photo(aid, r["photo_id"], caption=caption,
                                      reply_markup=markup, parse_mode=ParseMode.HTML)
            elif r.get("file_id"):
                await bot.send_document(aid, r["file_id"], caption=caption,
                                         reply_markup=markup, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(aid, caption,
                                        reply_markup=markup, parse_mode=ParseMode.HTML)
        except TelegramError as e:
            log.warning(f"notify_admins_new_request → {aid}: {e}")

async def show_promos_panel(query, ctx):
    promos = DB.cache_get(ctx.bot_data, "promocodes")
    lines  = ["🎁 <b>Promokodlar</b>\n"]
    rows   = [[btn("➕ Yangi promokod", "adm:promo:add")]]
    for p in promos:
        code  = p.get("code","—")
        amt   = p.get("amount","0")
        used  = p.get("used","0")
        total = p.get("total_uses","0")
        lines.append(f"▸ <code>{code}</code> — {amt} FC | {used}/{total}")
        rows.append([btn(f"🗑 {code}", f"adm:promo:del:{p.get('_msg_id')}")])
    rows.append([btn("🔙 Orqaga", "sa:panel")])
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML
    )

# ═══════════════════════════════════════════════════════════
#  ADD WIZARD
# ═══════════════════════════════════════════════════════════

async def start_add(query, ctx, uid, topic):
    if topic == "servers":
        # Server uchun avval havola yoki IP tanlash
        set_state(ctx, "add:servers", {"idx": -1})
        await query.edit_message_text(
            "🌐 <b>Server qo'shish</b>\n\n"
            "1. Birinchi server nomini kiriting:",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    steps = ADD_STEPS.get(topic)
    if not steps:
        await query.edit_message_text("❓ Bu bo'lim uchun qo'shish mumkin emas.",
                                       reply_markup=back_btn("adm:content"))
        return
    set_state(ctx, f"add:{topic}", {"idx": 0})
    key, prompt, optional, _ = steps[0]
    mk = skip_cancel_kb() if optional else cancel_btn()
    emoji, name = SECTIONS.get(topic, ("📄", topic))
    await query.edit_message_text(
        f"➕ <b>{emoji} {name}</b> qo'shish\n\n"
        f"<b>1/{len(steps)}</b> — {prompt}",
        reply_markup=mk,
        parse_mode=ParseMode.HTML
    )

async def finalize_add(msg_or_query, ctx, uid, topic, data):
    record = {k: v for k, v in data.items() if k not in ("idx",) and v}
    record.setdefault("date", datetime.now().strftime("%Y-%m-%d"))
    await DB.save(ctx.bot, ctx.bot_data, topic, record)
    clear_state(ctx)
    emoji, name = SECTIONS.get(topic, ("📄", topic))
    txt    = f"✅ <b>{emoji} {name}</b> ga muvaffaqiyatli qo'shildi!"
    fin_kb = kb([btn("📋 Ko'rish", f"sec:{topic}")], [btn("⚙️ Admin", "admin")])
    if hasattr(msg_or_query, "edit_message_text"):
        await msg_or_query.edit_message_text(txt, reply_markup=fin_kb, parse_mode=ParseMode.HTML)
    else:
        await msg_or_query.reply_text(txt, reply_markup=fin_kb, parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════
#  MAIN CALLBACK
# ═══════════════════════════════════════════════════════════

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    uid   = update.effective_user.id
    init_user_ctx(ctx, uid)
    admin = is_admin(uid, ctx.bot_data)
    sa    = is_superadmin(uid)

    if data == "noop":
        return

    # ── Bosh menyu ─────────────────────────────
    if data == "main":
        clear_state(ctx)
        await query.edit_message_text(
            "🎮 <b>FuizTime</b>\n\nQuyidagi bo'limlardan birini tanlang:",
            reply_markup=main_menu_kb(uid, ctx.bot_data),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "admin":
        if not admin:
            await query.answer("❌ Ruxsat yo'q!", show_alert=True)
            return
        clear_state(ctx)
        await query.edit_message_text("⚙️ <b>Admin paneli</b>",
                                       reply_markup=admin_menu_kb(ctx.bot_data),
                                       parse_mode=ParseMode.HTML)
        return

    if data == "sa:panel":
        if not sa:
            await query.answer("❌ Faqat superadmin!", show_alert=True)
            return
        await query.edit_message_text("👑 <b>Superadmin panel</b>",
                                       reply_markup=superadmin_menu_kb(ctx.bot_data),
                                       parse_mode=ParseMode.HTML)
        return

    if data.startswith("sa:toggle:"):
        if not sa:
            await query.answer("❌ Faqat superadmin!", show_alert=True)
            return
        feature = data[10:]
        features = ctx.bot_data.setdefault("features", {})
        current  = feature_on(ctx.bot_data, feature)
        features[feature] = not current
        state_txt = "✅ Yoqildi" if not current else "❌ O'chirildi"
        await query.answer(f"{feature}: {state_txt}", show_alert=True)
        await query.edit_message_text("👑 <b>Superadmin panel</b>",
                                       reply_markup=superadmin_menu_kb(ctx.bot_data),
                                       parse_mode=ParseMode.HTML)
        P.save_cache(ctx.bot_data)
        return

    if data == "cancel":
        clear_state(ctx)
        if admin:
            await query.edit_message_text("❌ Bekor qilindi.",
                                           reply_markup=back_btn("admin"))
        else:
            await query.edit_message_text("🏠 Bosh menyu",
                                           reply_markup=main_menu_kb(uid, ctx.bot_data))
        return

    if data == "check_sub":
        not_subbed = await CH.check_subscription(ctx.bot, uid, ctx.bot_data)
        if not_subbed:
            await query.edit_message_text(
                "⚠️ Hali obuna bo'lmadingiz:",
                reply_markup=CH.subscription_kb(not_subbed)
            )
        else:
            await query.edit_message_text(
                "✅ Obuna tasdiqlandi!\n\n🎮 <b>FuizTime</b>",
                reply_markup=main_menu_kb(uid, ctx.bot_data),
                parse_mode=ParseMode.HTML
            )
        return

    # ── Bo'limlar ──────────────────────────────
    if data.startswith("sec:"):
        try:
            await show_section(query, ctx, data[4:])
        except TelegramError as e:
            log.warning(f"show_section error: {e}")
            try:
                topic = data[4:]
                emoji, name = SECTIONS.get(topic, ("📄", topic))
                await query.message.reply_text(
                    f"{emoji} <b>{name}</b>",
                    reply_markup=kb([btn("🏠 Bosh menyu", "main")]),
                    parse_mode=ParseMode.HTML
                )
            except TelegramError:
                pass
        return

    if data.startswith("page:"):
        _, topic, pg = data.split(":")
        await show_section(query, ctx, topic, int(pg))
        return

    if data.startswith("view:"):
        _, topic, msg_id = data.split(":", 2)
        await show_item(query, ctx, topic, msg_id)
        return

    if data.startswith("dl:"):
        _, topic, msg_id = data.split(":", 2)
        items = DB.cache_get(ctx.bot_data, topic)
        r = next((x for x in items if str(x.get("_msg_id")) == msg_id), None)
        if r and r.get("apk"):
            await query.message.reply_document(
                document=r["apk"],
                caption=f"📥 <b>{r.get('title','APK')}</b>",
                parse_mode=ParseMode.HTML
            )
        else:
            await query.answer("Fayl topilmadi!", show_alert=True)
        return

    # ── Murojaat ───────────────────────────────
    if data == "contact:write":
        can, reason = C.can_send_contact(ctx.bot_data, uid)
        daily_free   = C.get_setting(ctx.bot_data, "contact_daily_free")
        paid_cost    = C.get_setting(ctx.bot_data, "contact_paid_cost")
        paid_count   = C.get_setting(ctx.bot_data, "contact_paid_count")
        usage        = C.get_contact_usage(ctx.bot_data, uid)
        free_used    = usage.get("free", 0)
        stars_price  = C.get_setting(ctx.bot_data, "stars_per_100fc")
        bal          = C.get_balance(ctx.bot_data, uid)

        if not can:
            await query.edit_message_text(
                f"⚠️ <b>Kunlik limit tugadi</b>\n\n"
                f"Bugun bepul: {free_used}/{daily_free}\n\n"
                f"<b>Qo'shimcha murojaat uchun:</b>\n"
                f"• {paid_cost} FC = {paid_count} ta murojaat\n"
                f"• Stars orqali FC olish: {stars_price} ⭐ = 100 FC\n\n"
                f"Sizda: <b>{bal} FC</b>",
                reply_markup=kb(
                    [btn(f"💰 {paid_cost} FC to'lash", "contact:pay_fc")],
                    [btn("⭐ Stars bilan FC olish", "coin:stars")],
                    [btn("🔙 Orqaga", "sec:contact")]
                ),
                parse_mode=ParseMode.HTML
            )
            return

        set_state(ctx, "contact:writing", {})
        await query.edit_message_text(
            f"✍️ <b>Murojaat</b>\n\n"
            f"Xabaringizni yozing (matn, rasm, fayl — istalgan format).\n"
            f"Keyin <b>Jo'natish</b> tugmasini bosing.\n\n"
            f"<i>Bugun bepul: {free_used}/{daily_free}</i>",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "contact:pay_fc":
        paid_cost  = C.get_setting(ctx.bot_data, "contact_paid_cost")
        paid_count = C.get_setting(ctx.bot_data, "contact_paid_count")
        bal        = C.get_balance(ctx.bot_data, uid)
        ok, _      = await C.sub_coins(ctx.bot, ctx.bot_data, uid, paid_cost,
                                        f"contact limit +{paid_count}")
        if not ok:
            await query.answer(f"Yetarli FC yo'q! Sizda: {bal} FC", show_alert=True)
            return
        C.add_paid_contacts(ctx.bot_data, uid, paid_count)
        set_state(ctx, "contact:writing", {})
        await query.edit_message_text(
            f"✅ {paid_cost} FC to'landi, {paid_count} ta murojaat huquqi qo'shildi!\n\n"
            f"✍️ Xabaringizni yozing:",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "contact:send":
        state = get_state(ctx)
        sdata = state.get("data", {})
        draft       = sdata.get("draft_text", "")
        draft_file  = sdata.get("draft_file")
        draft_photo = sdata.get("draft_photo")
        draft_ftype = sdata.get("draft_ftype", "doc")

        if not draft and not draft_file and not draft_photo:
            await query.answer("Xabar bo'sh!", show_alert=True)
            return

        user    = update.effective_user
        can, reason = C.can_send_contact(ctx.bot_data, uid)
        if not can:
            await query.answer("Limit tugagan!", show_alert=True)
            return

        # Limitni belgilash
        is_paid = reason == "paid"
        C.inc_contact_usage(ctx.bot_data, uid, is_paid)

        # DB ga yozish + adminlarga to'g'ridan-to'g'ri xabar yuborish
        r = await DB.save(ctx.bot, ctx.bot_data, "requests", {
            "uid":       str(uid),
            "name":      user.full_name or "",
            "username":  user.username or "",
            "text":      draft[:500],
            "file_id":   draft_file or "",
            "photo_id":  draft_photo or "",
            "ftype":     draft_ftype,
            "status":    "new",
            "date":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        if r.get("_msg_id"):
            await notify_admins_new_request(ctx.bot, ctx.bot_data, r)

        clear_state(ctx)
        await query.edit_message_text(
            "✅ <b>Murojaatingiz qabul qilindi!</b>\n\n"
            "Adminlar ko'rib, tez orada javob berishadi.",
            reply_markup=home_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    # ── Coin ───────────────────────────────────
    if data == "coin:menu":
        await show_coin_menu(query, ctx)
        return

    if data == "coin:history":
        await show_coin_history(query, ctx)
        return

    if data == "coin:promo":
        if not feature_on(ctx.bot_data, "promocodes") and not sa:
            await query.answer("Bu bo'lim o'chirilgan.", show_alert=True)
            return
        set_state(ctx, "use_promo", {})
        await query.edit_message_text(
            "🎁 Promokod kiriting:",
            reply_markup=cancel_btn()
        )
        return

    if data == "coin:transfer":
        if not feature_on(ctx.bot_data, "coins") and not sa:
            await query.answer("Bu bo'lim o'chirilgan.", show_alert=True)
            return
        set_state(ctx, "transfer:uid", {})
        await query.edit_message_text(
            "📤 <b>Transfer</b>\n\n"
            "Qabul qiluvchining Telegram ID sini kiriting:\n"
            "<i>(Username ham bo'ladi: @username)</i>",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "coin:stars":
        stars_price = C.get_setting(ctx.bot_data, "stars_per_100fc")
        await query.edit_message_text(
            f"⭐ <b>Stars → FuizCoin</b>\n\n"
            f"<b>{stars_price} Stars = 100 FC</b>\n\n"
            f"Qanday ishlaydi:\n"
            f"1. 📞 Murojaat orqali adminga yozing\n"
            f"2. Admin Stars qabul qiluvchi raqamni beradi\n"
            f"3. To'lovni amalga oshiring\n"
            f"4. Admin hisobingizga FC qo'shadi\n\n"
            f"<i>Murojaat bo'limiga o'tish uchun:</i>",
            reply_markup=kb(
                [btn("📞 Adminga murojaat", "sec:contact")],
                [btn("🔙 Orqaga", "coin:menu")]
            ),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "ref:menu":
        await show_ref_menu(query, ctx)
        return

    # ── Server type ────────────────────────────
    if data.startswith("srv_type:"):
        stype = data[9:]  # "link" | "ip"
        state = get_state(ctx)
        sdata = state.get("data", {})
        sdata["server_type"] = stype
        sdata["addr_step"]   = True
        set_state(ctx, "add:servers", sdata)
        prompt = "🔗 Server havolasini kiriting (masalan: https://...):" if stype == "link" \
                 else "🖥 Server IP manzilini kiriting (masalan: play.example.com:19132):"
        await query.edit_message_text(
            prompt,
            reply_markup=cancel_btn()
        )
        return

    # ── ADMIN AMALLAR ──────────────────────────
    if not admin:
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    if data == "adm:content":
        await query.edit_message_text("➕ <b>Kontent qo'shish</b>",
                                       reply_markup=content_add_kb(),
                                       parse_mode=ParseMode.HTML)
        return

    if data.startswith("adm:add:"):
        await start_add(query, ctx, uid, data[8:])
        return

    if data == "adm:edit:about":
        set_state(ctx, "edit_about", {})
        await query.edit_message_text(
            "✏️ <b>Haqida</b> matni (HTML qo'llab-quvvatlanadi):",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("adm:del_item:"):
        parts  = data.split(":")
        topic  = parts[2]
        msg_id = parts[3]
        items  = DB.cache_get(ctx.bot_data, topic)
        r      = next((x for x in items if str(x.get("_msg_id")) == msg_id), None)
        title  = r.get("title") or r.get("server_addr") or msg_id if r else msg_id
        ok = await DB.delete(ctx.bot, ctx.bot_data, topic, msg_id)
        result_text = f"✅ <b>{title}</b> o'chirildi!" if ok else "⚠️ O'chirishda xato!"
        # Media xabar bo'lishi mumkin — reply orqali yangi xabar yuboring
        try:
            await query.edit_message_text(
                result_text,
                reply_markup=back_btn(f"sec:{topic}"),
                parse_mode=ParseMode.HTML
            )
        except TelegramError:
            try:
                await query.message.delete()
            except TelegramError:
                pass
            await query.message.reply_text(
                result_text,
                reply_markup=back_btn(f"sec:{topic}"),
                parse_mode=ParseMode.HTML
            )
        return

    if data.startswith("adm:edit_item:"):
        parts  = data.split(":")
        topic  = parts[2]
        msg_id = parts[3]
        items  = DB.cache_get(ctx.bot_data, topic)
        r      = next((x for x in items if str(x.get("_msg_id")) == msg_id), None)
        if not r:
            await query.answer("Topilmadi!", show_alert=True)
            return
        steps = ADD_STEPS.get(topic, [])
        if not steps:
            await query.answer("Bu bo'lim uchun tahrirlash yo'q!", show_alert=True)
            return
        set_state(ctx, f"edit:{topic}:{msg_id}", {"idx": 0, "original": dict(r)})
        k, prompt, _, _ = steps[0]
        cur = r.get(k, "")
        edit_text = (
            f"✏️ <b>Tahrirlash</b>\n\n1/{len(steps)} — {prompt}\n"
            f"<i>Joriy: {cur or '(bosh)'}</i>"
        )
        try:
            await query.edit_message_text(
                edit_text,
                reply_markup=skip_cancel_kb(),
                parse_mode=ParseMode.HTML
            )
        except TelegramError:
            try:
                await query.message.delete()
            except TelegramError:
                pass
            await query.message.reply_text(
                edit_text,
                reply_markup=skip_cancel_kb(),
                parse_mode=ParseMode.HTML
            )
        return

    if data == "adm:delete":
        await show_delete_menu(query, ctx)
        return

    if data.startswith("adm:dellist:"):
        await show_delete_list(query, ctx, data[12:])
        return

    if data == "adm:stats":
        await show_stats(query, ctx)
        return

    if data == "adm:users" or data.startswith("adm:users:"):
        users = DB.cache_get(ctx.bot_data, "users")
        page  = int(data.split(":")[-1]) if data.startswith("adm:users:") else 0
        per   = 10
        start = page * per
        end   = start + per
        page_users = list(reversed(users))[start:end]

        rows = []
        for u in page_users:
            fname = (u.get("fullname","") or "?")[:12]
            uname = f"@{u.get('username')}" if u.get("username") else ""
            bal   = C.get_balance(ctx.bot_data, int(u.get("uid",0)))
            label = f"{fname} {uname} | {bal}FC".strip()
            rows.append([btn(f"👤 {label[:40]}", f"sa:user_profile:{u.get('uid')}")])

        nav = []
        if page > 0:
            nav.append(btn("◀", f"adm:users:{page-1}"))
        if end < len(users):
            nav.append(btn("▶", f"adm:users:{page+1}"))
        if nav:
            rows.append(nav)
        rows.append([btn("🔙 Orqaga", "admin")])

        await query.edit_message_text(
            f"👥 <b>Foydalanuvchilar</b> — {len(users)} ta",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "adm:admins":
        extra = ctx.bot_data.get("extra_admins", [])
        rows  = []
        text  = "👤 <b>Adminlar</b>\n\n👑 Superadmin: <code>" + str(SUPERADMIN) + "</code>"
        if not extra and not ADMIN_IDS:
            text += "\n\n<i>Qo'shimcha admin yo'q.</i>"
        else:
            text += "\n\n<i>Qo'shimcha adminlar:</i>"
        for a in ADMIN_IDS:
            rows.append([btn(f"🔒 {a} (config)", "noop")])
        for a in extra:
            row = [btn(f"👤 {a}", "noop")]
            if sa:
                row.append(btn("🗑", f"adm:admin_del:{a}"))
            rows.append(row)
        if sa:
            rows.append([btn("➕ Admin qo'shish", "adm:admin_add")])
        rows.append([btn("🔙 Orqaga", "admin")])
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "adm:admin_add":
        if not sa:
            await query.answer("❌ Faqat superadmin!", show_alert=True)
            return
        set_state(ctx, "add_admin", {})
        await query.edit_message_text(
            "➕ <b>Yangi admin qo'shish</b>\n\nFoydalanuvchining Telegram ID raqamini yuboring:",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("adm:admin_del:"):
        if not sa:
            await query.answer("❌ Faqat superadmin!", show_alert=True)
            return
        del_id = int(data.split(":")[-1])
        extra  = ctx.bot_data.get("extra_admins", [])
        if del_id in extra:
            extra.remove(del_id)
            rec = DB.cache_find(ctx.bot_data, "admins", uid=str(del_id))
            if rec and rec.get("_msg_id"):
                await DB.delete(ctx.bot, ctx.bot_data, "admins", rec["_msg_id"])
            P.save_cache(ctx.bot_data)
            await query.answer(f"✅ {del_id} adminlikdan olib tashlandi.", show_alert=True)
        else:
            await query.answer("Bu foydalanuvchi adminlar ro'yxatida yo'q.", show_alert=True)
        # Panelni yangilab qayta ko'rsatish
        extra = ctx.bot_data.get("extra_admins", [])
        rows  = []
        text  = "👤 <b>Adminlar</b>\n\n👑 Superadmin: <code>" + str(SUPERADMIN) + "</code>"
        if not extra and not ADMIN_IDS:
            text += "\n\n<i>Qo'shimcha admin yo'q.</i>"
        else:
            text += "\n\n<i>Qo'shimcha adminlar:</i>"
        for a in ADMIN_IDS:
            rows.append([btn(f"🔒 {a} (config)", "noop")])
        for a in extra:
            row = [btn(f"👤 {a}", "noop")]
            if sa:
                row.append(btn("🗑", f"adm:admin_del:{a}"))
            rows.append(row)
        if sa:
            rows.append([btn("➕ Admin qo'shish", "adm:admin_add")])
        rows.append([btn("🔙 Orqaga", "admin")])
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "adm:requests":
        reqs = DB.cache_get(ctx.bot_data, "requests")
        new_reqs = [r for r in reqs if r.get("status") == "new"]
        rows = []
        for r in reversed(reqs[-20:]):
            status = "🆕" if r.get("status") == "new" else "✅"
            name   = r.get("name","?")[:15]
            text   = r.get("text","")[:25]
            rows.append([btn(f"{status} {name}: {text}", f"adm:req_view:{r.get('_msg_id')}")])
        rows.append([btn("🔙 Orqaga", "admin")])
        await query.edit_message_text(
            f"📋 <b>Murojaatlar</b> — {len(reqs)} ta (yangi: {len(new_reqs)})",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("adm:req_view:"):
        msg_id = data[13:]
        reqs   = DB.cache_get(ctx.bot_data, "requests")
        r      = next((x for x in reqs if str(x.get("_msg_id")) == msg_id), None)
        if not r:
            await query.answer("Topilmadi!")
            return
        text  = request_view_text(r)
        rows = [[btn("💬 Javob berish", f"adm:reply:{r.get('uid')}:{msg_id}")]]
        if r.get("status") == "new":
            rows.append([btn("✅ Ko'rildi deb belgilash", f"adm:req_done:{msg_id}")])
        rows.append([btn("🗑 O'chirish", f"adm:req_del:{msg_id}")])
        rows.append([btn("🔙 Orqaga", "adm:requests")])
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("adm:req_done:"):
        msg_id = data[13:]
        reqs   = DB.cache_get(ctx.bot_data, "requests")
        r      = next((x for x in reqs if str(x.get("_msg_id")) == msg_id), None)
        if r:
            r["status"] = "done"
            await DB.update(ctx.bot, ctx.bot_data, "requests", r)
        await query.answer("✅ Belgilandi!")
        await query.edit_message_text("✅ Ko'rildi!", reply_markup=back_btn("adm:requests"))
        return

    if data.startswith("adm:req_del:"):
        msg_id = data[12:]
        await DB.delete(ctx.bot, ctx.bot_data, "requests", msg_id)
        await query.answer("🗑 O'chirildi!")
        # Bu tugma ham oddiy matnli panelda, ham (rasm/fayl bilan kelgan)
        # admin bildirishnoma xabarida bo'lishi mumkin — shunga moslab ishlaymiz.
        try:
            await query.edit_message_text(
                "🗑 Murojaat o'chirildi.",
                reply_markup=back_btn("adm:requests")
            )
        except TelegramError:
            try:
                await query.edit_message_caption(
                    caption="🗑 Murojaat o'chirildi.",
                    reply_markup=back_btn("adm:requests")
                )
            except TelegramError:
                try:
                    await query.message.delete()
                except TelegramError:
                    pass
                await query.message.reply_text(
                    "🗑 Murojaat o'chirildi.",
                    reply_markup=back_btn("adm:requests")
                )
        return

    if data.startswith("adm:reply:"):
        parts      = data[10:].split(":")
        target_uid = int(parts[0])
        req_mid    = parts[1] if len(parts) > 1 else ""
        set_state(ctx, f"admin_reply:{target_uid}:{req_mid}", {})
        await query.edit_message_text(
            f"💬 <b>Javob yozish</b>\n\n"
            f"Foydalanuvchi: <code>{target_uid}</code>\n\n"
            f"Xabaringizni yozing — yozib bo'lganingizdan keyin "
            f"<b>Jo'natish</b> tugmasi chiqadi:",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("adm:reply_confirm:"):
        # Admin javobni tasdiqladi — yuboramiz
        parts      = data[18:].split(":")
        target_uid = int(parts[0])
        req_mid    = parts[1] if len(parts) > 1 else ""
        state      = get_state(ctx)
        draft      = state.get("data", {}).get("draft", "")
        if not draft:
            await query.answer("Xabar bo'sh!", show_alert=True)
            return
        try:
            await ctx.bot.send_message(
                target_uid,
                f"💬 <b>Admin javobi:</b>\n\n{draft}",
                parse_mode=ParseMode.HTML
            )
            if req_mid:
                reqs = DB.cache_get(ctx.bot_data, "requests")
                r    = next((x for x in reqs if str(x.get("_msg_id")) == req_mid), None)
                if r:
                    r["status"] = "answered"
                    await DB.update(ctx.bot, ctx.bot_data, "requests", r)
            clear_state(ctx)
            await query.edit_message_text(
                "✅ Javob yuborildi!",
                reply_markup=back_btn("adm:requests")
            )
        except TelegramError as e:
            await query.edit_message_text(
                f"❌ Xabar yuborilmadi: {e}",
                reply_markup=cancel_btn()
            )
        return

    if data.startswith("adm:reply_cancel:"):
        clear_state(ctx)
        await query.edit_message_text(
            "❌ Javob bekor qilindi.",
            reply_markup=back_btn("adm:requests")
        )
        return

    if data == "adm:channels":
        await show_channels_panel(query, ctx)
        return

    if data in ("adm:ch:add:channel", "adm:ch:add:group"):
        ctype = "channel" if data.endswith("channel") else "group"
        set_state(ctx, f"add_ch:{ctype}", {"idx": 0})
        await query.edit_message_text(
            f"➕ {'Kanal' if ctype=='channel' else 'Guruh'} qo'shish\n\n"
            f"1. Chat ID yoki @username kiriting:",
            reply_markup=cancel_btn()
        )
        return

    if data.startswith("adm:ch:del:"):
        msg_id = data[11:]
        await DB.delete(ctx.bot, ctx.bot_data, "channels", msg_id)
        await query.edit_message_text("✅ O'chirildi!", reply_markup=back_btn("adm:channels"))
        return

    if data == "adm:broadcast":
        await show_broadcast_panel(query, ctx)
        return

    if data.startswith("adm:bc:"):
        bc_type = data[7:]
        set_state(ctx, f"broadcast:{bc_type}", {})
        targets = {
            "users": "foydalanuvchilarga",
            "channels": "kanallarga",
            "groups": "guruhlarga",
            "all": "HAMMAGA",
        }
        await query.edit_message_text(
            f"📣 <b>Reklama — {targets.get(bc_type,'')}</b>\n\n"
            f"Yubormoqchi bo'lgan xabarni yozing (HTML formatlab ham bo'ladi):",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    # Superadmin only
    if data == "adm:coin:give":
        await query.edit_message_text(
            "💰 <b>Coin berish</b>\n\nQanday usulda topasiz?",
            reply_markup=kb(
                [btn("🆔 ID orqali",       "adm:coin:give:id")],
                [btn("👤 @username orqali", "adm:coin:give:username")],
                [btn("❌ Bekor",            "cancel")],
            ),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "adm:coin:give:id":
        set_state(ctx, "admin_give_coin:uid", {"by": "id"})
        await query.edit_message_text(
            "💰 <b>Coin berish</b>\n\nTelegram ID ni kiriting:",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "adm:coin:give:username":
        set_state(ctx, "admin_give_coin:uid", {"by": "username"})
        await query.edit_message_text(
            "💰 <b>Coin berish</b>\n\n@username kiriting:",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "adm:coin:balances":
        coins = DB.cache_get(ctx.bot_data, "coins")
        sorted_coins = sorted(coins, key=lambda x: int(x.get("balance","0")), reverse=True)
        rows = []
        for r in sorted_coins[:20]:
            uname = f"@{r['username']}" if r.get("username") else r.get("uid","?")
            bal   = r.get("balance","0")
            rows.append([btn(f"👤 {uname} — {bal} FC", f"sa:user_profile:{r.get('uid')}")])
        rows.append([btn("🔙 Orqaga", "sa:panel")])
        await query.edit_message_text(
            "💰 <b>Balanslar (Top 20)</b>",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("sa:user_profile:"):
        target_uid = data[16:]
        users  = DB.cache_get(ctx.bot_data, "users")
        u      = next((x for x in users if str(x.get("uid")) == target_uid), {})
        bal    = C.get_balance(ctx.bot_data, int(target_uid))
        refs   = C.get_ref_count(ctx.bot_data, int(target_uid))
        hist   = C.get_history(ctx.bot_data, int(target_uid), 5)
        reqs   = [r for r in DB.cache_get(ctx.bot_data, "requests")
                  if str(r.get("uid")) == target_uid]
        uname  = f"@{u.get('username')}" if u.get("username") else "(yo'q)"
        fname  = u.get("fullname", "—")
        reg    = u.get("date", "—")

        hist_lines = ""
        for h in reversed(hist):
            amt  = h.get("amount","0")
            sign = "+" if not str(amt).startswith("-") else ""
            hist_lines += f"  {sign}{amt} FC — {h.get('reason','')[:25]}\n"

        # Back tugmasi — kim ko'ryapti
        back_to = "adm:users" if not sa else "adm:coin:balances"

        text = (
            f"👤 <b>User profili</b>\n\n"
            f"🆔 ID: <code>{target_uid}</code>\n"
            f"👤 Ism: {fname}\n"
            f"📛 Username: {uname}\n"
            f"📅 Ro'yxat: {reg}\n\n"
            f"💰 Balans: <b>{bal} FC</b>\n"
            f"👥 Referallar: <b>{refs}</b>\n"
            f"📋 Murojaatlar: <b>{len(reqs)}</b>\n\n"
            f"📜 So'nggi coinlar:\n{hist_lines or chr(32)*2+'(bosh)'}"
        )
        rows = [
            [btn("💰 Coin berish",    f"sa:give_to:{target_uid}")],
            [btn("💬 Xabar yuborish", f"sa:msg_to:{target_uid}")],
            [btn("🔙 Orqaga",         back_to)],
        ]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("sa:give_to:"):
        if not sa:
            await query.answer("Faqat superadmin!", show_alert=True)
            return
        target_uid = int(data[11:])
        set_state(ctx, "admin_give_coin:amount", {"to_uid": target_uid})
        await query.edit_message_text(
            f"💰 User <code>{target_uid}</code> ga qancha FC berasiz?",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("sa:msg_to:"):
        if not sa:
            await query.answer("Faqat superadmin!", show_alert=True)
            return
        target_uid = int(data[10:])
        set_state(ctx, f"admin_reply:{target_uid}:", {})
        await query.edit_message_text(
            f"💬 <code>{target_uid}</code> ga xabar yozing:",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "adm:promos":
        await show_promos_panel(query, ctx)
        return

    if data == "adm:promo:add":
        if not sa:
            await query.answer("Faqat superadmin!", show_alert=True)
            return
        set_state(ctx, "add_promo:code", {})
        await query.edit_message_text(
            "🎁 <b>Yangi promokod</b>\n\n1. Promokod kodi:",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("adm:promo:del:"):
        if not sa:
            await query.answer("Faqat superadmin!", show_alert=True)
            return
        msg_id = data[14:]
        await DB.delete(ctx.bot, ctx.bot_data, "promocodes", msg_id)
        await show_promos_panel(query, ctx)
        return

    if data == "sa:export":
        if not sa:
            await query.answer("Faqat superadmin!", show_alert=True)
            return
        await query.answer("⏳ Backup tayyorlanmoqda...")
        ok = await BK.export_backup(ctx.bot, ctx.bot_data)
        if ok:
            ctx.bot_data["change_counter"] = 0
        await query.edit_message_text(
            "✅ Backup backup topicga yuborildi!" if ok else "❌ Backup yuborishda xato!",
            reply_markup=back_btn("sa:panel")
        )
        return

    if data == "sa:import":
        if not sa:
            await query.answer("Faqat superadmin!", show_alert=True)
            return
        init_user_ctx(ctx, uid)
        set_state(ctx, "waiting_import", {})
        await query.edit_message_text(
            "📥 <b>Restore qilish</b>\n\n"
            "Backup JSON faylni yuboring:",
            reply_markup=cancel_btn(),
            parse_mode="HTML"
        )
        return

    if data == "sa:settings":
        if not sa:
            await query.answer("Faqat superadmin!", show_alert=True)
            return
        from coins import DEFAULT_SETTINGS
        s = ctx.bot_data.get("settings", {})
        def sv(k): return s.get(k, DEFAULT_SETTINGS[k])
        await query.edit_message_text(
            f"⚙️ <b>Narxlar va Limitlar</b>\n\n"
            f"1️⃣ 1 referal = <b>{sv('coin_per_referral')} FC</b>\n"
            f"2️⃣ Stars/100FC = <b>{sv('stars_per_100fc')} ⭐</b>\n"
            f"3️⃣ Kunlik bepul murojaat = <b>{sv('contact_daily_free')}</b> ta\n"
            f"4️⃣ Qo'shimcha murojaat narxi = <b>{sv('contact_paid_cost')} FC</b>\n"
            f"5️⃣ FC evaziga murojaat soni = <b>{sv('contact_paid_count')}</b> ta\n"
            f"6️⃣ Admin max coin berishi = <b>{sv('admin_max_coin')} FC</b>\n\n"
            f"O'zgartirish uchun raqamni tanlang:",
            reply_markup=kb(
                [btn("1️⃣ Referal FC",    "sa:set:coin_per_referral"),
                 btn("2️⃣ Stars/100FC",   "sa:set:stars_per_100fc")],
                [btn("3️⃣ Bepul limit",   "sa:set:contact_daily_free"),
                 btn("4️⃣ FC narxi",      "sa:set:contact_paid_cost")],
                [btn("5️⃣ Murojaat soni", "sa:set:contact_paid_count"),
                 btn("6️⃣ Admin max coin","sa:set:admin_max_coin")],
                [btn("🔙 Orqaga", "sa:panel")],
            ),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("sa:set:"):
        if not sa:
            await query.answer("Faqat superadmin!", show_alert=True)
            return
        setting_key = data[7:]
        labels = {
            "coin_per_referral":   "1 referal uchun FC miqdori",
            "stars_per_100fc":     "100 FC uchun Stars miqdori",
            "contact_daily_free":  "Kunlik bepul murojaatlar soni",
            "contact_paid_cost":   "Qo'shimcha murojaat FC narxi",
            "contact_paid_count":  "FC evaziga murojaatlar soni",
            "admin_max_coin":      "Admin bir marta bera oladigan max FC",
        }
        set_state(ctx, f"sa_setting:{setting_key}", {})
        await query.edit_message_text(
            f"⚙️ <b>{labels.get(setting_key, setting_key)}</b>\n\nYangi qiymatni kiriting (raqam):",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "skip":
        await handle_skip(query, ctx, uid)
        return

    if data.startswith("ch_ref:"):
        await handle_ch_ref(query, ctx, uid, data)
        return

    await query.edit_message_text("❓ Noma'lum amal.", reply_markup=home_btn())

# ═══════════════════════════════════════════════════════════
#  SKIP & CH_REF
# ═══════════════════════════════════════════════════════════

async def handle_skip(query, ctx, uid):
    state = get_state(ctx)
    sname = state.get("name","")
    sdata = state.get("data",{})

    if sname.startswith("add:"):
        topic = sname[4:]
        steps = ADD_STEPS.get(topic, [])
        idx   = sdata.get("idx", 0) + 1
        sdata["idx"] = idx
        if idx >= len(steps):
            await finalize_add(query, ctx, uid, topic, sdata)
            return
        k, prompt, optional, _ = steps[idx]
        set_state(ctx, sname, sdata)
        await query.edit_message_text(
            f"<b>{idx+1}/{len(steps)}</b> — {prompt}",
            reply_markup=skip_cancel_kb() if optional else cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if sname.startswith("edit:"):
        parts  = sname.split(":")
        topic  = parts[1]
        msg_id = parts[2]
        steps  = ADD_STEPS.get(topic, [])
        idx    = sdata.get("idx", 0) + 1
        sdata["idx"] = idx
        if idx >= len(steps):
            original = sdata.get("original", {})
            await DB.update(ctx.bot, ctx.bot_data, topic, original)
            DB.cache_update(ctx.bot_data, topic, msg_id, original)
            clear_state(ctx)
            await query.edit_message_text("✅ Yangilandi!", reply_markup=back_btn("admin"))
            return
        k, prompt, _, _ = steps[idx]
        cur = sdata.get("original",{}).get(k,"")
        set_state(ctx, sname, sdata)
        await query.edit_message_text(
            f"<b>{idx+1}/{len(steps)}</b> — {prompt}\n<i>Joriy: {cur or '(bosh)'}</i>",
            reply_markup=skip_cancel_kb(),
            parse_mode=ParseMode.HTML
        )

async def handle_ch_ref(query, ctx, uid, data):
    is_ref = data == "ch_ref:yes"
    state  = get_state(ctx)
    sname  = state.get("name","")
    sdata  = state.get("data",{})
    if not sname.startswith("add_ch:"):
        return
    ctype  = sname[7:]
    ch_id  = sdata.get("ch_id","")
    name   = sdata.get("name","")
    invite_link = ""
    try:
        chat = await ctx.bot.get_chat(ch_id)
        invite_link = chat.invite_link or ""
    except TelegramError:
        pass
    if ctype == "channel":
        r = await CH.add_channel(ctx.bot, ctx.bot_data, ch_id, name, invite_link, is_ref)
    else:
        r = await CH.add_group(ctx.bot, ctx.bot_data, ch_id, name, invite_link, is_ref)
    clear_state(ctx)
    if isinstance(r, str):
        await query.edit_message_text(f"❌ {r}", reply_markup=back_btn("adm:channels"))
    else:
        ref_txt = " (referal tizimida)" if is_ref else ""
        await query.edit_message_text(
            f"✅ <b>{name}</b>{ref_txt} qo'shildi!",
            reply_markup=back_btn("adm:channels"),
            parse_mode=ParseMode.HTML
        )

# ═══════════════════════════════════════════════════════════
#  MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    uid   = update.effective_user.id
    user  = update.effective_user
    init_user_ctx(ctx, uid)
    text  = msg.text or msg.caption or ""
    doc   = msg.document
    photo = msg.photo
    video = msg.video
    admin = is_admin(uid, ctx.bot_data)
    sa    = is_superadmin(uid)
    state = get_state(ctx)
    sname = state.get("name", "")
    sdata = state.get("data", {})

    # Guruhda bot faqat /start va /admin buyruqlariga javob beradi
    # Oddiy xabarlarga, forward larga javob bermaydi
    is_private = update.effective_chat.type == "private"
    if not is_private:
        return

    # Forward faqat wizard holatida (fayl yuborish uchun) o'tadi
    is_wizard = any(sname.startswith(p) for p in ("add:", "edit:", "waiting_import"))
    if msg.forward_origin and not is_wizard:
        return

    # ── Murojaat yozish (user) ─────────────────
    if sname == "contact:writing":
        sdata["draft_text"]  = text
        if photo:
            sdata["draft_photo"] = photo[-1].file_id
        elif doc:
            sdata["draft_file"]  = doc.file_id
            sdata["draft_ftype"] = "doc"
        elif video:
            sdata["draft_file"]  = video.file_id
            sdata["draft_ftype"] = "video"
        set_state(ctx, "contact:writing", sdata)

        preview = text[:100] if text else "[media]"
        await msg.reply_text(
            f"📝 <b>Xabaringiz:</b>\n{preview}\n\n"
            f"Jo'natishni tasdiqlaysizmi?",
            reply_markup=kb(
                [btn("📤 Jo'natish", "contact:send")],
                [btn("❌ Bekor", "cancel")]
            ),
            parse_mode=ParseMode.HTML
        )
        return

    # ── Promokod (user) ────────────────────────
    if sname == "use_promo":
        code = text.strip().upper()
        ok, result = await C.use_promo(ctx.bot, ctx.bot_data, uid, code,
                                        user.username or "")
        clear_state(ctx)
        await msg.reply_text(result, reply_markup=home_btn())
        return

    # ── Transfer (user) ────────────────────────
    if sname == "transfer:uid":
        t = text.strip()
        # @username yoki ID
        if t.startswith("@"):
            # username bo'yicha topish
            found = next(
                (u for u in DB.cache_get(ctx.bot_data, "users")
                 if u.get("username","").lower() == t[1:].lower()),
                None
            )
            if not found:
                await msg.reply_text(
                    "❌ Bu username topilmadi!\nTelegram ID ni to'g'ridan kiriting.",
                    reply_markup=cancel_btn()
                )
                return
            to_uid = int(found["uid"])
        elif t.lstrip("-").isdigit():
            to_uid = int(t)
        else:
            await msg.reply_text("❌ Noto'g'ri format! ID yoki @username kiriting.",
                                  reply_markup=cancel_btn())
            return

        if to_uid == uid:
            await msg.reply_text("❌ O'zingizga transfer qilib bo'lmaydi!",
                                  reply_markup=cancel_btn())
            return

        sdata["to_uid"] = to_uid
        set_state(ctx, "transfer:amount", sdata)
        await msg.reply_text(
            f"Qabul qiluvchi: <code>{to_uid}</code>\n\nQancha FC yuborasiz?",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if sname == "transfer:amount":
        if not text.strip().isdigit() or int(text.strip()) <= 0:
            await msg.reply_text("❌ Musbat raqam kiriting!", reply_markup=cancel_btn())
            return
        amount  = int(text.strip())
        to_uid  = sdata.get("to_uid")
        ok, err = await C.transfer_coins(ctx.bot, ctx.bot_data, uid, to_uid, amount)
        clear_state(ctx)
        if ok:
            new_bal = C.get_balance(ctx.bot_data, uid)
            await msg.reply_text(
                f"✅ <b>{to_uid}</b> ga <b>{amount} FC</b> o'tkazildi!\n"
                f"Qolgan balans: <b>{new_bal} FC</b>",
                reply_markup=home_btn(),
                parse_mode=ParseMode.HTML
            )
            try:
                await ctx.bot.send_message(
                    to_uid,
                    f"💰 Sizga <b>{amount} FC</b> transfer qilindi!\n"
                    f"Balans: <b>{C.get_balance(ctx.bot_data, to_uid)} FC</b>",
                    parse_mode=ParseMode.HTML
                )
            except TelegramError:
                pass
        else:
            cur_bal = C.get_balance(ctx.bot_data, uid)
            await msg.reply_text(
                f"❌ {err}\nSizda: <b>{cur_bal} FC</b>",
                reply_markup=home_btn(),
                parse_mode=ParseMode.HTML
            )
        return

    # ── ADMIN ONLY ─────────────────────────────
    if not admin:
        await msg.reply_text(
            "🎮 FuizTime botiga xush kelibsiz!\n/start",
            reply_markup=home_btn()
        )
        return

    # ── Import fayl kutish ────────────────────
    if sname == "waiting_import":
        # Forward yoki oddiy fayl — ikkalasi ham qabul
        if not doc:
            await msg.reply_text(
                "❌ Fayl yuboring! (JSON backup faylini forward qiling)",
                reply_markup=cancel_btn()
            )
            return
        if not doc.file_name.endswith(".json"):
            await msg.reply_text("❌ Faqat .json fayl qabul qilinadi!", reply_markup=cancel_btn())
            return
        await msg.reply_text("⏳ Restore qilinmoqda...")
        tg_file       = await ctx.bot.get_file(doc.file_id)
        content_bytes = await tg_file.download_as_bytearray()
        ok, result    = BK.import_backup(ctx.bot_data, bytes(content_bytes))
        if ok:
            P.save_cache(ctx.bot_data)
        clear_state(ctx)
        await msg.reply_text(result, parse_mode="HTML", reply_markup=back_btn("sa:panel"))
        return

    # ── Admin javob berish ─────────────────────
    if sname.startswith("admin_reply:"):
        parts      = sname[12:].split(":")
        target_uid = parts[0]
        req_mid    = parts[1] if len(parts) > 1 else ""
        if not text.strip():
            await msg.reply_text("❌ Xabar bo'sh!", reply_markup=cancel_btn())
            return
        # Draft saqlash va confirm so'rash
        sdata["draft"] = text.strip()
        set_state(ctx, sname, sdata)
        await msg.reply_text(
            f"💬 <b>Javob ko'rinishi:</b>\n\n{text.strip()}\n\n"
            f"Yuborilsinmi?",
            reply_markup=kb(
                [btn("✅ Ha, yuborish", f"adm:reply_confirm:{target_uid}:{req_mid}")],
                [btn("✏️ Qayta yozish", f"adm:reply:{target_uid}:{req_mid}")],
                [btn("❌ Bekor", f"adm:reply_cancel:{target_uid}:{req_mid}")]
            ),
            parse_mode=ParseMode.HTML
        )
        return

    # ── Superadmin settings ────────────────────
    if sname.startswith("sa_setting:"):
        setting_key = sname[11:]
        if not text.strip().lstrip("-").isdigit():
            await msg.reply_text("❌ Raqam kiriting!", reply_markup=cancel_btn())
            return
        value = int(text.strip())
        if value < 0:
            await msg.reply_text("❌ Manfiy bo'lmaydi!", reply_markup=cancel_btn())
            return
        C.set_setting(ctx.bot_data, setting_key, value)
        clear_state(ctx)
        P.save_cache(ctx.bot_data)
        await msg.reply_text(
            f"✅ <b>{setting_key}</b> = <b>{value}</b> ga o'zgartirildi!",
            reply_markup=back_btn("sa:settings"),
            parse_mode=ParseMode.HTML
        )
        return

    # ── Admin qo'shish (inline) ────────────────
    if sname == "add_admin":
        if not sa:
            clear_state(ctx)
            return
        if not text.strip().lstrip("-").isdigit():
            await msg.reply_text("❌ Faqat raqam (Telegram ID) kiriting!", reply_markup=cancel_btn())
            return
        new_id = int(text.strip())
        extra  = ctx.bot_data.setdefault("extra_admins", [])
        clear_state(ctx)
        if new_id == SUPERADMIN or new_id in extra or new_id in ADMIN_IDS:
            await msg.reply_text(
                "⚠️ Bu foydalanuvchi allaqachon admin.",
                reply_markup=back_btn("adm:admins")
            )
            return
        extra.append(new_id)
        await DB.save(ctx.bot, ctx.bot_data, "admins", {
            "uid":  str(new_id),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        P.save_cache(ctx.bot_data)
        await msg.reply_text(
            f"✅ <code>{new_id}</code> admin qilindi.",
            reply_markup=back_btn("adm:admins"),
            parse_mode=ParseMode.HTML
        )
        return

    # ── Haqida ────────────────────────────────

    if sname == "edit_about":
        ctx.bot_data["about_text"] = text
        about_mid = ctx.bot_data.get("about_msg_id")
        sent_mid  = await DB.db_write(ctx.bot, "about", {"title":"ABOUT","body":text}, about_mid)
        if sent_mid:
            ctx.bot_data["about_msg_id"] = sent_mid
        clear_state(ctx)
        await msg.reply_text("✅ <b>Haqida</b> yangilandi!",
                              reply_markup=back_btn("admin"),
                              parse_mode=ParseMode.HTML)
        return

    # ── Kontent qo'shish ──────────────────────
    if sname.startswith("add:"):
        topic = sname[4:]

        # Server alohida flow
        if topic == "servers":
            await handle_server_add(msg, ctx, uid, sdata, text, doc, photo, video)
            return

        steps = ADD_STEPS.get(topic, [])
        idx   = sdata.get("idx", 0)
        if idx >= len(steps):
            return
        key, _, optional, accept = steps[idx]

        val = None
        if accept == "doc":
            if doc:
                val = doc.file_id
            elif not optional:
                await msg.reply_text("❌ Fayl (dokument) yuboring!", reply_markup=cancel_btn())
                return
        elif accept == "photo_video":
            if photo:
                sdata["media_id"]   = photo[-1].file_id
                sdata["media_type"] = "photo"
                val = photo[-1].file_id
            elif video:
                sdata["media_id"]   = video.file_id
                sdata["media_type"] = "video"
                val = video.file_id
            elif doc and doc.mime_type and doc.mime_type.startswith("video"):
                sdata["media_id"]   = doc.file_id
                sdata["media_type"] = "video"
                val = doc.file_id
            elif not optional:
                await msg.reply_text("❌ Rasm yoki video yuboring!", reply_markup=cancel_btn())
                return
        else:
            val = text.strip() or None

        if key in ("media_id", "media_type"):
            pass  # Already set above
        elif val:
            sdata[key] = val

        idx += 1
        sdata["idx"] = idx

        if idx >= len(steps):
            set_state(ctx, sname, sdata)
            await finalize_add(msg, ctx, uid, topic, sdata)
            return

        nk, nprompt, noptional, _ = steps[idx]
        set_state(ctx, sname, sdata)
        await msg.reply_text(
            f"<b>{idx+1}/{len(steps)}</b> — {nprompt}",
            reply_markup=skip_cancel_kb() if noptional else cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    # ── Server qo'shish ───────────────────────
    if sname == "add:servers":
        await handle_server_add(msg, ctx, uid, sdata, text, doc, photo, video)
        return

    # ── Tahrirlash ────────────────────────────
    if sname.startswith("edit:"):
        parts    = sname.split(":")
        topic    = parts[1]
        msg_id   = parts[2]
        steps    = ADD_STEPS.get(topic, [])
        idx      = sdata.get("idx", 0)
        original = sdata.get("original", {})
        if idx >= len(steps):
            return
        key, _, _, accept = steps[idx]
        val = None
        if accept == "doc" and doc:
            val = doc.file_id
        elif accept == "photo_video":
            if photo:
                original["media_id"]   = photo[-1].file_id
                original["media_type"] = "photo"
                val = photo[-1].file_id
            elif video:
                original["media_id"]   = video.file_id
                original["media_type"] = "video"
                val = video.file_id
        elif text.strip():
            val = text.strip()
        if val and key not in ("media_id","media_type"):
            original[key] = val
        idx += 1
        sdata["idx"]      = idx
        sdata["original"] = original
        if idx >= len(steps):
            await DB.update(ctx.bot, ctx.bot_data, topic, original)
            DB.cache_update(ctx.bot_data, topic, msg_id, original)
            clear_state(ctx)
            await msg.reply_text("✅ Yangilandi!", reply_markup=back_btn("admin"))
            return
        k2, p2, _, _ = steps[idx]
        cur = original.get(k2,"")
        set_state(ctx, sname, sdata)
        await msg.reply_text(
            f"<b>{idx+1}/{len(steps)}</b> — {p2}\n<i>Joriy: {cur or '(bosh)'}</i>",
            reply_markup=skip_cancel_kb(),
            parse_mode=ParseMode.HTML
        )
        return

    # ── Kanal qo'shish ────────────────────────
    if sname.startswith("add_ch:"):
        step  = sdata.get("idx", 0)
        if step == 0:
            sdata["ch_id"] = text.strip()
            sdata["idx"]   = 1
            set_state(ctx, sname, sdata)
            await msg.reply_text("2. Kanal/guruh nomi:", reply_markup=cancel_btn())
        elif step == 1:
            sdata["name"] = text.strip()
            sdata["idx"]  = 2
            set_state(ctx, sname, sdata)
            await msg.reply_text(
                "3. Referal tizimiga qo'shilsinmi?",
                reply_markup=kb(
                    [btn("✅ Ha, referal", "ch_ref:yes"),
                     btn("❌ Yo'q",        "ch_ref:no")]
                )
            )
        return

    # ── Broadcast ─────────────────────────────
    if sname.startswith("broadcast:"):
        bc_type = sname[10:]
        bc_text = text or ""
        if not bc_text:
            await msg.reply_text("❌ Xabar bo'sh bo'lishi mumkin emas!")
            return
        await msg.reply_text("⏳ Yuborilmoqda...")
        if bc_type == "users":
            r   = await CH.broadcast_to_users(ctx.bot, ctx.bot_data, bc_text)
            res = f"✅ Foydalanuvchilar:\nYuborildi: {r['sent']}\nBlok: {r['blocked']}"
        elif bc_type == "channels":
            r   = await CH.broadcast_to_channels(ctx.bot, ctx.bot_data, bc_text)
            res = f"✅ Kanallar:\nYuborildi: {r['sent']}\nMuvaffaqiyatsiz: {r['failed']}"
        elif bc_type == "groups":
            r   = await CH.broadcast_to_groups(ctx.bot, ctx.bot_data, bc_text)
            res = f"✅ Guruhlar:\nYuborildi: {r['sent']}"
        else:
            r   = await CH.broadcast_to_all(ctx.bot, ctx.bot_data, bc_text)
            res = (f"✅ Jami:\nUserlar: {r['users']['sent']}\n"
                   f"Kanallar: {r['channels']['sent']}\n"
                   f"Guruhlar: {r['groups']['sent']}")
        clear_state(ctx)
        await msg.reply_text(res, reply_markup=back_btn("adm:broadcast"))
        return

    # ── Coin berish (superadmin) ───────────────
    if sname == "admin_give_coin:uid":
        t    = text.strip()
        by   = sdata.get("by", "id")
        to_uid = None

        if by == "username":
            uname = t.lstrip("@").lower()
            found = next(
                (u for u in DB.cache_get(ctx.bot_data, "users")
                 if u.get("username","").lower() == uname),
                None
            )
            if not found:
                await msg.reply_text(
                    f"❌ @{uname} topilmadi!\nUser avval /start bosgan bo'lishi kerak.",
                    reply_markup=cancel_btn()
                )
                return
            to_uid = int(found["uid"])
        else:
            if not t.lstrip("-").isdigit():
                await msg.reply_text("❌ Faqat raqam kiriting!", reply_markup=cancel_btn())
                return
            to_uid = int(t)

        sdata["to_uid"] = to_uid
        set_state(ctx, "admin_give_coin:amount", sdata)
        await msg.reply_text(
            f"✅ User: <code>{to_uid}</code>\n\nQancha FC berasiz?",
            reply_markup=cancel_btn(),
            parse_mode=ParseMode.HTML
        )
        return

    if sname == "admin_give_coin:amount":
        if not text.strip().lstrip("-").isdigit():
            await msg.reply_text("❌ Raqam kiriting!", reply_markup=cancel_btn())
            return
        amount = int(text.strip())
        to_uid = sdata.get("to_uid")

        # Admin limit tekshiruv (faqat superadmin emas adminlar uchun)
        if not sa:
            max_coin = C.get_setting(ctx.bot_data, "admin_max_coin")
            if max_coin and amount > max_coin:
                await msg.reply_text(
                    f"❌ Siz max <b>{max_coin} FC</b> bera olasiz!\n"
                    f"Siz kiritdingiz: {amount} FC",
                    reply_markup=cancel_btn(),
                    parse_mode=ParseMode.HTML
                )
                return

        new_bal = await C.add_coins(ctx.bot, ctx.bot_data, to_uid, amount,
                                     f"admin gift from {uid}")
        clear_state(ctx)
        await msg.reply_text(
            f"✅ <code>{to_uid}</code> ga <b>{amount} FC</b> berildi!\n"
            f"Yangi balans: <b>{new_bal} FC</b>",
            reply_markup=back_btn("sa:panel"),
            parse_mode=ParseMode.HTML
        )
        try:
            await ctx.bot.send_message(
                to_uid,
                f"🎁 Sizga admin tomonidan <b>{amount} FuizCoin</b> berildi!\n"
                f"💰 Balansingiz: <b>{new_bal} FC</b>",
                parse_mode=ParseMode.HTML
            )
        except TelegramError:
            pass
        return

    # ── Promokod yaratish ─────────────────────
    if sname == "add_promo:code":
        sdata["code"] = text.strip().upper()
        set_state(ctx, "add_promo:amount", sdata)
        await msg.reply_text("2. Qiymati (FC):", reply_markup=cancel_btn())
        return

    if sname == "add_promo:amount":
        if not text.strip().isdigit():
            await msg.reply_text("❌ Raqam kiriting!")
            return
        sdata["amount"] = int(text.strip())
        set_state(ctx, "add_promo:total", sdata)
        await msg.reply_text("3. Necha kishi foydalana oladi (jami):", reply_markup=cancel_btn())
        return

    if sname == "add_promo:total":
        if not text.strip().isdigit():
            await msg.reply_text("❌ Raqam kiriting!")
            return
        sdata["total_uses"] = int(text.strip())
        set_state(ctx, "add_promo:per_user", sdata)
        await msg.reply_text("4. Bir kishi necha marta foydalana oladi:", reply_markup=cancel_btn())
        return

    if sname == "add_promo:per_user":
        if not text.strip().isdigit():
            await msg.reply_text("❌ Raqam kiriting!")
            return
        sdata["per_user"] = int(text.strip())
        r = await C.create_promo(
            ctx.bot, ctx.bot_data,
            sdata["code"], sdata["amount"],
            sdata["total_uses"], sdata["per_user"]
        )
        clear_state(ctx)
        if "error" in r:
            await msg.reply_text(f"❌ {r['error']}", reply_markup=back_btn("adm:promos"))
        else:
            await msg.reply_text(
                f"✅ Promokod yaratildi!\n\n"
                f"Kod: <code>{r['code']}</code>\n"
                f"Qiymat: {r['amount']} FC\n"
                f"Limit: {r['total_uses']} kishi, har biri {r['per_user']} marta",
                reply_markup=back_btn("adm:promos"),
                parse_mode=ParseMode.HTML
            )
        return

    await msg.reply_text("❓ Noma'lum buyruq. /start yoki /admin")


async def handle_server_add(msg, ctx, uid, sdata, text, doc, photo, video):
    """Server qo'shish alohida flow."""
    idx = sdata.get("idx", -1)

    if idx == -1:
        # Title
        sdata["title"] = text.strip()
        sdata["idx"]   = 0  # endi server type so'raymiz
        set_state(ctx, "add:servers", sdata)
        await msg.reply_text(
            "2. Server ulanish turi:",
            reply_markup=ip_or_link_kb()
        )
        return

    if sdata.get("addr_step"):
        # Havola yoki IP kiritildi
        sdata["server_addr"] = text.strip()
        sdata.pop("addr_step", None)
        sdata["idx"] = 1
        set_state(ctx, "add:servers", sdata)
        await msg.reply_text(
            "3. Tavsif (ixtiyoriy):",
            reply_markup=skip_cancel_kb()
        )
        return

    if idx == 1:
        # desc
        sdata["desc"] = text.strip() if text.strip() else None
        sdata["idx"]  = 2
        set_state(ctx, "add:servers", sdata)
        await msg.reply_text(
            "4. Rasm yoki video (ixtiyoriy):",
            reply_markup=skip_cancel_kb()
        )
        return

    if idx == 2:
        # media
        if photo:
            sdata["media_id"]   = photo[-1].file_id
            sdata["media_type"] = "photo"
        elif video:
            sdata["media_id"]   = video.file_id
            sdata["media_type"] = "video"
        await finalize_add(msg, ctx, uid, "servers", sdata)
        return

# ═══════════════════════════════════════════════════════════
#  BOT GURUHGA QO'SHILGANDA
# ═══════════════════════════════════════════════════════════

async def on_my_chat_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return
    new_status = result.new_chat_member.status
    chat       = result.chat

    if new_status in ("member", "administrator"):
        gr_id   = str(chat.id)
        gr_name = chat.title or str(chat.id)
        existing = DB.cache_find(ctx.bot_data, "targets", gr_id=gr_id)
        if not existing:
            await DB.save(ctx.bot, ctx.bot_data, "targets", {
                "gr_id": gr_id,
                "name":  gr_name,
                "date":  datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
        # Guruhga qo'shilganda coin BERILMAYDI
        # Coin faqat referal havola orqali kelgan userlarga beriladi
        pass
    elif new_status in ("left", "kicked"):
        gr_id = str(chat.id)
        r = DB.cache_find(ctx.bot_data, "targets", gr_id=gr_id)
        if r:
            await DB.delete(ctx.bot, ctx.bot_data, "targets", r["_msg_id"])

# ═══════════════════════════════════════════════════════════
#  DB GROUP — xabar o'chirilganda keshdan ham o'chir
# ═══════════════════════════════════════════════════════════

async def on_db_message_deleted(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """DB groupda xabar o'chirilganda keshdan ham o'chirish."""
    msg = update.message
    if not msg:
        return
    if update.effective_chat.id != DB_GROUP_ID:
        return

    msg_id = str(msg.message_id)

    # Barcha topic larda shu msg_id ni qidirish va o'chirish
    cache = ctx.bot_data.get("cache", {})
    for topic, items in cache.items():
        before = len(items)
        cache[topic] = [r for r in items if str(r.get("_msg_id")) != msg_id]
        if len(cache[topic]) < before:
            log.info(f"DB sync: '{topic}' dan msg_id={msg_id} o'chirildi (DB group trigger)")
            P.save_cache(ctx.bot_data)
            return

# ═══════════════════════════════════════════════════════════
#  POST INIT / SHUTDOWN
# ═══════════════════════════════════════════════════════════

async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    """Har qanday ushlanmagan xatoni log qiladi va superadminga qisqa xabar yuboradi.
    Shu orqali tugma 'jim ishlamay qolish' holatlari endi ko'rinadigan bo'ladi."""
    err = ctx.error
    log.error(f"Ushlanmagan xato: {err}", exc_info=err)
    try:
        where = ""
        if isinstance(update, Update) and update.callback_query:
            where = f"\nTugma: <code>{update.callback_query.data}</code>"
        await ctx.bot.send_message(
            SUPERADMIN,
            f"⚠️ <b>Botda xato yuz berdi</b>{where}\n\n<code>{type(err).__name__}: {err}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

async def post_init(app: Application):
    P.restore_bot_data(app.bot_data)
    log.info("✅ Kesh yuklandi, bot tayyor.")
    # Bo'sh boshlangan bo'lsa — avval avtomatik restore urinib ko'ramiz
    restored = await BK.auto_restore_if_empty(app.bot, app.bot_data)
    if restored:
        P.save_cache(app.bot_data)
    # Har holda (restore bo'ldi yoki yo'q) adminlarga mos xabar yuboriladi
    await BK.check_empty_and_notify(app.bot, app.bot_data, auto_restored=restored)

async def post_shutdown(app: Application):
    P.save_cache(app.bot_data)
    log.info("✅ Kesh saqlandi.")

# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def main():
    import os
    import asyncio

    # Python 3.14 da event loop muammosini hal qilish
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    log.info("FuizTime Bot v2.1 ishga tushmoqda...")

    # Webhook URL — Render avtomatik beradi
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
    PORT        = int(os.environ.get("PORT", 8443))

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("admin",    cmd_admin))
    app.add_handler(CommandHandler("sa",       cmd_sa))
    app.add_handler(CommandHandler("addadmin", cmd_addadmin))
    app.add_handler(CommandHandler("deladmin", cmd_deladmin))
    app.add_handler(CommandHandler("export",   cmd_export))
    app.add_handler(CommandHandler("import",   cmd_import))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.Document.ALL | filters.PHOTO | filters.VIDEO) & ~filters.FORWARDED,
        on_message
    ))
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(
        filters.Chat(DB_GROUP_ID) & filters.ALL,
        on_db_message_deleted
    ))
    app.add_error_handler(on_error)

    # Har 5 daqiqada keshni saqlash
    jq = app.job_queue
    if jq:
        async def periodic_save(context):
            P.save_cache(context.application.bot_data)
        jq.run_repeating(periodic_save, interval=300, first=60)

        import datetime as dt
        async def daily_backup(context):
            await BK.export_backup(context.application.bot, context.application.bot_data)
            context.application.bot_data["change_counter"] = 0
        jq.run_daily(daily_backup, time=dt.time(hour=0, minute=0, second=0))

    log.info(f"Superadmin: {SUPERADMIN} | DB Group: {DB_GROUP_ID}")

    if WEBHOOK_URL:
        # Webhook mode — Render uchun
        log.info(f"Webhook mode: {WEBHOOK_URL}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="/webhook",
            webhook_url=f"{WEBHOOK_URL}/webhook",
            allowed_updates=["message", "callback_query", "my_chat_member"],
            drop_pending_updates=True
        )
    else:
        # Polling mode — lokal test uchun
        log.info("Polling mode (lokal)")
        app.run_polling(
            allowed_updates=["message", "callback_query", "my_chat_member"],
            drop_pending_updates=True
        )

if __name__ == "__main__":
    main()
