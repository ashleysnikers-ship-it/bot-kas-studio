import os
import json
import re
import base64
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

PROMPT_GAMBAR = """Kamu adalah asisten keuangan studio foto yang bertugas membaca nota/struk/kuitansi.

Analisis gambar ini dan ekstrak informasi transaksi keuangan. Tentukan:
1. Jenis transaksi: PEMASUKAN atau PENGELUARAN
2. Nominal uang (angka saja, tanpa titik/koma/Rp)
3. Deskripsi singkat transaksi (max 50 karakter)
4. Kategori yang cocok

Panduan kategori:
- PEMASUKAN: Foto Wedding, Foto Wisuda, Foto Produk, Foto Keluarga, DP Booking, Pelunasan, Transfer Masuk, Payroll, dll
- PENGELUARAN: Beli Alat, Operasional, Konsumsi, Transport, Cetak Foto, Software, Galon/Air, Listrik, dll

Balas HANYA dalam format JSON ini (tanpa teks lain, tanpa markdown):
{"jenis":"PEMASUKAN","nominal":50000,"deskripsi":"deskripsi singkat","kategori":"nama kategori"}

Kalau gambar bukan nota/struk atau tidak ada angka yang jelas, balas:
{"error":"Gambar tidak terbaca sebagai nota/struk. Silakan kirim gambar lebih jelas atau ketik manual."}"""

PROMPT_TEKS = """Kamu adalah asisten keuangan studio foto yang bertugas menganalisis teks transaksi keuangan.

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

Ubah singkatan: rb/ribu=x1000, jt/juta=x1000000, k=x1000

Balas HANYA dalam format JSON ini (tanpa teks lain, tanpa markdown):
{"jenis":"PEMASUKAN","nominal":50000,"deskripsi":"deskripsi singkat","kategori":"nama kategori"}

Kalau tidak bisa dipahami sebagai transaksi keuangan, balas:
{"error":"Tidak bisa memahami sebagai transaksi. Contoh: beli galon 5000 atau dp wedding 500rb"}"""


def parse_response(text):
    text = text.strip()
    # Hapus markdown code block kalau ada
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
    """Baca nota dari gambar menggunakan Groq Vision (Llama 4 Scout)."""
    try:
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        }
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
        result_text = response.choices[0].message.content
        return parse_response(result_text)
    except Exception as e:
        return {"error": f"Gagal membaca gambar: {str(e)}"}


def analisis_teks(teks):
    """Analisis teks input manual dari user."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": PROMPT_TEKS.format(teks=teks)
            }],
            max_tokens=200,
            temperature=0.1
        )
        result_text = response.choices[0].message.content
        return parse_response(result_text)
    except Exception as e:
        return {"error": f"Gagal menganalisis teks: {str(e)}"}
