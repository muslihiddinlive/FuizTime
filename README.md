# FuizTime Bot v2.0

## Fayl tuzilmasi
```
fuiztime_bot/
├── bot.py          — asosiy bot
├── db.py           — Telegram supergroup DB layer
├── coins.py        — FuizCoin tizimi
├── channels.py     — Majburiy kanallar + broadcast
├── config.py       — TOKEN va IDlar (BU FAYLNI TO'LDIRING)
├── requirements.txt
└── README.md
```

## Setup

### 1. Token oling
@BotFather → /newbot → tokenni config.py ga kiriting

### 2. config.py ni to'ldiring
```python
BOT_TOKEN = "7890123456:AAG..."   # yangi token
```
DB_GROUP_ID va TOPIC_IDS allaqachon to'ldirilgan ✅

### 3. Botni DB supergroupga admin qiling
- https://t.me/FT087502DB087502SITE087502 ga botni admin qiling
- "Xabar yuborish" huquqi kerak
- "Xabarlarni o'chirish" huquqi kerak (delete uchun)

### 4. Ishga tushiring
```bash
pip install -r requirements.txt
python bot.py
```

---

## Buyruqlar

| Buyruq | Kim | Tavsif |
|--------|-----|--------|
| `/start` | Hammaga | Bosh menyu |
| `/admin` | Adminlar | Admin paneli |
| `/addadmin <id>` | Superadmin | Admin qo'shish |
| `/deladmin <id>` | Superadmin | Admin o'chirish |

---

## Funksiyalar

### Foydalanuvchilar uchun
- 📦 Versiyalar, 📰 Yangiliklar, 🖼 Galereya, 🧩 Modlar
- 🌐 Serverlar, 📖 Wiki, 👥 Jamiyat, 🎬 Videolar
- ℹ️ Haqida, 📞 Aloqa
- 💰 FuizCoin balans ko'rish
- 📤 Coin transfer (user→user)
- 🎁 Promokod ishlatish
- 🛒 Shop dan narsa sotib olish
- 👥 Referal havola olish va ulashish
- 📜 Coin tarixi

### Admin panel
- ➕ Har bir bo'limga kontent qo'shish/tahrirlash/o'chirish
- 📢 Majburiy kanal/guruh qo'shish va o'chirish
- 📣 Reklama: userlarga / kanallarga / guruhlarga / hammaga
- 💰 Istalgan userga istagancha coin berish
- 📊 Balanslar ro'yxati (Top 20)
- 🎁 Promokod yaratish (nom, qiymat, jami limit, user limiti)
- 🛒 Shop itemlari boshqaruvi
- 📊 Statistika
- 👤 Adminlar boshqaruvi

### FuizCoin tizimi
- Referal orqali kelgan har user uchun: **10 FC**
- Bot guruhga qo'shilganda: **5 FC**
- Admin istalgancha coin bera oladi
- User→user transfer
- Promokod: nom + qiymat + jami_limit + user_limiti
- Shop: mahsulot sotib olish (coin sarflash)
- Kanal uchun alohida referal havola (user chat ID bilan)

### DB arxitekturasi
- Har bir yozuv = Telegram supergroup da bitta xabar
- Restart bo'lganda: in-memory kesh bo'shaydi
- Barcha ma'lumotlar Telegram serverida saqlanadi
- Admin paneldan o'chirilsa — DB dan ham o'chadi

---

## Muhim eslatma
Restart bo'lganda kesh tozalanadi — ma'lumotlar DB groupda saqlanadi
lekin bot ularni **avtomatik o'qimaydi** (Telegram Bot API cheklovlari).

Agar persistent kesh kerak bo'lsa — keyingi versiyada
bot_data ni pickle/json ga saqlash qo'shiladi.

