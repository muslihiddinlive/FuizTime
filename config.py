"""FuizTime Bot — Config"""

BOT_TOKEN = "8634089477:AAEwGEXJLTSMN73gRBBl0-vFMrNRAKa0_Fs"

SUPERADMIN = 5302627260
ADMIN_IDS: list[int] = []

DB_GROUP_ID = -1003996867983

TOPIC_IDS: dict[str, int] = {
    "contact":      2,
    "news":         4,
    "gallery":      6,
    "mods":         8,
    "servers":      10,
    "versions":     12,
    "wiki":         14,
    "community":    16,
    "videos":       25,
    "about":        32,
    "channels":     48,
    "admins":       50,
    "users":        52,
    "stats":        54,
    "targets":      71,
    "main_data":    73,
    "requests":     137,
    "db":           296,
    "backup":       384,   # Zahira nusxa
    "coins":        310,
    "referrals":    312,
    "promocodes":   314,
    "broadcasts":   316,
    "coin_history": 320,
}

# Superadmin o'chira oladigan bo'limlar
# True = yoqiq, False = o'chirilgan
FEATURES = {
    "coins":     True,
    "referrals": True,
    "promocodes": True,
}
