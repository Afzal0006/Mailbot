import os
import re
import random
import pytz
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, ChatPermissions
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from pymongo import MongoClient
from dotenv import load_dotenv
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
LOG_CHANNEL_ID_RAW = os.getenv("LOG_CHANNEL_ID")
OWNER_IDS_RAW = os.getenv("OWNER_IDS", "")

# Validating everything
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN is missing in .env file!")
if not MONGO_URI:
    raise ValueError("❌ MONGO_URI is missing in .env file!")
if not LOG_CHANNEL_ID_RAW:
    raise ValueError("❌ LOG_CHANNEL_ID is missing in .env file!")

try:
    LOG_CHANNEL_ID = int(LOG_CHANNEL_ID_RAW)
except ValueError:
    raise ValueError(f"❌ LOG_CHANNEL_ID must be a number! You put: {LOG_CHANNEL_ID_RAW}")

OWNER_IDS = []
if OWNER_IDS_RAW.strip():
    for uid in OWNER_IDS_RAW.split(","):
        uid = uid.strip()
        if uid.isdigit():
            OWNER_IDS.append(int(uid))

if not OWNER_IDS:
    raise ValueError("❌ At least one OWNER_IDS required!")

print("All config loaded perfectly ✅")


# ==== MONGO CONNECT ====
client = MongoClient(MONGO_URI)
db = client["escrow_bot"]
groups_col = db["groups"]
global_col = db["global"]
admins_col = db["admins"]

# Ensure global doc exists
if not global_col.find_one({"_id": "stats"}):
    global_col.insert_one({
        "_id": "stats",
        "total_deals": 0,
        "total_volume": 0,
        "total_fee": 0.0,
        "escrowers": {}
    })

# ==== HELPERS ====
async def is_admin(update: Update) -> bool:
    user_id = update.effective_user.id
    if user_id in OWNER_IDS:
        return True
    return admins_col.find_one({"user_id": user_id}) is not None

def init_group(chat_id: str):
    if not groups_col.find_one({"_id": chat_id}):
        groups_col.insert_one({
            "_id": chat_id,
            "deals": {},
            "total_deals": 0,
            "total_volume": 0,
            "total_fee": 0.0,
            "escrowers": {}
        })

def update_escrower_stats(group_id: str, escrower: str, amount: float):
    g = groups_col.find_one({"_id": group_id})
    g["total_deals"] += 1
    g["total_volume"] += amount
    g["escrowers"][escrower] = g["escrowers"].get(escrower, 0) + amount
    groups_col.update_one({"_id": group_id}, {"$set": g})

    global_data = global_col.find_one({"_id": "stats"})
    global_data["total_deals"] += 1
    global_data["total_volume"] += amount
    global_data["escrowers"][escrower] = global_data["escrowers"].get(escrower, 0) + amount
    global_col.update_one({"_id": "stats"}, {"$set": global_data})

def extract_username_from_user(user):
    return f"@{user.username}" if user.username else user.full_name

# ==== COMMANDS ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("alive")
    
import re
import random
import pytz
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

IST = pytz.timezone("Asia/Kolkata")

