import os
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")          
OWNER_IDS_STR = os.getenv("OWNER_IDS", "")


if not BOT_TOKEN:
    raise ValueError(" BOT_TOKEN not found in .env")
if not MONGO_URI:
    raise ValueError(" MONGO_URI not found in .env")
if not LOG_CHANNEL_ID:
    raise ValueError(" LOG_CHANNEL_ID not found in .env")

try:
    LOG_CHANNEL_ID = int(LOG_CHANNEL_ID)
except ValueError:
    raise ValueError("❌ LOG_CHANNEL_ID must be a number (e.g. -1001234567890)")

OWNER_IDS = []
if OWNER_IDS_STR:
    OWNER_IDS = [int(x.strip()) for x in OWNER_IDS_STR.split(",") if x.strip().isdigit()]

print("Config loaded successfully ")