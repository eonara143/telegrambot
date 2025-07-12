import logging
import random
import string
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application
from dotenv import load_dotenv
from db import get_db
from telegram.ext import MessageHandler, filters

# === Setup ===
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
secret_token = os.getenv("SECRET_KEY")
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def generate_auth_key(length=32):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# Add this somewhere above the main block
async def log_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.debug(f"Received update: {update}")

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 Welcome to *SCBPhil Access Bot!*\n\n"
        "This bot gives you a unique *AUTH KEY* to log into our tools dashboard.\n\n"
        "Use /register to get your login key.\n"
        "Use /authkey anytime to retrieve your key.\n\n"
        "🔒 *Keep your key private!*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# /register command
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = str(update.effective_user.id)
    username = update.effective_user.username or "unknown"
    auth_key = generate_auth_key()

    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO users (telegram_id, username, auth_key)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE auth_key = VALUES(auth_key), username = VALUES(username)
        """, (tg_id, username, auth_key))
        db.commit()

        msg = (
            "✅ *Registration Successful!*\n\n"
            "Your new AUTH KEY is:\n"
            f"`{auth_key}`\n\n"
            "Use it to log in at [scbphil.us](https://scbphil.us)"
        )
    except Exception as e:
        logging.error(f"Registration failed for user {tg_id}: {e}")
        msg = (
            "⚠️ *Database Error!*\n\n"
            "Registration failed due to a database issue.\n"
            f"Error: `{str(e)}`"
        )
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)


# /authkey command
async def authkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = str(update.effective_user.id)

    db = None
    result = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT auth_key FROM users WHERE telegram_id = %s", (tg_id,))
        result = cursor.fetchone()
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

    if result:
        msg = (
            "🔑 *Your AUTH KEY:*\n"
            f"`{result['auth_key']}`\n\n"
            "Use this to log in at [scbphil.us](https://scbphil.us)"
        )
    else:
        msg = "❗ You haven't registered yet.\nUse /register to generate your AUTH KEY."

    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

# /resetkey command
async def resetkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = str(update.effective_user.id)
    new_auth_key = generate_auth_key()

    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE users SET auth_key = %s WHERE telegram_id = %s", (new_auth_key, tg_id))
        db.commit()

        if cursor.rowcount > 0:
            msg = (
                "♻️ *AUTH KEY Reset Successful!*\n\n"
                f"Your new AUTH KEY is:\n`{new_auth_key}`\n\n"
                "Use it to log in at scbphil.us"
            )
        else:
            msg = "❗ You are not registered yet.\nUse /register first."
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = os.getenv("ADMIN_ID")
    sender_id = str(update.effective_user.id)

    if sender_id != admin_id:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        await update.message.reply_text(f"👥 Total registered users: *{total}*", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Failed to fetch user count: {e}")
        await update.message.reply_text(f"⚠️ Failed to fetch user count.\nError: `{e}`", parse_mode="Markdown")
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = os.getenv("ADMIN_ID")
    sender_id = str(update.effective_user.id)

    if sender_id != admin_id:
        await update.message.reply_text("❌ Unauthorized.")
        return

    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Usage: /broadcast Your message here")
        return

    db = None
    ids = []
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT telegram_id FROM users")
        ids = [row[0] for row in cursor.fetchall()]
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()

    sent, failed = 0, 0
    for tg_id in ids:
        try:
            await context.bot.send_message(chat_id=int(tg_id), text=message)
            sent += 1
        except Exception:
            logging.warning(f"Failed to send broadcast to {tg_id}")
            failed += 1

    await update.message.reply_text(f"📣 Broadcast sent to {sent} users. {failed} failed.")

async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = os.getenv("ADMIN_ID")
    sender_id = str(update.effective_user.id)

    if sender_id != admin_id:
        await update.message.reply_text("❌ Unauthorized.")
        return

    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT username, telegram_id, created_at FROM users ORDER BY created_at DESC LIMIT 5")
        rows = cursor.fetchall()

        if not rows:
            await update.message.reply_text("No logs found.")
            return

        log_text = "📝 *Recent Registrations:*\n\n"
        for r in rows:
            log_text += f"👤 `{r['username']}`\n🆔 {r['telegram_id']}\n🕒 {r['created_at']}\n\n"

        await update.message.reply_text(log_text, parse_mode="Markdown")
    finally:
        if db and db.is_connected():
            cursor.close()
            db.close()


# === Run the Bot ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("authkey", authkey))
    app.add_handler(CommandHandler("resetkey", resetkey))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("logs", logs))
    app.add_handler(MessageHandler(filters.ALL, log_all))

    logging.info("Webhook set successfully.")
    app.run_webhook(
        listen="0.0.0.0",
        port=5002,
        webhook_url="https://scbphil.us/webhook",
        secret_token=secret_token
    )

