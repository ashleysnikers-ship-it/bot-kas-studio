import os
import base64
import json
import re
import google.generativeai as genai
from PIL import Image
import io

# Konfigurasi Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

PROMPT_GAMBAR = """
Kamu adalah asisten keuangan studio foto yang bertugas membaca nota/struk/kuitansi.

Analisis gambar ini dan ekstrak informasi transaksi keuangan. Tentukan:
1. Jenis transaksi: PEMASUKAN atau PENGELUARAN
2. Nominal uang (angka saja, tanpa titik/koma/Rp)
3. Deskripsi singkat transaksi (max 50 karakter)
4. Kategori yang cocok

Panduan kategori:
- PEMASUKAN: Foto Wedding, Foto Wisuda, Foto Produk, Foto Keluarga, DP Booking, Pelunasan, Transfer Masuk, dll
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
- Kata seperti "beli", "bayar", "beli", "keluar", "biaya", "ongkos" → PENGELUARAN
- Kata seperti "terima", "dapat", "masuk", "bayaran", "dp", "lunas", "transfer masuk" → PEMASUKAN
- Kalau ada nama sesi foto (wedding, wisuda, dll) tanpa kata pengeluaran → PEMASUKAN

Contoh:
- "beli galon 5000" → PENGELUARAN, 5000, "Beli Galon", "Operasional"
- "dp wedding klien A 500rb" → PEMASUKAN, 500000, "DP Wedding Klien A", "DP Booking"
- "cetak foto 75000" → PENGELUARAN, 75000, "Cetak Foto", "Cetak Foto"
- "bayaran foto wisuda 300000" → PEMASUKAN, 300000, "Bayaran Foto Wisuda", "Foto Wisuda"

Ubah singkatan umum: rb/ribu=×1000, jt/juta=×1000000, k=×1000

Balas HANYA dalam format JSON ini (tanpa teks lain):
{
  "jenis": "PEMASUKAN" atau "PENGELUARAN",
  "nominal": 50000,
  "deskripsi": "deskripsi singkat",
  "kategori": "nama kategori"
}

Kalau tidak bisa dipahami sebagai transaksi keuangan, balas:
{
  "error": "Tidak bisa memahami sebagai transaksi. Contoh penulisan: 'beli galon 5000' atau 'dp wedding 500rb'"
}
"""


def parse_response(text):
    """Parse JSON response dari Gemini, toleran terhadap format aneh."""
    try:
        # Coba parse langsung
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # Coba extract JSON dari dalam teks
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {"error": "Gagal memproses respons AI. Coba lagi atau ketik manual."}


def baca_nota_gambar(image_bytes):
    """
    Baca nota dari gambar menggunakan Gemini Vision.
    
    Args:
        image_bytes: bytes dari gambar
    
    Returns:
        dict: {"jenis", "nominal", "deskripsi", "kategori"} atau {"error": "..."}
    """
    try:
        # Buka gambar dengan PIL
        image = Image.open(io.BytesIO(image_bytes))
        
        # Kirim ke Gemini Vision
        response = model.generate_content([PROMPT_GAMBAR, image])
        result_text = response.text.strip()
        
        return parse_response(result_text)
    
    except Exception as e:
        return {"error": f"Gagal membaca gambar: {str(e)}"}


def analisis_teks(teks):
    """
    Analisis teks input manual dari user.
    
    Args:
        teks: string input dari user, misal "beli galon 5000"
    
    Returns:
        dict: {"jenis", "nominal", "deskripsi", "kategori"} atau {"error": "..."}
    """
    try:
        prompt = PROMPT_TEKS.format(teks=teks)
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        return parse_response(result_text)
    
    except Exception as e:
        return {"error": f"Gagal menganalisis teks: {str(e)}"}
