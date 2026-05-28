import os
import logging
import threading
import html
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from flask import Flask, jsonify, render_template, send_from_directory

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)  # HARUS "app" supaya Gunicorn detect otomatis

@app.route("/")
def index():
    return render_template("lensera-finance.html")

@app.route("/lensera-finance.html")
def finance():
    return render_template("lensera-finance.html")

@app.route("/logo.png")
def logo():
    return send_from_directory(".", "logo.png")

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# ── Telegram Bot ──────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["💰 Cek Saldo", "📊 Laporan"], ["⚙️ Pengaturan", "❓ Bantuan"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Selamat datang di *Lensera Finance Bot*!\n\nPilih menu di bawah:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    safe = html.escape(text)
    responses = {
        "💰 Cek Saldo":  "💰 Saldo kamu: *Rp 0* (belum ada data)",
        "📊 Laporan":    "📊 Laporan keuangan belum tersedia.",
        "⚙️ Pengaturan": "⚙️ Pengaturan belum diimplementasi.",
        "❓ Bantuan":    "❓ *Bantuan*\n\nKetik /start untuk memulai ulang bot.",
    }
    reply = responses.get(text, f"Kamu mengetik: {safe}")
    await update.message.reply_text(reply, parse_mode="Markdown")

def _run_bot():
    """Jalankan bot polling di thread terpisah."""
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN tidak di-set, bot Telegram tidak berjalan.")
        return
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot Telegram mulai polling...")
    tg_app.run_polling()

# Jalankan bot saat modul di-import (termasuk oleh Gunicorn)
threading.Thread(target=_run_bot, daemon=True).start()

# ── Entry point lokal ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
