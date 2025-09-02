import os
import re
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from telegram.ext import Updater, CommandHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")

MAIL_TM_API = "https://api.mail.tm"

# --- Create Mail.tm Account ---
def create_mail_account():
    email = requests.post(
        f"{MAIL_TM_API}/accounts",
        json={"address": "", "password": "password123"}
    ).json()

    # Login to get token
    login = requests.post(
        f"{MAIL_TM_API}/token",
        json={"address": email["address"], "password": "password123"}
    ).json()

    return email["address"], login["token"]

# --- Fetch OTP from Mail.tm ---
def get_otp(token):
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(10):  # retry loop
        msgs = requests.get(f"{MAIL_TM_API}/messages", headers=headers).json()
        if "hydra:member" in msgs and msgs["hydra:member"]:
            msg_id = msgs["hydra:member"][0]["id"]
            msg = requests.get(f"{MAIL_TM_API}/messages/{msg_id}", headers=headers).json()
            otp = re.findall(r"\d{4,8}", msg.get("text", ""))
            if otp:
                return otp[0]
        time.sleep(5)
    return None

# --- Selenium driver setup (Heroku ready) ---
def get_driver():
    chrome_options = Options()
    chrome_options.binary_location = os.environ.get(
        "GOOGLE_CHROME_BIN", "/app/.apt/usr/bin/google-chrome"
    )
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(
        service=Service(os.environ.get("CHROMEDRIVER_PATH", "/app/.chromedriver/bin/chromedriver")),
        options=chrome_options
    )
    return driver

# --- Telegram Command ---
def start(update, context):
    fake_email, token = create_mail_account()
    update.message.reply_text(f"📧 Fake Email: {fake_email}\n⏳ OTP wait kar rahe hain...")

    driver = get_driver()
    driver.get("https://example.com/login")  # <-- apni site ka login URL daalo

    # Example selectors (update site ke hisaab se)
    driver.find_element(By.ID, "email").send_keys(fake_email)
    driver.find_element(By.ID, "submitBtn").click()

    otp = get_otp(token)
    if otp:
        driver.find_element(By.ID, "otp").send_keys(otp)
        driver.find_element(By.ID, "verifyBtn").click()
        update.message.reply_text(f"✅ OTP Found & Submitted: {otp}")
    else:
        update.message.reply_text("❌ OTP nahi mila.")

# --- Run Bot ---
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