# ==== Add deal ====
async def add_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return

    try:
        await update.message.delete()
    except:
        pass

    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to the DEAL INFO message!")

    if not context.args or not context.args[0].replace(".", "", 1).isdigit():
        return await update.message.reply_text("❌ Please provide amount like /add 50")

    amount = float(context.args[0])
    original_text = update.message.reply_to_message.text
    chat_id = str(update.effective_chat.id)
    reply_id = str(update.message.reply_to_message.message_id)
    init_group(chat_id)

    buyer_match = re.search(r"BUYER\s*:\s*(@\w+)", original_text, re.IGNORECASE)
    seller_match = re.search(r"SELLER\s*:\s*(@\w+)", original_text, re.IGNORECASE)

    buyer = buyer_match.group(1).strip() if buyer_match else "Unknown"
    seller = seller_match.group(1).strip() if seller_match else "Unknown"

    g = groups_col.find_one({"_id": chat_id})
    deals = g.get("deals", {})

    escrower = extract_username_from_user(update.effective_user)
    trade_id = f"TID{random.randint(100000, 999999)}"

    current_time = datetime.now(IST)
    timestamp = current_time.timestamp()
    iso_time = current_time.isoformat()

    deals[reply_id] = {
        "trade_id": trade_id,
        "added_amount": amount,
        "completed": False,
        "buyer": buyer,
        "seller": seller,
        "escrower": escrower,
        "time_added": timestamp,
        "created_at": iso_time
    }

    g["deals"] = deals
    groups_col.update_one({"_id": chat_id}, {"$set": g})

    update_escrower_stats(chat_id, escrower, amount)

    new_msg = (
        f"💰 Received Amount : ₹{amount}\n"
        f"📤 Release/Refund Amount : —\n"
        f"🆔 Trade ID: #{trade_id}\n\n"
        f"Continue the Deal ✅\n"
        f"Buyer : {buyer}\n"
        f"Seller : {seller}\n\n"
        f"Escrowed By : {escrower}"
    )

    keyboard = [
        [
            InlineKeyboardButton("3% Fee", callback_data=f"fee3_{trade_id}"),
            InlineKeyboardButton("5% Fee", callback_data=f"fee5_{trade_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_chat.send_message(
        new_msg,
        reply_markup=reply_markup,
        reply_to_message_id=update.message.reply_to_message.message_id,
        parse_mode="HTML"
    )


# ==== FEE BUTTON HANDLER (Admin Only) ====
async def fee_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    # ------------------ ADMIN CHECK ------------------
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    admins = await context.bot.get_chat_administrators(chat_id)
    admin_ids = [a.user.id for a in admins]

    if user_id not in admin_ids:
        return await query.answer("❌ Not for you! Admins only.", show_alert=True)
    # --------------------------------------------------

    await query.answer()

    data = query.data.split("_")
    fee_type = data[0]
    trade_id = data[1]

    deal = None
    for g in groups_col.find({}):
        for d in g.get("deals", {}).values():
            if d.get("trade_id") == trade_id:
                deal = d
                break
        if deal:
            break

    if not deal:
        return await query.edit_message_text("❌ Deal not found!")

    amount = float(deal["added_amount"])
    buyer = deal["buyer"]
    seller = deal["seller"]
    escrower = deal["escrower"]

    if fee_type == "fee3":
        fee = amount * 0.03
    else:
        fee = amount * 0.05

    release_amount = amount - fee

    text = (
        f"💰 Received Amount : ₹{amount:.2f}\n"
        f"📤 Release/Refund Amount : ₹{release_amount:.2f}\n"
        f"🆔 Trade ID: #{trade_id}\n\n"
        f"Continue the Deal✅\n"
        f"Buyer : {buyer}\n"
        f"Seller : {seller}\n\n"
        f"Escrowed By : {escrower}"
    )

    await query.edit_message_text(text, parse_mode="HTML")
    
# ==== release ====
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

async def release_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return

    try:
        await update.message.delete()
    except:
        pass

    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to the DEAL INFO message!")

    if not context.args or not context.args[0].replace(".", "", 1).isdigit():
        return await update.message.reply_text("❌ Please provide amount like /complete 50")

    released = float(context.args[0])
    chat_id = str(update.effective_chat.id)
    reply_id = str(update.message.reply_to_message.message_id)
    g = groups_col.find_one({"_id": chat_id})
    deal_info = g["deals"].get(reply_id)

    if not deal_info:
        return await update.message.reply_text("❌ Deal not found!")
    if deal_info.get("completed"):
        return await update.message.reply_text("⚠️ Already completed!")

    # Calculate fee
    added_amount = deal_info.get("added_amount", 0)
    fee = added_amount - released if added_amount > released else 0

    # Mark deal completed
    deal_info["completed"] = True
    deal_info["fee"] = fee
    deal_info["completed_at"] = datetime.utcnow().isoformat()
    g["deals"][reply_id] = deal_info

    # Update stats
    g["total_fee"] += fee
    groups_col.update_one({"_id": chat_id}, {"$set": g})

    global_data = global_col.find_one({"_id": "stats"})
    global_data["total_fee"] += fee
    global_col.update_one({"_id": "stats"}, {"$set": global_data})

    buyer = deal_info.get("buyer", "Unknown")
    seller = deal_info.get("seller", "Unknown")
    escrower = extract_username_from_user(update.effective_user)
    trade_id = deal_info.get("trade_id", "N/A")

    msg = (
        f"📤 Released Amount : ₹{released}\n"
        f"🆔 Trade ID: #{trade_id}\n\n"
        "Deal completed ✅\n"
        f"Buyer : {buyer}\n"
        f"Seller : {seller}\n\n"
        f"Escrowed By : {escrower}"
    )

    await update.effective_chat.send_message(
        msg,
        reply_to_message_id=update.message.reply_to_message.message_id,
        parse_mode="HTML"
    )

    # ==== log section ====
    try:
        log_msg = (
            "📜 <b>Deal Completed (Log)</b>\n"
            "────────────────\n"
            f"👤 Buyer   : {buyer}\n"
            f"👤 Seller  : {seller}\n"
            f"💸 Released: ₹{released}\n"
            f"🆔 Trade ID: #{trade_id}\n"
            f"💰 Fee     : ₹{fee}\n"
            f"🛡️ Escrowed by {escrower}\n"
            f"📌 Group: {update.effective_chat.title} ({update.effective_chat.id})"
        )

        keyboard = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📨 Vouch", url="https://t.me/+4TL7eYFRwzkwN2M1"),
        InlineKeyboardButton("💬 Chat", url="https://t.me/+KYQXPzUS6S8zYTNl")
    ],
    [
        InlineKeyboardButton("⚡ Trusify", url="https://t.me/trustifyescrow")
    ]
])

        await context.bot.send_message(
            LOG_CHANNEL_ID,
            log_msg,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except Exception as e:
        print(f"Log Error: {e}")
    
# ==== Update by Traid id ====
async def update_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.message.reply_text("❌ Only admins can use this command!")

    if not context.args:
        return await update.message.reply_text("❌ Usage: /update <trade_id>")

    trade_id = context.args[0].strip().replace("#", "").upper()
    found = None
    chat_id = None
    reply_id = None

    
    for g in groups_col.find({}):
        for rid, deal in (g.get("deals") or {}).items():
            if deal and str(deal.get("trade_id", "")).upper() == trade_id:
                found = deal
                chat_id = g["_id"]
                reply_id = rid
                break
        if found:
            break

    if not found:
        return await update.message.reply_text("⚠️ No deal found with this Trade ID!")

    if found.get("completed"):
        return await update.message.reply_text("⚠️ Already completed!")

    
    found["completed"] = True
    g = groups_col.find_one({"_id": chat_id})
    g["deals"][reply_id] = found
    groups_col.update_one({"_id": chat_id}, {"$set": g})

    buyer = found.get("buyer", "Unknown")
    seller = found.get("seller", "Unknown")
    released = found.get("added_amount", 0)
    escrower = extract_username_from_user(update.effective_user)

    msg = (
        f"✅ <b>Deal Completed!</b> \n"
        "────────────────\n"
        f"👤 Buyer  : {buyer}\n"
        f"👤 Seller : {seller}\n"
        f"💸 Released : ₹{released}\n"
        f"🆔 Trade ID : #{trade_id}\n"
        f"💰 Fee     : ₹0\n"
        "────────────────\n"
        f"🛡️ Escrowed by {escrower}"
    )

    
    try:
        if reply_id:
            await context.bot.send_message(
                chat_id=int(chat_id),
                text=msg,
                parse_mode="HTML",
                reply_to_message_id=int(reply_id)
            )
        else:
            await update.message.reply_text(msg, parse_mode="HTML")
    except:
        await update.message.reply_text(msg, parse_mode="HTML")

    
    try:
        log_msg = (
            "📜 <b>Deal Completed by Trade ID (0% Fee)</b>\n"
            "────────────────\n"
            f"👤 Buyer  : {buyer}\n"
            f"👤 Seller : {seller}\n"
            f"💸 Released : ₹{released}\n"
            f"🆔 Trade ID : #{trade_id}\n"
            f"💰 Fee     : ₹0\n"
            f"🛡️ Escrowed by {escrower}\n"
        )
        await context.bot.send_message(LOG_CHANNEL_ID, log_msg, parse_mode="HTML")
    except:
        pass

# ==== Status by Trade ID ====
async def deal_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❌ Usage: /status <trade_id>")

    trade_id = context.args[0].strip().replace("#", "").upper()
    found = None

    for g in groups_col.find({}):
        for deal in g.get("deals", {}).values():
            if deal and deal.get("trade_id", "").upper() == trade_id:
                found = deal
                break
        if found:
            break

    if not found:
        return await update.message.reply_text("⚠️ No deal found with this Trade ID!")

    status = "✅ Completed" if found.get("completed") else "⌛ Pending"
    msg = (
        f"📌 <b>Deal Status</b>\n"
        f"🆔 Trade ID: #{found.get('trade_id')}\n"
        f"👤 Buyer: {found.get('buyer', 'Unknown')}\n"
        f"👤 Seller: {found.get('seller', 'Unknown')}\n"
        f"💰 Amount: ₹{found.get('added_amount', 0)}\n"
        f"📊 Status: {status}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

# ==== Global stats ====
async def global_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return
    g = global_col.find_one({"_id": "stats"})
    escrowers_text = "\n".join([f"{name} = ₹{amt}" for name, amt in g["escrowers"].items()]) or "No deals yet"
    msg = (
        f"🌍 Global Stats\n\n"
        f"{escrowers_text}\n\n"
        f"🔹 Total Deals: {g['total_deals']}\n"
        f"💰 Total Volume: ₹{g['total_volume']}\n"
        f"💸 Total Fee: ₹{g['total_fee']}"
    )
    await update.message.reply_text(msg)

# === Top 20 Users===
async def topuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.message.reply_text("❌ Only admins can use this command!")

    users_data = {}
    for g in groups_col.find({}):
        for deal in g.get("deals", {}).values():
            if not deal:
                continue
            for user_key in ["buyer", "seller"]:
                user = str(deal.get(user_key, "")).strip()
                amount = float(deal.get("added_amount", 0))
                if user.startswith("@"):
                    users_data.setdefault(user, 0)
                    users_data[user] += amount

    if not users_data:
        return await update.message.reply_text("📊 No Top user found.")

    
    sorted_users = sorted(users_data.items(), key=lambda x: x[1], reverse=True)[:20]

    
    msg = "🏆 <b>Top 20 Traders (by Volume)</b>\n"
    msg += "────────────────────────────\n"

    
    badges = {1: "🥇", 2: "🥈", 3: "🥉"}

    
    for i, (user, volume) in enumerate(sorted_users, start=1):
        badge = badges.get(i, f"{i}.")
        msg += f"{badge} {user} — ₹{volume:.1f}\n"

    
    date_str = datetime.now().strftime("%d %b %Y, %I:%M %p") + " IST"
    msg += f"\n📅 Generated on {date_str}"

    await update.message.reply_text(msg, parse_mode="HTML")
    
# ==== Admin commands ====
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in OWNER_IDS:
        return await update.message.reply_text("❌ Only owners can add admins!")

    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("❌ Provide a valid user_id, e.g. /addadmin 123456789")

    new_admin_id = int(context.args[0])
    if admins_col.find_one({"user_id": new_admin_id}):
        return await update.message.reply_text("⚠️ Already an admin!")

    admins_col.insert_one({"user_id": new_admin_id})
    await update.message.reply_text(f"✅ Added as admin: <code>{new_admin_id}</code>", parse_mode="HTML")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in OWNER_IDS:
        return await update.message.reply_text("❌ Only owners can remove admins!")

    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("❌ Provide a valid user_id, e.g. /removeadmin 123456789")

    remove_id = int(context.args[0])
    if not admins_col.find_one({"user_id": remove_id}):
        return await update.message.reply_text("⚠️ This user is not an admin!")

    admins_col.delete_one({"user_id": remove_id})
    await update.message.reply_text(f"✅ Removed admin: <code>{remove_id}</code>", parse_mode="HTML")

async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return
    admins = list(admins_col.find({}, {"_id": 0, "user_id": 1}))
    owners = [f"⭐ Owner: <code>{oid}</code>" for oid in OWNER_IDS]
    admins_text = "\n".join([f"👮 Admin: <code>{a['user_id']}</code>" for a in admins]) or "No extra admins added."
    msg = "📋 <b>Admin List</b>\n\n" + "\n".join(owners) + "\n" + admins_text
    await update.message.reply_text(msg, parse_mode="HTML")

# ==== ongoing deals ====
async def ongoing_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.full_name
    user_check = username.lower().strip()
    isAdmin = await is_admin(update)

    # 🚫 Restrict access
    if not isAdmin:
        return await update.message.reply_text("❌ Only admins can view pending deals!")

    ongoing_list = []

    for g in groups_col.find({}):
        deals = g.get("deals") or {}
        for rid, deal in deals.items():
            if not deal:
                continue
            if deal.get("completed"):
                continue
            ongoing_list.append(deal)

    if not ongoing_list:
        return await update.message.reply_text("📊 There are currently no ongoing deals.")

    text = "🔄 <b>ongoing Deals (Top 100)</b>\n\n"
    for i, deal in enumerate(ongoing_list[:100], start=1):
        text += (
            f"{i}. 🆔 #{deal.get('trade_id', 'N/A')} — ₹{deal.get('added_amount', 0)}\n"
            f"👤 Buyer: {deal.get('buyer', 'Unknown')}\n"
            f"👤 Seller: {deal.get('seller', 'Unknown')}\n"
            "────────────────\n"
        )

    await update.message.reply_text(text, parse_mode="HTML")

async def holding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    isAdmin = await is_admin(update)

    
    if not isAdmin:
        return await update.message.reply_text("❌ Only admins can use this command!")

    holdings = {}

    
    for g in groups_col.find({}):
        for deal in g.get("deals", {}).values():
            if deal and not deal.get("completed"):
                escrower = deal.get("escrower", "Unknown")
                amount = float(deal.get("added_amount", 0))
                holdings[escrower] = holdings.get(escrower, 0) + amount

    if not holdings:
        return await update.message.reply_text("🌱 No holding amounts right now!")

    # 📊 Format output
    text = "💼 <b>Current Holdings (Pending Amounts)</b>\n\n"
    total = 0
    for i, (escrower, amount) in enumerate(sorted(holdings.items(), key=lambda x: x[1], reverse=True), start=1):
        text += f"{i}. {escrower} → ₹{amount:.2f}\n"
        total += amount

    text += f"\n────────────────\n🏦 <b>Total Hold:</b> ₹{total:.2f}"

    await update.message.reply_text(text, parse_mode="HTML")

# ==== My Deals ====
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

DEALS_PER_PAGE = 100  
MAX_DEALS = 100      

async def mydeals(update, context, page=0):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.full_name

    # Collect user deals
    all_user_deals = []
    for g in groups_col.find({}):
        for deal in g.get("deals", {}).values():
            if deal.get("escrower") == username:
                all_user_deals.append(deal)

    if not all_user_deals:
        return await update.message.reply_text("🎉 You have no deals yet!")

    # Sort deals by trade_id (assuming trade_id increases over time)
    all_user_deals.sort(key=lambda x: x.get("trade_id"))

    # Keep only latest 100 deals
    latest_deals = all_user_deals[-MAX_DEALS:]

    # Separate pending & completed
    pending_deals = []
    completed_deals = []
    total_hold = 0
    completed_counter = 0  

    for deal in latest_deals:
        trade_id = deal.get("trade_id", "Unknown")
        amount = float(deal.get("added_amount", 0))
        if deal.get("completed"):
            completed_counter += 1
            completed_deals.append(f"{completed_counter}. #{trade_id}")
        else:
            pending_deals.append(f"#{trade_id} → ₹{amount:.2f}")
            total_hold += amount

    # Build text
    text_lines = []

    # Active deals
    if page == 0:
        if pending_deals:
            text_lines.append(f"🕒 Active Deals: ({len(pending_deals)})")
            text_lines.extend(pending_deals)
            text_lines.append(f"💼 Total Holding: ₹{total_hold:.2f}")
        else:
            text_lines.append("🕒 No active deals found.")
        text_lines.append("────────────────")

    # Completed deals pagination
    if completed_deals:
        total_pages = (len(completed_deals) + DEALS_PER_PAGE - 1) // DEALS_PER_PAGE
        start = page * DEALS_PER_PAGE
        end = start + DEALS_PER_PAGE
        chunk = completed_deals[start:end]

        if page == 0:
            text_lines.append(f"✅ Completed Deals ({len(completed_deals)}):")
        if chunk:
            text_lines.extend(chunk)
        else:
            text_lines.append("No more completed deals.")
    else:
        if page == 0:
            text_lines.append("✅ No completed deals yet.")

    text = "📜 <b>Your Deals Summary</b>\n────────────────\n" + "\n".join(text_lines)
    await update.message.reply_text(text, parse_mode="HTML")

from datetime import datetime, timedelta

# ==== today Summary ====
async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.message.reply_text("❌ Only admins can use this command!")

    today = datetime.utcnow().date()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())

    total_deals = 0
    total_volume = 0.0
    total_fee = 0.0

    for g in groups_col.find({}):
        for deal in g.get("deals", {}).values():
            if not deal or not deal.get("completed"):
                continue

            dt = deal.get("completed_at")
            if not dt:
                continue

            # Convert to datetime 
            if isinstance(dt, str):
                try:
                    dt = datetime.fromisoformat(dt)
                except:
                    continue

            if start <= dt <= end:
                total_deals += 1
                total_volume += float(deal.get("added_amount", 0))  # ✅ fixed key
                total_fee += float(deal.get("fee", 0))

    if total_deals == 0:
        return await update.message.reply_text("📅 No deals completed today!")

    date_str = today.strftime("%d %b %Y")

    msg = (
        f"📅 <b>Today's Summary</b>\n"
        "────────────────\n"
        f"📊 Deals: {total_deals}\n"
        f"💰 Volume: ₹{total_volume}\n"
        f"💵 Total Fee: ₹{total_fee}\n"
        f"🗓 Date: {date_str}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


# ==== Weekly Summary ====
async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.message.reply_text("❌ Only admins can use this command!")

    today = datetime.utcnow().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    start = datetime.combine(start_of_week, datetime.min.time())
    end = datetime.combine(end_of_week, datetime.max.time())

    total_deals = 0
    total_volume = 0.0
    total_fee = 0.0

    for g in groups_col.find({}):
        for deal in g.get("deals", {}).values():
            if not deal or not deal.get("completed"):
                continue

            dt = deal.get("completed_at")
            if not dt:
                continue

            if isinstance(dt, str):
                try:
                    dt = datetime.fromisoformat(dt)
                except:
                    continue

            if start <= dt <= end:
                total_deals += 1
                total_volume += float(deal.get("added_amount", 0))  # ✅ fixed key
                total_fee += float(deal.get("fee", 0))

    if total_deals == 0:
        return await update.message.reply_text("📅 No deals completed this week!")

    msg = (
        f"🗓 <b>Weekly Summary</b>\n"
        "────────────────\n"
        f"📊 Deals: {total_deals}\n"
        f"💰 Volume: ₹{total_volume}\n"
        f"💵 Total Fee: ₹{total_fee}\n"
        f"📅 Week: {start_of_week.strftime('%d %b')} - {end_of_week.strftime('%d %b %Y')}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

import io
import pytz
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from telegram import Update, InputFile
from telegram.ext import ContextTypes

IST = pytz.timezone("Asia/Kolkata")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.full_name

    # === Collect deals (from Mongo) ===
    all_deals = []
    for g in groups_col.find({}):
        for d in g.get("deals", {}).values():
            if username in [d.get("buyer"), d.get("seller"), d.get("escrower")]:
                # Try to extract proper datetime
                time_val = d.get("time_added") or d.get("created_at") or d.get("timestamp")
                ts = None
                if time_val:
                    try:
                        if isinstance(time_val, (int, float)):
                            ts = datetime.fromtimestamp(time_val)
                        elif isinstance(time_val, str):
                            ts = datetime.fromisoformat(time_val)
                    except:
                        ts = None
                all_deals.append([
                    d.get("buyer", ""),
                    d.get("seller", ""),
                    d.get("escrower", ""),
                    d.get("trade_id", ""),
                    f"{d.get('added_amount', 0)} INR",
                    ts or datetime.min
                ])

    if not all_deals:
        return await update.message.reply_text("📜 No deals found for you!")

    # === Sort by timestamp ===
    all_deals.sort(key=lambda x: x[-1])
    numbered_deals = [[str(i)] + deal[:-1] for i, deal in enumerate(all_deals, start=1)]

    # === Create PDF ===
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4, title=f"{username}_deals",
                            rightMargin=40, leftMargin=40, topMargin=60, bottomMargin=40)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name="TitleStyle", parent=styles['Title'],
                                 fontSize=22, leading=26, alignment=1, textColor=colors.HexColor("#1F4E79"))
    subtitle_style = ParagraphStyle(name="Subtitle", parent=styles['Normal'],
                                    fontSize=11, leading=14, textColor=colors.grey, alignment=1)
    footer_style = ParagraphStyle(name="Footer", parent=styles['Normal'],
                                  fontSize=9, textColor=colors.grey, alignment=1)

    elements = [
        Paragraph("<b>TRUSTIFY ESCROW SUMMARY</b>", title_style),
        Paragraph(f"Generated for {username}", subtitle_style),
        Spacer(1, 12),
        Paragraph(datetime.now(IST).strftime("📅 %B %d, %Y • %I:%M %p IST"), subtitle_style),
        Spacer(1, 18)
    ]

    table_data = [["#", "BUYER", "SELLER", "ESCROWER", "TRADE ID", "AMOUNT"]] + numbered_deals
    table = Table(table_data, colWidths=[30, 100, 100, 100, 130, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#DDEBF7")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#A6A6A6")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.whitesmoke, colors.HexColor("#F7FBFF")]),
    ]))
    elements += [table, Spacer(1, 20),
                 Paragraph("💼 Generated securely via <b>Trustify escrow</b><br/>"
                           "This report summarizes all completed and ongoing trades.",
                           footer_style)]

    pdf.build(elements)
    buffer.seek(0)

    await update.effective_chat.send_document(
        document=InputFile(buffer, filename=f"{username.strip('@')}_deals.pdf"),
        caption=f"All deal history for {username}"
    )

