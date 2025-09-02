import os
import re
import time
import requests
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from telegram.ext import Updater, CommandHandler

# Telegram Bot Token from Heroku ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")

chromedriver_autoinstaller.install()

def get_fake_email():
    url = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
    return requests.get(url).json()[0]

def get_otp(email):
    login, domain = email.split('@')
    for _ in range(10):
        resp = requests.get(
            f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
        ).json()
        if resp:
            msg_id = resp[0]['id']
            mail = requests.get(
                f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}"
            ).json()
            otp = re.findall(r"\d{4,8}", mail['body'])
            if otp:
                return otp[0]
        time.sleep(5)
    return None

def start(update, context):
    fake_email = get_fake_email()
    update.message.reply_text(f"📧 Fake Email: {fake_email}\n⏳ OTP wait kar rahe hain...")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920x1080")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get("https://example.com/login")  # <-- apni site ka URL daalo

    driver.find_element(By.ID, "email").send_keys(fake_email)
    driver.find_element(By.ID, "submitBtn").click()

    otp = get_otp(fake_email)
    if otp:
        driver.find_element(By.ID, "otp").send_keys(otp)
        driver.find_element(By.ID, "verifyBtn").click()
        update.message.reply_text(f"✅ OTP Found & Submitted: {otp}")
    else:
        update.message.reply_text("❌ OTP nahi mila.")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
