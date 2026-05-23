import os
import json
import re
import base64
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

PROMPT_GAMBAR = """
Kamu adalah asisten keuangan studio foto yang bertugas membaca nota/struk/kuitansi.

Analisis gambar ini dan ekstrak informasi transaksi keuangan. Tentukan:
1. Jenis transaksi: PEMASUKAN atau PENGELUARAN
2. Nominal uang (angka saja, tanpa titik/koma/Rp)
3. Deskripsi singkat transaksi (max 50 karakter)
4. Kategori yang cocok

Panduan kategori:
- PEMASUKAN: Foto Wedding, Foto Wisuda, Foto Produk, Foto Keluarga, DP Booking, Pelunasan, Transfer Masuk, Payroll, dll
- PENGELUARAN: Beli Alat, Operasional, Konsumsi, Transport, Cetak Foto, Software, Galon/Air, Listrik, dll

Balas HANYA dalam format JSON ini (tanpa teks lain):
{
  "jenis": "PEMASUKAN" atau "PENGELUARAN",
  "nominal": 50000,
  "deskripsi": "deskripsi singkat",
  "kategori": "nama kategori"
}

Kalau gambar bukan nota/struk atau tidak ada angka yang jelas, balas:
{
  "error": "Gambar tidak terbaca sebagai nota/struk. Silakan kirim gambar yang lebih jelas atau ketik manual."
}
"""

PROMPT_TEKS = """
Kamu adalah asisten keuangan studio foto yang bertugas menganalisis teks transaksi keuangan.

Teks dari pengguna: "{teks}"

Tentukan:
1. Jenis transaksi: PEMASUKAN atau PENGELUARAN
2. Nominal uang (angka saja, tanpa titik/koma/Rp)
3. Deskripsi singkat (max 50 karakter)
4. Kategori yang cocok

Panduan:
- Kata seperti "beli", "bayar", "keluar", "biaya", "ongkos" → PENGELUARAN
- Kata seperti "terima", "dapat", "masuk", "bayaran", "dp", "lunas", "transfer masuk", "payroll" → PEMASUKAN
- Kalau ada nama sesi foto (wedding, wisuda, dll) tanpa kata pengeluaran → PEMASUKAN

Contoh:
- "beli galon 5000" → PENGELUARAN, 5000, "Beli Galon", "Operasional"
- "dp wedding klien A 500rb" → PEMASUKAN, 500000, "DP Wedding Klien A", "DP Booking"
- "cetak foto 75000" → PENGELUARAN, 75000, "Cetak Foto", "Cetak Foto"
- "bayaran foto wisuda 300000" → PEMASUKAN, 300000, "Bayaran Foto Wisuda", "Foto Wisuda"

Ubah singkatan umum: rb/ribu=x1000, jt/juta=x1000000, k=x1000

Balas HANYA dalam format JSON ini (tanpa teks lain):
{
  "jenis": "PEMASUKAN" atau "PENGELUARAN",
  "nominal": 50000,
  "deskripsi": "deskripsi singkat",
  "kategori": "nama kategori"
}

Kalau tidak bisa dipahami sebagai transaksi keuangan, balas:
{
  "error": "Tidak bisa memahami sebagai transaksi. Contoh: 'beli galon 5000' atau 'dp wedding 500rb'"
}
"""


def parse_response(text):
    try:
        return json.loads(text.strip())
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
        # Encode ke base64 string — cara yang benar untuk SDK 0.8.x
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        image_part = {
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": image_b64
            }
        }
        response = model.generate_content([PROMPT_GAMBAR, image_part])
        return parse_response(response.text.strip())
    except Exception as e:
        return {"error": f"Gagal membaca gambar: {str(e)}"}


def analisis_teks(teks):
    try:
        prompt = PROMPT_TEKS.format(teks=teks)
        response = model.generate_content(prompt)
        return parse_response(response.text.strip())
    except Exception as e:
        return {"error": f"Gagal menganalisis teks: {str(e)}"}
