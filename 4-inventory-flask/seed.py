"""Isi data demo (fiktif). Jalankan: python seed.py  (hanya jika database masih kosong)."""
import sqlite3

from app import app, init_db, now

DATA = [  # sku, nama, kategori, beli, jual, stok, min
    ("BRS-5KG", "Beras Premium 5 kg", "Sembako", 62000, 68000, 40, 10),
    ("MNY-1L", "Minyak Goreng 1 L", "Sembako", 15500, 17500, 4, 12),
    ("GLA-1KG", "Gula Pasir 1 kg", "Sembako", 14000, 16000, 25, 10),
    ("TLR-1KG", "Telur Ayam 1 kg", "Sembako", 27000, 30000, 0, 8),
    ("IDM-GRG", "Mi Instan Goreng", "Makanan", 2800, 3500, 120, 40),
    ("BSK-ROT", "Biskuit Kelapa", "Makanan", 7000, 9000, 18, 15),
    ("TEH-BTL", "Teh Botol 350 ml", "Minuman", 3500, 5000, 6, 24),
    ("AQA-600", "Air Mineral 600 ml", "Minuman", 2200, 3000, 96, 48),
    ("KOP-SCH", "Kopi Sachet (10 pcs)", "Minuman", 9500, 12000, 30, 10),
    ("SBN-BTG", "Sabun Mandi Batang", "Rumah Tangga", 3200, 4500, 55, 20),
    ("DTG-800", "Deterjen Bubuk 800 g", "Rumah Tangga", 16000, 20000, 9, 10),
    ("TSU-BOX", "Tisu Wajah Box", "Rumah Tangga", 8000, 11000, 33, 10),
]

init_db()
with sqlite3.connect(app.config["DB_PATH"]) as c:
    if c.execute("SELECT COUNT(*) FROM produk").fetchone()[0]:
        raise SystemExit("Database tidak kosong, seed dibatalkan.")
    for sku, nama, kat, beli, jual, stok, mn in DATA:
        cur = c.execute("INSERT INTO produk(sku,nama,kategori,harga_beli,harga_jual,stok,stok_min,dibuat) VALUES(?,?,?,?,?,?,?,?)",
                        (sku, nama, kat, beli, jual, stok, mn, now()))
        if stok:
            c.execute("INSERT INTO mutasi(produk_id,tipe,jumlah,stok_akhir,catatan,waktu) VALUES(?,?,?,?,?,?)",
                      (cur.lastrowid, "masuk", stok, stok, "Stok awal (demo)", now()))
print(f"{len(DATA)} produk demo ditambahkan.")
