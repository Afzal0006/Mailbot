import re
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pymongo import MongoClient

# ==== CONFIG ====
BOT_TOKEN = "8411607342:AAHSDSB98MDYeuYMZUk6nHqKtZy2zquhVig"
MONGO_URI = "mongodb+srv://afzal99550:afzal99550@cluster0.aqmbh9q.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
LOG_CHANNEL_ID = -1002330347621

OWNER_IDS = [6998916494]  # Add as many owners as needed

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
    msg = (
        "✨ <b>Welcome to @Escrow_LuckyWorld !</b> ✨\n\n"
        "• /add <code>amount</code> – Add a new deal\n"
        "• /complete <code>amount</code> – Complete a deal (reply-based)\n"
        "• /update <code>trade_id</code> – Complete deal by Trade ID (0% fee)\n"
        "• /status <code>trade_id</code> – Check deal status by Trade ID\n"
        "• /stats – Your personal stats\n"
        "• /gstats – Global stats (Admin only)\n"
        "• /topuser – top 20 user list (Admin only)\n"
        "• /ongoing – View ongoing deals\n"
        "• /addadmin <code>user_id</code> – Owner only\n"
        "• /removeadmin <code>user_id</code> – Owner only\n"
        "• /adminlist – Show all admins"
        "• there are many command not mentioned above\n"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

from datetime import datetime
import random, re
from telegram import Update
from telegram.ext import ContextTypes

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
    deals = g["deals"]

    escrower = extract_username_from_user(update.effective_user)
    trade_id = f"TID{random.randint(100000, 999999)}"

    # ✅ Added "escrower" field
    deals[reply_id] = {
        "trade_id": trade_id,
        "added_amount": amount,
        "completed": False,
        "buyer": buyer,
        "seller": seller,
        "escrower": escrower
    }

    g["deals"] = deals
    groups_col.update_one({"_id": chat_id}, {"$set": g})

    update_escrower_stats(chat_id, escrower, amount)

    msg = (
        f"✅ <b>Amount Received!</b>\n"
        "────────────────\n"
        f"👤 Buyer : {buyer}\n"
        f"👤 Seller : {seller}\n"
        f"💰 Amount : ₹{amount}\n"
        f"🆔 Trade ID : #{trade_id}\n"
        "────────────────\n"
        f"🛡️ Escrowed by {escrower}"
    )

    await update.effective_chat.send_message(
        msg,
        reply_to_message_id=update.message.reply_to_message.message_id,
        parse_mode="HTML"
    )


# ==== Complete deal (reply-based) ====
from datetime import datetime

async def complete_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if deal_info["completed"]:
        return await update.message.reply_text("⚠️ Already completed!")

    # ✅ Calculate fee
    added_amount = deal_info["added_amount"]
    fee = added_amount - released if added_amount > released else 0

    # ✅ Mark deal completed, store fee & timestamp
    deal_info["completed"] = True
    deal_info["fee"] = fee
    deal_info["completed_at"] = datetime.utcnow().isoformat()

    # ✅ Re-save updated deal info
    g["deals"][reply_id] = deal_info

    # ✅ Update group & global stats
    g["total_fee"] += fee
    groups_col.update_one({"_id": chat_id}, {"$set": g})

    global_data = global_col.find_one({"_id": "stats"})
    global_data["total_fee"] += fee
    global_col.update_one({"_id": "stats"}, {"$set": global_data})

    buyer = deal_info.get("buyer", "Unknown")
    seller = deal_info.get("seller", "Unknown")
    escrower = extract_username_from_user(update.effective_user)
    trade_id = deal_info["trade_id"]

    # ✅ Send completion message
    msg = (
        f"✅ <b>Deal Completed!</b>\n"
        "────────────────\n"
        f"👤 Buyer  : {buyer}\n"
        f"👤 Seller : {seller}\n"
        f"💸 Released : ₹{released}\n"
        f"🆔 Trade ID : #{trade_id}\n"
        f"💰 Fee     : ₹{fee}\n"
        "────────────────\n"
        f"🛡️ Escrowed by {escrower}"
    )
    await update.effective_chat.send_message(
        msg,
        reply_to_message_id=update.message.reply_to_message.message_id,
        parse_mode="HTML"
    )

    # ✅ Log to channel
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
            f"📆 Date: {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}\n"
            f"📌 Group: {update.effective_chat.title} ({update.effective_chat.id})"
        )
        await context.bot.send_message(LOG_CHANNEL_ID, log_msg, parse_mode="HTML")
    except:
        pass
