import os
import logging
import threading
import html
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from flask import Flask, jsonify, render_template
from ocr import baca_nota_gambar, analisis_teks
from database import init_db, simpan_transaksi, ambil_semua_transaksi, hitung_saldo

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

MENUNGGU_KONFIRMASI = 1

# ── Flask ─────────────────────────────────────────────────────────────────────
app_flask = Flask(__name__)

@app_flask.route("/")
def dashboard():
    try:
        return render_template("dashboard.html")
    except Exception:
        return "<h1>Bot Kas Studio - Running</h1>", 200

@app_flask.route("/api/laporan")
def api_laporan():
    return jsonify(hitung_saldo())

@app_flask.route("/api/riwayat")
def api_riwayat():
    rows = ambil_semua_transaksi()
    hasil = []
    for r in rows[:20]:
        hasil.append({
            "id": r[0], "tanggal": r[1], "kategori": r[2],
            "keterangan": r[3], "nominal": r[4], "timestamp": r[5]
        })
    return jsonify(hasil)

def jalankan_flask():
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host="0.0.0.0", port=port, debug=False,
                  use_reloader=False, threaded=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def format_rupiah(nominal):
    return f"Rp {int(nominal):,}".replace(",", ".")

def bersihkan(teks):
    """Escape karakter HTML agar aman dikirim via Telegram HTML mode."""
    return html.escape(str(teks))

def buat_data_db(ai_result):
    from datetime import datetime
    jenis = ai_result["jenis"]
    kategori_ai = ai_result.get("kategori", "Umum")
    if jenis == "PEMASUKAN":
        kategori_db = f"Pendapatan - {kategori_ai}"
    else:
        kategori_db = f"Pengeluaran - {kategori_ai}"
    return {
        "tanggal": datetime.now().strftime("%Y-%m-%d"),
        "kategori": kategori_db,
        "keterangan": ai_result.get("deskripsi", ""),
        "nominal": int(ai_result["nominal"])
    }

def buat_pesan_konfirmasi(data):
    emoji = "💰" if data["jenis"] == "PEMASUKAN" else "💸"
    # Pakai HTML parse_mode, escape semua teks dari AI
    return (
        f"{emoji} <b>Transaksi Terdeteksi</b>\n\n"
        f"Jenis    : <b>{bersihkan(data['jenis'])}</b>\n"
        f"Nominal  : <b>{format_rupiah(data['nominal'])}</b>\n"
        f"Deskripsi: {bersihkan(data['deskripsi'])}\n"
        f"Kategori : {bersihkan(data['kategori'])}\n\n"
        f"Simpan transaksi ini?"
    )

def keyboard_konfirmasi():
    return ReplyKeyboardMarkup(
        [["✅ Ya, Simpan", "❌ Batal"]],
        one_time_keyboard=True, resize_keyboard=True
    )


# ── Commands ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nama = update.effective_user.first_name
    await update.message.reply_text(
        f"Halo {nama}! 👋\n\n"
        "Selamat datang di <b>Bot Buku Kas Studio</b> 📷\n\n"
        "Cara pakai:\n"
        "📸 Kirim <b>foto nota/struk</b> → AI baca otomatis\n"
        "✍️ Ketik manual, contoh:\n"
        "   • <code>beli galon 5000</code>\n"
        "   • <code>dp wedding klien A 500rb</code>\n"
        "   • <code>bayaran foto wisuda 300000</code>\n\n"
        "📊 /laporan → Ringkasan keuangan\n"
        "📋 /riwayat → 5 transaksi terakhir\n"
        "❓ /bantuan → Panduan lengkap",
        parse_mode="HTML"
    )

async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ <b>Panduan Bot Kas Studio</b>\n\n"
        "<b>📸 Kirim Foto Nota:</b>\n"
        "Foto struk, nota, kuitansi apapun → AI baca otomatis\n\n"
        "<b>✍️ Ketik Manual (format bebas):</b>\n"
        "• <code>beli tinta printer 45000</code>\n"
        "• <code>dp foto wedding 1jt</code>\n"
        "• <code>lunas foto keluarga 350rb</code>\n"
        "• <code>bayar listrik 200000</code>\n\n"
        "<b>Singkatan:</b> rb/ribu=×1.000 · jt/juta=×1.000.000\n\n"
        "<b>Perintah:</b>\n"
        "/laporan · /riwayat · /start",
        parse_mode="HTML"
    )