async def escrow(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # === /history ===
    if not await is_admin(update):
        return await update.message.reply_text("You are not authorised to use this command ")

    user = update.effective_user
    username = f"@{user.username}" if user.username else user.full_name

    # === Collect all deals (All Time) ===
    all_deals = []
    for g in groups_col.find({}):
        for d in g.get("deals", {}).values():
            time_val = d.get("time_added") or d.get("timestamp") or d.get("created_at")

            # Format date/time
            date_str = ""
            time_str = ""
            if time_val:
                try:
                    if isinstance(time_val, (int, float)):
                        dt = datetime.fromtimestamp(time_val, tz=IST)
                    elif isinstance(time_val, str):
                        dt = datetime.fromisoformat(time_val).astimezone(IST)
                    else:
                        dt = None

                    if dt:
                        date_str = dt.strftime("%d %b %Y")
                        time_str = dt.strftime("%I:%M %p")

                except:
                    date_str = "—"
                    time_str = "—"
            else:
                date_str = "—"
                time_str = "—"

            all_deals.append([
                d.get("buyer", "Unknown"),
                d.get("seller", "Unknown"),
                d.get("escrower", "Unknown"),
                d.get("trade_id", "N/A"),
                f"{d.get('added_amount', 0)} INR",
                date_str,
                time_str
            ])

    if not all_deals:
        return await update.message.reply_text("❌ No escrow deals found!")

    # Sort
    all_deals.sort(key=lambda x: x[-2], reverse=True)

    # Numbering
    numbered_deals = [[str(i)] + deal for i, deal in enumerate(all_deals, start=1)]

    # Create PDF
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="All Escrow Deals Summary",
        rightMargin=40,
        leftMargin=40,
        topMargin=60,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="TitleStyle",
        parent=styles['Title'],
        fontSize=22,
        leading=26,
        alignment=1,
        textColor=colors.HexColor("#1F4E79")
    )
    subtitle_style = ParagraphStyle(
        name="Subtitle",
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        textColor=colors.grey,
        alignment=1
    )

    footer_style = ParagraphStyle(
        name="Footer",
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=1
    )

    elements = [
        Paragraph("<b>LUCKY ESCROW SUMMARY</b>", title_style),
        Paragraph("All-Time Escrow History", subtitle_style),
        Spacer(1, 12),
        Paragraph(datetime.now(IST).strftime("📅 %B %d, %Y • %I:%M %p IST"), subtitle_style),
        Spacer(1, 18)
    ]

    table_data = [
        ["#", "BUYER", "SELLER", "ESCROWER", "TRADE ID", "AMOUNT", "DATE", "TIME"]
    ] + numbered_deals

    table = Table(table_data, colWidths=[25, 80, 80, 80, 100, 70, 70, 70])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#DDEBF7")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#A6A6A6")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#F7FBFF")]),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    total_amount = sum(
        float(d.get('added_amount', 0))
        for g in groups_col.find({})
        for d in g.get("deals", {}).values()
    )

    elements.append(Paragraph(
        f"💰 <b>Total Escrow Volume:</b> ₹{total_amount:.2f}<br/><br/>"
        "💼 Generated via Lucky Escrow Bot",
        footer_style
    ))

    pdf.build(elements)
    buffer.seek(0)

    await update.effective_chat.send_document(
        document=InputFile(buffer, filename="all_escrow_summary.pdf"),
        caption=f"📜 All-Time Escrow Summary (Total: ₹{total_amount:.2f})"
    )