# ==== Update by Trade ID (0% Fee, tag original message) ====
async def update_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.message.reply_text("❌ Only admins can use this command!")

    if not context.args:
        return await update.message.reply_text("❌ Usage: /update <trade_id>")

    trade_id = context.args[0].strip().replace("#", "").upper()
    found = None
    chat_id = None
    reply_id = None

    # Search all groups for the trade_id
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

    # Complete deal with 0% fee
    found["completed"] = True
    g = groups_col.find_one({"_id": chat_id})
    g["deals"][reply_id] = found
    groups_col.update_one({"_id": chat_id}, {"$set": g})

    buyer = found.get("buyer", "Unknown")
    seller = found.get("seller", "Unknown")
    released = found.get("added_amount", 0)
    escrower = extract_username_from_user(update.effective_user)

    msg = (
        f"✅ <b>Deal Completed!</b> (0% Fee)\n"
        "────────────────\n"
        f"👤 Buyer  : {buyer}\n"
        f"👤 Seller : {seller}\n"
        f"💸 Released : ₹{released}\n"
        f"🆔 Trade ID : #{trade_id}\n"
        f"💰 Fee     : ₹0\n"
        "────────────────\n"
        f"🛡️ Escrowed by {escrower}"
    )

    # Send message as reply if original message exists
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

    # Optional log
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

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from telegram import InputFile
from datetime import datetime, timezone, timedelta

# ==== /stats Command (Table PDF version) ====
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.full_name
    user_check = username.lower().strip()

    # === Collect Data ===
    total_deals = 0
    total_volume = 0.0
    ongoing_deals = 0
    highest_deal = 0.0

    completed_volume = 0.0
    completed_deals = 0

    for g in groups_col.find({}):
        deals = g.get("deals", {})
        for deal in deals.values():
            if not deal:
                continue
            buyer = str(deal.get("buyer", "")).lower().strip()
            seller = str(deal.get("seller", "")).lower().strip()
            amount = float(deal.get("added_amount", 0))
            completed = bool(deal.get("completed", False))

            if user_check in [buyer, seller]:
                total_deals += 1
                total_volume += amount
                highest_deal = max(highest_deal, amount)
                if completed:
                    completed_deals += 1
                    completed_volume += amount
                else:
                    ongoing_deals += 1

    if total_deals == 0:
        return await update.message.reply_text("📊 No deals found for you!")

    avg_deal = total_volume / total_deals if total_deals else 0

    # === IST Time ===
    IST = timezone(timedelta(hours=5, minutes=30))
    date_str = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")

    # === PDF Creation ===
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"{username}_stats",
        rightMargin=40, leftMargin=40,
        topMargin=60, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="TitleStyle", parent=styles['Title'],
        fontSize=22, leading=26, alignment=1, textColor=colors.HexColor("#1F4E79")
    )
    subtitle_style = ParagraphStyle(
        name="Subtitle", parent=styles['Normal'],
        fontSize=11, leading=14, textColor=colors.grey, alignment=1
    )
    footer_style = ParagraphStyle(
        name="Footer", parent=styles['Normal'],
        fontSize=9, textColor=colors.grey, alignment=1
    )

    elements = []
    elements.append(Paragraph("<b>LUCKY ESCROW — USER STATS</b>", title_style))
    elements.append(Paragraph(f"📈 Summary for {username}", subtitle_style))
    elements.append(Paragraph(f"🕓 Generated on {date_str}", subtitle_style))
    elements.append(Spacer(1, 20))

    # === Table Data ===
    data = [
        ["Metric", "Value"],
        ["Total Deals", f"{total_deals}"],
        ["Completed Deals", f"{completed_deals}"],
        ["Ongoing Deals", f"{ongoing_deals}"],
        ["Total Volume", f"₹{total_volume:,.2f}"],
        ["Completed Volume", f"₹{completed_volume:,.2f}"],
        ["Highest Single Deal", f"₹{highest_deal:,.2f}"],
        ["Average Deal Size", f"₹{avg_deal:,.2f}"],
    ]

    table = Table(data, colWidths=[200, 200])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#DDEBF7")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#A6A6A6")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.whitesmoke, colors.HexColor("#F7FBFF")]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(
        "📜 Generated securely by <b>Lucky Escrow Bot</b> — User stats summary report.",
        footer_style
    ))

    pdf.build(elements)
    buffer.seek(0)

    await update.effective_chat.send_document(
        document=InputFile(buffer, filename=f"{username.strip('@')}_stats.pdf"),
        caption=f"📊 Stats Summary for {username}"
    )
