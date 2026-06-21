#!/usr/bin/env python3
"""
Topic ID Helper — Supergroup topic IDlarini topish uchun.

Ishlatish:
  1. config.py ga BOT_TOKEN va DB_GROUP_ID ni kiriting
  2. python get_topic_ids.py
  3. Supergroupdagi har bir topicga bitta xabar yuboring
  4. Loglarda message_thread_id ko'rinadi — uni config.py ga kiriting
"""

import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, DB_GROUP_ID

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

async def on_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    chat_id = msg.chat.id
    if chat_id != DB_GROUP_ID:
        return
    thread_id = getattr(msg, "message_thread_id", None)
    text      = msg.text or msg.caption or "(media)"
    print(f"\n📨 Xabar: '{text[:40]}'")
    print(f"   chat_id        : {chat_id}")
    print(f"   message_thread_id : {thread_id}  ← Bu topic IDsi!")
    print(f"   message_id     : {msg.message_id}")

def main():
    print("=" * 50)
    print("Topic ID Helper")
    print("=" * 50)
    print(f"DB Group: {DB_GROUP_ID}")
    print("\nSupergroupdagi har bir topicga xabar yuboring.")
    print("message_thread_id — bu config.py ga kiriting.\n")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, on_msg))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
