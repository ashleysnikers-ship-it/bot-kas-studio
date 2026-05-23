import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from flask import Flask, render_template, jsonify
import threading
from ocr import baca_nota_gambar, analisis_teks
from database import simpan_transaksi, get_laporan, get_riwayat

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── State ConversationHandler ─────────────────────────────────────────────────
MENUNGGU_KONFIRMASI = 1

# ── Flask App ─────────────────────────────────────────────────────────────────
app_flask = Flask(__name__)

@app_flask.route("/")
def dashboard():
    return render_template("dashboard.html")

@app_flask.route("/api/laporan")
def api_laporan():
    return jsonify(get_laporan())

@app_flask.route("/api/riwayat")
def api_riwayat():
    return jsonify(get_riwayat(limit=20))


# ── Helpers ───────────────────────────────────────────────────────────────────
def format_rupiah(nominal):
    return f"Rp {int(nominal):,}".replace(",", ".")


def buat_pesan_konfirmasi(data):
    emoji = "💰" if data["jenis"] == "PEMASUKAN" else "💸"
    return (
        f"{emoji} *Transaksi Terdeteksi*\n\n"
        f"Jenis    : *{data['jenis']}*\n"
        f"Nominal  : *{format_rupiah(data['nominal'])}*\n"
        f"Deskripsi: {data['deskripsi']}\n"
        f"Kategori : {data['kategori']}\n\n"
        f"Simpan transaksi ini?"
    )


def keyboard_konfirmasi():
    return ReplyKeyboardMarkup(
        [["✅ Ya, Simpan", "❌ Batal"]],
        one_time_keyboard=True,
        resize_keyboard=True
    )


# ── Command Handlers ──────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nama = update.effective_user.first_name
    await update.message.reply_text(
        f"Halo {nama}! 👋\n\n"
        "Selamat datang di *Bot Buku Kas Studio* 📷\n\n"
        "Cara pakai:\n"
        "📸 Kirim *foto nota/struk* → AI akan baca otomatis\n"
        "✍️ Ketik manual, contoh:\n"
        "   • `beli galon 5000`\n"
        "   • `dp wedding klien A 500rb`\n"
        "   • `bayaran foto wisuda 300000`\n\n"
        "📊 /laporan → Ringkasan keuangan\n"
        "📋 /riwayat → 5 transaksi terakhir\n"
        "❓ /bantuan → Panduan lengkap",
        parse_mode="Markdown"
    )


async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *Panduan Bot Kas Studio*\n\n"
        "*📸 Kirim Foto Nota:*\n"
        "Foto struk, nota, kuitansi apapun → AI baca otomatis\n\n"
        "*✍️ Ketik Manual:*\n"
        "Format bebas, contoh:\n"
        "• `beli tinta printer 45000`\n"
        "• `dp foto wedding 1jt`\n"
        "• `lunas foto keluarga 350rb`\n"
        "• `bayar listrik 200000`\n"
        "• `transfer masuk wisuda 500000`\n\n"
        "*Singkatan yang dimengerti:*\n"
        "• `rb` atau `ribu` = × 1.000\n"
        "• `jt` atau `juta` = × 1.000.000\n"
        "• `k` = × 1.000\n\n"
        "*Perintah:*\n"
        "• /laporan → Ringkasan keuangan\n"
        "• /riwayat → 5 transaksi terakhir\n"
        "• /start → Mulai ulang",
        parse_mode="Markdown"
    )


async def laporan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_laporan()
    pemasukan = data.get("total_pemasukan", 0)
    pengeluaran = data.get("total_pengeluaran", 0)
    saldo = pemasukan - pengeluaran

    emoji_saldo = "✅" if saldo >= 0 else "⚠️"
    await update.message.reply_text(
        f"📊 *Laporan Keuangan Studio*\n\n"
        f"💰 Pemasukan : *{format_rupiah(pemasukan)}*\n"
        f"💸 Pengeluaran: *{format_rupiah(pengeluaran)}*\n"
        f"{'─'*30}\n"
        f"{emoji_saldo} Saldo     : *{format_rupiah(saldo)}*",
        parse_mode="Markdown"
    )


async def riwayat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    transaksi_list = get_riwayat(limit=5)
    if not transaksi_list:
        await update.message.reply_text("Belum ada transaksi yang tercatat.")
        return

    pesan = "📋 *5 Transaksi Terakhir*\n\n"
    for t in transaksi_list:
        emoji = "💰" if t["jenis"] == "PEMASUKAN" else "💸"
        pesan += (
            f"{emoji} {t['deskripsi']}\n"
            f"   {format_rupiah(t['nominal'])} · {t.get('tanggal', '')[:10]}\n\n"
        )
    await update.message.reply_text(pesan, parse_mode="Markdown")