# === Top 20 Users (Text Output with 🥇🥈🥉 badges) ===
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

    # Sort users by total volume
    sorted_users = sorted(users_data.items(), key=lambda x: x[1], reverse=True)[:20]

    # Header
    msg = "🏆 <b>Top 20 Traders (by Volume)</b>\n"
    msg += "────────────────────────────\n"

    # Badge map for top 3
    badges = {1: "🥇", 2: "🥈", 3: "🥉"}

    # User list with badges
    for i, (user, volume) in enumerate(sorted_users, start=1):
        badge = badges.get(i, f"{i}.")
        msg += f"{badge} {user} — ₹{volume:.1f}\n"

    # Footer (IST)
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

# ==== ongoing deals (Fixed, top 100) ====
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

    # ✅ Sirf admin hi use kar sake
    if not isAdmin:
        return await update.message.reply_text("❌ Only admins can use this command!")

    holdings = {}

    # 🔍 Har group ke deals check karte hain
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

# ==== My Deals (Simple View) ====
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

DEALS_PER_PAGE = 100  # number of completed deals per page
MAX_DEALS = 100      # show only latest 100 deals

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
    completed_counter = 0  # for numbering 101, 102...

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

    # Active deals (only first page)
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

# ==== Daily Summary ====
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

            # Convert to datetime if it's a string
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
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from datetime import datetime


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.full_name

    # === Collect deals (replace with Mongo data) ===
    all_deals = []
    for g in groups_col.find({}):
        for d in g.get("deals", {}).values():
            if username in [d.get("buyer"), d.get("seller"), d.get("escrower")]:
                all_deals.append([
                    d.get("buyer", ""),
                    d.get("seller", ""),
                    d.get("escrower", ""),
                    d.get("trade_id", ""),
                    f"{d.get('added_amount', 0)} INR",
                    d.get("time_added", "")  # for sorting if available
                ])

    if not all_deals:
        return await update.message.reply_text(" No deals found for you!")

    # === Sort by time or trade_id (old → new) ===
    all_deals.sort(key=lambda x: x[-1])  # sort by time_added (last element)

    # === Add numbering column ===
    numbered_deals = []
    for i, deal in enumerate(all_deals, start=1):
        numbered_deals.append([str(i)] + deal[:-1])  # remove last 'time_added'

    # === Create PDF in memory ===
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"{username}'s Deals Summary",
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
        alignment=1,  # center
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

    elements = []

    # === Header ===
    elements.append(Paragraph("<b>LUCKY ESCROW SUMMARY</b>", title_style))
    elements.append(Paragraph(f"Generated for {username}", subtitle_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(datetime.now().strftime("📅 %B %d, %Y • %I:%M %p UTC"), subtitle_style))
    elements.append(Spacer(1, 18))

    # === Table Data ===
    table_data = [["#", "BUYER", "SELLER", "ESCROWER", "TRADE ID", "AMOUNT"]] + numbered_deals

    table = Table(table_data, colWidths=[30, 100, 100, 100, 130, 80])
    table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#DDEBF7")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),

        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#A6A6A6")),

        # Alternate row color
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.whitesmoke, colors.HexColor("#F7FBFF")]),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # === Footer ===
    elements.append(Paragraph(
        "💼 Generated securely via <b>Lucky Escrow Bot</b><br/>"
        "This report summarizes all completed and ongoing trades.",
        footer_style
    ))

    pdf.build(elements)
    buffer.seek(0)

    # === Send PDF ===
    await update.effective_chat.send_document(
        document=InputFile(buffer, filename=f"{username.strip('@')}_deals.pdf"),
        caption=f"All deal history for {username}"
    )

