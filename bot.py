import os
import logging
import threading
import time
import html
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from flask import Flask, jsonify, render_template, send_from_directory
from ocr import baca_nota_gambar, analisis_teks
from database import init_db, simpan_transaksi, ambil_semua_transaksi, hitung_saldo

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Flask ─────────────────────────────────────────────────────────────────────
app_flask = Flask(__name__)

@app_flask.route("/")
def dashboard():
    try:
        transaksi_rows = ambil_semua_transaksi()
        saldo_data = hitung_saldo()
        data = []
        for r in transaksi_rows:
            data.append({
                "id": r[0], "tanggal": r[1], "kategori": r[2],
                "keterangan": r[3] or "", "nominal": r[4], "timestamp": r[5]
            })
        return render_template(
            "dashboard.html",
            masuk=saldo_data["masuk"],
            keluar=saldo_data["keluar"],
            saldo=saldo_data["saldo"],
            data=data
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return "<h1>Bot Kas Studio - Running</h1><p>Dashboard sedang dimuat...</p>", 200

@app_flask.route("/lensera-finance.html")
def lensera():
    return send_from_directory('.', 'lensera-finance.html')

@app_flask.route("/api/laporan")
def api_laporan():
    return jsonify(hitung_saldo())

@app_flask.route("/api/riwayat")
def api_riwayat():
    rows = ambil_semua_transaksi()
    hasil = []
    for r in rows[:500]:
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


# ── Commands ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nama = update.effective_user.first_name
    await update.message.reply_text(
        f"Halo {nama}! 👋\n\n"
        "Selamat datang di <b>Bot Buku Kas Studio</b> 📷\n\n"
        "Cara pakai:\n"
        "📸 Kirim <b>foto nota/struk</b> → langsung tersimpan otomatis\n"
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
        "Foto struk, nota, kuitansi apapun → langsung tersimpan!\n\n"
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
    await update.message.reply_text("🔍 Membaca nota...")
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
        result = baca_nota_gambar(bytes(image_bytes))

        if "error" in result:
            await update.message.reply_text(
                f"⚠️ {bersihkan(result['error'])}\n\nCoba ketik manual:\n<code>beli galon 5000</code>",
                parse_mode="HTML"
            )
            return

        simpan_transaksi(buat_data_db(result))
        emoji = "💰" if result["jenis"] == "PEMASUKAN" else "💸"
        await update.message.reply_text(
            f"{emoji} <b>Tersimpan!</b>\n\n"
            f"Jenis    : <b>{bersihkan(result['jenis'])}</b>\n"
            f"Nominal  : <b>{format_rupiah(result['nominal'])}</b>\n"
            f"Deskripsi: {bersihkan(result['deskripsi'])}\n"
            f"Kategori : {bersihkan(result['kategori'])}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error foto: {e}")
        await update.message.reply_text("❌ Error memproses foto. Coba lagi atau ketik manual.")


# ── Teks Handler ──────────────────────────────────────────────────────────────
async def terima_teks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.message.text.strip()
    if len(teks) < 3:
        return

    await update.message.reply_text("🤔 Menganalisis...")
    try:
        result = analisis_teks(teks)
        if "error" in result:
            await update.message.reply_text(bersihkan(result['error']))
            return

        simpan_transaksi(buat_data_db(result))
        emoji = "💰" if result["jenis"] == "PEMASUKAN" else "💸"
        await update.message.reply_text(
            f"{emoji} <b>Tersimpan!</b>\n\n"
            f"Jenis    : <b>{bersihkan(result['jenis'])}</b>\n"
            f"Nominal  : <b>{format_rupiah(result['nominal'])}</b>\n"
            f"Deskripsi: {bersihkan(result['deskripsi'])}\n"
            f"Kategori : {bersihkan(result['kategori'])}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error teks: {e}")
        await update.message.reply_text("❌ Terjadi error. Coba lagi ya.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN tidak ditemukan!")
    if not os.environ.get("GROQ_API_KEY"):
        raise ValueError("GROQ_API_KEY tidak ditemukan!")

    init_db()

    flask_thread = threading.Thread(target=jalankan_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask thread started")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bantuan", bantuan))
    app.add_handler(CommandHandler("laporan", laporan))
    app.add_handler(CommandHandler("riwayat", riwayat))
    app.add_handler(MessageHandler(filters.PHOTO, terima_foto))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, terima_teks))

    logger.info("Bot polling dimulai...")
    while True:
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Polling error: {e}, restarting in 10 seconds...")
        time.sleep(10)

if __name__ == "__main__":
    main()
