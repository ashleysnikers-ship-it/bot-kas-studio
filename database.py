import sqlite3
from datetime import datetime

DB_FILE = "buku_kas.db"

def init_db():
    """Bikin tabel kalau belum ada"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT NOT NULL,
            kategori TEXT NOT NULL,
            keterangan TEXT,
            nominal INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def simpan_transaksi(data):
    """Simpan satu transaksi ke database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transaksi (tanggal, kategori, keterangan, nominal, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        data["tanggal"],
        data["kategori"],
        data["keterangan"],
        data["nominal"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()

def ambil_semua_transaksi():
    """Ambil semua transaksi, terbaru duluan"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM transaksi ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

def hitung_saldo():
    """Hitung total masuk, keluar, dan saldo"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT SUM(nominal) FROM transaksi WHERE kategori LIKE 'Pendapatan%'")
    total_masuk = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(nominal) FROM transaksi WHERE kategori LIKE 'Pengeluaran%'")
    total_keluar = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        "masuk": total_masuk,
        "keluar": total_keluar,
        "saldo": total_masuk - total_keluar
    }