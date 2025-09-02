import telebot
import requests
import json
import os
import datetime
import concurrent.futures
import base64
import time

# === CONFIG ===
BOT_TOKEN = '7648911646:AAGeBBLxrE63NscaXyy3ZzC6MYn4k7OV-aQ'
ADMIN_ID = 6998916494   # yaha apna telegram chat ID number daalna
bot = telebot.TeleBot(BOT_TOKEN)

# === FILES ===
USERS_FILE = 'users.json'
COOLDOWN_FILE = 'cooldown.json'

# === JSON Helpers ===
def load_json(file):
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump({}, f)
    with open(file, 'r') as f:
        return json.load(f)

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

users = load_json(USERS_FILE)
cooldowns = load_json(COOLDOWN_FILE)

# === AUTO RESET DAILY ===
def auto_reset():
    now = datetime.datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    if os.path.exists("last_reset.txt"):
        with open("last_reset.txt", "r") as f:
            last = f.read().strip()
    else:
        last = ""

    if today_str != last:
        save_json(USERS_FILE, {})
        save_json(COOLDOWN_FILE, {})
        with open("last_reset.txt", "w") as f:
            f.write(today_str)
        print("🌀 Daily reset done.")

auto_reset()

# === Message Splitter ===
def split_text(text, max_length=4000):
    lines = text.split('\n')
    chunks, chunk = [], ""
    for line in lines:
        if len(chunk + line + '\n') > max_length:
            chunks.append(chunk)
            chunk = ""
        chunk += line + '\n'
    chunks.append(chunk)
    return chunks

# === IG Checker (with Proxy support) ===
def check_username(uname):
    try:
        url = f"https://www.instagram.com/{uname}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "en-US,en;q=0.9"
        }

        # 🔁 INSERT YOUR PROXY DETAILS HERE
        proxies = {
            "http": "http://user:pass@proxy_ip:port",
            "https": "http://user:pass@proxy_ip:port"
        }

        r = requests.get(url, headers=headers, proxies=proxies, timeout=10)

        if r.status_code == 404 or "Page Not Found" in r.text:
            return f"❌ @{uname} — Suspended"
        elif "profilePage_" in r.text:
            return f"✅ @{uname} — Active"
        else:
            return f"⚠️ @{uname} — Private or Unknown"
    except:
        return f"⚠️ @{uname} — Error"

# === Start Command ===
@bot.message_handler(commands=['start'])
def start(m):
    uid = str(m.from_user.id)
    username = m.from_user.username or f"id_{uid}"
    if uid not in users:
        users[uid] = {
            "username": username,
            "joined": int(datetime.datetime.now().timestamp()),
            "last_used": int(datetime.datetime.now().timestamp())
        }
        save_json(USERS_FILE, users)

    msg = (
        "👋 Welcome to *Insta Status Checker Premium*\n\n"
        "📤 Send 1 or more Instagram usernames to check status:\n"
        "✅ Active = Working ID\n"
        "❌ Suspended = Banned or Blocked\n\n"
        "⚠️ Max 50 usernames per request.\n"
        "⏱ 1-minute cooldown per scan.\n\n"
        + base64.b64decode("T3duZWQgQnkgQEJhY2hhR2FuZ3M=").decode()
    )
    bot.send_message(m.chat.id, msg, parse_mode='Markdown')

# === Main Checker with Cooldown and Animation ===
@bot.message_handler(func=lambda m: True)
def check_usernames(m):
    uid = str(m.from_user.id)
    username = m.from_user.username or f"id_{uid}"
    now = time.time()

    users[uid] = {
        "username": username,
        "joined": users.get(uid, {}).get("joined", int(datetime.datetime.now().timestamp())),
        "last_used": int(now)
    }
    save_json(USERS_FILE, users)

    # Cooldown Check
    if uid in cooldowns:
        last_check = cooldowns[uid]
        if now - last_check < 60:
            remaining = int(60 - (now - last_check))
            bot.send_message(m.chat.id, f"⏳ Please wait {remaining} seconds before checking again.")
            return

    # Clean and slice input
    raw = m.text.replace(',', '\n').split('\n')
    usernames = [u.strip().replace('@', '') for u in raw if u.strip()]
    usernames = usernames[:50]

    if not usernames:
        bot.send_message(m.chat.id, "⚠️ Please send valid usernames (max 50).")
        return

    anim = bot.send_message(m.chat.id, "🔍 Scanning usernames...\n▫️▫️▫️▫️▫️", parse_mode='Markdown')
    time.sleep(0.6)
    bot.edit_message_text("🔍 Scanning usernames...\n▪️▫️▫️▫️▫️", m.chat.id, anim.message_id)
    time.sleep(0.6)
    bot.edit_message_text("🔍 Scanning usernames...\n▪️▪️▫️▫️▫️", m.chat.id, anim.message_id)
    time.sleep(0.6)
    bot.edit_message_text("🔍 Scanning usernames...\n▪️▪️▪️▫️▫️", m.chat.id, anim.message_id)
    time.sleep(0.6)
    bot.edit_message_text("🔍 Scanning usernames...\n▪️▪️▪️▪️▫️", m.chat.id, anim.message_id)
    time.sleep(0.6)
    bot.edit_message_text("🔍 Scanning usernames...\n▪️▪️▪️▪️▪️", m.chat.id, anim.message_id)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(check_username, usernames))

    results = [r for r in results if r]
    bot.delete_message(m.chat.id, anim.message_id)

    # Save cooldown
    cooldowns[uid] = now
    save_json(COOLDOWN_FILE, cooldowns)

    if not results:
        bot.send_message(m.chat.id, "⚠️ All accounts are either Private or Unknown.")
        return

    results.insert(0, "📂 *Results:*")
    results.append(base64.b64decode("Y2hlY2tlZCBieSBzYWZlIHRvb2xz").decode())  # hidden footer

    for part in split_text("\n".join(results)):
        bot.send_message(m.chat.id, part, parse_mode='Markdown')

# === Admin Panel — View Users ===
@bot.message_handler(commands=['users'])
def list_users(m):
    if m.from_user.id != ADMIN_ID:
        bot.send_message(m.chat.id, "🚫 Not allowed.")
        return

    if not users:
        bot.send_message(m.chat.id, "📭 No users yet.")
        return

    lines = ["📋 *Users Today:*"]
    for uid, info in users.items():
        uname = info.get("username", "N/A")
        joined = datetime.datetime.fromtimestamp(info['joined']).strftime('%Y-%m-%d')
        last = datetime.datetime.fromtimestamp(info['last_used']).strftime('%Y-%m-%d %H:%M')
        lines.append(f"👤 @{uname}\n📆 Joined: {joined}\n🕒 Last: {last}\n")

    for part in split_text("\n".join(lines[:50])):
        bot.send_message(m.chat.id, part, parse_mode='Markdown')

# === START BOT ===
print("✅ Insta Status Checker Premium Running...")
bot.infinity_polling()
