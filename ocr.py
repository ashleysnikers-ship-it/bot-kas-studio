import os
import json
import re
import base64
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

PROMPT_GAMBAR = """Kamu adalah asisten keuangan studio foto milik ANGGI HARIADI.

Analisis gambar nota/struk/kuitansi ini dan tentukan jenis transaksi berdasarkan aturan berikut:

ATURAN UTAMA untuk struk transfer bank:
- Kalau "ANGGI HARIADI" ada di bagian REKENING SUMBER / pengirim → PENGELUARAN (uang keluar)
- Kalau "ANGGI HARIADI" ada di bagian PENERIMA / tujuan → PEMASUKAN (uang masuk)
- Kalau tidak ada nama ANGGI HARIADI → tentukan dari konteks (nota belanja = PENGELUARAN, bukti bayar klien = PEMASUKAN)

ATURAN untuk nota/struk lain:
- Nota belanja, struk toko, tagihan = PENGELUARAN
- Bukti pembayaran dari klien, DP, pelunasan foto = PEMASUKAN

Ekstrak juga:
- Nominal: gunakan Total Transaksi (bukan nominal transfer saja, karena sudah termasuk biaya admin)
- Deskripsi singkat (max 50 karakter)
- Kategori yang cocok

Panduan kategori:
- PEMASUKAN: Foto Wedding, Foto Wisuda, Foto Produk, Foto Keluarga, DP Booking, Pelunasan, Transfer Masuk, Payroll
- PENGELUARAN: Beli Alat, Operasional, Konsumsi, Transport, Cetak Foto, Software, Galon/Air, Listrik, Transfer Keluar

Balas HANYA dalam format JSON ini (tanpa teks lain, tanpa markdown):
{"jenis":"PEMASUKAN","nominal":50000,"deskripsi":"deskripsi singkat","kategori":"nama kategori"}

Kalau gambar tidak jelas atau bukan nota/struk:
{"error":"Gambar tidak terbaca. Silakan kirim gambar lebih jelas atau ketik manual."}"""

PROMPT_TEKS = """Kamu adalah asisten keuangan studio foto milik ANGGI HARIADI.

Teks dari pengguna: "{teks}"

Tentukan jenis transaksi:
- Kata seperti "beli", "bayar", "keluar", "biaya", "ongkos", "transfer ke", "kirim ke" → PENGELUARAN
- Kata seperti "terima", "dapat", "masuk", "bayaran", "dp", "lunas", "dibayar", "transfer dari" → PEMASUKAN
- Nama sesi foto (wedding, wisuda, keluarga, produk) tanpa kata pengeluaran → PEMASUKAN

Ubah singkatan: rb/ribu=x1000, jt/juta=x1000000, k=x1000

Balas HANYA dalam format JSON ini (tanpa teks lain, tanpa markdown):
{"jenis":"PEMASUKAN","nominal":50000,"deskripsi":"deskripsi singkat","kategori":"nama kategori"}

Kalau tidak bisa dipahami sebagai transaksi:
{"error":"Tidak bisa memahami. Contoh: beli galon 5000 atau dp wedding 500rb"}"""


def parse_response(text):
    text = text.strip()
    text = re.sub(r'```(?:json)?', '', text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {"error": "Gagal memproses respons AI. Coba lagi atau ketik manual."}


def baca_nota_gambar(image_bytes):
    try:
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                    },
                    {
                        "type": "text",
                        "text": PROMPT_GAMBAR
                    }
                ]
            }],
            max_tokens=300,
            temperature=0.1
        )
        return parse_response(response.choices[0].message.content)
    except Exception as e:
        return {"error": f"Gagal membaca gambar: {str(e)}"}


def analisis_teks(teks):
    try:
        prompt = PROMPT_TEKS.replace("{teks}", teks)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": prompt
            }],
            max_tokens=200,
            temperature=0.1
        )
        return parse_response(response.choices[0].message.content)
    except Exception as e:
        return {"error": f"Gagal menganalisis teks: {str(e)}"}