# ── Foto Handler ──────────────────────────────────────────────────────────────
async def terima_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Sedang membaca nota... Tunggu sebentar ya!")

    try:
        # Ambil foto resolusi terbaik
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        # Analisis dengan Gemini Vision
        result = baca_nota_gambar(bytes(image_bytes))

        if "error" in result:
            await update.message.reply_text(
                f"⚠️ {result['error']}\n\n"
                "Coba ketik manual, contoh:\n`beli galon 5000`",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        # Simpan data sementara
        context.user_data["transaksi_pending"] = result

        await update.message.reply_text(
            buat_pesan_konfirmasi(result),
            parse_mode="Markdown",
            reply_markup=keyboard_konfirmasi()
        )
        return MENUNGGU_KONFIRMASI

    except Exception as e:
        logger.error(f"Error foto: {e}")
        await update.message.reply_text(
            "❌ Terjadi error saat memproses foto. Coba lagi atau ketik manual."
        )
        return ConversationHandler.END


# ── Teks Handler ──────────────────────────────────────────────────────────────
async def terima_teks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.message.text.strip()

    # Abaikan kalau teks terlalu pendek
    if len(teks) < 3:
        return ConversationHandler.END

    await update.message.reply_text("🤔 Menganalisis transaksi...")

    try:
        result = analisis_teks(teks)

        if "error" in result:
            await update.message.reply_text(
                f"⚠️ {result['error']}",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        context.user_data["transaksi_pending"] = result

        await update.message.reply_text(
            buat_pesan_konfirmasi(result),
            parse_mode="Markdown",
            reply_markup=keyboard_konfirmasi()
        )
        return MENUNGGU_KONFIRMASI

    except Exception as e:
        logger.error(f"Error teks: {e}")
        await update.message.reply_text("❌ Terjadi error. Coba lagi ya.")
        return ConversationHandler.END


# ── Konfirmasi Handler ────────────────────────────────────────────────────────
async def konfirmasi_simpan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jawaban = update.message.text

    if jawaban == "✅ Ya, Simpan":
        data = context.user_data.get("transaksi_pending")
        if not data:
            await update.message.reply_text("⚠️ Data tidak ditemukan. Coba ulang.")
            return ConversationHandler.END

        try:
            simpan_transaksi(
                jenis=data["jenis"],
                nominal=data["nominal"],
                deskripsi=data["deskripsi"],
                kategori=data["kategori"]
            )
            emoji = "💰" if data["jenis"] == "PEMASUKAN" else "💸"
            await update.message.reply_text(
                f"{emoji} *Transaksi tersimpan!*\n\n"
                f"{data['deskripsi']} — {format_rupiah(data['nominal'])}\n\n"
                "Kirim foto atau ketik transaksi berikutnya 👇",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
            )
        except Exception as e:
            logger.error(f"Error simpan: {e}")
            await update.message.reply_text("❌ Gagal menyimpan. Coba lagi.")

    else:  # Batal
        await update.message.reply_text(
            "❌ Transaksi dibatalkan.\n\nKirim foto atau ketik transaksi baru.",
            reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
        )

    context.user_data.pop("transaksi_pending", None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("transaksi_pending", None)
    await update.message.reply_text("Dibatalkan. Kirim foto atau ketik transaksi baru.")
    return ConversationHandler.END


# ── Main ──────────────────────────────────────────────────────────────────────
def jalankan_flask():
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host="0.0.0.0", port=port)


def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN tidak ditemukan di environment!")

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY tidak ditemukan di environment!")

    # Jalankan Flask di thread terpisah
    flask_thread = threading.Thread(target=jalankan_flask, daemon=True)
    flask_thread.start()

    # Setup bot
    app = Application.builder().token(token).build()

    # ConversationHandler untuk alur foto & teks → konfirmasi
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.PHOTO, terima_foto),
            MessageHandler(filters.TEXT & ~filters.COMMAND, terima_teks),
        ],
        states={
            MENUNGGU_KONFIRMASI: [
                MessageHandler(filters.Regex("^(✅ Ya, Simpan|❌ Batal)$"), konfirmasi_simpan)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bantuan", bantuan))
    app.add_handler(CommandHandler("laporan", laporan))
    app.add_handler(CommandHandler("riwayat", riwayat))
    app.add_handler(conv_handler)

    logger.info("Bot berjalan...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
