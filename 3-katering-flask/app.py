"""Contoh website katering UMKM (fiktif) — Flask + SQLite.

Variabel lingkungan:
  ADMIN_PASSWORD  (wajib untuk login admin)
  SECRET_KEY      (disarankan; jika kosong dibuat acak tiap start, sesi login hilang saat restart)
  DB_PATH         (opsional, default pesanan.db)
"""
import csv
import hmac
import io
import os
import secrets
import sqlite3
from datetime import datetime

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "pesanan.db"))

PRODUK = {  # kode: (nama, harga, deskripsi, emoji)
    "nasi-box": ("Nasi Box Ayam Bakar", 25000, "Nasi, ayam bakar, lalap, sambal, buah", "🍱"),
    "tumpeng": ("Tumpeng Mini (5 org)", 175000, "Nasi kuning, urap, ayam, telur, perkedel", "🍚"),
    "snack": ("Snack Box", 15000, "3 kue basah + air mineral", "🥮"),
    "prasmanan": ("Paket Prasmanan (/org)", 45000, "5 lauk, 2 sayur, kerupuk, es buah", "🍛"),
}
STATUS = ["baru", "diproses", "selesai", "batal"]
MIN_QTY, MAX_QTY = 1, 1000


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS pesanan(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dibuat TEXT NOT NULL, nama TEXT NOT NULL, wa TEXT NOT NULL,
            produk TEXT NOT NULL, jumlah INTEGER NOT NULL, total INTEGER NOT NULL,
            tanggal TEXT NOT NULL, alamat TEXT NOT NULL, catatan TEXT,
            status TEXT NOT NULL DEFAULT 'baru')""")


def csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf"] = csrf
app.jinja_env.filters["rp"] = lambda n: "Rp" + f"{int(n):,}".replace(",", ".")


@app.before_request
def check_csrf():
    if request.method == "POST":
        if not hmac.compare_digest(request.form.get("_csrf", ""), session.get("csrf", "x")):
            abort(400, "Token form tidak valid, muat ulang halaman.")


@app.get("/")
def index():
    return render_template("index.html", produk=PRODUK, form={})


@app.post("/pesan")
def pesan():
    f = {k: request.form.get(k, "").strip() for k in
         ("nama", "wa", "produk", "jumlah", "tanggal", "alamat", "catatan")}
    err = []
    if not (2 <= len(f["nama"]) <= 80):
        err.append("Nama 2–80 karakter.")
    wa = "".join(ch for ch in f["wa"] if ch.isdigit())
    if not (9 <= len(wa) <= 15):
        err.append("Nomor WhatsApp tidak valid.")
    if f["produk"] not in PRODUK:
        err.append("Pilih produk.")
    try:
        qty = int(f["jumlah"])
        if not MIN_QTY <= qty <= MAX_QTY:
            raise ValueError
    except ValueError:
        qty = 0
        err.append(f"Jumlah {MIN_QTY}–{MAX_QTY}.")
    try:
        if datetime.strptime(f["tanggal"], "%Y-%m-%d").date() < datetime.now().date():
            err.append("Tanggal tidak boleh di masa lalu.")
    except ValueError:
        err.append("Tanggal tidak valid.")
    if not (5 <= len(f["alamat"]) <= 300):
        err.append("Alamat 5–300 karakter.")
    if len(f["catatan"]) > 500:
        err.append("Catatan maksimal 500 karakter.")
    if err:
        for e in err:
            flash(e, "err")
        return render_template("index.html", produk=PRODUK, form=f), 400
    total = PRODUK[f["produk"]][1] * qty
    cur = db().execute(
        "INSERT INTO pesanan(dibuat,nama,wa,produk,jumlah,total,tanggal,alamat,catatan)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), f["nama"], wa, f["produk"], qty,
         total, f["tanggal"], f["alamat"], f["catatan"]))
    db().commit()
    return redirect(url_for("terima_kasih", pid=cur.lastrowid))


@app.get("/terima-kasih/<int:pid>")
def terima_kasih(pid):
    row = db().execute("SELECT id,nama,produk,jumlah,total,tanggal FROM pesanan WHERE id=?", (pid,)).fetchone()
    if not row:
        abort(404)
    return render_template("terima_kasih.html", p=row, produk=PRODUK)


# ---------- admin ----------
def need_admin():
    if not session.get("admin"):
        return redirect(url_for("login"))


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    pw = os.environ.get("ADMIN_PASSWORD", "")
    if request.method == "POST":
        if not pw:
            flash("ADMIN_PASSWORD belum diatur di server.", "err")
        elif hmac.compare_digest(request.form.get("password", ""), pw):
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin"))
        else:
            flash("Kata sandi salah.", "err")
    return render_template("login.html")


@app.post("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.get("/admin")
def admin():
    if (r := need_admin()):
        return r
    st = request.args.get("status", "")
    q = "SELECT * FROM pesanan" + (" WHERE status=?" if st in STATUS else "") + " ORDER BY id DESC"
    rows = db().execute(q, (st,) if st in STATUS else ()).fetchall()
    omzet = sum(r["total"] for r in rows if r["status"] != "batal")
    return render_template("admin.html", rows=rows, produk=PRODUK, status=STATUS, st=st, omzet=omzet)


@app.post("/admin/status/<int:pid>")
def set_status(pid):
    if (r := need_admin()):
        return r
    s = request.form.get("status")
    if s in STATUS:
        db().execute("UPDATE pesanan SET status=? WHERE id=?", (s, pid))
        db().commit()
    return redirect(request.referrer or url_for("admin"))


@app.get("/admin/export.csv")
def export():
    if (r := need_admin()):
        return r
    out = io.StringIO()
    w = csv.writer(out)
    rows = db().execute("SELECT * FROM pesanan ORDER BY id").fetchall()
    w.writerow(rows[0].keys() if rows else ["kosong"])
    for r_ in rows:  # awali sel berbahaya agar aman dibuka di Excel
        w.writerow(["'" + str(v) if isinstance(v, str) and v and v[0] in "=+-@" else v for v in tuple(r_)])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=pesanan.csv"})


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
