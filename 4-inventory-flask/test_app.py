import json
import os
import tempfile
import unittest

_tmp = tempfile.mkdtemp()
os.environ.update(DB_PATH=os.path.join(_tmp, "t.db"), ADMIN_PASSWORD="rahasia-tes", SECRET_KEY="k")
import app as A  # noqa: E402


def sql(q, *a):
    with A.sqlite3.connect(A.app.config["DB_PATH"]) as c:
        c.execute("PRAGMA foreign_keys=ON")
        return c.execute(q, a).fetchall()


class Base(unittest.TestCase):
    def setUp(self):
        sql("DELETE FROM penjualan_item")
        sql("DELETE FROM penjualan")
        sql("DELETE FROM mutasi")
        sql("DELETE FROM produk")
        sql("DELETE FROM pengguna")
        A.FAILS.clear()
        self.c = A.app.test_client()

    def login(self, user="admin", pw="rahasia-tes", client=None):
        c = client or self.c
        c.get("/login")
        with c.session_transaction() as s:
            t = s["csrf"]
        return c.post("/login", data={"username": user, "password": pw, "_csrf": t})

    def post(self, url, client=None, **d):
        c = client or self.c
        c.get("/kasir")  # halaman yang bisa dibuka semua peran; memastikan token CSRF ada
        with c.session_transaction() as s:
            d["_csrf"] = s.get("csrf", "")
        return c.post(url, data=d)

    def tambah(self, sku="A1", stok="10", jual="150"):
        return self.post("/produk/baru", sku=sku, nama="Barang " + sku, kategori="", harga_beli="100",
                         harga_jual=jual, stok=stok, stok_min="3")

    def pid(self, sku="A1"):
        return sql("SELECT id FROM produk WHERE sku=?", sku)[0][0]

    def stok(self, sku="A1"):
        return sql("SELECT stok FROM produk WHERE sku=?", sku)[0][0]

    def buat_kasir(self, user="budi", pw="sandi-kasir-1"):
        self.login()
        self.post("/pengguna/baru", username=user, nama="Budi", password=pw)
        k = A.app.test_client()
        self.login(user, pw, client=k)
        return k

    def jual(self, client, items, metode="tunai", bayar="100000"):
        return self.post("/kasir/bayar", client=client, keranjang=json.dumps(items), metode=metode, bayar=bayar)


class Inventori(Base):
    def test_wajib_login(self):
        self.assertEqual(self.c.get("/").status_code, 302)
        self.assertEqual(self.c.get("/export.csv").status_code, 302)
        self.assertEqual(self.c.get("/kasir").status_code, 302)

    def test_login_salah_dan_benar(self):
        self.login(pw="salah")
        self.assertEqual(self.c.get("/").status_code, 302)
        self.login()
        self.assertEqual(self.c.get("/").status_code, 200)

    def test_csrf_ditolak(self):
        self.assertEqual(self.c.post("/login", data={"username": "admin", "password": "rahasia-tes"}).status_code, 400)

    def test_rate_limit_login(self):
        for _ in range(A.MAX_FAIL):
            self.login(pw="x")
        self.login()  # sandi benar tapi terkunci
        self.assertEqual(self.c.get("/").status_code, 302)

    def test_tambah_dan_sku_ganda(self):
        self.login()
        self.assertEqual(self.tambah().status_code, 302)
        self.assertEqual(self.tambah().status_code, 200)
        self.assertEqual(sql("SELECT COUNT(*) FROM produk")[0][0], 1)

    def test_validasi(self):
        self.login()
        r = self.post("/produk/baru", sku="!", nama="x", harga_beli="-1", harga_jual="abc", stok="1", stok_min="1")
        self.assertEqual(r.status_code, 200)

    def test_mutasi_dan_stok_negatif(self):
        self.login()
        self.tambah()
        pid = self.pid()
        self.post(f"/produk/{pid}/mutasi", tipe="keluar", jumlah="4")
        self.post(f"/produk/{pid}/mutasi", tipe="keluar", jumlah="99")  # ditolak
        self.post(f"/produk/{pid}/mutasi", tipe="masuk", jumlah="5")
        self.assertEqual(self.stok(), 11)
        self.assertEqual(sql("SELECT COUNT(*) FROM mutasi")[0][0], 3)

    def test_hapus_cascade(self):
        self.login()
        self.tambah()
        self.post(f"/produk/{self.pid()}/hapus")
        self.assertEqual(sql("SELECT COUNT(*) FROM mutasi")[0][0], 0)

    def test_xss_dan_csv(self):
        self.login()
        self.post("/produk/baru", sku="X1", nama="<script>alert(1)</script>", kategori="", harga_beli="1",
                  harga_jual="2", stok="1", stok_min="1")
        self.assertNotIn(b"<script>alert(1)</script>", self.c.get("/produk").data)
        self.post("/produk/baru", sku="X2", nama="=CMD()", kategori="", harga_beli="1", harga_jual="2", stok="1", stok_min="1")
        self.assertIn("'=CMD()", self.c.get("/export.csv").get_data(as_text=True))


