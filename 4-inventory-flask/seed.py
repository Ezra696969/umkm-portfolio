"""Isi data demo (fiktif). Jalankan: python seed.py  (hanya jika database masih kosong)."""
from app import DEMO_PRODUK, seed_demo, init_db

init_db()
if not seed_demo():
    raise SystemExit("Database tidak kosong, seed dibatalkan.")
print(f"{len(DEMO_PRODUK)} produk demo ditambahkan.")