async def laporan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = hitung_saldo()
    masuk = data.get("masuk", 0)
    keluar = data.get("keluar", 0)
    saldo = data.get("saldo", 0)
    emoji_saldo = "✅" if saldo >= 0 else "⚠️"
    await update.message.reply_text(
        f"📊 <b>Laporan Keuangan Studio</b>\n\n"
        f"💰 Pemasukan : <b>{format_rupiah(masuk)}</b>\n"
        f"💸 Pengeluaran: <b>{format_rupiah(keluar)}</b>\n"
        f"{'─'*28}\n"
        f"{emoji_saldo} Saldo     : <b>{format_rupiah(saldo)}</b>",
        parse_mode="HTML"
    )

async def riwayat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = ambil_semua_transaksi()
    if not rows:
        await update.message.reply_text("Belum ada transaksi yang tercatat.")
        return
    pesan = "📋 <b>5 Transaksi Terakhir</b>\n\n"
    for r in rows[:5]:
        kategori = r[2]
        emoji = "💰" if "Pendapatan" in kategori else "💸"
        pesan += f"{emoji} {bersihkan(r[3] or kategori)}\n   {format_rupiah(r[4])} · {r[1]}\n\n"
    await update.message.reply_text(pesan, parse_mode="HTML")


# ── Foto Handler ──────────────────────────────────────────────────────────────
async def terima_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Sedang membaca nota... Tunggu sebentar ya!")
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
        result = baca_nota_gambar(bytes(image_bytes))

        if "error" in result:
            await update.message.reply_text(
                f"⚠️ {bersihkan(result['error'])}\n\n"
                f"Coba ketik manual:\n<code>beli galon 5000</code>",
                parse_mode="HTML"
            )
            return ConversationHandler.END

        context.user_data["transaksi_pending"] = result
        await update.message.reply_text(
            buat_pesan_konfirmasi(result),
            parse_mode="HTML",
            reply_markup=keyboard_konfirmasi()
        )
        return MENUNGGU_KONFIRMASI
    except Exception as e:
        logger.error(f"Error foto: {e}")
        await update.message.reply_text("❌ Error memproses foto. Coba lagi atau ketik manual.")
        return ConversationHandler.END


# ── Teks Handler ──────────────────────────────────────────────────────────────
async def terima_teks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.message.text.strip()
    if len(teks) < 3:
        return ConversationHandler.END

    await update.message.reply_text("🤔 Menganalisis transaksi...")
    try:
        result = analisis_teks(teks)
        if "error" in result:
            await update.message.reply_text(bersihkan(result['error']))
            return ConversationHandler.END

        context.user_data["transaksi_pending"] = result
        await update.message.reply_text(
            buat_pesan_konfirmasi(result),
            parse_mode="HTML",
            reply_markup=keyboard_konfirmasi()
        )
        return MENUNGGU_KONFIRMASI
    except Exception as e:
        logger.error(f"Error teks: {e}")
        await update.message.reply_text("❌ Terjadi error. Coba lagi ya.")
        return ConversationHandler.END


# ── Konfirmasi ────────────────────────────────────────────────────────────────
async def konfirmasi_simpan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jawaban = update.message.text
    if jawaban == "✅ Ya, Simpan":
        data_ai = context.user_data.get("transaksi_pending")
        if not data_ai:
            await update.message.reply_text("⚠️ Data tidak ditemukan. Coba ulang.")
            return ConversationHandler.END
        try:
            simpan_transaksi(buat_data_db(data_ai))
            emoji = "💰" if data_ai["jenis"] == "PEMASUKAN" else "💸"
            await update.message.reply_text(
                f"{emoji} <b>Transaksi tersimpan!</b>\n\n"
                f"{bersihkan(data_ai['deskripsi'])} — {format_rupiah(data_ai['nominal'])}\n\n"
                f"Kirim foto atau ketik transaksi berikutnya 👇",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
            )
        except Exception as e:
            logger.error(f"Error simpan: {e}")
            await update.message.reply_text("❌ Gagal menyimpan. Coba lagi.")
    else:
        await update.message.reply_text(
            "❌ Dibatalkan. Kirim foto atau ketik transaksi baru.",
            reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
        )
    context.user_data.pop("transaksi_pending", None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("transaksi_pending", None)
    await update.message.reply_text("Dibatalkan.")
    return ConversationHandler.END


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN tidak ditemukan!")
    if not os.environ.get("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY tidak ditemukan!")

    init_db()

    flask_thread = threading.Thread(target=jalankan_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask thread started")

    app = Application.builder().token(token).build()

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

    logger.info("Bot polling dimulai...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
