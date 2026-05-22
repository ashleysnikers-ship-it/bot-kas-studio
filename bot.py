import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from database import init_db, simpan_transaksi, hitung_saldo, ambil_semua_transaksi
from ocr import proses_struk

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(level=logging.INFO)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo! Gua Bot Buku Kas Studio lu.\n\n"
        "📸 Kirim foto struk → langsung gua catat otomatis\n"
        "📊 /laporan → lihat ringkasan keuangan\n"
        "📋 /riwayat → 5 transaksi terakhir\n"
        "❓ /help → bantuan"
    )

async def cmd_laporan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saldo = hitung_saldo()
    pesan = (
        f"📊 *Laporan Keuangan*\n\n"
        f"✅ Total Masuk : Rp {saldo['masuk']:,}\n"
        f"❌ Total Keluar: Rp {saldo['keluar']:,}\n"
        f"💰 Saldo       : Rp {saldo['saldo']:,}"
    )
    await update.message.reply_text(pesan, parse_mode="Markdown")

async def cmd_riwayat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    transaksi = ambil_semua_transaksi()[:5]
    if not transaksi:
        await update.message.reply_text("Belum ada transaksi tercatat.")
        return
    pesan = "📋 *5 Transaksi Terakhir:*\n\n"
    for t in transaksi:
        pesan += f"• {t[1]} | {t[2]}\n  {t[3][:40]}...\n  Rp {t[4]:,}\n\n"
    await update.message.reply_text(pesan, parse_mode="Markdown")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Cara Pakai Bot:*\n\n"
        "1. Foto struk belanja/pembayaran\n"
        "2. Kirim ke bot ini\n"
        "3. Bot otomatis baca & catat\n\n"
        "📌 *Commands:*\n"
        "/laporan - Ringkasan keuangan\n"
        "/riwayat - 5 transaksi terakhir\n"
        "/start - Pesan sambutan",
        parse_mode="Markdown"
    )

async def handle_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Lagi baca struk, tunggu sebentar...")
    foto = update.message.photo[-1]
    file = await context.bot.get_file(foto.file_id)
    foto_bytes = await file.download_as_bytearray()
    data = proses_struk(bytes(foto_bytes))
    if not data:
        await update.message.reply_text("❌ Gagal baca struk. Coba foto ulang.")
        return
    if data["nominal"] == 0:
        context.user_data["pending"] = data
        await update.message.reply_text(
            "📸 Struk terbaca! Tapi nominal nggak kedeteksi.\n\n"
            "Ketik nominalnya (contoh: 4500000):"
        )
        return
    simpan_transaksi(data)
    await update.message.reply_text(
        f"✅ *Struk berhasil dicatat!*\n\n"
        f"📅 Tanggal  : {data['tanggal']}\n"
        f"🏷️ Kategori : {data['kategori']}\n"
        f"💵 Nominal  : Rp {data['nominal']:,}\n"
        f"📝 Keterangan: {data['keterangan'][:60]}...",
        parse_mode="Markdown"
    )

async def handle_teks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "pending" in context.user_data:
        teks = update.message.text.replace(".", "").replace(",", "").strip()
        if teks.isdigit():
            data = context.user_data.pop("pending")
            data["nominal"] = int(teks)
            simpan_transaksi(data)
            await update.message.reply_text(
                f"✅ *Tercatat!*\n\n"
                f"📅 Tanggal  : {data['tanggal']}\n"
                f"🏷️ Kategori : {data['kategori']}\n"
                f"💵 Nominal  : Rp {int(teks):,}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("Ketik angka aja ya, contoh: 4500000")

def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("laporan", cmd_laporan))
    app.add_handler(CommandHandler("riwayat", cmd_riwayat))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.PHOTO, handle_foto))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_teks))
    print("🤖 Bot berjalan... Tekan Ctrl+C untuk stop.")
    app.run_polling()

if __name__ == "__main__":
    main()