class Kasir(Base):
    def test_kasir_dibatasi_perannya(self):
        k = self.buat_kasir()
        self.assertEqual(k.get("/kasir").status_code, 200)
        self.assertEqual(k.get("/produk").status_code, 403)
        self.assertEqual(k.get("/laporan").status_code, 403)
        self.assertEqual(k.get("/pengguna").status_code, 403)
        self.assertEqual(k.get("/export.csv").status_code, 403)
        self.assertEqual(k.get("/").status_code, 302)  # diarahkan ke /kasir

    def test_penjualan_mengurangi_stok_dan_mencatat_mutasi(self):
        self.login()
        self.tambah(stok="10", jual="150")
        k = self.buat_kasir()
        r = self.jual(k, [{"id": self.pid(), "qty": 3}], bayar="1000")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.stok(), 7)
        total, kembali, kasir = sql("SELECT total,kembali,kasir FROM penjualan")[0]
        self.assertEqual((total, kembali, kasir), (450, 550, "budi"))
        self.assertIn("Penjualan INV", sql("SELECT catatan FROM mutasi ORDER BY id DESC")[0][0])

    def test_harga_dari_server_bukan_browser(self):
        self.login()
        self.tambah(jual="150")
        k = self.buat_kasir()
        self.jual(k, [{"id": self.pid(), "qty": 2, "harga": 1}], bayar="500")
        self.assertEqual(sql("SELECT total FROM penjualan")[0][0], 300)

    def test_stok_kurang_membatalkan_seluruh_transaksi(self):
        self.login()
        self.tambah("A1", stok="10")
        self.tambah("B1", stok="1")
        k = self.buat_kasir()
        self.jual(k, [{"id": self.pid("A1"), "qty": 2}, {"id": self.pid("B1"), "qty": 5}])
        self.assertEqual(self.stok("A1"), 10)  # A1 tidak ikut berkurang
        self.assertEqual(sql("SELECT COUNT(*) FROM penjualan")[0][0], 0)

    def test_uang_kurang_ditolak(self):
        self.login()
        self.tambah(jual="150")
        k = self.buat_kasir()
        self.jual(k, [{"id": self.pid(), "qty": 2}], bayar="299")
        self.assertEqual(sql("SELECT COUNT(*) FROM penjualan")[0][0], 0)
        self.assertEqual(self.stok(), 10)

    def test_keranjang_tidak_valid(self):
        self.login()
        self.tambah()
        k = self.buat_kasir()
        for bad in ("bukan json", "[]", json.dumps([{"id": self.pid(), "qty": -1}]), json.dumps([{"id": 9999, "qty": 1}])):
            self.post("/kasir/bayar", client=k, keranjang=bad, metode="tunai", bayar="9999")
        self.assertEqual(sql("SELECT COUNT(*) FROM penjualan")[0][0], 0)

    def test_batal_mengembalikan_stok(self):
        self.login()
        self.tambah(stok="10")
        k = self.buat_kasir()
        self.jual(k, [{"id": self.pid(), "qty": 4}])
        sid = sql("SELECT id FROM penjualan")[0][0]
        self.assertEqual(self.post(f"/penjualan/{sid}/batal", client=k).status_code, 403)  # kasir tidak boleh
        self.assertEqual(self.stok(), 6)
        self.post(f"/penjualan/{sid}/batal")
        self.assertEqual(self.stok(), 10)
        self.post(f"/penjualan/{sid}/batal")  # kedua kali tidak menambah lagi
        self.assertEqual(self.stok(), 10)

    def test_kasir_hanya_lihat_struk_sendiri(self):
        self.login()
        self.tambah()
        k1 = self.buat_kasir("budi")
        self.jual(k1, [{"id": self.pid(), "qty": 1}])
        self.login()  # admin
        self.post("/pengguna/baru", username="sari", nama="Sari", password="sandi-kasir-2")
        k2 = A.app.test_client()
        self.login("sari", "sandi-kasir-2", client=k2)
        sid = sql("SELECT id FROM penjualan")[0][0]
        self.assertEqual(k1.get(f"/struk/{sid}").status_code, 200)
        self.assertEqual(k2.get(f"/struk/{sid}").status_code, 404)

    def test_kasir_nonaktif_tidak_bisa_login(self):
        self.buat_kasir()
        uid = sql("SELECT id FROM pengguna")[0][0]
        self.post(f"/pengguna/{uid}/toggle")
        k = A.app.test_client()
        self.login("budi", "sandi-kasir-1", client=k)
        self.assertEqual(k.get("/kasir").status_code, 302)

    def test_sandi_kasir_di_hash(self):
        self.buat_kasir()
        h = sql("SELECT hash FROM pengguna")[0][0]
        self.assertNotIn("sandi-kasir-1", h)

    def test_username_admin_tidak_boleh_dibuat(self):
        self.login()
        self.post("/pengguna/baru", username="admin", nama="X", password="sandi-panjang-1")
        self.assertEqual(sql("SELECT COUNT(*) FROM pengguna")[0][0], 0)


if __name__ == "__main__":
    unittest.main()
