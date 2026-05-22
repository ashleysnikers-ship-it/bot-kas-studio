import re
import requests
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
OCRSPACE_API_KEY = os.getenv("OCRSPACE_API_KEY")

def baca_struk(image_bytes):
    url = "https://api.ocr.space/parse/image"
    response = requests.post(
        url,
        files={"file": ("struk.jpg", image_bytes, "image/jpeg")},
        data={"isoverlayrequired": False, "language": "eng", "filetype": "JPG"},
        headers={"apikey": OCRSPACE_API_KEY}
    )
    result = response.json()
    print("OCR RESPONSE:", result)
    if result.get("ParsedResults"):
        return result["ParsedResults"][0]["ParsedText"]
    return None

def ekstrak_nominal(teks):
    # Bersihkan newline dulu
    teks_bersih = teks.replace('\r\n', ' ').replace('\n', ' ')
    pola = r'Rp\.?\s*([\d,]+(?:\.\d{2})?)'
    matches = re.findall(pola, teks_bersih)
    angka_list = []
    for m in matches:
        bersih = re.sub(r'\.\d+$', '', m)
        bersih = bersih.replace(',', '')
        if bersih.isdigit():
            nilai = int(bersih)
            if 1000 <= nilai <= 999000000:
                angka_list.append(nilai)
    return max(angka_list) if angka_list else 0

def deteksi_kategori(teks):
    teks_lower = teks.lower()
    if any(x in teks_lower for x in ["print", "tinta", "kertas", "canon", "flash", "led", "lighting", "tripod"]):
        return "Pengeluaran - Alat Studio"
    elif any(x in teks_lower for x in ["listrik", "pln", "air", "pdam", "sewa"]):
        return "Pengeluaran - Operasional"
    elif any(x in teks_lower for x in ["wedding", "graduation", "potrait", "pas foto", "foto"]):
        return "Pendapatan - Jasa Foto"
    elif any(x in teks_lower for x in ["dp", "uang muka", "booking"]):
        return "Pendapatan - DP"
    elif any(x in teks_lower for x in ["lunas", "pelunasan"]):
        return "Pendapatan - Pelunasan"
    elif any(x in teks_lower for x in ["gojek", "grab", "shopee", "tokopedia"]):
        return "Pengeluaran - Pengiriman"
    else:
        return "Lainnya"

def proses_struk(image_bytes):
    teks = baca_struk(image_bytes)
    if not teks:
        return None
    nominal = ekstrak_nominal(teks)
    kategori = deteksi_kategori(teks)
    return {
        "tanggal": datetime.now().strftime("%Y-%m-%d"),
        "kategori": kategori,
        "keterangan": teks[:100].strip(),
        "nominal": nominal
    }