# ======================================================
# ✅ CONFIRMATION HANDLER: release / relese / refund
# ======================================================
import pytz
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application, MessageHandler, ContextTypes, filters
)

IST = pytz.timezone("Asia/Kolkata")

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.lower().strip()
    if not any(word in text for word in ("release", "relese", "refund")):
        return

    chat = update.effective_chat
    chat_id = str(chat.id)
    user = update.effective_user
    username_display = f"@{user.username}" if user.username else user.full_name
    username_cmp = username_display.lower()

    if not msg.reply_to_message:
        return await msg.reply_text("⚠️ Please reply to the deal message using confirmation.")

    reply_id = str(msg.reply_to_message.message_id)
    group_data = groups_col.find_one({"_id": chat_id})
    if not group_data:
        return await msg.reply_text("⚠️ No deal data found!")

    deals = group_data.get("deals") or {}
    deal = deals.get(reply_id)
    if not deal:
        return await msg.reply_text("⚠️ Deal not found!")

    buyer = str(deal.get("buyer", "")).lower()
    seller = str(deal.get("seller", "")).lower()
    trade_id = deal.get("trade_id")

    if deal.get("status") in ["confirmed_release", "confirmed_refund"]:
        return await msg.reply_text("⚠️ Already confirmed this deal.")

    if "refund" in text:
        action = "refund"
        emoji = "🔴"
        title_word = "Refund"
    else:
        action = "release"
        emoji = "🟢"
        title_word = "Release"

    mute_until = datetime.utcnow() + timedelta(minutes=30)

    if action == "release":
        if username_cmp == seller:
            return await msg.reply_text(f"🟥 You are assigned as seller. {buyer} must confirm.")
        elif username_cmp != buyer:
            try:
                await context.bot.restrict_chat_member(
                    chat_id=int(chat_id),
                    user_id=user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_until
                )
            except Exception as e:
                print(f"MUTE FAILED: {e}")
            return await chat.send_message(f"🚫 {username_display} tried unauthorized release confirmation! Muted 30 min.")

    elif action == "refund":
        if username_cmp == buyer:
            return await msg.reply_text(f"🟥 You are assigned as buyer. {seller} must confirm.")
        elif username_cmp != seller:
            try:
                await context.bot.restrict_chat_member(
                    chat_id=int(chat_id),
                    user_id=user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_until
                )
            except Exception as e:
                print(f"MUTE FAILED: {e}")
            return await chat.send_message(f"🚫 {username_display} tried unauthorized refund confirmation! Muted 30 min.")

    now_ist = datetime.now(IST)
    time_str = now_ist.strftime("%d %b %Y, %I:%M %p IST")

    confirm_msg = (
        f"{emoji} {title_word} CONFIRMED by {username_display} (awaiting admin completion)\n"
        f"📆 {time_str}\n"
        f"🆔 #{trade_id}"
    )

    deal["status"] = f"confirmed_{action}"
    deals[reply_id] = deal
    groups_col.update_one({"_id": chat_id}, {"$set": {"deals": deals}})

    try:
        await context.bot.send_message(
            chat_id=int(chat_id),
            text=confirm_msg,
            reply_to_message_id=int(reply_id),
            parse_mode="HTML"
        )
    except:
        await msg.reply_text(confirm_msg)


