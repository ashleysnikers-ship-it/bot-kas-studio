from flask import Flask, render_template
from database import init_db, ambil_semua_transaksi, hitung_saldo

app = Flask(__name__)

@app.route("/")
def dashboard():
    try:
        transaksi = ambil_semua_transaksi()
        saldo = hitung_saldo()

        data = []
        for t in transaksi:
            data.append({
                "id": t[0],
                "tanggal": t[1],
                "kategori": t[2],
                "keterangan": t[3],
                "nominal": t[4],
                "timestamp": t[5]
            })

        return render_template("dashboard.html",
            saldo=saldo["saldo"],
            masuk=saldo["masuk"],
            keluar=saldo["keluar"],
            data=data
        )
    except Exception as e:
        return render_template("dashboard.html",
            saldo=0, masuk=0, keluar=0, data=[]
        )

if __name__ == "__main__":
    init_db()
    app.run(debug=False, port=5000, use_reloader=False)