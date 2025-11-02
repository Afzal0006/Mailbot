import os
import io
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient
from PIL import Image, ImageDraw, ImageFont
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("8411607342:AAHSDSB98MDYeuYMZUk6nHqKtZy2zquhVig")
MONGO_URI = os.getenv("mongodb+srv://afzal99550:afzal99550@cluster0.aqmbh9q.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client.get_database()
groups_col = db.get_collection("groups")  # aapke deals collection

# ===== Helper =====
async def is_admin(update: Update):
    user = update.effective_user
    # simple check: replace with your admin list or Mongo-based admin
    admins = ["@YourUsername"]
    username = f"@{user.username}" if user.username else user.full_name
    return username in admins

# ===== /tonprice command =====
async def tonprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.message.reply_text("❌ Only admins can use this command!")

    api_url = "https://api.coingecko.com/api/v3/coins/toncoin"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params, timeout=10) as resp:
                data = await resp.json()
    except:
        return await update.message.reply_text("⚠️ Could not fetch live price.")

    market = data.get("market_data", {})
    price_usd = market.get("current_price", {}).get("usd", 0.0)
    price_inr = market.get("current_price", {}).get("inr", 0.0)
    change_24h = market.get("price_change_percentage_24h", 0.0)
    change_7d = market.get("price_change_percentage_7d", 0.0)
    updated_unix = data.get("last_updated", None)

    if updated_unix:
        updated_dt_utc = datetime.fromisoformat(updated_unix.replace("Z", "+00:00"))
    else:
        updated_dt_utc = datetime.utcnow()
    ist_dt = updated_dt_utc + timedelta(hours=5, minutes=30)
    time_str = ist_dt.strftime("%d %b %Y, %I:%M %p (IST)")

    # Image
    width, height = 800, 550
    bg = (255,255,255)
    black = (0,0,0)
    red = (220,20,20)
    green = (34,139,34)
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(20,20),(width-20, height-20)], outline=black, width=4)

    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 48)
        font = ImageFont.truetype("DejaVuSans.ttf", 34)
    except:
        title_font = ImageFont.load_default()
        font = ImageFont.load_default()

    draw.text((width//2 - 180, 40), "TON Live Price & Trends", font=title_font, fill=black)
    draw.text((60,120), f"₹ {price_inr:,.2f}", font=title_font, fill=black)
    draw.text((60,180), f"$ {price_usd:,.4f}", font=font, fill=black)

    c24_color = green if change_24h >= 0 else red
    c7_color = green if change_7d >= 0 else red
    draw.text((60,260), f"24h Change: {change_24h:+.2f}%", font=font, fill=c24_color)
    draw.text((60,310), f"7d Change: {change_7d:+.2f}%", font=font, fill=c7_color)
    draw.text((60, height-80), f"⏱️ Updated: {time_str}", font=font, fill=(120,120,120))

    bio = io.BytesIO()
    img.save(bio, "PNG", optimize=True)
    bio.seek(0)

    caption = (f"🔔 TON Live Price\n₹ {price_inr:,.2f} | $ {price_usd:,.4f}\n"
               f"24h: {change_24h:+.2f}% • 7d: {change_7d:+.2f}%")
    await update.message.reply_photo(photo=bio, caption=caption)

# ===== Bot Runner =====
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("tonprice", tonprice))
    print("Bot started...")
    app.run_polling()