# ======================================================
# ✅ MAIN APP SETUP
# ======================================================

from datetime import datetime, timezone, timedelta
from telegram import Update, User
from telegram.ext import ContextTypes

# ==== /stats ====
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    args = context.args

    # ==== Detect target user ====
    target_user = None

    # 1️⃣ If tagged in reply
    if msg.reply_to_message:
        target_user = msg.reply_to_message.from_user

    # 2️⃣ If username mentioned in args
    elif args:
        username_arg = args[0].strip()
        if not username_arg.startswith("@"):
            username_arg = f"@{username_arg}"
        target_user = User(id=0, first_name=username_arg, is_bot=False, username=username_arg[1:])

    # 3️⃣ Default = self
    else:
        target_user = msg.from_user

    username = f"@{target_user.username}" if target_user.username else target_user.full_name
    user_check = username.lower().strip()

    total_deals = 0
    total_volume = 0
    ongoing_deals = 0
    highest_deal = 0
    all_users = {}

    # === Collect data from all groups ===
    for g in groups_col.find({}):
        for deal in g.get("deals", {}).values():
            if not deal:
                continue

            buyer = str(deal.get("buyer", "")).lower().strip()
            seller = str(deal.get("seller", "")).lower().strip()
            amount = float(deal.get("added_amount", 0) or 0)
            completed = deal.get("completed", False)

            # For this target user
            if user_check in [buyer, seller]:
                total_deals += 1
                total_volume += amount
                highest_deal = max(highest_deal, amount)
                if not completed:
                    ongoing_deals += 1

            # For global ranking
            for u in [buyer, seller]:
                if u.startswith("@"):
                    all_users.setdefault(u, {"volume": 0})
                    all_users[u]["volume"] += amount

    # === No deals ===
    if total_deals == 0:
        return await msg.reply_text(f"📊 No deals found for {username}.")

    # === Rank Calculation (by total volume) ===
    sorted_users = sorted(all_users.items(), key=lambda x: x[1]["volume"], reverse=True)
    rank = next((i + 1 for i, (u, _) in enumerate(sorted_users) if u == user_check), "N/A")

    # === Format reply ===
    msg_text = (
        f"📊 Participant Stats for {username}\n\n"
        f"👑 Ranking: {rank}\n"
        f"📈 Total Volume: ₹{total_volume:,.1f}\n"
        f"🧳 Total Deals: {total_deals}\n"
        f"🧿 Ongoing Deals: {ongoing_deals}\n"
        f"💳 Highest Deal - ₹{highest_deal:,.1f}"
    )

    await msg.reply_text(msg_text)

