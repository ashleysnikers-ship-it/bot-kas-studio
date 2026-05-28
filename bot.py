import os
import logging
import threading
import time
import html
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from flask import Flask, jsonify, render_template, send_from_directory

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Flask App ─────────────────────────────────────────────────────────────────
app_flask = Flask(__name__)

@app_flask.route("/")
def index():
    return render_template("lensera-finance.html")

@app_flask.route("/lensera-finance.html")
def finance():
    return render_template("lensera-finance.html")

@app_flask.route("/logo.png")
def logo():
    return send_from_directory('.', 'logo.png')

@app_flask.route("/health")
def health():
    return jsonify({"status": "ok"})

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host="0.0.0.0", port=port)

# ── Telegram Bot ──────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["💰 Cek Saldo", "📊 Laporan"], ["⚙️ Pengaturan", "❓ Bantuan"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Selamat datang di *Lensera Finance Bot*!\n\nPilih menu di bawah:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    safe = html.escape(text)

    if text == "💰 Cek Saldo":
        await update.message.reply_text("💰 Saldo kamu: *Rp 0* (belum ada data)", parse_mode="Markdown")
    elif text == "📊 Laporan":
        await update.message.reply_text("📊 Laporan keuangan belum tersedia.", parse_mode="Markdown")
    elif text == "⚙️ Pengaturan":
        await update.message.reply_text("⚙️ Pengaturan belum diimplementasi.", parse_mode="Markdown")
    elif text == "❓ Bantuan":
        await update.message.reply_text(
            "❓ *Bantuan*\n\nKetik /start untuk memulai ulang bot.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"Kamu mengetik: {safe}")

def run_bot():
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN tidak di-set, bot Telegram tidak akan berjalan.")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()
