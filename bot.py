from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import requests

TON_API = "https://api.coingecko.com/api/v3/simple/price?ids=toncoin&vs_currencies=usd"

NFT_API = "https://api.opensea.io/api/v1/asset"  # OpenSea asset endpoint

async def nft_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "t.me/nft/" not in text.lower():
        return  # ignore non-NFT links

    try:
        # Parse link
        parts = text.split('/')[-1].split('-')
        collection_slug = "-".join(parts[:-1])
        token_id = parts[-1]

        # --- Fetch NFT data ---
        url = f"{NFT_API}/{collection_slug}/{token_id}/"
        headers = {"Accept": "application/json"}
        nft_res = requests.get(url, headers=headers).json()

        nft_name = nft_res.get("name") or f"{collection_slug} #{token_id}"
        floor_price_eth = nft_res.get("last_sale", {}).get("total_price") or 0.5
        permalink = nft_res.get("permalink", f"https://opensea.io/assets/{collection_slug}/{token_id}")

        # ETH -> USD
        eth_price = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd").json()["ethereum"]["usd"]
        floor_usd = float(floor_price_eth) * eth_price

        # USD -> TON
        ton_price = requests.get(TON_API).json()["toncoin"]["usd"]
        floor_ton = floor_usd / ton_price

        message = (
            f"🖼 NFT: {nft_name}\n"
            f"💰 Floor Price: {floor_price_eth} ETH\n"
            f"💵 USD: ${floor_usd:.2f}\n"
            f"💎 TON: {floor_ton:.2f} TON\n"
            f"🔗 OpenSea: {permalink}"
        )
        await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"Error fetching NFT info: {e}")

# ==== Bot Setup ====
if __name__ == "__main__":
    app = ApplicationBuilder().token("8411607342:AAHSDSB98MDYeuYMZUk6nHqKtZy2zquhVig").build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, nft_link_handler))
    print("NFT Link Bot started...")
    app.run_polling()