# ==== /find command ====
async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    args = context.args

    # 🔹 Detect target user
    if msg.reply_to_message:
        target_user = msg.reply_to_message.from_user
    elif args:
        username_arg = args[0].strip()
        if not username_arg.startswith("@"):
            username_arg = f"@{username_arg}"
        target_user = User(id=0, first_name=username_arg, is_bot=False, username=username_arg[1:])
    else:
        return await msg.reply_text("❌ Please reply to a user or provide a username.")

    username = f"@{target_user.username}" if target_user.username else target_user.full_name
    user_check = username.lower().strip()

    # 🔹 Collect ongoing deals for this user
    ongoing_list = []

    for g in groups_col.find({}):
        deals = g.get("deals") or {}
        for deal in deals.values():
            if not deal or deal.get("completed"):
                continue
            buyer = str(deal.get("buyer", "")).lower().strip()
            seller = str(deal.get("seller", "")).lower().strip()
            if user_check in [buyer, seller]:
                ongoing_list.append(deal)

    if not ongoing_list:
        return await msg.reply_text(f"📊 No ongoing deals found for {username}.")

    # 🔹 Format output
    text = f" <b>Ongoing Deals for {username}</b>\n\n"
    for i, deal in enumerate(ongoing_list[:50], start=1):
        text += (
            f"{i}. 🆔 #{deal.get('trade_id', 'N/A')} — ₹{deal.get('added_amount', 0)}\n"
            f"👤 Buyer: {deal.get('buyer', 'Unknown')}\n"
            f"👤 Seller: {deal.get('seller', 'Unknown')}\n"
            "────────────────\n"
        )

    await msg.reply_text(text, parse_mode="HTML")

