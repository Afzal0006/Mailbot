import requests, time, re
from selenium import webdriver
from selenium.webdriver.common.by import By
from telegram.ext import Updater, CommandHandler

BOT_TOKEN = "8311824260:AAGW-fZPpNBP4f3vtZbb1QWKpTSlqdT2olo"

# --- Generate Fake Email ---
def get_fake_email():
    url = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
    return requests.get(url).json()[0]

# --- Fetch OTP ---
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

# --- Telegram Command ---
def start(update, context):
    fake_email = get_fake_email()
    update.message.reply_text(f"Fake Email: {fake_email}\nOTP aane ka wait karo...")

    # Launch browser
    driver = webdriver.Chrome()
    driver.get("https://example.com/login")
    driver.find_element(By.ID, "email").send_keys(fake_email)
    driver.find_element(By.ID, "submitBtn").click()

    otp = get_otp(fake_email)
    if otp:
        driver.find_element(By.ID, "otp").send_keys(otp)
        driver.find_element(By.ID, "verifyBtn").click()
        update.message.reply_text(f"✅ OTP Entered: {otp}")
    else:
        update.message.reply_text("❌ OTP nahi mila.")

updater = Updater(BOT_TOKEN)
updater.dispatcher.add_handler(CommandHandler("start", start))
updater.start_polling()
