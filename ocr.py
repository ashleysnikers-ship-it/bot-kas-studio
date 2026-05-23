import os
import json
import re
import base64
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

PROMPT_GAMBAR = """Kamu adalah asisten keuangan studio foto milik ANGGI HARIADI.

Analisis gambar nota/struk/kuitansi ini dan tentukan jenis transaksi.

=== ATURAN WAJIB UNTUK STRUK TRANSFER BANK ===

Cari dua bagian di struk: REKENING SUMBER (pengirim) dan PENERIMA (tujuan).

CONTOH STRUK MANDIRI / LIVIN:
  Penerima: DEWI SRI SETIA ADJI
  Rekening Sumber: ANGGI HARIADI
  → ANGGI HARIADI = PENGIRIM = UANG KELUAR = PENGELUARAN ✅

  Penerima: ANGGI HARIADI
  Rekening Sumber: BUDI SANTOSO
  → ANGGI HARIADI = PENERIMA = UANG MASUK = PEMASUKAN ✅

ATURAN:
1. Jika "ANGGI HARIADI" muncul di bagian REKENING SUMBER / PENGIRIM / "From" → PENGELUARAN
2. Jika "ANGGI HARIADI" muncul di bagian PENERIMA / TUJUAN / "To" → PEMASUKAN
3. JANGAN lihat keterangan transaksi untuk menentukan jenis — lihat POSISI nama ANGGI HARIADI
4. Jika tidak ada nama ANGGI HARIADI → tentukan dari konteks (nota belanja = PENGELUARAN, bukti bayar klien = PEMASUKAN)

=== ATURAN NOTA/STRUK LAIN ===
- Nota belanja, struk toko, tagihan = PENGELUARAN
- Bukti pembayaran dari klien, DP, pelunasan foto = PEMASUKAN

=== EKSTRAKSI ===
- Nominal: gunakan Total Transaksi (sudah termasuk admin)
- Deskripsi singkat max 50 karakter — SERTAKAN nama penerima jika transfer keluar (contoh: "Payroll April - Dewi Sri")
- Kategori yang cocok

Panduan kategori:
- PEMASUKAN: Foto Wedding, Foto Wisuda, Foto Produk, Foto Keluarga, DP Booking, Pelunasan, Transfer Masuk, Payroll
- PENGELUARAN: Beli Alat, Operasional, Konsumsi, Transport, Cetak Foto, Software, Galon/Air, Listrik, Transfer Keluar, Payroll

Balas HANYA dalam format JSON ini (tanpa teks lain, tanpa markdown):
{"jenis":"PEMASUKAN","nominal":50000,"deskripsi":"deskripsi singkat","kategori":"nama kategori"}

Kalau gambar tidak jelas atau bukan nota/struk:
{"error":"Gambar tidak terbaca. Silakan kirim gambar lebih jelas atau ketik manual."}"""

PROMPT_TEKS = """Kamu adalah asisten keuangan studio foto milik ANGGI HARIADI.

Teks dari pengguna: "{teks}"

Tentukan jenis transaksi:
- Kata seperti "beli", "bayar", "keluar", "biaya", "ongkos", "transfer ke", "kirim ke", "payroll", "gaji" → PENGELUARAN
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


def validasi_transfer(result, teks_ocr=""):
    """
    Safety net: kalau AI masih salah, koreksi paksa berdasarkan
    pola teks yang terdeteksi dari gambar/keterangan.
    
    Logika: rekening pusat = ANGGI HARIADI
    - ANGGI HARIADI sebagai sumber/pengirim → PENGELUARAN
    - ANGGI HARIADI sebagai penerima/tujuan → PEMASUKAN
    """
    if "error" in result:
        return result

    teks_upper = teks_ocr.upper()

    # Pola: "Rekening Sumber: ANGGI HARIADI" atau "From: ANGGI HARIADI"
    pola_pengirim = [
        r'rekening sumber[\s\S]{0,30}anggi hariadi',
        r'pengirim[\s\S]{0,20}anggi hariadi',
        r'from[\s\S]{0,20}anggi hariadi',
        r'sumber[\s\S]{0,20}anggi hariadi',
    ]
    # Pola: "Penerima: ANGGI HARIADI" atau "To: ANGGI HARIADI"
    pola_penerima = [
        r'penerima[\s\S]{0,20}anggi hariadi',
        r'to[\s\S]{0,20}anggi hariadi',
        r'tujuan[\s\S]{0,20}anggi hariadi',
    ]

    for pola in pola_pengirim:
        if re.search(pola, teks_upper):
            if result.get("jenis") != "PENGELUARAN":
                result["jenis"] = "PENGELUARAN"
                result["_koreksi"] = "auto-koreksi: ANGGI HARIADI sebagai pengirim"
            return result

    for pola in pola_penerima:
        if re.search(pola, teks_upper):
            if result.get("jenis") != "PEMASUKAN":
                result["jenis"] = "PEMASUKAN"
                result["_koreksi"] = "auto-koreksi: ANGGI HARIADI sebagai penerima"
            return result

    return result


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
        raw_text = response.choices[0].message.content
        result = parse_response(raw_text)
        # Validasi tambahan menggunakan teks mentah dari AI sebagai konteks
        result = validasi_transfer(result, teks_ocr=raw_text)
        return result
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
        result = parse_response(response.choices[0].message.content)
        # Validasi juga untuk input teks (kalau user paste info transfer manual)
        result = validasi_transfer(result, teks_ocr=teks)
        return result
    except Exception as e:
        return {"error": f"Gagal menganalisis teks: {str(e)}"}