# ==== /refund =====
async def refund_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return

    try:
        await update.message.delete()
    except:
        pass

    # Must reply to deal form
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to the DEAL INFO message!")

    # Amount required
    if not context.args or not context.args[0].replace(".", "", 1).isdigit():
        return await update.message.reply_text("❌ Usage: /refund 50")

    refund_amount = float(context.args[0])
    chat_id = str(update.effective_chat.id)
    reply_id = str(update.message.reply_to_message.message_id)

    g = groups_col.find_one({"_id": chat_id})
    deal_info = g["deals"].get(reply_id)

    if not deal_info:
        return await update.message.reply_text("❌ Deal not found!")
    if deal_info.get("completed"):
        return await update.message.reply_text("⚠️ Already completed!")

    # Mark completed
    deal_info["completed"] = True
    deal_info["fee"] = 0
    deal_info["completed_at"] = datetime.utcnow().isoformat()

    g["deals"][reply_id] = deal_info
    groups_col.update_one({"_id": chat_id}, {"$set": g})

    buyer = deal_info.get("buyer", "Unknown")
    seller = deal_info.get("seller", "Unknown")
    escrower = extract_username_from_user(update.effective_user)
    trade_id = deal_info["trade_id"]

    # Display refund message
    msg = (
        f"📤 Refunded Amount : ₹{refund_amount}\n"
        f"🆔 Trade ID: #{trade_id}\n\n"
        f"Deal refunded ‼️\n"
        f"Buyer : {buyer}\n"
        f"Seller : {seller}\n\n"
        f"Escrowed By : {escrower}"
    )

    await update.effective_chat.send_message(
        msg,
        reply_to_message_id=int(reply_id),
        parse_mode="HTML"
    )

    # Log to channel
    try:
        log_msg = (
            "📜 <b>Deal Refunded (Log)</b>\n"
            "────────────────\n"
            f"👤 Buyer   : {buyer}\n"
            f"👤 Seller  : {seller}\n"
            f"💸 Refunded: ₹{refund_amount}\n"
            f"🆔 Trade ID: #{trade_id}\n"
            f"🛡️ Escrowed by {escrower}\n"
            f"📌 Group: {update.effective_chat.title} ({update.effective_chat.id})"
        )
        await context.bot.send_message(LOG_CHANNEL_ID, log_msg, parse_mode="HTML")
    except:
        pass
        # ===== /adm ======