from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ContextTypes

# ==== /stats Command (IST Clean Version) ====
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.full_name
    user_check = username.lower().strip()

    total_deals = 0
    total_volume = 0.0
    ongoing_deals = 0
    highest_deal = 0.0
    all_users = {}

    # === Collect data from all groups ===
    for g in groups_col.find({}):
        deals = g.get("deals", {})
        for deal in deals.values():
            if not deal:
                continue

            buyer = str(deal.get("buyer", "")).lower().strip()
            seller = str(deal.get("seller", "")).lower().strip()
            amount = float(deal.get("added_amount", 0) or 0)
            completed = bool(deal.get("completed", False))

            # Count stats for this user
            if user_check in [buyer, seller]:
                total_deals += 1
                total_volume += amount
                highest_deal = max(highest_deal, amount)
                if not completed:
                    ongoing_deals += 1

            # Add to global stats
            for u in [buyer, seller]:
                if u.startswith("@") and u != "":
                    all_users.setdefault(u, {"volume": 0})
                    all_users[u]["volume"] += amount

    # === No deals found ===
    if total_deals == 0:
        return await update.message.reply_text("🎉 No stats found for you.")

    # === Rank Calculation ===
    sorted_users = sorted(all_users.items(), key=lambda x: x[1]["volume"], reverse=True)
    rank = next((i + 1 for i, (u, _) in enumerate(sorted_users) if u == user_check), "N/A")

    # === IST Time === (no pytz)
    IST = timezone(timedelta(hours=5, minutes=30))
    time_now = datetime.now(IST).strftime("%d %b %Y, %I:%M %p")

    # === Clean Text Output ===
    msg = (
        f"📊 Participant Stats for {username}\n\n"
        f"👑 Ranking: {rank}\n"
        f"📈 Total Volume: ₹{total_volume:,.1f}\n"
        f"🧳 Total Deals: {total_deals}\n"
        f"🧿 Ongoing Deals: {ongoing_deals}\n"
        f"💳 Highest Deal - ₹{highest_deal:,.1f}\n\n"
        f"🕓 Updated on {time_now} (IST)"
    )

    await update.message.reply_text(msg)
        
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_deal))
    app.add_handler(CommandHandler("complete", complete_deal))
    app.add_handler(CommandHandler("update", update_deal))
    app.add_handler(CommandHandler("status", deal_status))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("gstats", global_stats))
    app.add_handler(CommandHandler("topuser", topuser))
    app.add_handler(CommandHandler("ongoing", ongoing_deals))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("adminlist", admin_list))
    app.add_handler(CommandHandler("holding", holding))
    app.add_handler(CommandHandler("mydeals", mydeals))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("history", history))

    print("Bot started... ✅")
    app.run_polling()

if __name__ == "__main__":
    main()
