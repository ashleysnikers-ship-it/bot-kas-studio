import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Deteksi PostgreSQL atau SQLite ────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")

USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    logger.info("✅ Menggunakan PostgreSQL (Supabase)")
else:
    import sqlite3
    DB_FILE = "buku_kas.db"
    logger.info("⚠️  DATABASE_URL tidak ditemukan, fallback ke SQLite")


# ── Koneksi ───────────────────────────────────────────────────────────────────
def get_conn():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return conn
    else:
        return sqlite3.connect(DB_FILE)


# ── Init DB ───────────────────────────────────────────────────────────────────
def init_db():
    """Buat tabel kalau belum ada"""
    conn = get_conn()
    cursor = conn.cursor()
    if USE_POSTGRES:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transaksi (
                id        SERIAL PRIMARY KEY,
                tanggal   TEXT NOT NULL,
                kategori  TEXT NOT NULL,
                keterangan TEXT,
                nominal   BIGINT NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
    else:
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
    logger.info("✅ Database siap")


# ── Simpan Transaksi ──────────────────────────────────────────────────────────
def simpan_transaksi(data):
    """Simpan satu transaksi ke database"""
    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if USE_POSTGRES:
        cursor.execute('''
            INSERT INTO transaksi (tanggal, kategori, keterangan, nominal, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        ''', (
            data["tanggal"],
            data["kategori"],
            data["keterangan"],
            data["nominal"],
            now
        ))
    else:
        cursor.execute('''
            INSERT INTO transaksi (tanggal, kategori, keterangan, nominal, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data["tanggal"],
            data["kategori"],
            data["keterangan"],
            data["nominal"],
            now
        ))
    conn.commit()
    conn.close()


# ── Ambil Semua Transaksi ─────────────────────────────────────────────────────
def ambil_semua_transaksi():
    """Ambil semua transaksi, terbaru duluan"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM transaksi ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows


# ── Hitung Saldo ──────────────────────────────────────────────────────────────
def hitung_saldo():
    """Hitung total masuk, keluar, dan saldo"""
    conn = get_conn()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute("SELECT COALESCE(SUM(nominal), 0) FROM transaksi WHERE kategori LIKE 'Pendapatan%'")
        total_masuk = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(nominal), 0) FROM transaksi WHERE kategori LIKE 'Pengeluaran%'")
        total_keluar = cursor.fetchone()[0]
    else:
        cursor.execute("SELECT SUM(nominal) FROM transaksi WHERE kategori LIKE 'Pendapatan%'")
        total_masuk = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(nominal) FROM transaksi WHERE kategori LIKE 'Pengeluaran%'")
        total_keluar = cursor.fetchone()[0] or 0

    conn.close()

    return {
        "masuk": int(total_masuk),
        "keluar": int(total_keluar),
        "saldo": int(total_masuk) - int(total_keluar)
    }
