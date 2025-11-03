# ==========================================
# Telegram Bot: /write command (Enhanced Styled Version)
# Big text, stretched line spacing, clean top-left layout
# ==========================================

import io
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Your Bot Token ---
BOT_TOKEN = "8411607342:AAHSDSB98MDYeuYMZUk6nHqKtZy2zquhVig"

# --- Font Path (stylish font if available) ---
# You can download any TTF font (e.g., "PlayfairDisplay-Bold.ttf") and use it
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"


# === Function to Generate Image ===
def generate_image(text: str):
    # Canvas setup
    W, H = 2000, 2000
    bg_color = (255, 255, 255)      # white background
    text_color = (0, 0, 0)          # pure black text
    font_size = 140                 # bigger font

    # Load font
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except:
        font = ImageFont.load_default()

    # Create image
    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # Word wrapping (auto new line)
    lines = []
    words = text.split()
    line = ""
    for word in words:
        if font.getlength(line + word + " ") <= W - 200:  # wider margin
            line += word + " "
        else:
            lines.append(line.strip())
            line = word + " "
    lines.append(line.strip())

    # Start top-left with margin
    x, y = 80, 80
    line_height = int(font.getbbox("A")[3] * 1.8)  # stretched line spacing (1.8x)

    # Draw all lines
    for line in lines:
        draw.text((x, y), line, fill=text_color, font=font)
        y += line_height
        if y > H - 200:
            break  # stop if bottom reached

    # Convert to bytes
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio


# === Telegram Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✍️ Use `/write <your text>`\nI'll write it beautifully on an image!"
    )


async def write_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(
            "❗Usage: `/write your text here`", parse_mode="Markdown"
        )

    text = " ".join(context.args).strip()
    if len(text) > 5000:
        return await update.message.reply_text("⚠️ Text too long (max 5000 chars).")

    img = generate_image(text)
    await update.message.reply_photo(photo=img, caption="🖋️ Here's your styled text image!")


# === Main ===
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("write", write_command))

    print("✅ Bot is running... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
