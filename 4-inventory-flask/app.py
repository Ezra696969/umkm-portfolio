"""Contoh sistem inventori UMKM (fiktif) — Flask + SQLite.

Env: ADMIN_PASSWORD (wajib), SECRET_KEY (disarankan), DB_PATH (opsional), PORT (opsional).
"""
import csv
import hmac
import io
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
EMBED = os.environ.get("EMBED_DEMO") == "1"  # demo di dalam iframe situs portofolio (lintas-situs) butuh SameSite=None + HTTPS
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="None" if EMBED else "Lax", SESSION_COOKIE_SECURE=EMBED,
                  SESSION_COOKIE_NAME=os.environ.get("SESSION_COOKIE_NAME", "session"))  # nama unik bila beberapa app dalam satu domain
app.config["DB_PATH"] = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "inventori.db"))

TIPE = {"masuk": "Barang masuk", "keluar": "Barang keluar", "koreksi": "Koreksi (set stok)"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS produk(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT NOT NULL UNIQUE, nama TEXT NOT NULL, kategori TEXT NOT NULL DEFAULT 'Umum',
  harga_beli INTEGER NOT NULL CHECK(harga_beli>=0), harga_jual INTEGER NOT NULL CHECK(harga_jual>=0),
  stok INTEGER NOT NULL DEFAULT 0 CHECK(stok>=0), stok_min INTEGER NOT NULL DEFAULT 5 CHECK(stok_min>=0),
  dibuat TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mutasi(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  produk_id INTEGER NOT NULL REFERENCES produk(id) ON DELETE CASCADE,
  tipe TEXT NOT NULL CHECK(tipe IN ('masuk','keluar','koreksi')),
  jumlah INTEGER NOT NULL, stok_akhir INTEGER NOT NULL, catatan TEXT, waktu TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_mutasi_produk ON mutasi(produk_id, id DESC);
CREATE TABLE IF NOT EXISTS pengguna(
  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, nama TEXT NOT NULL,
  hash TEXT NOT NULL, aktif INTEGER NOT NULL DEFAULT 1, dibuat TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS penjualan(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kode TEXT NOT NULL UNIQUE, waktu TEXT NOT NULL,
  kasir TEXT NOT NULL, metode TEXT NOT NULL CHECK(metode IN ('tunai','qris','transfer')),
  total INTEGER NOT NULL, bayar INTEGER NOT NULL, kembali INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'selesai' CHECK(status IN ('selesai','batal')), dibatalkan_oleh TEXT);
CREATE INDEX IF NOT EXISTS ix_penjualan_waktu ON penjualan(waktu);
CREATE TABLE IF NOT EXISTS penjualan_item(
  id INTEGER PRIMARY KEY AUTOINCREMENT, penjualan_id INTEGER NOT NULL REFERENCES penjualan(id) ON DELETE CASCADE,
  produk_id INTEGER REFERENCES produk(id) ON DELETE SET NULL,
  sku TEXT NOT NULL, nama TEXT NOT NULL, qty INTEGER NOT NULL CHECK(qty>0),
  harga INTEGER NOT NULL, harga_beli INTEGER NOT NULL);
"""
METODE = {"tunai": "Tunai", "qris": "QRIS", "transfer": "Transfer"}


def db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    c = g.pop("db", None)
    if c:
        c.close()


def init_db():
    with sqlite3.connect(app.config["DB_PATH"]) as c:
        c.executescript(SCHEMA)


def now():
    return datetime.now().isoformat(timespec="seconds")


def csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals.update(csrf=csrf, TIPE=TIPE, METODE=METODE)
app.jinja_env.filters["rp"] = lambda n: "Rp" + f"{int(n):,}".replace(",", ".")
app.jinja_env.filters["tgl"] = lambda s: s.replace("T", " ")[:16]


ADMIN_ONLY = {"dashboard", "produk_list", "produk_baru", "produk_edit", "produk_detail", "produk_hapus",
              "mutasi", "riwayat", "export", "laporan", "batal_penjualan",
              "pengguna", "pengguna_baru", "pengguna_toggle", "pengguna_reset"}


@app.before_request
def guard():
    if request.method == "POST" and not hmac.compare_digest(
            request.form.get("_csrf", ""), session.get("csrf", "x")):
        abort(400, "Token form tidak valid, muat ulang halaman.")
    ep = request.endpoint
    if ep in (None, "login", "static"):
        return
    role = session.get("role")
    if not role:
        return redirect(url_for("login"))
    if ep in ADMIN_ONLY and role != "admin":
        if ep == "dashboard":
            return redirect(url_for("kasir"))
        abort(403)


# ---------- login (dengan pembatasan percobaan) ----------
FAILS = {}  # ip -> [timestamps]
MAX_FAIL, WINDOW = 5, 300


def locked(ip):
    FAILS[ip] = [t for t in FAILS.get(ip, []) if time.time() - t < WINDOW]
    return len(FAILS[ip]) >= MAX_FAIL


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("role"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        ip = request.remote_addr
        user = request.form.get("username", "").strip().lower()
        pw = request.form.get("password", "")
        if locked(ip):
            flash("Terlalu banyak percobaan. Coba lagi dalam 5 menit.", "err")
            return render_template("login.html")
        role = nama = None
        if user == "admin":  # sandi admin hanya dari variabel lingkungan, tidak disimpan
            env = os.environ.get("ADMIN_PASSWORD", "")
            if not env:
                flash("ADMIN_PASSWORD belum diatur di server.", "err")
                return render_template("login.html")
            if hmac.compare_digest(pw, env):
                role, nama = "admin", "Admin"
        else:
            row = db().execute("SELECT * FROM pengguna WHERE username=? AND aktif=1", (user,)).fetchone()
            if row and check_password_hash(row["hash"], pw):
                role, nama = "kasir", row["nama"]
        if role:
            session.clear()
            session.update(user=user, role=role, nama=nama)
            FAILS.pop(ip, None)
            return redirect(url_for("dashboard"))
        FAILS.setdefault(ip, []).append(time.time())
        flash("Username atau kata sandi salah.", "err")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- dashboard ----------
@app.get("/")
def dashboard():
    d = db()
    ring = d.execute("""SELECT COUNT(*) n, COALESCE(SUM(stok),0) unit,
        COALESCE(SUM(stok*harga_beli),0) nilai, COALESCE(SUM(stok<=stok_min),0) rendah,
        COALESCE(SUM(stok=0),0) habis FROM produk""").fetchone()
    low = d.execute("SELECT * FROM produk WHERE stok<=stok_min ORDER BY stok-stok_min, nama LIMIT 8").fetchall()
    recent = d.execute("""SELECT m.*, p.nama, p.sku FROM mutasi m JOIN produk p ON p.id=m.produk_id
        ORDER BY m.id DESC LIMIT 8""").fetchall()
    kat = d.execute("SELECT kategori, SUM(stok*harga_beli) nilai FROM produk GROUP BY kategori ORDER BY nilai DESC").fetchall()
    hari = d.execute("""SELECT COUNT(*) n, COALESCE(SUM(total),0) omzet FROM penjualan
        WHERE status='selesai' AND substr(waktu,1,10)=?""", (now()[:10],)).fetchone()
    return render_template("dashboard.html", r=ring, low=low, recent=recent, kat=kat, hari=hari)


# ---------- produk ----------
def parse_produk(f, pid=None):
    v = {k: f.get(k, "").strip() for k in ("sku", "nama", "kategori", "harga_beli", "harga_jual", "stok_min", "stok")}
    err = []
    v["sku"] = v["sku"].upper()
    if not (2 <= len(v["sku"]) <= 30) or not all(c.isalnum() or c in "-_" for c in v["sku"]):
        err.append("SKU 2–30 karakter (huruf/angka/-/_).")
    if not (2 <= len(v["nama"]) <= 100):
        err.append("Nama 2–100 karakter.")
    if not (1 <= len(v["kategori"] or "Umum") <= 40):
        err.append("Kategori maksimal 40 karakter.")
    v["kategori"] = v["kategori"] or "Umum"
    for k, lab, mx in (("harga_beli", "Harga beli", 10**9), ("harga_jual", "Harga jual", 10**9),
                       ("stok_min", "Stok minimum", 10**6)) + ((("stok", "Stok awal", 10**6),) if pid is None else ()):
        try:
            n = int(v[k] or 0)
            if not 0 <= n <= mx:
                raise ValueError
            v[k] = n
        except ValueError:
            err.append(f"{lab} harus angka 0–{mx}.")
    return v, err


@app.get("/produk")
def produk_list():
    q = request.args.get("q", "").strip()
    kat = request.args.get("kat", "")
    low = request.args.get("low") == "1"
    sql, args = "SELECT * FROM produk WHERE 1=1", []
    if q:
        sql += " AND (nama LIKE ? ESCAPE '\\' OR sku LIKE ? ESCAPE '\\')"
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        args += [like, like]
    if kat:
        sql += " AND kategori=?"
        args.append(kat)
    if low:
        sql += " AND stok<=stok_min"
    rows = db().execute(sql + " ORDER BY nama", args).fetchall()
    kats = [r[0] for r in db().execute("SELECT DISTINCT kategori FROM produk ORDER BY 1")]
    return render_template("produk_list.html", rows=rows, kats=kats, q=q, kat=kat, low=low)


@app.route("/produk/baru", methods=["GET", "POST"])
def produk_baru():
    v, err = {}, []
    if request.method == "POST":
        v, err = parse_produk(request.form)
        if not err:
            try:
                d = db()
                cur = d.execute("INSERT INTO produk(sku,nama,kategori,harga_beli,harga_jual,stok,stok_min,dibuat)"
                                " VALUES(?,?,?,?,?,?,?,?)",
                                (v["sku"], v["nama"], v["kategori"], v["harga_beli"], v["harga_jual"], v["stok"], v["stok_min"], now()))
                if v["stok"]:
                    d.execute("INSERT INTO mutasi(produk_id,tipe,jumlah,stok_akhir,catatan,waktu) VALUES(?,?,?,?,?,?)",
                              (cur.lastrowid, "masuk", v["stok"], v["stok"], "Stok awal", now()))
                d.commit()
                flash("Produk ditambahkan.", "ok")
                return redirect(url_for("produk_detail", pid=cur.lastrowid))
            except sqlite3.IntegrityError:
                err.append("SKU sudah dipakai.")
        for e in err:
            flash(e, "err")
    return render_template("produk_form.html", v=v, edit=False)


def get_produk(pid):
    p = db().execute("SELECT * FROM produk WHERE id=?", (pid,)).fetchone()
    if not p:
        abort(404)
    return p


@app.route("/produk/<int:pid>/edit", methods=["GET", "POST"])
def produk_edit(pid):
    p = get_produk(pid)
    v = dict(p)
    if request.method == "POST":
        v, err = parse_produk(request.form, pid)
        if not err:
            try:
                db().execute("UPDATE produk SET sku=?,nama=?,kategori=?,harga_beli=?,harga_jual=?,stok_min=? WHERE id=?",
                             (v["sku"], v["nama"], v["kategori"], v["harga_beli"], v["harga_jual"], v["stok_min"], pid))
                db().commit()
                flash("Perubahan disimpan.", "ok")
                return redirect(url_for("produk_detail", pid=pid))
            except sqlite3.IntegrityError:
                err.append("SKU sudah dipakai.")
        for e in err:
            flash(e, "err")
    return render_template("produk_form.html", v=v, edit=True, pid=pid)


@app.get("/produk/<int:pid>")
def produk_detail(pid):
    p = get_produk(pid)
    riwayat = db().execute("SELECT * FROM mutasi WHERE produk_id=? ORDER BY id DESC LIMIT 50", (pid,)).fetchall()
    return render_template("produk_detail.html", p=p, riwayat=riwayat)


@app.post("/produk/<int:pid>/hapus")
def produk_hapus(pid):
    p = get_produk(pid)
    db().execute("DELETE FROM produk WHERE id=?", (pid,))
    db().commit()
    flash(f"Produk {p['nama']} dihapus beserta riwayatnya.", "ok")
    return redirect(url_for("produk_list"))


# ---------- mutasi stok (atomik) ----------
@app.post("/produk/<int:pid>/mutasi")
def mutasi(pid):
    tipe = request.form.get("tipe", "")
    catatan = request.form.get("catatan", "").strip()[:200]
    try:
        jml = int(request.form.get("jumlah", ""))
        if not (0 <= jml <= 10**6) or (tipe != "koreksi" and jml < 1):
            raise ValueError
    except ValueError:
        flash("Jumlah tidak valid.", "err")
        return redirect(url_for("produk_detail", pid=pid))
    if tipe not in TIPE:
        abort(400)
    d = db()
    d.execute("BEGIN IMMEDIATE")  # kunci tulis: cegah dua kasir mengubah stok bersamaan
    try:
        p = d.execute("SELECT stok FROM produk WHERE id=?", (pid,)).fetchone()
        if not p:
            d.rollback()
            abort(404)
        akhir = {"masuk": p["stok"] + jml, "keluar": p["stok"] - jml, "koreksi": jml}[tipe]
        if akhir < 0:
            d.rollback()
            flash(f"Stok tidak cukup (tersedia {p['stok']}).", "err")
            return redirect(url_for("produk_detail", pid=pid))
        d.execute("UPDATE produk SET stok=? WHERE id=?", (akhir, pid))
        d.execute("INSERT INTO mutasi(produk_id,tipe,jumlah,stok_akhir,catatan,waktu) VALUES(?,?,?,?,?,?)",
                  (pid, tipe, jml, akhir, catatan, now()))
        d.commit()
    except sqlite3.Error:
        d.rollback()
        raise
    flash(f"Stok sekarang {akhir}.", "ok")
    return redirect(url_for("produk_detail", pid=pid))


@app.get("/riwayat")
def riwayat():
    rows = db().execute("""SELECT m.*, p.nama, p.sku FROM mutasi m JOIN produk p ON p.id=m.produk_id
        ORDER BY m.id DESC LIMIT 200""").fetchall()
    return render_template("riwayat.html", rows=rows)


@app.get("/export.csv")
def export():
    rows = db().execute("SELECT sku,nama,kategori,harga_beli,harga_jual,stok,stok_min FROM produk ORDER BY nama").fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["sku", "nama", "kategori", "harga_beli", "harga_jual", "stok", "stok_min"])
    for r in rows:
        w.writerow(["'" + c if isinstance(c, str) and c and c[0] in "=+-@" else c for c in tuple(r)])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=inventori.csv"})


# ---------- kasir (POS) ----------
class Gagal(Exception):
    pass


@app.get("/kasir")
def kasir():
    prods = db().execute("SELECT id,sku,nama,kategori,harga_jual,stok FROM produk ORDER BY nama").fetchall()
    return render_template("kasir.html", prods=[dict(p) for p in prods])


def baca_keranjang(raw):
    try:
        data = json.loads(raw)
        gabung = {}
        for it in data:
            pid, qty = int(it["id"]), int(it["qty"])
            if not 1 <= qty <= 10_000:
                raise ValueError
            gabung[pid] = gabung.get(pid, 0) + qty
        if not 1 <= len(gabung) <= 100:
            raise ValueError
        return gabung
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise Gagal("Keranjang tidak valid.")


@app.post("/kasir/bayar")
def bayar():
    d = db()
    try:
        keranjang = baca_keranjang(request.form.get("keranjang", ""))
        metode = request.form.get("metode", "")
        if metode not in METODE:
            raise Gagal("Metode pembayaran tidak valid.")
        try:
            uang = int(request.form.get("bayar") or 0)
        except ValueError:
            raise Gagal("Jumlah bayar tidak valid.")
        d.execute("BEGIN IMMEDIATE")  # kunci tulis: stok dicek & dikurangi dalam satu langkah
        try:
            baris, total = [], 0
            for pid, qty in keranjang.items():  # harga SELALU dari database, bukan dari browser
                p = d.execute("SELECT * FROM produk WHERE id=?", (pid,)).fetchone()
                if not p:
                    raise Gagal("Ada produk yang sudah tidak tersedia.")
                if p["stok"] < qty:
                    raise Gagal(f"Stok {p['nama']} tidak cukup (tersedia {p['stok']}).")
                baris.append((p, qty))
                total += p["harga_jual"] * qty
            if metode == "tunai":
                if uang < total:
                    raise Gagal(f"Uang kurang {total - uang:,}".replace(",", "."))
                kembali = uang - total
            else:
                uang, kembali = total, 0
            tgl = now()
            seq = d.execute("SELECT COUNT(*) FROM penjualan WHERE substr(waktu,1,10)=?", (tgl[:10],)).fetchone()[0] + 1
            kode = f"INV{tgl[:10].replace('-', '')}-{seq:04d}"
            sid = d.execute("INSERT INTO penjualan(kode,waktu,kasir,metode,total,bayar,kembali) VALUES(?,?,?,?,?,?,?)",
                            (kode, tgl, session["user"], metode, total, uang, kembali)).lastrowid
            for p, qty in baris:
                akhir = p["stok"] - qty
                d.execute("INSERT INTO penjualan_item(penjualan_id,produk_id,sku,nama,qty,harga,harga_beli) VALUES(?,?,?,?,?,?,?)",
                          (sid, p["id"], p["sku"], p["nama"], qty, p["harga_jual"], p["harga_beli"]))
                d.execute("UPDATE produk SET stok=? WHERE id=?", (akhir, p["id"]))
                d.execute("INSERT INTO mutasi(produk_id,tipe,jumlah,stok_akhir,catatan,waktu) VALUES(?,?,?,?,?,?)",
                          (p["id"], "keluar", qty, akhir, f"Penjualan {kode} ({session['user']})", tgl))
            d.commit()
        except BaseException:
            d.rollback()
            raise
    except Gagal as e:
        flash(str(e), "err")
        return redirect(url_for("kasir"))
    return redirect(url_for("struk", sid=sid))


def get_penjualan(sid):
    s = db().execute("SELECT * FROM penjualan WHERE id=?", (sid,)).fetchone()
    if not s or (session["role"] != "admin" and s["kasir"] != session["user"]):
        abort(404)
    return s


@app.get("/struk/<int:sid>")
def struk(sid):
    s = get_penjualan(sid)
    items = db().execute("SELECT * FROM penjualan_item WHERE penjualan_id=?", (sid,)).fetchall()
    return render_template("struk.html", s=s, items=items)


@app.get("/kasir/riwayat")
def kasir_riwayat():
    admin = session["role"] == "admin"
    cond, args = "substr(waktu,1,10)=?", [now()[:10]]
    if not admin:
        cond += " AND kasir=?"
        args.append(session["user"])
    rows = db().execute(f"SELECT * FROM penjualan WHERE {cond} ORDER BY id DESC", args).fetchall()
    ok = [r for r in rows if r["status"] == "selesai"]
    per = {m: sum(r["total"] for r in ok if r["metode"] == m) for m in METODE}
    return render_template("kasir_riwayat.html", rows=rows, n=len(ok), total=sum(per.values()), per=per)


# ---------- laporan penjualan & pembatalan (admin) ----------
@app.get("/laporan")
def laporan():
    today = datetime.now().date()
    sampai = request.args.get("sampai") or today.isoformat()
    dari = request.args.get("dari") or (today - timedelta(days=29)).isoformat()
    try:
        datetime.strptime(dari, "%Y-%m-%d"), datetime.strptime(sampai, "%Y-%m-%d")
    except ValueError:
        flash("Format tanggal tidak valid.", "err")
        dari, sampai = (today - timedelta(days=29)).isoformat(), today.isoformat()
    d, rng = db(), (dari, sampai)
    w = "status='selesai' AND substr(waktu,1,10) BETWEEN ? AND ?"
    ring = d.execute(f"SELECT COUNT(*) n, COALESCE(SUM(total),0) omzet FROM penjualan WHERE {w}", rng).fetchone()
    laba = d.execute("""SELECT COALESCE(SUM(i.qty*(i.harga-i.harga_beli)),0) FROM penjualan_item i
        JOIN penjualan s ON s.id=i.penjualan_id WHERE s.status='selesai' AND substr(s.waktu,1,10) BETWEEN ? AND ?""", rng).fetchone()[0]
    harian = d.execute(f"SELECT substr(waktu,1,10) tgl, COUNT(*) n, SUM(total) omzet FROM penjualan WHERE {w} GROUP BY tgl ORDER BY tgl DESC", rng).fetchall()
    per_kasir = d.execute(f"SELECT kasir, COUNT(*) n, SUM(total) omzet FROM penjualan WHERE {w} GROUP BY kasir ORDER BY omzet DESC", rng).fetchall()
    laris = d.execute(f"""SELECT i.nama, SUM(i.qty) qty, SUM(i.qty*i.harga) omzet FROM penjualan_item i
        JOIN penjualan s ON s.id=i.penjualan_id WHERE s.status='selesai' AND substr(s.waktu,1,10) BETWEEN ? AND ?
        GROUP BY i.sku ORDER BY qty DESC LIMIT 8""", rng).fetchall()
    trx = d.execute("SELECT * FROM penjualan WHERE substr(waktu,1,10) BETWEEN ? AND ? ORDER BY id DESC LIMIT 100", rng).fetchall()
    return render_template("laporan.html", dari=dari, sampai=sampai, r=ring, laba=laba, harian=harian,
                           per_kasir=per_kasir, laris=laris, trx=trx)


@app.post("/penjualan/<int:sid>/batal")
def batal_penjualan(sid):
    d = db()
    d.execute("BEGIN IMMEDIATE")
    try:
        s = d.execute("SELECT * FROM penjualan WHERE id=?", (sid,)).fetchone()
        if not s:
            d.rollback()
            abort(404)
        if s["status"] == "batal":
            d.rollback()
            flash("Transaksi sudah dibatalkan.", "err")
            return redirect(request.referrer or url_for("laporan"))
        tgl = now()
        for it in d.execute("SELECT * FROM penjualan_item WHERE penjualan_id=?", (sid,)).fetchall():
            if it["produk_id"] is None:  # produk sudah dihapus dari katalog
                continue
            akhir = d.execute("SELECT stok FROM produk WHERE id=?", (it["produk_id"],)).fetchone()["stok"] + it["qty"]
            d.execute("UPDATE produk SET stok=? WHERE id=?", (akhir, it["produk_id"]))
            d.execute("INSERT INTO mutasi(produk_id,tipe,jumlah,stok_akhir,catatan,waktu) VALUES(?,?,?,?,?,?)",
                      (it["produk_id"], "masuk", it["qty"], akhir, f"Batal {s['kode']}", tgl))
        d.execute("UPDATE penjualan SET status='batal', dibatalkan_oleh=? WHERE id=?", (session["user"], sid))
        d.commit()
    except BaseException:
        d.rollback()
        raise
    flash(f"{s['kode']} dibatalkan, stok dikembalikan.", "ok")
    return redirect(request.referrer or url_for("laporan"))


# ---------- manajemen pegawai (admin) ----------
@app.get("/pengguna")
def pengguna():
    rows = db().execute("""SELECT u.*, (SELECT COUNT(*) FROM penjualan s WHERE s.kasir=u.username) trx
        FROM pengguna u ORDER BY u.aktif DESC, u.nama""").fetchall()
    return render_template("pengguna.html", rows=rows)


def sandi_valid(pw):
    return 8 <= len(pw) <= 100


@app.post("/pengguna/baru")
def pengguna_baru():
    u = request.form.get("username", "").strip().lower()
    nama = request.form.get("nama", "").strip()
    pw = request.form.get("password", "")
    if not (3 <= len(u) <= 20 and u.replace("_", "").isalnum() and u.isascii()) or u == "admin":
        flash("Username 3–20 karakter huruf/angka/_ (bukan 'admin').", "err")
    elif not (2 <= len(nama) <= 60):
        flash("Nama 2–60 karakter.", "err")
    elif not sandi_valid(pw):
        flash("Kata sandi minimal 8 karakter.", "err")
    else:
        try:
            db().execute("INSERT INTO pengguna(username,nama,hash,dibuat) VALUES(?,?,?,?)",
                         (u, nama, generate_password_hash(pw), now()))
            db().commit()
            flash(f"Akun kasir {u} dibuat.", "ok")
        except sqlite3.IntegrityError:
            flash("Username sudah dipakai.", "err")
    return redirect(url_for("pengguna"))


@app.post("/pengguna/<int:uid>/toggle")
def pengguna_toggle(uid):
    db().execute("UPDATE pengguna SET aktif=1-aktif WHERE id=?", (uid,))
    db().commit()
    return redirect(url_for("pengguna"))


@app.post("/pengguna/<int:uid>/reset")
def pengguna_reset(uid):
    pw = request.form.get("password", "")
    if not sandi_valid(pw):
        flash("Kata sandi minimal 8 karakter.", "err")
    else:
        db().execute("UPDATE pengguna SET hash=? WHERE id=?", (generate_password_hash(pw), uid))
        db().commit()
        flash("Kata sandi diganti.", "ok")
    return redirect(url_for("pengguna"))


# ---------- data demo ----------
DEMO_PRODUK = [  # sku, nama, kategori, beli, jual, stok, min
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


def seed_demo(reset=False):
    """Isi data contoh. reset=True menghapus semua data dulu. Return False bila DB tidak kosong."""
    with sqlite3.connect(app.config["DB_PATH"]) as c:
        c.execute("PRAGMA foreign_keys=ON")
        if reset:
            c.executescript("DELETE FROM penjualan_item; DELETE FROM penjualan; DELETE FROM mutasi; DELETE FROM produk; DELETE FROM pengguna;")
        if c.execute("SELECT COUNT(*) FROM produk").fetchone()[0]:
            return False
        for sku, nama, kat, beli, jual, stok, mn in DEMO_PRODUK:
            cur = c.execute("INSERT INTO produk(sku,nama,kategori,harga_beli,harga_jual,stok,stok_min,dibuat) VALUES(?,?,?,?,?,?,?,?)",
                            (sku, nama, kat, beli, jual, stok, mn, now()))
            if stok:
                c.execute("INSERT INTO mutasi(produk_id,tipe,jumlah,stok_akhir,catatan,waktu) VALUES(?,?,?,?,?,?)",
                          (cur.lastrowid, "masuk", stok, stok, "Stok awal (demo)", now()))
        kp = os.environ.get("DEMO_KASIR_PASSWORD")
        if kp:  # akun kasir demo, sandi dari variabel lingkungan
            c.execute("INSERT OR IGNORE INTO pengguna(username,nama,hash,dibuat) VALUES(?,?,?,?)",
                      ("kasir", "Kasir Demo", generate_password_hash(kp), now()))
    return True


init_db()
# Mode demo publik: data direset & diisi ulang tiap server start; login page menampilkan DEMO_HINT.
DEMO = os.environ.get("DEMO_MODE") == "1"
if DEMO:
    seed_demo(reset=True)
app.jinja_env.globals["DEMO_HINT"] = os.environ.get("DEMO_HINT", "") if DEMO else ""

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
