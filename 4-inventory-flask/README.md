# Stokku — contoh kasir (POS) + inventori UMKM (Flask + SQLite)

Usaha fiktif ("Toko Maju Jaya"), untuk portofolio. Dua peran yang saling terhubung:

| Peran | Bisa apa |
|---|---|
| **Kasir** (pegawai) | Layar kasir: cari/pilih produk, keranjang, bayar (tunai/QRIS/transfer), kembalian otomatis, struk cetak, rekap transaksi & kas hari ini miliknya. Tidak bisa membuka inventori, laporan, atau pegawai. |
| **Admin** (pemilik) | Semua fitur kasir + dashboard, inventori (CRUD produk, mutasi stok), laporan penjualan (omzet, laba kotor, terlaris, per kasir/hari), pembatalan transaksi, kelola akun kasir, ekspor CSV. |

**Keterhubungan:** setiap penjualan di kasir otomatis mengurangi stok dan tercatat sebagai mutasi (`Penjualan INV…`). Admin membatalkan transaksi → stok dikembalikan dan tercatat. Stok menipis muncul di dashboard admin.

## Menjalankan (PowerShell)

```powershell
cd E:\Project\UMKM\4-inventory-flask
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:ADMIN_PASSWORD = "kata-sandi-kuat"
$env:SECRET_KEY = "string-acak-panjang"
.venv\Scripts\python seed.py    # opsional: 12 produk demo (hanya jika DB kosong)
.venv\Scripts\python app.py     # http://127.0.0.1:5000
```

1. Login `admin` + `ADMIN_PASSWORD`.
2. Menu **Pegawai** → buat akun kasir (username + kata sandi min. 8 karakter).
3. Kasir login dengan akunnya sendiri → langsung ke layar kasir.

Tes otomatis (20 tes, tanpa dependensi tambahan):

```powershell
.venv\Scripts\python -m unittest -v
```

## Poin teknis
- **Transaksi penjualan atomik:** `BEGIN IMMEDIATE`; stok semua item dicek dan dikurangi dalam satu transaksi. Satu item kurang → seluruh penjualan batal, tidak ada stok setengah berubah.
- **Harga dari server:** browser hanya mengirim id + qty; harga, total, dan kembalian dihitung ulang di server.
- **Struk menyimpan salinan** nama/harga/harga beli saat transaksi, jadi laporan lama tetap benar meski produk diubah atau dihapus.
- **Peran (RBAC):** daftar endpoint khusus admin dicek di satu `before_request`; kasir hanya bisa melihat struk miliknya.
- Sandi kasir di-hash (Werkzeug); sandi admin hanya dari `ADMIN_PASSWORD`, tidak disimpan. Pembatasan 5 login gagal/5 menit per IP.
- CSRF token di semua POST, query berparameter, output di-escape, CSV aman dari injeksi rumus.

## Batasan (jelaskan ke klien)
- Belum ada diskon/pajak, retur sebagian, shift kasir, atau integrasi printer/QRIS sungguhan (QRIS/transfer hanya dicatat).
- Pembatas login di memori (1 proses). Produksi: WSGI server (`waitress`/`gunicorn`) + HTTPS, cadangkan `inventori.db` berkala.