async def adm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return

    try:
        await update.message.delete()
    except:
        pass

    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to the DEAL INFO message!")

    if not context.args or not context.args[0].replace(".", "", 1).isdigit():
        return await update.message.reply_text("❌ Provide amount like /adm 50")

    amount = float(context.args[0])
    original_text = update.message.reply_to_message.text
    chat_id = str(update.effective_chat.id)
    reply_id = str(update.message.reply_to_message.message_id)
    init_group(chat_id)

    buyer_match = re.search(r"BUYER\s*:\s*(@\w+)", original_text, re.IGNORECASE)
    seller_match = re.search(r"SELLER\s*:\s*(@\w+)", original_text, re.IGNORECASE)

    buyer = buyer_match.group(1).strip() if buyer_match else "Unknown"
    seller = seller_match.group(1).strip() if seller_match else "Unknown"

    g = groups_col.find_one({"_id": chat_id})
    deals = g.get("deals", {})

    escrower = extract_username_from_user(update.effective_user)
    trade_id = f"TID{random.randint(100000, 999999)}"

    deals[reply_id] = {
        "trade_id": trade_id,
        "added_amount": amount,
        "completed": False,
        "buyer": buyer,
        "seller": seller,
        "escrower": escrower,
        "fee": 0,                  # 🔥 0% fee
        "time_added": datetime.now().timestamp(),
        "created_at": datetime.now(IST).isoformat()
    }

    g["deals"] = deals
    groups_col.update_one({"_id": chat_id}, {"$set": g})

    # 0% fee update stats
    update_escrower_stats(chat_id, escrower, amount)

    new_msg = (
        f"💰 Received Amount : ₹{amount}\n"
        f"📤 Release/Refund Amount : ₹{amount}\n"
        f"🆔 Trade ID: #{trade_id}\n\n"
        f"Continue the Deal\n"
        f"Buyer : {buyer}\n"
        f"Seller : {seller}\n\n"
        f"🛡️ Escrowed By : {escrower} "
    )

    await update.effective_chat.send_message(
        new_msg,
        reply_to_message_id=int(reply_id),
        parse_mode="HTML"
        )
    
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_deal))
    app.add_handler(CommandHandler("release", release_deal))
    app.add_handler(CommandHandler("update", update_deal))
    app.add_handler(CommandHandler("status", deal_status))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("gstats", global_stats))
    app.add_handler(CommandHandler("topuser", topuser))
    app.add_handler(CommandHandler("ongoing", ongoing_deals))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("adminlist", admin_list))
    app.add_handler(CommandHandler("holding", holding))
    app.add_handler(CommandHandler("mydeals", mydeals))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("escrow", escrow))
    app.add_handler(CommandHandler("find", find))
    app.add_handler(CallbackQueryHandler(fee_button_handler, pattern="^fee"))
    app.add_handler(CommandHandler("refund", refund_deal))
    app.add_handler(CommandHandler("adm", adm))
    
    confirmation_handler = MessageHandler(
        filters.Regex(r"(?i)\b(release|relese|refund)\b") & ~filters.COMMAND,
        handle_confirmation
    )
    app.add_handler(confirmation_handler)

    print("Bot started... ✅")
    app.run_polling()


if __name__ == "__main__":
    main()
