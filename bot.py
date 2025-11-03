# ==========================================
# Telegram Bot: /write command (PDF Version)
# Creates a clean white PDF with your text
# ==========================================

import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Your Bot Token ---
BOT_TOKEN = "8411607342:AAHSDSB98MDYeuYMZUk6nHqKtZy2zquhVig"


# === Function to Generate PDF ===
def generate_pdf(text: str):
    # Create an in-memory bytes buffer
    buffer = io.BytesIO()

    # A4 page setup
    page_width, page_height = A4
    margin = 2 * cm
    font_size = 24  # Large font
    line_spacing = font_size * 1.8  # stretched spacing

    # Create canvas
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle("WriteBot Output")
    pdf.setFont("Helvetica-Bold", font_size)

    # Start coordinates
    x, y = margin, page_height - margin

    # Split words for wrapping
    words = text.split()
    line = ""

    for word in words:
        test_line = line + word + " "
        if pdf.stringWidth(test_line, "Helvetica-Bold", font_size) < (page_width - 2 * margin):
            line = test_line
        else:
            pdf.drawString(x, y, line.strip())
            y -= line_spacing
            line = word + " "
            # If page filled, create new page
            if y < margin:
                pdf.showPage()
                pdf.setFont("Helvetica-Bold", font_size)
                y = page_height - margin

    # Draw last line
    if line:
        pdf.drawString(x, y, line.strip())

    pdf.save()
    buffer.seek(0)
    return buffer


# === Telegram Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send `/write <text>` and I'll return a clean, stylish PDF of your text!"
    )


async def write_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(
            "❗Usage: `/write your text here`", parse_mode="Markdown"
        )

    text = " ".join(context.args).strip()
    if len(text) > 8000:
        return await update.message.reply_text("⚠️ Text too long (max 8000 chars).")

    pdf_bytes = generate_pdf(text)

    await update.message.reply_document(
        document=pdf_bytes,
        filename="WriteBot_Output.pdf",
        caption="🖋️ Here's your text as a PDF!"
    )


# === Main ===
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("write", write_command))

    print("✅ PDF WriteBot is running... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
