# ============================
# Telegram Bot: /write command
# Makes a clean image with text you send
# ============================

import io
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- YOUR BOT TOKEN HERE ---
BOT_TOKEN = "8411607342:AAHSDSB98MDYeuYMZUk6nHqKtZy2zquhVig"
# Optional font (you can change path or use default)
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# === Generate image ===
def generate_image(text: str):
    # Image setup
    W, H = 2000, 700
    bg_color = (20, 20, 20)       # dark background
    text_color = (255, 255, 255)  # white text
    font_size = 24

    # Load font
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except:
        font = ImageFont.load_default()

    # Wrap text for neat layout
    lines = []
    words = text.split()
    line = ""
    for word in words:
        if font.getlength(line + word + " ") <= W - 100:
            line += word + " "
        else:
            lines.append(line.strip())
            line = word + " "
    lines.append(line.strip())

    # Calculate height
    line_height = font.getbbox("A")[3] + 10
    total_text_height = len(lines) * line_height
    y_start = (H - total_text_height) // 2

    # Create image
    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # Draw each line centered
    for line in lines:
        w = font.getlength(line)
        x = (W - w) // 2
        draw.text((x, y_start), line, fill=text_color, font=font)
        y_start += line_height

    # Convert to bytes
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio


# === Command handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send /write <text> and I’ll make it into an image!")


async def write_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❗Usage: `/write your text here`", parse_mode="Markdown")

    text = " ".join(context.args).strip()
    if len(text) > 10000:
        return await update.message.reply_text("⚠️ Text too long! Keep under 10000 characters.")

    img = generate_image(text)
    await update.message.reply_photo(photo=img, caption="🖋️ Here's your text image!")


# === Main ===
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("write", write_command))

    print("✅ Bot is running... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
