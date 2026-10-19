# Dapur Lestari — contoh website katering (Flask + SQLite)

Usaha fiktif untuk portofolio. Fitur: form pesanan (validasi server) → SQLite, halaman admin (login, filter status, ubah status, ekspor CSV).

## Menjalankan (PowerShell)

```powershell
cd E:\Project\UMKM\3-katering-flask
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:ADMIN_PASSWORD = "isi-kata-sandi-kuat"
$env:SECRET_KEY = "isi-string-acak-panjang"
.venv\Scripts\python app.py
```

Buka http://127.0.0.1:5000 — admin di `/admin` (kata sandi = `ADMIN_PASSWORD`).

## Variabel lingkungan

| Nama | Fungsi |
|---|---|
| `ADMIN_PASSWORD` | Wajib. Tanpa ini login admin ditolak. Tidak ada di kode. |
| `SECRET_KEY` | Penanda sesi. Jika kosong, acak tiap start (login hilang saat restart). |
| `DB_PATH` | Opsional, lokasi file SQLite (default `pesanan.db`). |
| `PORT` | Opsional, default 5000. |

## Catatan produksi
- Jalankan dengan WSGI server (mis. `waitress`/`gunicorn`) di belakang HTTPS; jangan pakai server bawaan Flask.
- Belum ada pembatasan percobaan login (rate limit) — tambahkan jika dipublikasikan.
- Cadangkan `pesanan.db` berkala.
