from flask import (
    Flask,
    request,
    render_template,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    send_from_directory,
)
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import time
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
import random
import string
import os
import re
import locale
import smtplib
import urllib.parse
import webbrowser
from flask_mail import Mail, Message
import jwt

import midtransclient

import logging # Tambahkan di bagian atas file Python Anda
import uuid # Tambahkan import uuid
import random # random untuk gambar galeri di beranda user

from dateutil.relativedelta import relativedelta
import json

# Koneksi ke database MongoDB
connection_string = "mongodb+srv://test:sparta@cluster0.9kunvma.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(connection_string)
db = client.dbfotografi
users_collection = db.users
reviews_collection = db.reviews 

app = Flask(__name__)
app.secret_key = "super-secret-key"


# Konfigurasi logging dasar jika belum ada
logging.basicConfig(level=logging.DEBUG)




# -- Tambahan untuk bagian login, daftar, dkk ---
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "DANANDA34")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "KILLING23")
app.config["PASSWORD_RESET_TIMEOUT_MINUTES"] = 30  # Token valid for 30 minutes

# Konfigurasi Upload File
DEFAULT_GCS_PROFILE_PIC_URL = (
    "https://storage.googleapis.com/a1aa/image/10b4ac45-2b8b-450f-888c-bd7182757e8a.jpg"
)

# --- PERUBAHAN DI SINI ---
UPLOAD_FOLDER = "gambar_profil_user"  # Sesuai dengan folder Anda
# --- AKHIR PERUBAHAN ---
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
#app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # Maks 16MB untuk upload

# --- Flask-Mail Configuration ---
app.config["MAIL_SERVER"] = "smtp.gmail.com"  # Contoh: untuk Gmail
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get(
    "EMAIL_USER", "ovalphotoo@gmail.com"
)  # Email pengirim
app.config["MAIL_PASSWORD"] = os.environ.get(
    "EMAIL_PASS", "cvmo ujrb jjpp rsip"
)  # Password email pengirim atau App Password
app.config["MAIL_DEFAULT_SENDER"] = "ovalphotoo@gmail.com"  # Email default pengirim

mail = Mail(app)  # Inisialisasi Flask-Mail


# --- Helper Functions ---
def is_valid_email(email):
    """Simple email validation."""
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


def allowed_file(filename):
    """Checks if the uploaded file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS



#Terikat Login
def login_required(f):
    """Decorator to protect routes that require user login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "message": "Anda harus login untuk mengakses ini."}), 401
            flash("Anda harus login untuk mengakses halaman ini.", "danger")
            return redirect(url_for('masuk'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(allowed_roles):
    """Decorator to protect routes based on user role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Tentukan URL login default berdasarkan peran yang diizinkan untuk dashboard ini
            login_url_for_role = url_for('masuk') # Default ke login user
            if 'admin' in allowed_roles:
                login_url_for_role = url_for('admin_login')
            elif 'pemilik' in allowed_roles:
                login_url_for_role = url_for('pemilik_login_page')

            # --- PERBAIKAN DI SINI ---
            # Jika user_id tidak ada di session, redirect ke halaman login yang relevan
            if 'user_id' not in session:
                flash("Anda harus login untuk mengakses halaman ini.", "danger")
                return redirect(login_url_for_role) # <--- DIUBAH KE login_url_for_role
            # --- AKHIR PERBAIKAN ---

            user = users_collection.find_one({"_id": ObjectId(session['user_id'])})
            if not user or user.get('role') not in allowed_roles:
                flash("Anda tidak memiliki izin untuk mengakses halaman ini.", "danger")
                # Redirect ke halaman login yang relevan jika tidak berizin
                # Ini sudah benar, karena sudah disesuaikan di atas
                return redirect(login_url_for_role) 
            return f(*args, **kwargs)
        return decorated_function
    return decorator







# Function to mask full name
def mask_name(full_name):
    if not full_name:
        return ""
    parts = full_name.split()
    masked_parts = []
    for part in parts:
        if len(part) <= 2:
            masked_parts.append("*" * len(part))
        else:
            masked_parts.append(part[0] + "*" * (len(part) - 2) + part[-1])
    return " ".join(masked_parts)


# Function to format date to Indonesian locale
@app.template_filter('tanggal_id') # Make this a Jinja2 filter as well
def tanggal_id(date_obj):
    if not date_obj:
        return "N/A"
    try:
        locale.setlocale(locale.LC_TIME, 'id_ID.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'id_ID')
        except locale.Error:
            print("Warning: Could not set locale to id_ID. Dates might not be in Indonesian.")
            pass
    return date_obj.strftime("%d %B %Y")








# Route untuk halaman user
@app.route('/')
def beranda():
    try:
        # --- Bagian Layanan & Galeri (tidak ada perubahan) ---
        layanan_data = list(db.layanan.find({'status': True}))
        if not layanan_data:
            print("PERINGATAN: Tidak ada data layanan aktif ditemukan di database.")

        all_gallery_items = list(db.galeri.find({'status': True}))
        all_images = []
        for item in all_gallery_items:
            if 'gambar' in item and isinstance(item['gambar'], list):
                valid_images = [img for img in item['gambar'] if isinstance(img, str) and img.strip()]
                all_images.extend(valid_images)
        random.shuffle(all_images)
        random_gallery_images = all_images[:8]

        # --- Bagian Ulasan (Logika diubah total) ---
        # Mengambil 5 ulasan terbaru untuk ditampilkan di beranda.
        latest_reviews_cursor = db.reviews.find().sort('created_at', -1).limit(5)
        testimonials_data = []
        for review in latest_reviews_cursor:
            user = db.users.find_one({"_id": review['user_id']})
            
            # Variabel default untuk nama layanan dan paket
            nama_layanan = "Tidak Diketahui"
            nama_paket = "Tidak Diketahui"

            # Ambil nama layanan berdasarkan layanan_id dari review
            if 'layanan_id' in review:
                layanan = db.layanan.find_one({"_id": review['layanan_id']})
                if layanan:
                    nama_layanan = layanan.get('nama', nama_layanan)
            
            # Ambil nama paket berdasarkan paket_id dari review
            if 'paket_id' in review:
                paket = db.paket.find_one({"_id": review['paket_id']})
                if paket:
                    nama_paket = paket.get('nama', nama_paket)

            # Bangun string format baru sesuai permintaan
            service_package_string = f"Layanan {nama_layanan} - Paket {nama_paket}"

            if user:
                testimonials_data.append({
                    "name": mask_name(user.get('full_name', 'Pengguna Anonim')),
                    "date": tanggal_id(review.get('created_at')),
                    "stars": review.get('rating', 5),
                    "package": service_package_string, # Menggunakan string format baru
                    "text": review.get('comment', ''),
                    "imgSrc": user.get('profile_picture_url', 'URL_GAMBAR_DEFAULT_ANDA'), # Ganti URL Default
                    "imgAlt": f"Foto profil {mask_name(user.get('full_name', 'Pengguna Anonim'))}"
                })

        # Kirim semua data ke template
        return render_template(
            'user/beranda.html',
            layanan=layanan_data,
            random_gallery_images=random_gallery_images,
            testimonials=testimonials_data
        )

    except Exception as e:
        logging.error(f"ERROR: Terjadi kesalahan saat memuat halaman beranda: {e}")
        return render_template(
            'user/beranda.html',
            layanan=[],
            random_gallery_images=[],
            testimonials=[],
            error_message="Gagal memuat konten. Silakan coba lagi nanti."
        )




def sanitize_filename(name):
    # Ganti spasi dengan underscore dan hapus karakter tidak valid
    name = name.strip().lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name)
    return name


# Admin - Layanan Fotografi
@app.route("/admin_layananFotografi")
def admin_layananFotografi():
    layanan = list(db.layanan.find())
    return render_template(
        "admin/layananFotografi.html", layanan=layanan, current_route=request.path
    )


@app.route("/admin_layananFotografi_toggle/<id>", methods=["POST"])
def admin_layananFotografi_toggle(id):
    data = request.get_json()
    status_baru = bool(data.get("status", True))
    db.layanan.update_one({"_id": ObjectId(id)}, {"$set": {"status": status_baru}})
    return jsonify({"ok": True})


@app.route("/admin_layananFotografi_tambah", methods=["GET", "POST"])
def admin_layananFotografi_tambah():
    layanan_exists = False

    if request.method == "POST":
        nama = request.form["nama"]
        gambar = request.files["gambar"]
        deskripsi = request.form["deskripsi"]

        # Periksa apakah Nama Layanan sudah ada
        existing_layanan = db.layanan.find_one({"nama": nama})
        if existing_layanan:
            layanan_exists = True
        else:
            if gambar and gambar.filename != "":
                ekstensi = os.path.splitext(gambar.filename)[1]
                timestamp = str(int(time.time()))
                nama_file_gambar = f"{sanitize_filename(nama)}_{timestamp}{ekstensi}"
                file_path = os.path.join("static/images/imgLayanan", nama_file_gambar)
                gambar.save(file_path)
            else:
                nama_file_gambar = None

            doc = {
                "nama": nama,
                "gambar": nama_file_gambar,
                "deskripsi": deskripsi,
                "status": True,  # layanan aktif secara default
            }
            db.layanan.insert_one(doc)
            return redirect(url_for("admin_layananFotografi"))
    return render_template(
        "admin/layananFotografi_tambah.html", layanan_exists=layanan_exists
    )


@app.route("/check_nama_layanan", methods=["POST"])
def check_nama_layanan():
    data = request.json
    nama_layanan = data.get("nama", "")

    # Periksa apakah nama layanan sudah ada di database MongoDB
    existing_layanan = db.layanan.find_one(
        {"nama": {"$regex": f"^{nama_layanan}$", "$options": "i"}}
    )
    if existing_layanan:
        return jsonify({"exists": True})
    else:
        return jsonify({"exists": False})


@app.route("/admin_layananFotografi_ubah/<_id>", methods=["GET", "POST"])
def admin_layananFotografi_ubah(_id):
    layanan_exists = False

    if request.method == "POST":
        id = request.form["_id"]
        nama = request.form["nama"]
        deskripsi = request.form["deskripsi"]
        gambar = request.files["gambar"]

        # Periksa apakah Nama Layanan sudah ada, kecuali layanan yang sedang diubah
        existing_layanan = db.layanan.find_one(
            {"nama": nama, "_id": {"$ne": ObjectId(id)}}
        )
        if existing_layanan:
            layanan_exists = True
        else:
            # Ambil data lama untuk akses gambar lama
            old_layanan = db.layanan.find_one({"_id": ObjectId(_id)})
            doc = {
                "nama": nama,
                "deskripsi": deskripsi,
                "status": True,
                "gambar": old_layanan.get("gambar"),  # default ke gambar lama
            }

            # Cek apakah user mengunggah file baru
            if gambar and gambar.filename != "":
                ekstensi = os.path.splitext(gambar.filename)[1]
                timestamp = str(int(time.time()))
                nama_file_gambar = f"{sanitize_filename(nama)}_{timestamp}{ekstensi}"
                file_path = os.path.join("static/images/imgLayanan", nama_file_gambar)
                gambar.save(file_path)
                doc["gambar"] = nama_file_gambar

                # Hapus gambar lama
                old_image_filename = old_layanan.get("gambar")
                if old_image_filename and old_image_filename != nama_file_gambar:
                    old_image_path = os.path.join(
                        "static/images/imgLayanan", old_image_filename
                    )
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)

            # Update/ubah layanan
            db.layanan.update_one({"_id": ObjectId(_id)}, {"$set": doc})
            return redirect(url_for("admin_layananFotografi"))

    id = ObjectId(_id)
    data = list(db.layanan.find({"_id": id}))
    return render_template(
        "admin/layananFotografi_ubah.html", data=data, layanan_exists=layanan_exists
    )


@app.route("/katalog_layanan")
def katalog_layanan():
    layanan_list = list(db.layanan.find({"status": True}))  # hanya layanan aktif

    # Ambil tanggal-tanggal yang sudah terisi dari pesanan
    # dengan status "Menunggu Konfirmasi", "Telah Dikonfirmasi", atau "Belum Pemotretan"
    disabled_statuses = [
        "Menunggu Konfirmasi",
        "Telah Dikonfirmasi",
        "Belum Pemotretan",
    ]

    booked_dates_cursor = db.pesanan.find(
        {"status_pesanan": {"$in": disabled_statuses}},
        {"tanggal_mulai_acara": 1, "tanggal_selesai_acara": 1, "_id": 0},
    )

    booked_dates = set() # Menggunakan set untuk menghindari duplikasi tanggal
    for order in booked_dates_cursor:
        start_date_obj = order.get("tanggal_mulai_acara")
        end_date_obj = order.get("tanggal_selesai_acara")

        if start_date_obj and end_date_obj:
            # Iterasi melalui setiap hari dalam rentang tanggal
            current_date = start_date_obj
            while current_date <= end_date_obj:
                booked_dates.add(current_date.strftime("%Y-%m-%d")) # Format ke 'YYYY-MM-DD'
                current_date += timedelta(days=1) # Maju satu hari

    for layanan in layanan_list:
        # Ambil paket aktif untuk setiap layanan
        paket_list = list(db.paket.find({"layanan_id": layanan["_id"], "status": True}))

        # Format tanggal
        for p in paket_list:
            mulai = p.get("tanggal_mulai")
            selesai = p.get("tanggal_selesai")

            if isinstance(mulai, datetime) and isinstance(selesai, datetime):
                p["tanggal_mulai_formatted"] = tanggal_id(mulai)
                p["tanggal_selesai_formatted"] = tanggal_id(selesai)
            else:
                p["tanggal_mulai_formatted"] = "Tanggal tidak tersedia"
                p["tanggal_selesai_formatted"] = "Tanggal tidak tersedia"

        # Tambahkan paket_list ke dalam data layanan
        layanan["paket_list"] = paket_list
        
    return render_template(
        "user/katalog_layanan.html",
        layanan=layanan_list,
        booked_dates=list(booked_dates), # Kirim sebagai list ke frontend
        current_route=request.path
    )


def tanggal_id(dt: datetime) -> str:
    """
    Ubah datetime ⇢ string "01 Januari 2025".
    Jatuh-bakal ke locale default jika `id_ID` tidak tersedia.
    """
    try:
        locale.setlocale(locale.LC_TIME, "id_ID.UTF-8")
    except locale.Error:

        bulan_map = {
            "January": "Januari",
            "February": "Februari",
            "March": "Maret",
            "April": "April",
            "May": "Mei",
            "June": "Juni",
            "July": "Juli",
            "August": "Agustus",
            "September": "September",
            "October": "Oktober",
            "November": "November",
            "December": "Desember",
        }
        en = dt.strftime("%d %B %Y")
        for en_bulan, id_bulan in bulan_map.items():
            en = en.replace(en_bulan, id_bulan)
        return en
    return dt.strftime("%d %B %Y")


# Admin - Paket Fotografi
@app.route("/admin_paketFotografi")
def admin_paketFotografi():
    paket = list(db.paket.find())
    layanan_map = {str(l["_id"]): l["nama"] for l in db.layanan.find()}

    # Tambahkan nama layanan ke dalam setiap dokumen paket
    for p in paket:
        layanan_id = str(p.get("layanan_id"))
        p["layanan"] = layanan_map.get(layanan_id, "Tidak ditemukan")

        mulai = p.get("tanggal_mulai")
        selesai = p.get("tanggal_selesai")

        if isinstance(mulai, datetime) and isinstance(selesai, datetime):
            p["tanggal_mulai_formatted"] = tanggal_id(mulai)
            p["tanggal_selesai_formatted"] = tanggal_id(selesai)
        else:
            p["tanggal_mulai_formatted"] = "Tanggal tidak tersedia"
            p["tanggal_selesai_formatted"] = "Tanggal tidak tersedia"

    return render_template(
        "admin/paketFotografi.html", paket=paket, current_route=request.path
    )


@app.route("/admin_paketFotografi_toggle/<id>", methods=["POST"])
def admin_paketFotografi_toggle(id):
    data = request.get_json()
    status_baru = bool(data.get("status", True))
    db.paket.update_one({"_id": ObjectId(id)}, {"$set": {"status": status_baru}})
    return jsonify({"ok": True})


@app.route("/admin_paketFotografi_tambah", methods=["GET", "POST"])
def admin_paketFotografi_tambah():
    paket_exists = False

    if request.method == "POST":
        nama = request.form["nama"]
        layanan_id = request.form["layanan"]
        harga = int(request.form["harga"])
        deposit = int(request.form["deposit"])
        keuntungan = request.form["keuntungan"]
        tim_kerja = request.form["tim_kerja"]
        tanggal_mulai_str = request.form["tanggal_mulai"]
        tanggal_selesai_str = request.form["tanggal_selesai"]

        # Konversi tanggal
        tanggal_mulai = datetime.strptime(tanggal_mulai_str, "%Y-%m-%d")
        tanggal_selesai = datetime.strptime(tanggal_selesai_str, "%Y-%m-%d")

        # Simpan ke dalam dokumen
        doc = {
            "nama": nama,
            "layanan_id": ObjectId(layanan_id),
            "harga": harga,
            "deposit": deposit,
            "keuntungan": keuntungan,
            "tim_kerja": tim_kerja,
            "tanggal_mulai": tanggal_mulai,
            "tanggal_selesai": tanggal_selesai,
            "status": True,
            "created_at": datetime.utcnow(),
        }
        db.paket.insert_one(doc)
        return redirect(url_for("admin_paketFotografi"))

    layanan = list(db.layanan.find())
    return render_template(
        "admin/paketFotografi_tambah.html", layanan=layanan, paket_exists=paket_exists
    )


@app.route("/check_nama_paket", methods=["POST"])
def check_nama_paket():
    data = request.json
    nama_paket = data.get("nama", "")

    # Periksa apakah nama paket sudah ada di database MongoDB
    existing_paket = db.paket.find_one(
        {"nama": {"$regex": f"^{nama_paket}$", "$options": "i"}}
    )
    if existing_paket:
        return jsonify({"exists": True})
    else:
        return jsonify({"exists": False})


@app.route("/admin_paketFotografi_ubah/<_id>", methods=["GET", "POST"])
def admin_paketFotografi_ubah(_id):
    paket_exists = False

    if request.method == "POST":
        id = request.form["_id"]
        nama = request.form["nama"]
        layanan_id = request.form["layanan"]
        harga = int(request.form["harga"])
        deposit = int(request.form["deposit"])
        keuntungan = request.form["keuntungan"]
        tim_kerja = request.form["tim_kerja"]
        tanggal_mulai_str = request.form["tanggal_mulai"]
        tanggal_selesai_str = request.form["tanggal_selesai"]

        tanggal_mulai = datetime.strptime(tanggal_mulai_str, "%Y-%m-%d")
        tanggal_selesai = datetime.strptime(tanggal_selesai_str, "%Y-%m-%d")

        # Periksa apakah Nama paket sudah ada, kecuali paket yang sedang diubah
        existing_paket = db.paket.find_one({"nama": nama, "_id": {"$ne": ObjectId(id)}})
        if existing_paket:
            paket_exists = True
        else:
            doc = {
                "nama": nama,
                "layanan_id": ObjectId(layanan_id),
                "harga": harga,
                "deposit": deposit,
                "keuntungan": keuntungan,
                "tim_kerja": tim_kerja,
                "tanggal_mulai": tanggal_mulai,
                "tanggal_selesai": tanggal_selesai,
                "status": True,  # paket aktif secara default
            }

            db.paket.update_one({"_id": ObjectId(_id)}, {"$set": doc})
            return redirect(url_for("admin_paketFotografi"))

    id = ObjectId(_id)
    data = db.paket.find_one({"_id": id})
    layanan = list(db.layanan.find())

    formatted_tanggal_mulai = ""
    formatted_tanggal_selesai = ""

    if data and "tanggal_mulai" in data and isinstance(data["tanggal_mulai"], datetime):
        formatted_tanggal_mulai = data["tanggal_mulai"].strftime("%Y-%m-%d")

    if (
        data
        and "tanggal_selesai" in data
        and isinstance(data["tanggal_selesai"], datetime)
    ):
        formatted_tanggal_selesai = data["tanggal_selesai"].strftime("%Y-%m-%d")

    return render_template(
        "admin/paketFotografi_ubah.html",
        data=data,
        layanan=layanan,
        paket_exists=paket_exists,
        formatted_tanggal_mulai=formatted_tanggal_mulai,
        formatted_tanggal_selesai=formatted_tanggal_selesai,
    )


# User - Lihat Paket
@app.route("/lihat_paket/<layanan_id>")
def lihat_paket(layanan_id):
    # Cari layanan berdasarkan id
    layanan = db.layanan.find_one({"_id": ObjectId(layanan_id)})

    # Hanya ambil paket yang aktif
    paket_list = list(
        db.paket.find(
            {
                "layanan_id": ObjectId(layanan_id),
                "status": True,  # hanya paket dengan status aktif
            }
        )
    )

    for p in paket_list:
        mulai = p.get("tanggal_mulai")
        selesai = p.get("tanggal_selesai")

        if isinstance(mulai, datetime) and isinstance(selesai, datetime):
            p["tanggal_mulai_formatted"] = tanggal_id(mulai)
            p["tanggal_selesai_formatted"] = tanggal_id(selesai)
        else:
            p["tanggal_mulai_formatted"] = "Tanggal tidak tersedia"
            p["tanggal_selesai_formatted"] = "Tanggal tidak tersedia"

    return render_template(
        "user/lihat_paket.html", layanan=layanan, paket_list=paket_list
    )


# Admin - Galeri
@app.route('/admin_galeri')
def admin_galeri():
    logger = app.logger
    logger.info("Mengakses route /admin_galeri")
    processed_gallery_items = []
    
    # Menangkap pesan SweetAlert dari URL
    sa_status = request.args.get('_sa_status')
    sa_message = request.args.get('_sa_message')

    try:
        gallery_items_cursor = db.galeri.find().sort("tanggal_upload", -1)

        for item in gallery_items_cursor:
            nama_layanan_terkait = "-"
            nama_lokasi_terkait = "-"

            if item.get('kategori') == 'layanan' and item.get('id_layanan'):
                try:
                    # Pastikan id_layanan adalah ObjectId sebelum query
                    layanan_obj = db.layanan.find_one({"_id": ObjectId(item['id_layanan'])})
                    if layanan_obj:
                        nama_layanan_terkait = layanan_obj.get('nama', 'N/A')
                except Exception as e:
                    logger.warning(f"Error ObjectId/query layanan untuk galeri {item.get('_id')}: {e}")

            elif item.get('kategori') == 'lokasi' and item.get('id_lokasi'):
                try:
                    # Pastikan id_lokasi adalah ObjectId sebelum query
                    lokasi_obj = db.lokasi.find_one({"_id": ObjectId(item.get('id_lokasi'))})
                    if lokasi_obj:
                        nama_lokasi_terkait = lokasi_obj.get('nama', 'N/A')
                except Exception as e:
                    logger.warning(f"Error ObjectId/query lokasi untuk galeri {item.get('_id')}: {e}")

            item['nama_layanan_display'] = nama_layanan_terkait
            item['nama_lokasi_display'] = nama_lokasi_terkait
            item['status'] = item.get('status', True)

            if item.get('thumbnail'):
                item['thumbnail'] = item['thumbnail']
            elif isinstance(item.get('gambar'), list) and item.get('gambar'):
                item['thumbnail'] = item['gambar'][0]
            else:
                item['thumbnail'] = None

            # Convert ObjectId to string for safe JSON/Jinja2 usage
            item['_id'] = str(item['_id'])
            if 'id_layanan' in item and isinstance(item['id_layanan'], ObjectId):
                item['id_layanan'] = str(item['id_layanan'])
            if 'id_lokasi' in item and isinstance(item['id_lokasi'], ObjectId):
                item['id_lokasi'] = str(item['id_lokasi'])

            processed_gallery_items.append(item)

    except Exception as e:
        logger.error(f"Error di route /admin_galeri: {e}", exc_info=True)
        processed_gallery_items = []
        # Mengirim pesan error melalui SweetAlert jika terjadi di sini
        sa_status = 'error'
        sa_message = "Terjadi kesalahan saat mengambil data galeri."

    return render_template(
        'admin/galeri.html',
        galeri_items=processed_gallery_items,
        current_route=request.path,
        _sa_status=sa_status,  # Teruskan ke template
        _sa_message=sa_message # Teruskan ke template
    )

@app.route("/admin_galeri_toggle_status/<item_id>", methods=["POST"])
def admin_galeri_toggle_status(item_id):
    logger = app.logger
    try:
        data = request.get_json()
        status_baru = bool(data.get("status", False))

        result = db.galeri.update_one(
            {"_id": ObjectId(item_id)},
            {"$set": {"status": status_baru}}
        )

        if result.matched_count == 0:
            return jsonify({"success": False, "message": "Item galeri tidak ditemukan."}), 404

        # Pesan sukses untuk SweetAlert dari AJAX
        return jsonify({"success": True, "message": "Status galeri berhasil diubah."})
    except Exception as e:
        logger.error(f"Error saat toggle status galeri {item_id}: {e}", exc_info=True)
        # Pesan error untuk SweetAlert dari AJAX
        return jsonify({"success": False, "message": "Terjadi kesalahan internal saat mengubah status."}), 500


@app.route('/admin_galeri_tambah', methods=['GET', 'POST'])
def admin_galeri_tambah():
    layanan = list(db.layanan.find())
    lokasi = list(db.lokasi.find({"is_active": True}))

    if request.method == 'POST':
        app.logger.debug(f"Request form data: {request.form}")
        app.logger.debug(f"Request files: {request.files}")

        kategori = request.form.get('kategori')
        layanan_id = request.form.get('layanan')
        lokasi_id = request.form.get('lokasi')
        gambar_files = request.files.getlist('gambar[]')

        app.logger.debug(f"Kategori: {kategori}")
        app.logger.debug(f"Layanan ID: {layanan_id}")
        app.logger.debug(f"Lokasi ID: {lokasi_id}")
        app.logger.debug(f"Jumlah file diterima: {len(gambar_files)}")
        if gambar_files:
            for i, f in enumerate(gambar_files):
                app.logger.debug(f"File {i}: filename='{f.filename}', content_type='{f.content_type}'")

        if not kategori or not gambar_files:
            return redirect(url_for('admin_galeri_tambah',
                                     _sa_status='error',
                                     _sa_message='Kategori dan gambar wajib diisi.'))

        nama_file_gambar = []
        base_save_path = os.path.join(app.root_path, 'static', 'images', 'imgGaleri')
        if not os.path.exists(base_save_path):
            try:
                os.makedirs(base_save_path)
                app.logger.info(f"Direktori {base_save_path} dibuat.")
            except OSError as e:
                app.logger.error(f"Gagal membuat direktori {base_save_path}: {e}")
                return redirect(url_for('admin_galeri_tambah',
                                         _sa_status='error',
                                         _sa_message='Terjadi kesalahan server saat membuat direktori penyimpanan.'))


        for gambar in gambar_files:
            if gambar and gambar.filename:
                nama_file = secure_filename(gambar.filename)
                simpan_path = os.path.join(base_save_path, nama_file)
                app.logger.debug(f"Mencoba menyimpan file ke: {simpan_path}")
                try:
                    gambar.save(simpan_path)
                    nama_file_gambar.append(nama_file)
                    app.logger.info(f"File {nama_file} berhasil disimpan.")
                except Exception as e:
                    app.logger.error(f"Gagal menyimpan file {nama_file}: {e}")
            else:
                app.logger.warning("Sebuah file dilewati karena tidak valid atau tidak ada filename.")


        if not nama_file_gambar:
            return redirect(url_for('admin_galeri_tambah',
                                     _sa_status='warning',
                                     _sa_message='Tidak ada file gambar yang berhasil diproses atau disimpan.'))

        initial_thumbnail = nama_file_gambar[0] if nama_file_gambar else None

        doc = {
            'kategori': kategori,
            'gambar': nama_file_gambar,
            'id_layanan': ObjectId(layanan_id) if layanan_id else None,
            'id_lokasi': ObjectId(lokasi_id) if lokasi_id else None,
            'tanggal_upload': datetime.now(),
            'status': True,
            'thumbnail': initial_thumbnail
        }

        try:
            db.galeri.insert_one(doc)
            app.logger.info(f"Dokumen galeri berhasil disimpan ke DB: {doc.get('_id')}")
            return redirect(url_for('admin_galeri',
                                     _sa_status='success',
                                     _sa_message='Galeri berhasil ditambahkan!'))
        except Exception as e:
            app.logger.error(f"Gagal menyimpan dokumen ke DB: {e}")

            for nf in nama_file_gambar:
                file_to_delete = os.path.join(base_save_path, nf)
                if os.path.exists(file_to_delete):
                    try:
                        os.remove(file_to_delete)
                        app.logger.info(f"File {nf} dihapus karena gagal insert DB.")
                    except OSError as del_err:
                        app.logger.error(f"Gagal menghapus file {nf}: {del_err}")

            return redirect(url_for('admin_galeri_tambah',
                                     _sa_status='error',
                                     _sa_message='Gagal menyimpan data galeri ke database.'))

    return render_template('admin/galeri_tambah.html',
                           layanan=layanan,
                           lokasi=lokasi,
                           current_route=request.path,
                           _sa_status=request.args.get('_sa_status'), # Meneruskan status/message dari redirect
                           _sa_message=request.args.get('_sa_message'))


@app.route('/admin_galeri_ubah/<item_id>', methods=['GET', 'POST'])
def admin_galeri_ubah(item_id):
    upload_folder_galeri = os.path.join(app.static_folder, 'images', 'imgGaleri')

    if not os.path.exists(upload_folder_galeri):
        try:
            os.makedirs(upload_folder_galeri)
            app.logger.info(f"Direktori upload '{upload_folder_galeri}' berhasil dibuat.")
        except OSError as e:
            app.logger.error(f"Gagal membuat direktori upload '{upload_folder_galeri}': {e}", exc_info=True)
            return redirect(url_for('admin_galeri', # Redirect ke halaman utama dengan pesan error SweetAlert
                                     _sa_status='error',
                                     _sa_message=f"Gagal membuat direktori upload: {e}. Periksa izin folder."))

    try:
        gallery_item_to_edit = db.galeri.find_one({'_id': ObjectId(item_id)})
        if not gallery_item_to_edit:
            app.logger.error(f"Item galeri dengan ID '{item_id}' tidak ditemukan di database.")
            return redirect(url_for('admin_galeri', # Redirect ke halaman utama dengan pesan error SweetAlert
                                     _sa_status='error',
                                     _sa_message='Item galeri tidak ditemukan.'))

        if request.method == 'POST':
            app.logger.info(f"Menerima POST request untuk ubah gambar galeri ID: '{item_id}' (hanya hapus)")

            # Retrieve form fields for update (if any, current code only handles deletions)
            # category = request.form.get('kategori') # Example of retrieving other fields
            # ... and so on for other fields you might want to update

            deleted_images_filenames = request.form.getlist('deleted_images[]')

            current_image_list = list(gallery_item_to_edit.get('gambar', []))
            images_after_deletion = []

            files_deleted_count = 0
            for existing_filename in current_image_list:
                if existing_filename in deleted_images_filenames:
                    try:
                        file_path_to_delete = os.path.join(upload_folder_galeri, existing_filename)
                        if os.path.exists(file_path_to_delete):
                            os.remove(file_path_to_delete)
                            app.logger.info(f"File lama berhasil dihapus dari disk: '{existing_filename}'")
                            files_deleted_count += 1
                        else:
                            app.logger.warning(f"File lama '{existing_filename}' tidak ditemukan di disk saat mencoba menghapus. Mungkin sudah dihapus sebelumnya.")
                    except Exception as e_del:
                        app.logger.error(f"ERROR: Gagal menghapus file fisik '{existing_filename}': {e_del}", exc_info=True)
                        # Tidak ada flash di sini, akan ditangani oleh redirect SweetAlert di akhir

                else:
                    images_after_deletion.append(existing_filename)

            updated_image_list = images_after_deletion

            # --- LOGIKA UNTUK UPDATE THUMBNAIL DI SINI ---
            thumbnail_to_update = None
            if updated_image_list:
                thumbnail_to_update = updated_image_list[0]
            # --- AKHIR LOGIKA UPDATE THUMBNAIL ---

            # Prepare update document for MongoDB
            doc_to_update = {
                'gambar': updated_image_list,
                'tanggal_modifikasi': datetime.now(),
                # Keep other fields as they were if not explicitly updated via form
                'kategori': request.form.get('kategori', gallery_item_to_edit.get('kategori')),
                'id_layanan': ObjectId(request.form.get('layanan')) if request.form.get('layanan') else gallery_item_to_edit.get('id_layanan'),
                'id_lokasi': ObjectId(request.form.get('lokasi')) if request.form.get('lokasi') else gallery_item_to_edit.get('id_lokasi'),
                'status': gallery_item_to_edit.get('status', True), # Assuming status is not changed in this form
                'thumbnail': thumbnail_to_update
            }
            
            # Additional check if there are no images left
            if not updated_image_list:
                # Optionally, delete the whole gallery item if no images are left
                # db.galeri.delete_one({"_id": ObjectId(item_id)})
                # app.logger.info(f"Item galeri ID '{item_id}' dihapus dari DB karena tidak ada gambar tersisa.")
                # return redirect(url_for('admin_galeri', _sa_status='success', _sa_message='Item galeri berhasil dihapus karena tidak ada gambar tersisa.'))
                
                # Or, just redirect with a warning if no images left
                return redirect(url_for('admin_galeri_ubah',
                                        item_id=item_id,
                                        _sa_status='warning',
                                        _sa_message='Semua gambar telah dihapus! Item galeri tidak memiliki gambar lagi.'))


            db.galeri.update_one({"_id": ObjectId(item_id)}, {"$set": doc_to_update})
            app.logger.info(f"Item galeri ID '{item_id}' berhasil diupdate di database (setelah penghapusan). Total gambar sekarang: {len(updated_image_list)}. Thumbnail: {thumbnail_to_update}.")

            return redirect(url_for('admin_galeri_ubah', # Redirect ke halaman ubah itu sendiri dengan pesan sukses
                                     item_id=item_id,
                                     _sa_status='success',
                                     _sa_message='Gambar galeri berhasil diperbarui (dihapus).'))

        # --- GET request (menampilkan form ubah) ---
        # Convert ObjectId to string for safe Jinja2 usage in select/input fields
        if 'id_layanan' in gallery_item_to_edit and isinstance(gallery_item_to_edit['id_layanan'], ObjectId):
            gallery_item_to_edit['id_layanan'] = str(gallery_item_to_edit['id_layanan'])
        if 'id_lokasi' in gallery_item_to_edit and isinstance(gallery_item_to_edit['id_lokasi'], ObjectId):
            gallery_item_to_edit['id_lokasi'] = str(gallery_item_to_edit['id_lokasi'])
        gallery_item_to_edit['_id'] = str(gallery_item_to_edit['_id']) # Ensure _id is string for template

        layanan_all_list = list(db.layanan.find({}, {"nama": 1, "_id": 1}))
        lokasi_all_list = list(db.lokasi.find({}, {"nama": 1, "_id": 1}))

        # Convert ObjectId to string for select options
        for lay in layanan_all_list: lay['_id'] = str(lay['_id'])
        for loc in lokasi_all_list: loc['_id'] = str(loc['_id'])


        return render_template('admin/galeri_ubah.html',
                                gallery_item=gallery_item_to_edit,
                                layanan_all=layanan_all_list,
                                lokasi_all=lokasi_all_list,
                                current_route=request.path,
                                _sa_status=request.args.get('_sa_status'), # Meneruskan status/message dari redirect
                                _sa_message=request.args.get('_sa_message'))

    except Exception as e:
        app.logger.error(f"Terjadi error tak terduga di route /admin_galeri_ubah untuk ID '{item_id}': {e}", exc_info=True)
        return redirect(url_for('admin_galeri', # Redirect ke halaman utama dengan pesan error SweetAlert
                                 _sa_status='error',
                                 _sa_message=f"Terjadi kesalahan saat memproses permintaan ubah galeri: {e}"))


# Galeri - User
@app.route('/galeri')
def galeri():
    """Menampilkan halaman galeri user dengan semua foto aktif secara default."""
    return render_template('user/galeri.html')

@app.route('/api/galeri_data', methods=['GET'])
def get_galeri_data():
    """Endpoint API untuk mengambil data galeri berdasarkan filter."""
    kategori = request.args.get('kategori')
    pilihan_kategori_id = request.args.get('pilihan_kategori')
    limit = request.args.get('limit', type=int) # New: Optional limit for preview sections

    app.logger.debug(f"API call received: kategori='{kategori}', pilihan_kategori_id='{pilihan_kategori_id}', limit='{limit}'")

    query = {"status": True}  # Hanya tampilkan yang aktif

    galeri_items = []
    # Description data will only be populated for specific selections, not 'all'
    description_data = {}

    try:
        if kategori and kategori != 'all':
            query['kategori'] = kategori
            if pilihan_kategori_id and pilihan_kategori_id != 'all':
                app.logger.debug(f"Applying specific filter: kategori='{kategori}', ID='{pilihan_kategori_id}'")
                if kategori == 'layanan':
                    try:
                        obj_id = ObjectId(pilihan_kategori_id)
                        query['id_layanan'] = obj_id
                        layanan_obj = db.layanan.find_one({"_id": obj_id})
                        if layanan_obj:
                            description_data["nama_layanan"] = layanan_obj.get('nama', 'N/A')
                            description_data["biaya"] = layanan_obj.get('harga', 'N/A')
                        app.logger.debug(f"Layanan object found: {layanan_obj.get('nama')} with ID {obj_id}")
                    except Exception as e:
                        app.logger.error(f"Error converting layanan_id to ObjectId or finding layanan: {e}", exc_info=True)
                        galeri_items = []
                        # Jika terjadi kesalahan, pastikan description_data kosong agar tidak ditampilkan
                        return jsonify({"gallery_items": galeri_items, "description_data": {}})
                elif kategori == 'lokasi':
                    try:
                        obj_id = ObjectId(pilihan_kategori_id)
                        query['id_lokasi'] = obj_id
                        lokasi_obj = db.lokasi.find_one({"_id": obj_id})
                        if lokasi_obj:
                            description_data["nama_layanan"] = "Galeri Lokasi" # Untuk lokasi, ini bisa jadi judul
                            description_data["lokasi"] = lokasi_obj.get('nama', 'N/A')
                            description_data["maps"] = lokasi_obj.get('link_maps', 'N/A')
                            description_data["biaya"] = lokasi_obj.get('biaya', 'N/A')
                        app.logger.debug(f"Lokasi object found: {lokasi_obj.get('nama')} with ID {obj_id}")
                    except Exception as e:
                        app.logger.error(f"Error converting lokasi_id to ObjectId or finding lokasi: {e}", exc_info=True)
                        galeri_items = []
                        # Jika terjadi kesalahan, pastikan description_data kosong agar tidak ditampilkan
                        return jsonify({"gallery_items": galeri_items, "description_data": {}})
                # If specific category and choice are selected, description data is relevant
                # Set default values if keys don't exist yet, to ensure consistent structure
                description_data.setdefault("nama_layanan", "-")
                description_data.setdefault("lokasi", "-")
                description_data.setdefault("maps", "-")
                description_data.setdefault("biaya", "-")
            else:
                # When a specific category is selected but 'all' choice, description should be empty
                description_data = {}
                app.logger.debug(f"Kategori selected, but specific choice is 'all'. Query: {query}")
        else:
            # When 'all' category is selected, no description data is relevant
            description_data = {}
            app.logger.debug(f"Kategori 'all' selected. Query: {query}")

        app.logger.debug(f"Final MongoDB Query for galeri: {query}")
        
        cursor = db.galeri.find(query)
        if limit:
            cursor = cursor.limit(limit) # Apply limit if provided
        
        # Check if there are documents matching the query before iterating
        # Note: count_documents() is a more robust way to check than cursor.count() (deprecated)
        if db.galeri.count_documents(query) == 0:
            app.logger.warning(f"No gallery items found for query: {query}")
        
        for item in cursor:
            # Ensure all ObjectId are converted to string for JSON serialization
            item['_id'] = str(item['_id'])
            if item.get('id_layanan'):
                item['id_layanan'] = str(item['id_layanan'])
            if item.get('id_lokasi'):
                item['id_lokasi'] = str(item['id_lokasi'])
            
            # Hanya tambahkan item jika ada setidaknya satu gambar yang valid
            if isinstance(item.get('gambar'), list) and item['gambar'] and any(img for img in item['gambar'] if img and isinstance(img, str)):
                galeri_items.append(item)
            else:
                app.logger.warning(f"Skipping gallery item {item.get('_id')} due to missing or invalid 'gambar' field.")

        app.logger.debug(f"Number of gallery items returned: {len(galeri_items)}")
        
    except Exception as e:
        app.logger.error(f"Error saat mengambil data galeri: {e}", exc_info=True) 
        return jsonify({"error": "Terjadi kesalahan saat mengambil data galeri."}), 500

    return jsonify({
        "gallery_items": galeri_items,
        "description_data": description_data
    })

@app.route('/api/kategori_options', methods=['GET'])
def get_kategori_options():
    """Endpoint API untuk mengambil opsi kategori dan pilihan kategori."""
    data = {
        "kategori": [
            {"value": "all", "text": "Semua Kategori"},
            {"value": "layanan", "text": "Layanan"},
            {"value": "lokasi", "text": "Lokasi"}
        ],
        "pilihan_kategori": {
            "layanan": [{"value": "all", "text": "Semua Layanan"}],
            "lokasi": [{"value": "all", "text": "Semua Lokasi"}]
        }
    }

    try:
        # Mengambil layanan yang statusnya aktif
        layanan_cursor = db.layanan.find({"status": True}, {"_id": 1, "nama": 1}).sort("nama", 1) # Sort by name
        for layanan in layanan_cursor:
            data["pilihan_kategori"]["layanan"].append({
                "value": str(layanan['_id']),
                "text": layanan['nama']
            })

        # Mengambil lokasi yang statusnya aktif
        lokasi_cursor = db.lokasi.find({"is_active": True}, {"_id": 1, "nama": 1}).sort("nama", 1) # Sort by name
        for lokasi in lokasi_cursor:
            data["pilihan_kategori"]["lokasi"].append({
                "value": str(lokasi['_id']),
                "text": lokasi['nama']
            })

    except Exception as e:
        app.logger.error(f"Error saat mengambil opsi kategori: {e}", exc_info=True) 
        return jsonify({"error": "Terjadi kesalahan saat mengambil opsi kategori."}), 500

    return jsonify(data)




# Admin - Lokasi
@app.route("/admin_lokasi")
def admin_lokasi():
    lokasi = list(db.lokasi.find())
    return render_template(
        "admin/lokasi.html", lokasi=lokasi, current_route=request.path
    )


@app.route("/admin_lokasi_tambah", methods=["GET", "POST"])
def admin_lokasi_tambah():
    lokasi_exists = False

    if request.method == "POST":
        nama = request.form["nama"]
        alamat = request.form["alamat"]
        link_maps = request.form["link_maps"]

        # Periksa apakah Nama Lokasi sudah ada
        existing_lokasi = db.lokasi.find_one({"nama": nama})
        if existing_lokasi:
            lokasi_exists = True
        else:
            doc = {
                "nama": nama,
                "alamat": alamat,
                "link_maps": link_maps,
                "is_active": True,
            }
            db.lokasi.insert_one(doc)
            return redirect(url_for("admin_lokasi"))

    return render_template("admin/lokasi_tambah.html", lokasi_exists=lokasi_exists)


@app.route("/check_nama_lokasi", methods=["POST"])
def check_nama_lokasi():
    data = request.json
    nama_lokasi = data.get("nama", "")

    # Periksa apakah nama lokasi sudah ada di database MongoDB
    existing_lokasi = db.lokasi.find_one(
        {"nama": {"$regex": f"^{nama_lokasi}$", "$options": "i"}}
    )
    if existing_lokasi:
        return jsonify({"exists": True})
    else:
        return jsonify({"exists": False})


@app.route("/admin_lokasi_ubah/<id>", methods=["GET", "POST"])
def admin_lokasi_ubah(id):
    """
    Menampilkan form ubah lokasi dan menangani update data.
    """
    try:
        lokasi_id = ObjectId(id)
    except:
        return redirect(url_for("admin_lokasi"))  

    lokasi = db.lokasi.find_one({"_id": lokasi_id})

    if not lokasi:
        return redirect(url_for("admin_lokasi"))  

    if request.method == "POST":
        new_nama = request.form["nama"].strip()
        new_alamat = request.form["alamat"].strip()
        new_link_maps = request.form["link_maps"].strip()

        
        existing_lokasi = db.lokasi.find_one(
            {
                "nama": {"$regex": f"^{new_nama}$", "$options": "i"},
                "_id": {"$ne": lokasi_id},  
            }
        )

        if existing_lokasi:
            return render_template(
                "admin/lokasi_ubah.html", lokasi=lokasi, name_exists_error=True
            )
        else:
            db.lokasi.update_one(
                {"_id": lokasi_id},
                {
                    "$set": {
                        "nama": new_nama,
                        "alamat": new_alamat,
                        "link_maps": new_link_maps,
                    }
                },
            )
            return redirect(url_for("admin_lokasi"))

    return render_template(
        "admin/lokasi_ubah.html", lokasi=lokasi, current_route=request.path
    )


@app.route("/toggle_lokasi_status/<id>", methods=["POST"])
def toggle_lokasi_status(id):
    """
    Mengubah status aktif/nonaktif lokasi.
    """
    try:
        lokasi_id = ObjectId(id)
    except:
        return jsonify({"success": False, "message": "Invalid ID"}), 400

    lokasi = db.lokasi.find_one({"_id": lokasi_id})

    if not lokasi:
        return jsonify({"success": False, "message": "Location not found"}), 404

    current_status = lokasi.get("is_active", False)
    new_status = not current_status

    db.lokasi.update_one({"_id": lokasi_id}, {"$set": {"is_active": new_status}})
    return jsonify({"success": True, "new_status": new_status})



# Admin - Jadwal (Menampilkan semua jadwal)
@app.route("/admin_jadwal")
def admin_jadwal():
    all_pesanan_list = []
    try:
        # Ambil semua pesanan dari database
        pesanan_cursor = db.pesanan.find().sort(
            "created_at", -1
        )  # Urutkan dari yang terbaru

        # Buat map nama layanan, paket, dan lokasi berdasarkan _id
        layanan_map = {str(l["_id"]): l["nama"] for l in db.layanan.find()}
        paket_map = {str(l["_id"]): l["nama"] for l in db.paket.find()}
        lokasi_map = {str(l["_id"]): l["nama"] for l in db.lokasi.find()}

        for pesanan in pesanan_cursor:
            # Konversi ObjectId pesanan ke string
            pesanan["_id"] = str(pesanan["_id"])

            # Layanan
            layanan_id = str(pesanan.get("layanan_id", ""))
            pesanan["layanan"] = layanan_map.get(layanan_id, "Tidak ditemukan")

            # Paket
            paket_id = str(pesanan.get("paket_id", ""))
            pesanan["paket"] = paket_map.get(paket_id, "Tidak ditemukan")

            # Lokasi (bisa None atau kosong jika input manual)
            lokasi_id = str(pesanan.get("lokasi_id", ""))
            if lokasi_id and lokasi_id != "None":
                pesanan["lokasi"] = lokasi_map.get(lokasi_id, "Tidak ditemukan")
            else:
                pesanan["lokasi"] = (
                    "Lokasi pilihan sendiri"
                    if pesanan.get("alamat_lokasi_acara")
                    else "Tidak tersedia"
                )

            # Format tanggal
            if isinstance(pesanan.get("tanggal_mulai_acara"), datetime):
                pesanan["tanggal_mulai_acara_formatted"] = tanggal_id(
                    pesanan["tanggal_mulai_acara"]
                )
            else:
                pesanan["tanggal_mulai_acara_formatted"] = (
                    "N/A"  # Fallback for missing or invalid date
                )
            if isinstance(pesanan.get("tanggal_selesai_acara"), datetime):
                pesanan["tanggal_selesai_acara_formatted"] = tanggal_id(
                    pesanan["tanggal_selesai_acara"]
                )
            else:
                pesanan["tanggal_selesai_acara_formatted"] = (
                    "N/A"  # Fallback for missing or invalid date
                )

            all_pesanan_list.append(pesanan)

        return render_template(
            "admin/jadwal.html", pesanan=all_pesanan_list, current_route=request.path
        )

    except Exception as e:
        flash(f"Terjadi kesalahan saat mengambil data jadwal: {e}", "danger")
        # Jika terjadi kesalahan, Anda bisa me-render template dengan daftar kosong
        # atau redirect ke halaman dashboard admin.
        return render_template(
            "admin/jadwal.html", pesanan=[], current_route=request.path
        )


@app.route("/admin_jadwal_ubah/<_id>", methods=["GET", "POST"])
def admin_jadwal_ubah(_id):
    try:
        data = db.pesanan.find_one({"_id": ObjectId(_id)})
        if not data:
            flash("Data jadwal tidak ditemukan.", "danger")
            return redirect(url_for("admin_jadwal"))

        layanan_list = list(db.layanan.find())
        lokasi_list = list(db.lokasi.find())
        paket_list = list(db.paket.find())

        # --- START: New logic to fetch booked dates excluding current order ---
        disabled_statuses = [
            "Menunggu Konfirmasi",
            "Telah Dikonfirmasi",
            "Belum Pemotretan",
        ]

        # Fetch all booked dates that are NOT the current schedule being edited
        booked_dates_cursor = db.pesanan.find(
            {
                "status_pesanan": {"$in": disabled_statuses},
                "_id": {"$ne": ObjectId(_id)}  # Exclude the current order
            },
            {"tanggal_mulai_acara": 1, "tanggal_selesai_acara": 1, "_id": 0},
        )

        booked_date_ranges = []
        for order in booked_dates_cursor:
            start_date = order.get("tanggal_mulai_acara")
            end_date = order.get("tanggal_selesai_acara")
            if start_date and end_date:
                booked_date_ranges.append(
                    {
                        "start": start_date.strftime("%Y-%m-%d"),
                        "end": end_date.strftime("%Y-%m-%d"),
                    }
                )
        # --- END: New logic to fetch booked dates excluding current order ---

        if request.method == "POST":
            jam_acara = request.form.get("jam_acara")
            tanggal_mulai_acara = request.form.get("tanggal_mulai_acara")
            tanggal_selesai_acara = request.form.get("tanggal_selesai_acara")
            nama_klien = request.form.get("nama_klien")
            layanan_id = request.form.get("layanan")
            paket_id = request.form.get("paket")
            lokasi_id = request.form.get("lokasi")
            alamat = request.form.get("alamat")
            link_maps = request.form.get("link_maps")

            db.pesanan.update_one(
                {"_id": ObjectId(_id)},
                {
                    "$set": {
                        "jam_acara": jam_acara,
                        "tanggal_mulai_acara": datetime.strptime(
                            tanggal_mulai_acara, "%Y-%m-%d"
                        ),
                        "tanggal_selesai_acara": datetime.strptime(
                            tanggal_selesai_acara, "%Y-%m-%d"
                        ),
                        "nama": nama_klien,
                        "layanan_id": layanan_id,
                        "paket_id": paket_id,
                        "lokasi_id": lokasi_id,
                        "alamat_lokasi_acara": alamat,
                        "link_maps_acara": link_maps,
                    }
                },
            )

            flash("Jadwal berhasil diperbarui.", "success")
            return redirect(url_for("admin_jadwal"))

        formatted_tanggal_mulai = (
            data["tanggal_mulai_acara"].strftime("%Y-%m-%d")
            if isinstance(data.get("tanggal_mulai_acara"), datetime)
            else ""
        )
        formatted_tanggal_selesai = (
            data["tanggal_selesai_acara"].strftime("%Y-%m-%d")
            if isinstance(data.get("tanggal_selesai_acara"), datetime)
            else ""
        )

        return render_template(
            "admin/jadwal_ubah.html",
            data=data,
            layanan=layanan_list,
            lokasi=lokasi_list,
            paket=paket_list,
            formatted_tanggal_mulai=formatted_tanggal_mulai,
            formatted_tanggal_selesai=formatted_tanggal_selesai,
            booked_date_ranges=booked_date_ranges, # Pass booked dates to the template
        )

    except Exception as e:
        flash(f"Terjadi kesalahan saat memproses data: {e}", "danger")
        return redirect(url_for("admin_jadwal"))



# Pesanan
# --- Routes API untuk Frontend ---


@app.route("/api/all_paket", methods=["GET"])
def api_all_paket():
    """Mengembalikan semua data paket, termasuk harga dan deposit."""
    paket_data = list(db.paket.find({"status": True}))
    for paket in paket_data:
        if "_id" in paket:
            paket["_id"] = str(paket["_id"])
        if "layanan_id" in paket:
            paket["layanan_id"] = str(paket["layanan_id"])

        if "deposit" not in paket or not isinstance(paket["deposit"], (int, float)):
            paket["deposit"] = 0

        if "harga" not in paket or not isinstance(paket["harga"], (int, float)):
            paket["harga"] = 0
    return jsonify(paket_data)


@app.route("/api/all_lokasi", methods=["GET"])
def api_all_lokasi():
    """Mengembalikan semua data lokasi, termasuk biaya."""
    lokasi_data = list(db.lokasi.find({"is_active": True}))
    for lokasi in lokasi_data:
        if "_id" in lokasi:
            lokasi["_id"] = str(lokasi["_id"])

        if "biaya" not in lokasi or not isinstance(lokasi["biaya"], (int, float)):
            lokasi["biaya"] = 0
    return jsonify(lokasi_data)


# Admin - Pesanan
@app.route('/admin_pesanan')
def admin_pesanan():
    pesanan = list(db.pesanan.find().sort('created_at', -1))
    layanan_map = {str(l['_id']): l['nama'] for l in db.layanan.find()}

    # Tambahkan nama layanan ke dalam setiap dokumen pesanan
    for p in pesanan:
        layanan_id = str(p.get('layanan_id'))
        p['layanan'] = layanan_map.get(layanan_id, 'Tidak ditemukan')
       

        if isinstance(p.get('tanggal_mulai_acara'), datetime):
            p['tanggal_mulai_acara_formatted'] = tanggal_id(p['tanggal_mulai_acara'])
        if isinstance(p.get('tanggal_selesai_acara'), datetime):
            p['tanggal_selesai_acara_formatted'] = tanggal_id(p['tanggal_selesai_acara'])
    return render_template('admin/pesanan.html', pesanan=pesanan, current_route=request.path)

UPLOAD_FOLDER_SURAT_IZIN = 'static/suratIzin'
if not os.path.exists(UPLOAD_FOLDER_SURAT_IZIN):
    os.makedirs(UPLOAD_FOLDER_SURAT_IZIN)
app.config['UPLOAD_FOLDER_SURAT_IZIN'] = UPLOAD_FOLDER_SURAT_IZIN



@app.route('/admin_pesanan_tambah', methods=['GET', 'POST'])
def admin_pesanan_tambah():
    if request.method == 'POST':
        try:
            # Mengambil data dari form
            tanggal_pemesanan_str = request.form['tanggal_pemesanan']
            layanan_id = request.form['layanan_id'] # From hidden input
            paket_id = request.form['paket_id']     # From hidden input
            nama_klien = request.form['nama_klien']
            nama_orang_tua = request.form['nama_orang_tua']
            email_klien = request.form['email_klien']
            telepon_klien = request.form['telepon_klien']
            instagram_klien = request.form.get('instagram_klien', '')
            facebook_klien = request.form.get('facebook_klien', '')

            jam_acara_str = request.form['jam_acara']
            tanggal_mulai_acara_str = request.form['tanggal_mulai_acara']
            tanggal_selesai_acara_str = request.form['tanggal_selesai_acara']

            lokasi_luar_str = request.form['lokasi_luar']
            lokasi_luar = True if lokasi_luar_str == 'iya' else False

            lokasi_pilihan_user = request.form.get('lokasi_id')

            alamat_lokasi_manual = request.form.get('alamat_lokasi_manual', '')
            link_maps_manual = request.form.get('link_maps_manual', '')




            # Konversi tanggal dan waktu
            tanggal_pemesanan = datetime.strptime(tanggal_pemesanan_str, '%Y-%m-%d')
            jam_acara = jam_acara_str
            tanggal_mulai_acara = datetime.strptime(tanggal_mulai_acara_str, '%Y-%m-%d')
            tanggal_selesai_acara = datetime.strptime(tanggal_selesai_acara_str, '%Y-%m-%d')

           
            harga_paket = float(request.form.get('harga_paket_dasar', '0'))
            deposit_paket = float(request.form.get('deposit_paket_dasar', '0'))



            biaya_transportasi = int(
                request.form.get("biaya_transportasi") or 0
            )  
            biaya_tambah_hari = int(
                request.form.get("biayaTambahHari") or 0
            )  
            biaya_lokasi = int(
                request.form.get("biayaLokasi") or 0
            )



            # Determine Lokasi details and cost
            alamat_lokasi_final = None
            link_maps_final = None
            lokasi_id_db = None

            if lokasi_pilihan_user == "pilih_lokasi_sendiri":
                alamat_lokasi_final = alamat_lokasi_manual
                link_maps_final = link_maps_manual
            elif lokasi_pilihan_user:
                selected_lokasi = db.lokasi.find_one({'_id': ObjectId(lokasi_pilihan_user)})
                if selected_lokasi:
                    alamat_lokasi_final = selected_lokasi.get('alamat')
                    link_maps_final = selected_lokasi.get('link_maps')
                    lokasi_id_db = ObjectId(lokasi_pilihan_user)
            else: 
                alamat_lokasi_final = ""
                link_maps_final = ""

            recalculated_total_harga = harga_paket + biaya_tambah_hari + biaya_lokasi + biaya_transportasi
            recalculated_sisa_bayar = recalculated_total_harga - deposit_paket

            # Handle upload Surat Izin Lokasi (Opsional)
            surat_izin_lokasi_filename = None
            if 'surat_izin_lokasi' in request.files:
                surat_izin_file = request.files['surat_izin_lokasi']
                if surat_izin_file and surat_izin_file.filename != '':
                    filename_ext = os.path.splitext(surat_izin_file.filename)
                    # Use sanitized client name for filename
                    unique_filename = f"{sanitize_filename(nama_klien)}_surat_izin_{int(time.time())}{filename_ext[1]}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER_SURAT_IZIN'], unique_filename)
                    surat_izin_file.save(file_path)
                    surat_izin_lokasi_filename = unique_filename

            # Buat dokumen pesanan
            pesanan_doc = {
                'tanggal_pemesanan': tanggal_pemesanan, # Store as datetime object
                'layanan_id': ObjectId(layanan_id),
                'paket_id': ObjectId(paket_id),
                'nama_klien': nama_klien,
                'nama_orang_tua': nama_orang_tua,
                'email_klien': email_klien,
                'telepon_klien': telepon_klien,
                'instagram_klien': instagram_klien,
                'facebook_klien': facebook_klien,
                'jam_acara': jam_acara,
                'tanggal_mulai_acara': tanggal_mulai_acara, 
                'tanggal_selesai_acara': tanggal_selesai_acara, 
                'lokasi_luar_labuhanbatu': lokasi_luar,
                'lokasi_id': lokasi_id_db,
                'alamat_lokasi_acara': alamat_lokasi_final,
                'link_maps_acara': link_maps_final,
                'surat_izin_lokasi': surat_izin_lokasi_filename,
                'biaya_transportasi_akomodasi': biaya_transportasi,
                'biaya_tambah_hari': biaya_tambah_hari,
                'biaya_lokasi': biaya_lokasi,
                'harga_paket': harga_paket, 
                'deposit': deposit_paket,   
                'total_harga': recalculated_total_harga, 
                'sisa_bayar': recalculated_sisa_bayar,  
                'status_pesanan': 'Menunggu Konfirmasi',
                'created_at': datetime.utcnow()
            }

            db.pesanan.insert_one(pesanan_doc)
            flash("Pesanan berhasil dibuat!", "success")
            return redirect(url_for("admin_pesanan")) 

        except Exception as e:
            print(f"Error adding order: {e}")
            flash(f"Terjadi kesalahan saat menambahkan pesanan: {e}", "danger")
            layanan_list = list(db.layanan.find({'status': True}))
            lokasi_list = list(db.lokasi.find({'is_active': True}))
            for layanan in layanan_list:
                layanan['_id'] = str(layanan['_id'])
            for lokasi in lokasi_list:
                lokasi['_id'] = str(lokasi['_id'])
            return render_template('user/booking.html',
                                   layanan_list=layanan_list, 
                                   lokasi_list=lokasi_list,
                                   error_message=f"Terjadi kesalahan: {e}",
                                   selected_paket_id=request.form.get('paket_id'),
                                   selected_layanan_id=request.form.get('layanan_id'),
                                   selected_paket_nama=request.form.get('paket_nama'), 
                                   selected_paket_harga_raw=float(request.form.get('harga_paket_dasar', '0')),
                                   selected_paket_deposit_raw=float(request.form.get('deposit_paket_dasar', '0'))
                                   )

   
    layanan_list = list(db.layanan.find({'status': True}))
    lokasi_list = list(db.lokasi.find({'is_active': True}))
    for layanan in layanan_list:
        layanan['_id'] = str(layanan['_id'])
    for lokasi in lokasi_list:
        lokasi['_id'] = str(lokasi['_id'])
    return render_template('admin/pesanan_tambah.html',
                           layanan_list=layanan_list,
                           lokasi_list=lokasi_list)

@app.route('/admin_pesanan_detail')
def admin_pesanan_detail():
    pesanan_id = request.args.get('pesanan_id')

    if not pesanan_id:
        flash("ID Pesanan tidak ditemukan.", "danger")
        return redirect(url_for('admin_pesanan'))

    try:
        pesanan = db.pesanan.find_one({'_id': ObjectId(pesanan_id)})

        # Pengecekan jika pesanan tidak ditemukan di database
        if not pesanan:
            flash(f"Pesanan dengan ID '{pesanan_id}' tidak ditemukan.", "danger")
            return redirect(url_for('admin_pesanan'))

        # Buat map nama layanan, paket, dan lokasi berdasarkan _id
        layanan_map = {str(l['_id']): l['nama'] for l in db.layanan.find()}
        paket_map = {str(l['_id']): l['nama'] for l in db.paket.find()}
        lokasi_map = {str(l['_id']): l['nama'] for l in db.lokasi.find()}

        # Konversi ObjectId pesanan ke string untuk digunakan di URL/form
        pesanan['_id'] = str(pesanan['_id'])

        # Layanan
        layanan_id = str(pesanan.get('layanan_id', ''))
        pesanan['layanan'] = layanan_map.get(layanan_id, 'Tidak ditemukan')

        # Paket
        paket_id = str(pesanan.get('paket_id', ''))
        pesanan['paket'] = paket_map.get(paket_id, 'Tidak ditemukan')

        # Lokasi (bisa None atau kosong jika input manual)
        lokasi_id = str(pesanan.get('lokasi_id', ''))
        if lokasi_id and lokasi_id != "None":
            pesanan['lokasi'] = lokasi_map.get(lokasi_id, 'Tidak ditemukan')
        else:
            pesanan['lokasi'] = 'Lokasi pilihan sendiri' if pesanan.get('alamat_lokasi_acara') else 'Tidak tersedia'

        # Format tanggal
        if isinstance(pesanan.get('tanggal_pemesanan'), datetime):
            pesanan['tanggal_pemesanan_formatted'] = tanggal_id(pesanan['tanggal_pemesanan'])
        if isinstance(pesanan.get('tanggal_mulai_acara'), datetime):
            pesanan['tanggal_mulai_acara_formatted'] = tanggal_id(pesanan['tanggal_mulai_acara'])
        if isinstance(pesanan.get('tanggal_selesai_acara'), datetime):
            pesanan['tanggal_selesai_acara_formatted'] = tanggal_id(pesanan['tanggal_selesai_acara'])

        return render_template('admin/pesanan_detail.html', pesanan=[pesanan], current_route=request.path)

    except Exception as e:
        flash(f"Terjadi kesalahan saat mengambil detail pesanan: {e}", "danger")
        return redirect(url_for('admin_pesanan'))


@app.route('/admin_pesanan_update/<pesanan_id>', methods=['POST'])
def admin_pesanan_update(pesanan_id):
    pesanan = db.pesanan.find_one({'_id': ObjectId(pesanan_id)})

    if not pesanan:
        flash("Pesanan tidak ditemukan.", "danger")
        return redirect(url_for('admin_pesanan'))

    status = request.form.get('status_pesanan')
    catatan = request.form.get('catatan')
    link_drive = request.form.get('link_google_drive')

    def parse_currency_input(value_str):
        if value_str:
            # hapus dots dan koma, lalu convert ke int
            clean_value = value_str.replace('.', '').replace(',', '')
            try:
                return int(clean_value)
            except ValueError:
                return 0
        return 0
    
    biaya_tambah_hari = parse_currency_input(request.form.get('biaya_tambah_hari'))
    biaya_lokasi = parse_currency_input(request.form.get('biaya_lokasi'))
    biaya_transportasi = parse_currency_input(request.form.get('biaya_transportasi'))

    # Ambil harga_paket dan deposit_paket dari data pesanan yang ada
    harga_paket = pesanan.get('harga_paket', 0)
    deposit_paket = pesanan.get('deposit_paket', 0)

    # Hitung ulang total_harga dan sisa_bayar
    recalculated_total_harga = harga_paket + biaya_tambah_hari + biaya_lokasi + biaya_transportasi
    recalculated_sisa_bayar = recalculated_total_harga - deposit_paket

    update_data = {}
    if status is not None:
        update_data['status_pesanan'] = status
    if catatan is not None:
        update_data['catatan'] = catatan
    if link_drive is not None:
        update_data['link_google_drive'] = link_drive

    update_data['biaya_tambah_hari'] = biaya_tambah_hari
    update_data['biaya_lokasi'] = biaya_lokasi
    update_data['biaya_transportasi_akomodasi'] = biaya_transportasi
    update_data['total_harga'] = recalculated_total_harga
    update_data['sisa_bayar'] = recalculated_sisa_bayar

    try:
        db.pesanan.update_one({'_id': ObjectId(pesanan_id)}, {'$set': update_data})
        flash("Data pesanan berhasil diperbarui!", "success")
    except Exception as e:
        flash(f"Gagal memperbarui data pesanan: {e}", "danger")

    return redirect(url_for('admin_pesanan'))





def kirim_email_pengingat(to, subject, body):
    try:
        msg = Message(subject, recipients=[to])
        msg.body = body
        mail.send(msg)
        print(f"[SUKSES] Email terkirim ke {to}")
    except Exception as e:
        print(f"[ERROR] Gagal kirim email ke {to} | Error: {e}")

@app.route('/admin_kirim_pengingat', methods=['POST'])
def admin_kirim_pengingat():
    email = request.form['email_klien']
    status = request.form['status_pesanan']
    nama = request.form['nama_klien']
    pesanan_id_for_redirect = request.form.get('pesanan_id_for_redirect')

    # Format isi pesan
    if status == 'Belum Pemotretan':
        pesan = f"Halo {nama}, ini adalah pengingat untuk jadwal pemotretan Anda bersama Oval Photo."
    elif status == 'Sudah Pemotretan':
        pesan = f"Halo {nama}, mohon melakukan pelunasan pembayaran untuk layanan fotografi Oval Photo."
    elif status == 'Sudah Kirim File & Album':
        pesan = f"Halo {nama}, semoga Anda puas. Silakan beri ulasan mengenai layanan kami di Oval Photo :)"
    else:
        pesan = f"Halo {nama}, status pesanan Anda saat ini: {status}. Tidak ada pengingat spesifik."

    # Kirim email resmi
    kirim_email_pengingat(email, "Pengingat dari Oval Photo", pesan)

    flash("Pengingat berhasil dikirim melalui Email resmi", "success")

    if pesanan_id_for_redirect:
        return redirect(url_for('admin_pesanan', pesanan_id=pesanan_id_for_redirect))
    else:
        return redirect(url_for('admin_pesanan'))

# User - Pemesanan (GET request - tampilan form)
@app.route("/booking", methods=["GET"])
@login_required
def booking():
    paket_id = request.args.get("paket_id")

    selected_paket_id = None
    selected_layanan_id = None
    selected_layanan_nama = None
    selected_paket_nama = None
    selected_paket_harga_formatted = None
    selected_paket_deposit_formatted = None
    selected_paket_harga_raw = 0
    selected_paket_deposit_raw = 0

    lokasi_list = list(db.lokasi.find({"is_active": True}))
    for lokasi in lokasi_list:
        lokasi["_id"] = str(lokasi["_id"])

    disabled_statuses = [
        "Menunggu Konfirmasi",
        "Telah Dikonfirmasi",
        "Belum Pemotretan",
    ]

    booked_dates_cursor = db.pesanan.find(
        {"status_pesanan": {"$in": disabled_statuses}},
        {"tanggal_mulai_acara": 1, "tanggal_selesai_acara": 1, "_id": 0},
    )

    booked_date_ranges = []
    for order in booked_dates_cursor:
        start_date = order.get("tanggal_mulai_acara")
        end_date = order.get("tanggal_selesai_acara")
        if start_date and end_date:
            booked_date_ranges.append(
                {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d"),
                }
            )

    if paket_id:
        try:
            paket_data = db.paket.find_one({"_id": ObjectId(paket_id)})
            if paket_data:
                selected_paket_id = str(paket_data["_id"])
                selected_paket_nama = paket_data.get("nama")
                harga = paket_data.get("harga")
                deposit = paket_data.get("deposit")
                layanan_id = paket_data.get("layanan_id")

                if layanan_id:
                    selected_layanan_id = str(layanan_id)
                    layanan_data = db.layanan.find_one({"_id": ObjectId(layanan_id)})
                    if layanan_data:
                        selected_layanan_nama = layanan_data.get("nama")

                if harga is not None:
                    selected_paket_harga_raw = float(harga)
                    selected_paket_harga_formatted = "{:,.0f}".format(
                        selected_paket_harga_raw
                    ).replace(",", ".")
                if deposit is not None:
                    selected_paket_deposit_raw = float(deposit)
                    selected_paket_deposit_formatted = "{:,.0f}".format(
                        selected_paket_deposit_raw
                    ).replace(",", ".")
            else:
                flash(f"Paket dengan ID '{paket_id}' tidak ditemukan.", "danger")
                return redirect(
                    url_for("katalog_layanan")
                )  # Redirect if package not found
        except Exception as e:
            print(f"Error fetching package data: {e}")
            flash("Terjadi kesalahan saat memuat detail paket.", "danger")
            return redirect(url_for("katalog_layanan"))

    return render_template(
        "user/booking.html",
        selected_paket_id=selected_paket_id,
        selected_layanan_id=selected_layanan_id,
        selected_layanan_nama=selected_layanan_nama,
        selected_paket_nama=selected_paket_nama,
        selected_paket_harga=selected_paket_harga_formatted,
        selected_paket_deposit=selected_paket_deposit_formatted,
        selected_paket_harga_raw=selected_paket_harga_raw,
        selected_paket_deposit_raw=selected_paket_deposit_raw,
        lokasi_list=lokasi_list,
        booked_date_ranges=booked_date_ranges,
    )


# User - Pemesanan (POST request - submit form)
@app.route("/booking", methods=["POST"])
@login_required
def submit_booking():
    try:
        # Mendapatkan user_id dari sesi
        user_id_pemesan = session.get("user_id")
        if not user_id_pemesan:
            flash("Sesi pengguna tidak valid. Silakan login ulang.", "danger")
            return redirect(url_for("masuk"))
        layanan_id = request.form["layanan_id"]
        paket_id = request.form["paket_id"]
        nama_klien = request.form["nama_klien"]
        nama_orang_tua = request.form["nama_orang_tua"]
        email_klien = request.form[
            "email_klien"
        ]  # email yang diisi di form, bukan email login
        telepon_klien = request.form["telepon_klien"]
        instagram_klien = request.form.get("instagram_klien", "")
        facebook_klien = request.form.get("facebook_klien", "")

        jam_acara_str = request.form["jam_acara"]
        tanggal_mulai_acara_str = request.form["tanggal_mulai_acara"]
        tanggal_selesai_acara_str = request.form["tanggal_selesai_acara"]

        lokasi_luar_str = request.form["lokasi_luar"]
        lokasi_luar = True if lokasi_luar_str == "iya" else False

        lokasi_pilihan_user = request.form.get("lokasi_id")

        alamat_lokasi_manual = request.form.get("alamat_lokasi_manual", "")
        link_maps_manual = request.form.get("link_maps_manual", "")

        # Konversi tanggal dan waktu
        jam_acara = jam_acara_str
        tanggal_mulai_acara = datetime.strptime(tanggal_mulai_acara_str, "%Y-%m-%d")
        tanggal_selesai_acara = datetime.strptime(tanggal_selesai_acara_str, "%Y-%m-%d")

        # Get harga paket dan deposit dari form (hidden fields)
        harga_paket = float(request.form.get("harga_paket_dasar", "0"))
        deposit_paket = float(request.form.get("deposit_paket_dasar", "0"))

        biaya_transportasi = int(0)
        biaya_tambah_hari = int(0)
        biaya_lokasi = int(0)

        alamat_lokasi_final = None
        link_maps_final = None
        lokasi_id_db = None

        if lokasi_pilihan_user == "pilih_lokasi_sendiri":
            alamat_lokasi_final = alamat_lokasi_manual
            link_maps_final = link_maps_manual
        elif lokasi_pilihan_user:
            selected_lokasi = db.lokasi.find_one({"_id": ObjectId(lokasi_pilihan_user)})
            if selected_lokasi:
                alamat_lokasi_final = selected_lokasi.get("alamat")
                link_maps_final = selected_lokasi.get("link_maps")
                lokasi_id_db = ObjectId(lokasi_pilihan_user)
        else:
            alamat_lokasi_final = ""
            link_maps_final = ""

        recalculated_total_harga = (
            harga_paket + biaya_tambah_hari + biaya_lokasi + biaya_transportasi
        )
        recalculated_sisa_bayar = recalculated_total_harga - deposit_paket

        # Buat dokumen pesanan
        pesanan_doc = {
            "user_id_pemesan": ObjectId(user_id_pemesan),  
            "tanggal_pemesanan": datetime.utcnow(),
            "layanan_id": ObjectId(layanan_id),
            "paket_id": ObjectId(paket_id),
            "nama_klien": nama_klien,
            "nama_orang_tua": nama_orang_tua,
            "email_klien": email_klien,
            "telepon_klien": telepon_klien,
            "instagram_klien": instagram_klien,
            "facebook_klien": facebook_klien,
            "jam_acara": jam_acara,
            "tanggal_mulai_acara": tanggal_mulai_acara,
            "tanggal_selesai_acara": tanggal_selesai_acara,
            "lokasi_luar_labuhanbatu": lokasi_luar,
            "lokasi_id": lokasi_id_db,
            "alamat_lokasi_acara": alamat_lokasi_final,
            "link_maps_acara": link_maps_final,
            "surat_izin_lokasi": "Tidak ada file",
            "biaya_transportasi_akomodasi": biaya_transportasi,
            "biaya_tambah_hari": biaya_tambah_hari,
            "biaya_lokasi": biaya_lokasi,
            "harga_paket": harga_paket,
            "deposit": deposit_paket,
            "total_harga": recalculated_total_harga,
            "sisa_bayar": recalculated_sisa_bayar,
            "status_pesanan": "Menunggu Konfirmasi",
            "status_pembayaran_deposit": "Belum Bayar",
            "status_pembayaran_pelunasan": "Belum Bayar",
            "midtrans_deposit_order_id": None,
            "midtrans_pelunasan_order_id": None,
            "created_at": datetime.utcnow(),
        }

        db.pesanan.insert_one(pesanan_doc)
        flash("Pesanan berhasil dibuat!", "success")
        return redirect(url_for("ripe_menunggu_konfirmasi"))

    except Exception as e:
        print(f"Error adding order: {e}")
        flash(f"Terjadi kesalahan saat menambahkan pesanan: {e}", "danger")
        return redirect(url_for("ripe_menunggu_konfirmasi"))
 










# User - Ubah Pemesanan 
@app.route("/booking/ubah/<pesanan_id>", methods=["GET", "POST"])
@login_required
def booking_ubah(pesanan_id):
    # Ensure the logged-in user is the owner of this booking
    user_id = session.get('user_id')
    if not user_id:
        flash("Anda harus login untuk mengakses halaman ini.", "danger")
        return redirect(url_for('masuk'))

    try:
        pesanan = db.pesanan.find_one({"_id": ObjectId(pesanan_id), "user_id_pemesan": ObjectId(user_id)})
        if not pesanan:
            flash("Pesanan tidak ditemukan atau Anda tidak memiliki izin untuk mengubahnya.", "danger")
            return redirect(url_for("riwayat_pemesanan")) # Redirect to general history if not found/authorized

        # Check if the booking status allows modification (e.g., cannot modify if already in progress or completed)
        # You can define which statuses allow modification. Example: only 'Menunggu Konfirmasi'
        allowed_statuses_for_edit = ["Menunggu Konfirmasi"] # Add other statuses if allowed
        if pesanan.get("status_pesanan") not in allowed_statuses_for_edit:
            flash(f"Pesanan dengan status '{pesanan.get('status_pesanan')}' tidak dapat diubah.", "warning")
            return redirect(url_for("ripe_menunggu_konfirmasi")) # Redirect to history of that status


        # --- GET Request: Display the form with existing data ---
        if request.method == "GET":
            # Fetch related data for display
            selected_layanan = db.layanan.find_one({"_id": pesanan.get("layanan_id")})
            selected_paket = db.paket.find_one({"_id": pesanan.get("paket_id")})
            
            selected_layanan_nama = selected_layanan["nama"] if selected_layanan else "N/A"
            selected_paket_nama = selected_paket["nama"] if selected_paket else "N/A"
            
            # Format harga dan deposit for display
            selected_paket_harga_formatted = "{:,.0f}".format(pesanan.get("harga_paket", 0)).replace(",", ".")
            selected_paket_deposit_formatted = "{:,.0f}".format(pesanan.get("deposit", 0)).replace(",", ".")

            # Get all active locations for the dropdown
            lokasi_list = list(db.lokasi.find({"is_active": True}))
            for lokasi in lokasi_list:
                lokasi["_id"] = str(lokasi["_id"]) # Convert ObjectId to string for template

            # Format current booking dates for input fields (YYYY-MM-DD)
            pesanan["tanggal_mulai_acara_str"] = pesanan["tanggal_mulai_acara"].strftime("%Y-%m-%d") if isinstance(pesanan.get("tanggal_mulai_acara"), datetime) else ""
            pesanan["tanggal_selesai_acara_str"] = pesanan["tanggal_selesai_acara"].strftime("%Y-%m-%d") if isinstance(pesanan.get("tanggal_selesai_acara"), datetime) else ""

            # Fetch booked dates to disable in the calendar, excluding the current booking's dates
            disabled_statuses = [
                "Menunggu Konfirmasi",
                "Telah Dikonfirmasi",
                "Belum Pemotretan",
            ]
            booked_dates_cursor = db.pesanan.find(
                {"status_pesanan": {"$in": disabled_statuses}, "_id": {"$ne": ObjectId(pesanan_id)}},
                {"tanggal_mulai_acara": 1, "tanggal_selesai_acara": 1, "_id": 0},
            )

            booked_date_ranges = []
            for order in booked_dates_cursor:
                start_date = order.get("tanggal_mulai_acara")
                end_date = order.get("tanggal_selesai_acara")
                if start_date and end_date:
                    booked_date_ranges.append(
                        {
                            "start": start_date.strftime("%Y-%m-%d"),
                            "end": end_date.strftime("%Y-%m-%d"),
                        }
                    )

            return render_template(
                "user/booking_ubah.html",
                pesanan=pesanan,
                selected_layanan_nama=selected_layanan_nama,
                selected_paket_nama=selected_paket_nama,
                selected_paket_harga=selected_paket_harga_formatted,
                selected_paket_deposit=selected_paket_deposit_formatted,
                lokasi_list=lokasi_list,
                booked_date_ranges=booked_date_ranges
            )

        # --- POST Request: Process form submission for update ---
        elif request.method == "POST":
            # Extract data from the form
            nama_klien = request.form['nama_klien']
            nama_orang_tua = request.form['nama_orang_tua']
            email_klien = request.form['email_klien']
            telepon_klien = request.form['telepon_klien']
            instagram_klien = request.form.get('instagram_klien', '')
            facebook_klien = request.form.get('facebook_klien', '')
            jam_acara_str = request.form['jam_acara']
            tanggal_mulai_acara_str = request.form['tanggal_mulai_acara']
            tanggal_selesai_acara_str = request.form['tanggal_selesai_acara']
            lokasi_luar_str = request.form['lokasi_luar']
            lokasi_id_selected = request.form.get('lokasi_id') # This is the value from the select
            alamat_lokasi_manual = request.form.get('alamat_lokasi_manual', '')
            link_maps_manual = request.form.get('link_maps_manual', '')

            # Convert types
            lokasi_luar_labuhanbatu = True if lokasi_luar_str == 'iya' else False
            jam_acara = jam_acara_str
            tanggal_mulai_acara = datetime.strptime(tanggal_mulai_acara_str, '%Y-%m-%d')
            tanggal_selesai_acara = datetime.strptime(tanggal_selesai_acara_str, '%Y-%m-%d')

            # Determine final location details and ID to store
            final_lokasi_id = None
            final_alamat_lokasi_acara = ""
            final_link_maps_acara = ""

            if lokasi_id_selected == "pilih_lokasi_sendiri":
                final_alamat_lokasi_acara = alamat_lokasi_manual
                final_link_maps_acara = link_maps_manual
            elif lokasi_id_selected:
                selected_lokasi_data = db.lokasi.find_one({"_id": ObjectId(lokasi_id_selected)})
                if selected_lokasi_data:
                    final_lokasi_id = ObjectId(lokasi_id_selected)
                    final_alamat_lokasi_acara = selected_lokasi_data.get('alamat', '')
                    final_link_maps_acara = selected_lokasi_data.get('link_maps', '')
            # If nothing selected, keep it empty string and None for ID

            # Update the booking document
            update_data = {
                "nama_klien": nama_klien,
                "nama_orang_tua": nama_orang_tua,
                "email_klien": email_klien,
                "telepon_klien": telepon_klien,
                "instagram_klien": instagram_klien,
                "facebook_klien": facebook_klien,
                "jam_acara": jam_acara,
                "tanggal_mulai_acara": tanggal_mulai_acara,
                "tanggal_selesai_acara": tanggal_selesai_acara,
                "lokasi_luar_labuhanbatu": lokasi_luar_labuhanbatu,
                "lokasi_id": final_lokasi_id,
                "alamat_lokasi_acara": final_alamat_lokasi_acara,
                "link_maps_acara": final_link_maps_acara,
                "last_updated": datetime.utcnow() # Track when it was last updated
            }

            db.pesanan.update_one(
                {"_id": ObjectId(pesanan_id)},
                {"$set": update_data}
            )

            flash("Pesanan Anda berhasil diperbarui!", "success")
            return redirect(url_for("ripe_menunggu_konfirmasi")) # Redirect to pending confirmation


    except Exception as e:
        app.logger.error(f"Error in booking_ubah for pesanan_id {pesanan_id}: {e}", exc_info=True)
        flash(f"Terjadi kesalahan saat mengubah pesanan: {e}", "danger")
        return redirect(url_for("ripe_menunggu_konfirmasi")) # Fallback redirect on error







# User - Menunggu Konfirmasi (GET request)
@app.route('/ripe_menunggu_konfirmasi')
@login_required
def ripe_menunggu_konfirmasi():
    user_id = session.get('user_id')
    if not user_id:
        flash("Anda harus login untuk melihat riwayat pemesanan.", "warning")
        return redirect(url_for('masuk'))

    pesanan_user_list = []
    try:
        # Filter pesanan berdasarkan user_id_pemesan dan status 'Menunggu Konfirmasi'
        pesanan_cursor = db.pesanan.find({
            "user_id_pemesan": ObjectId(user_id),
            "status_pesanan": "Menunggu Konfirmasi"
        }).sort('created_at', -1)

        layanan_map = {str(l['_id']): l['nama'] for l in db.layanan.find()}
        paket_map = {str(l['_id']): l['nama'] for l in db.paket.find()}
        lokasi_map = {str(l['_id']): l['nama'] for l in db.lokasi.find()}

        for pesanan in pesanan_cursor:
            pesanan['_id'] = str(pesanan['_id'])
            layanan_id = str(pesanan.get('layanan_id', ''))
            pesanan['layanan'] = layanan_map.get(layanan_id, 'Tidak ditemukan')

            paket_id = str(pesanan.get('paket_id', ''))
            pesanan['paket'] = paket_map.get(paket_id, 'Tidak ditemukan')

            lokasi_id = str(pesanan.get('lokasi_id', ''))
            if lokasi_id and lokasi_id != "None":
                pesanan['lokasi'] = lokasi_map.get(lokasi_id, 'Tidak ditemukan')
            else:
                pesanan['lokasi'] = 'Lokasi pilihan sendiri' if pesanan.get('alamat_lokasi_acara') else 'Tidak tersedia'

            if isinstance(pesanan.get('tanggal_mulai_acara'), datetime):
                pesanan['tanggal_mulai_acara_formatted'] = tanggal_id(pesanan['tanggal_mulai_acara'])
            else:
                pesanan['tanggal_mulai_acara_formatted'] = 'N/A'
            if isinstance(pesanan.get('tanggal_selesai_acara'), datetime):
                pesanan['tanggal_selesai_acara_formatted'] = tanggal_id(pesanan['tanggal_selesai_acara'])
            else:
                pesanan['tanggal_selesai_acara_formatted'] = 'N/A'

            # Add formatted creation date for display
            if isinstance(pesanan.get('created_at'), datetime):
                pesanan['created_at_formatted'] = pesanan['created_at'].strftime('%d %b %Y %H:%M')
            else:
                pesanan['created_at_formatted'] = 'N/A'
            
            # Tambahkan status pembayaran (penting untuk tab 'Telah Dikonfirmasi')
            pesanan['status_pembayaran_deposit'] = pesanan.get('status_pembayaran_deposit', 'Belum Bayar')
            pesanan['status_pembayaran_pelunasan'] = pesanan.get('status_pembayaran_pelunasan', 'Belum Bayar')

            pesanan_user_list.append(pesanan)

        return render_template('user/ripe_menunggu_konfirmasi.html', pesanan=pesanan_user_list, current_route=request.path)

    except Exception as e:
        flash(f"Terjadi kesalahan saat mengambil riwayat pemesanan Anda: {e}", "danger")
        return render_template('user/ripe_menunggu_konfirmasi.html', pesanan=[], current_route=request.path)
    



@app.route('/batalkan_pesanan/<string:pesanan_id>', methods=['POST'])
def batalkan_pesanan(pesanan_id):
    # Query pesanan berdasarkan ID dan update status
    pesanan = db.pesanan.find_one({'_id': ObjectId(pesanan_id)})
    if pesanan:
        db.pesanan.update_one({'_id': ObjectId(pesanan_id)}, {'$set': {'status_pesanan': 'Pesanan Dibatalkan'}})
        return jsonify({'success': True})
    return jsonify({'success': False}), 404




# --- USER - Telah Dikonfirmasi (GET request) ---
@app.route('/riwayat_pemesanan')
@login_required
def riwayat_pemesanan():
    user_id = session.get('user_id')
    if not user_id:
        flash("Anda harus login untuk melihat riwayat pemesanan.", "warning")
        return redirect(url_for('masuk'))

    pesanan_user_list = []
    try:
        # Filter pesanan berdasarkan user_id_pemesan dan status 'Telah Dikonfirmasi'
        pesanan_cursor = db.pesanan.find({
            "user_id_pemesan": ObjectId(user_id),
            "status_pesanan": "Telah Dikonfirmasi"
        }).sort('created_at', -1)

        layanan_map = {str(l['_id']): l['nama'] for l in db.layanan.find()}
        paket_map = {str(l['_id']): l['nama'] for l in db.paket.find()}
        lokasi_map = {str(l['_id']): l['nama'] for l in db.lokasi.find()}

        for pesanan in pesanan_cursor:
            pesanan['_id'] = str(pesanan['_id'])
            layanan_id = str(pesanan.get('layanan_id', ''))
            pesanan['layanan'] = layanan_map.get(layanan_id, 'Tidak ditemukan')

            paket_id = str(pesanan.get('paket_id', ''))
            pesanan['paket'] = paket_map.get(paket_id, 'Tidak ditemukan')

            lokasi_id = str(pesanan.get('lokasi_id', ''))
            if lokasi_id and lokasi_id != "None":
                pesanan['lokasi'] = lokasi_map.get(lokasi_id, 'Tidak ditemukan')
            else:
                pesanan['lokasi'] = 'Lokasi pilihan sendiri' if pesanan.get('alamat_lokasi_acara') else 'Tidak tersedia'

            if isinstance(pesanan.get('tanggal_mulai_acara'), datetime):
                pesanan['tanggal_mulai_acara_formatted'] = tanggal_id(pesanan['tanggal_mulai_acara'])
            else:
                pesanan['tanggal_mulai_acara_formatted'] = 'N/A'
            if isinstance(pesanan.get('tanggal_selesai_acara'), datetime):
                pesanan['tanggal_selesai_acara_formatted'] = tanggal_id(pesanan['tanggal_selesai_acara'])
            else:
                pesanan['tanggal_selesai_acara_formatted'] = 'N/A'

            # Add formatted creation date for display
            if isinstance(pesanan.get('created_at'), datetime):
                pesanan['created_at_formatted'] = pesanan['created_at'].strftime('%d %b %Y %H:%M')
            else:
                pesanan['created_at_formatted'] = 'N/A'

            # --- TAMBAHAN PENTING UNTUK STATUS PEMBAYARAN ---
            # Mengambil status pembayaran deposit dan pelunasan dari database
            # Memberikan nilai default 'Belum Bayar' jika tidak ada di dokumen pesanan
            pesanan['status_pembayaran_deposit'] = pesanan.get('status_pembayaran_deposit', 'Belum Bayar')
            pesanan['status_pembayaran_pelunasan'] = pesanan.get('status_pembayaran_pelunasan', 'Belum Bayar')
            # --- AKHIR TAMBAHAN ---

            pesanan_user_list.append(pesanan)

        return render_template(
            "user/riwayat_pemesanan.html",
            pesanan=pesanan_user_list,
            current_route=request.path,
            MIDTRANS_CLIENT_KEY=MIDTRANS_CLIENT_KEY # Pass client key to frontend
        )

    except Exception as e:
        app.logger.error(
            f"Terjadi kesalahan saat mengambil riwayat pemesanan Anda: {e}",
            exc_info=True,
        )
        flash(
            f"Terjadi kesalahan saat mengambil riwayat pemesanan Anda. Mohon coba lagi nanti.",
            "danger",
        )
        return render_template(
            "user/riwayat_pemesanan.html",
            pesanan=[],
            current_route=request.path,
            MIDTRANS_CLIENT_KEY=MIDTRANS_CLIENT_KEY
        )





# User - Diproses (GET request)
@app.route('/ripe_diproses')
@login_required
def ripe_diproses():
    user_id = session.get('user_id')
    if not user_id:
        flash("Anda harus login untuk melihat riwayat pemesanan.", "warning")
        return redirect(url_for('masuk'))

    pesanan_user_list = []
    try:
        # Filter pesanan berdasarkan user_id_pemesan dan status yang termasuk 'diproses'
        diproses_statuses = ['Belum Pemotretan', 'Sudah Pemotretan', 'Belum Kirim File & Album']
        pesanan_cursor = db.pesanan.find({
            "user_id_pemesan": ObjectId(user_id),
            "status_pesanan": {"$in": diproses_statuses}
        }).sort('created_at', -1)

        layanan_map = {str(l['_id']): l['nama'] for l in db.layanan.find()}
        paket_map = {str(l['_id']): l['nama'] for l in db.paket.find()}
        lokasi_map = {str(l['_id']): l['nama'] for l in db.lokasi.find()}

        for pesanan in pesanan_cursor:
            pesanan['_id'] = str(pesanan['_id'])
            layanan_id = str(pesanan.get('layanan_id', ''))
            pesanan['layanan'] = layanan_map.get(layanan_id, 'Tidak ditemukan')

            paket_id = str(pesanan.get('paket_id', ''))
            pesanan['paket'] = paket_map.get(paket_id, 'Tidak ditemukan')

            lokasi_id = str(pesanan.get('lokasi_id', ''))
            if lokasi_id and lokasi_id != "None":
                pesanan['lokasi'] = lokasi_map.get(lokasi_id, 'Tidak ditemukan')
            else:
                pesanan['lokasi'] = 'Lokasi pilihan sendiri' if pesanan.get('alamat_lokasi_acara') else 'Tidak tersedia'

            if isinstance(pesanan.get('tanggal_mulai_acara'), datetime):
                pesanan['tanggal_mulai_acara_formatted'] = tanggal_id(pesanan['tanggal_mulai_acara'])
            else:
                pesanan['tanggal_mulai_acara_formatted'] = 'N/A'
            if isinstance(pesanan.get('tanggal_selesai_acara'), datetime):
                pesanan['tanggal_selesai_acara_formatted'] = tanggal_id(pesanan['tanggal_selesai_acara'])
            else:
                pesanan['tanggal_selesai_acara_formatted'] = 'N/A'

            # Add formatted creation date for display
            if isinstance(pesanan.get('created_at'), datetime):
                pesanan['created_at_formatted'] = pesanan['created_at'].strftime('%d %b %Y %H:%M')
            else:
                pesanan['created_at_formatted'] = 'N/A'
            
            # Tambahkan status pembayaran (penting untuk tab 'Telah Dikonfirmasi')
            pesanan['status_pembayaran_deposit'] = pesanan.get('status_pembayaran_deposit', 'Belum Bayar')
            pesanan['status_pembayaran_pelunasan'] = pesanan.get('status_pembayaran_pelunasan', 'Belum Bayar')

            pesanan_user_list.append(pesanan)

        return render_template('user/ripe_diproses.html', pesanan=pesanan_user_list, current_route=request.path)

    except Exception as e:
        flash(f"Terjadi kesalahan saat mengambil riwayat pemesanan Anda: {e}", "danger")
        return render_template('user/ripe_diproses.html', pesanan=[], current_route=request.path)
    


# User - Ubah Jadwal 
@app.route("/jadwal/ubah/<pesanan_id>", methods=["GET", "POST"])
@login_required
def jadwal_ubah(pesanan_id):
    # Ensure the logged-in user is the owner of this booking
    user_id = session.get('user_id')
    if not user_id:
        flash("Anda harus login untuk mengakses halaman ini.", "danger")
        return redirect(url_for('masuk'))

    try:
        pesanan = db.pesanan.find_one({"_id": ObjectId(pesanan_id), "user_id_pemesan": ObjectId(user_id)})
        if not pesanan:
            flash("Pesanan tidak ditemukan atau Anda tidak memiliki izin untuk mengubahnya.", "danger")
            return redirect(url_for("ripe_diproses")) # Redirect to general history if not found/authorized

        # Check if the booking status allows modification (e.g., cannot modify if already in progress or completed)
        # You can define which statuses allow modification. Example: only 'Menunggu Konfirmasi'
        allowed_statuses_for_edit = ['Belum Pemotretan', 'Sudah Pemotretan', 'Belum Kirim File & Album']
        if pesanan.get("status_pesanan") not in allowed_statuses_for_edit:
            flash(f"Pesanan dengan status '{pesanan.get('status_pesanan')}' tidak dapat diubah.", "warning")
            return redirect(url_for("ripe_diproses")) # Redirect to history of that status


        # --- GET Request: Display the form with existing data ---
        if request.method == "GET":
            # Fetch related data for display
            selected_layanan = db.layanan.find_one({"_id": pesanan.get("layanan_id")})
            selected_paket = db.paket.find_one({"_id": pesanan.get("paket_id")})
            
            selected_layanan_nama = selected_layanan["nama"] if selected_layanan else "N/A"
            selected_paket_nama = selected_paket["nama"] if selected_paket else "N/A"
            
            # Format harga dan deposit for display
            selected_paket_harga_formatted = "{:,.0f}".format(pesanan.get("harga_paket", 0)).replace(",", ".")
            selected_paket_deposit_formatted = "{:,.0f}".format(pesanan.get("deposit", 0)).replace(",", ".")

            # Get all active locations for the dropdown
            lokasi_list = list(db.lokasi.find({"is_active": True}))
            for lokasi in lokasi_list:
                lokasi["_id"] = str(lokasi["_id"]) # Convert ObjectId to string for template

            # Format current booking dates for input fields (YYYY-MM-DD)
            pesanan["tanggal_mulai_acara_str"] = pesanan["tanggal_mulai_acara"].strftime("%Y-%m-%d") if isinstance(pesanan.get("tanggal_mulai_acara"), datetime) else ""
            pesanan["tanggal_selesai_acara_str"] = pesanan["tanggal_selesai_acara"].strftime("%Y-%m-%d") if isinstance(pesanan.get("tanggal_selesai_acara"), datetime) else ""

            # Fetch booked dates to disable in the calendar, excluding the current booking's dates
            disabled_statuses = [
                "Menunggu Konfirmasi",
                "Telah Dikonfirmasi",
                "Belum Pemotretan",
            ]
            booked_dates_cursor = db.pesanan.find(
                {"status_pesanan": {"$in": disabled_statuses}, "_id": {"$ne": ObjectId(pesanan_id)}},
                {"tanggal_mulai_acara": 1, "tanggal_selesai_acara": 1, "_id": 0},
            )

            booked_date_ranges = []
            for order in booked_dates_cursor:
                start_date = order.get("tanggal_mulai_acara")
                end_date = order.get("tanggal_selesai_acara")
                if start_date and end_date:
                    booked_date_ranges.append(
                        {
                            "start": start_date.strftime("%Y-%m-%d"),
                            "end": end_date.strftime("%Y-%m-%d"),
                        }
                    )

            return render_template(
                "user/jadwal_ubah.html",
                pesanan=pesanan,
                selected_layanan_nama=selected_layanan_nama,
                selected_paket_nama=selected_paket_nama,
                selected_paket_harga=selected_paket_harga_formatted,
                selected_paket_deposit=selected_paket_deposit_formatted,
                lokasi_list=lokasi_list,
                booked_date_ranges=booked_date_ranges
            )

        # --- POST Request: Process form submission for update ---
        elif request.method == "POST":
            # Extract data from the form
            jam_acara_str = request.form['jam_acara']
            tanggal_mulai_acara_str = request.form['tanggal_mulai_acara']
            tanggal_selesai_acara_str = request.form['tanggal_selesai_acara']
           

            jam_acara = jam_acara_str
            tanggal_mulai_acara = datetime.strptime(tanggal_mulai_acara_str, '%Y-%m-%d')
            tanggal_selesai_acara = datetime.strptime(tanggal_selesai_acara_str, '%Y-%m-%d')

          

           
            
            update_data = {
                "jam_acara": jam_acara,
                "tanggal_mulai_acara": tanggal_mulai_acara,
                "tanggal_selesai_acara": tanggal_selesai_acara,
                "last_updated": datetime.utcnow() # Track when it was last updated
            }

            db.pesanan.update_one(
                {"_id": ObjectId(pesanan_id)},
                {"$set": update_data}
            )

            flash("Pesanan Anda berhasil diperbarui!", "success")
            return redirect(url_for("ripe_diproses")) # Redirect to pending confirmation


    except Exception as e:
        app.logger.error(f"Error in jadwal_ubah for pesanan_id {pesanan_id}: {e}", exc_info=True)
        flash(f"Terjadi kesalahan saat mengubah pesanan: {e}", "danger")
        return redirect(url_for("ripe_diproses")) # Fallback redirect on error





# User - Selesai (GET request)
@app.route('/ripe_selesai')
@login_required
def ripe_selesai():
    user_id = session.get('user_id')
    if not user_id:
        flash("Anda harus login untuk melihat riwayat pemesanan.", "warning")
        return redirect(url_for('masuk'))

    pesanan_user_list = []
    try:
        # Filter pesanan berdasarkan user_id_pemesan dan status 'Selesai' dan 'Sudah Kirim File & Album'
        selesai_statuses = ['Selesai', 'Sudah Kirim File & Album']
        pesanan_cursor = db.pesanan.find({
            "user_id_pemesan": ObjectId(user_id),
            "status_pesanan": {"$in": selesai_statuses}
        }).sort('created_at', -1)

        layanan_map = {str(l['_id']): l['nama'] for l in db.layanan.find()}
        paket_map = {str(l['_id']): l['nama'] for l in db.paket.find()}
        lokasi_map = {str(l['_id']): l['nama'] for l in db.lokasi.find()}

        for pesanan in pesanan_cursor:
            pesanan['_id'] = str(pesanan['_id'])
            layanan_id = str(pesanan.get('layanan_id', ''))
            pesanan['layanan'] = layanan_map.get(layanan_id, 'Tidak ditemukan')

            paket_id = str(pesanan.get('paket_id', ''))
            pesanan['paket'] = paket_map.get(paket_id, 'Tidak ditemukan')

            lokasi_id = str(pesanan.get('lokasi_id', ''))
            if lokasi_id and lokasi_id != "None":
                pesanan['lokasi'] = lokasi_map.get(lokasi_id, 'Tidak ditemukan')
            else:
                pesanan['lokasi'] = 'Lokasi pilihan sendiri' if pesanan.get('alamat_lokasi_acara') else 'Tidak tersedia'

            if isinstance(pesanan.get('tanggal_mulai_acara'), datetime):
                pesanan['tanggal_mulai_acara_formatted'] = tanggal_id(pesanan['tanggal_mulai_acara'])
            else:
                pesanan['tanggal_mulai_acara_formatted'] = 'N/A'
            if isinstance(pesanan.get('tanggal_selesai_acara'), datetime):
                pesanan['tanggal_selesai_acara_formatted'] = tanggal_id(pesanan['tanggal_selesai_acara'])
            else:
                pesanan['tanggal_selesai_acara_formatted'] = 'N/A'

            # Add formatted creation date for display
            if isinstance(pesanan.get('created_at'), datetime):
                pesanan['created_at_formatted'] = pesanan['created_at'].strftime('%d %b %Y %H:%M')
            else:
                pesanan['created_at_formatted'] = 'N/A'
            
            # Tambahkan status pembayaran (penting untuk tab 'Telah Dikonfirmasi')
            pesanan['status_pembayaran_deposit'] = pesanan.get('status_pembayaran_deposit', 'Belum Bayar')
            pesanan['status_pembayaran_pelunasan'] = pesanan.get('status_pembayaran_pelunasan', 'Belum Bayar')


                        
            existing_review = reviews_collection.find_one({"pesanan_id": ObjectId(pesanan['_id'])})
            pesanan['has_reviewed'] = True if existing_review else False


            pesanan_user_list.append(pesanan)

        return render_template('user/ripe_selesai.html', pesanan=pesanan_user_list, current_route=request.path)

    except Exception as e:
        flash(f"Terjadi kesalahan saat mengambil riwayat pemesanan Anda: {e}", "danger")
        return render_template('user/ripe_selesai.html', pesanan=[], current_route=request.path)


# User - Dibatalkan (GET request)
@app.route('/ripe_dibatalkan')
@login_required
def ripe_dibatalkan():
    user_id = session.get('user_id')
    if not user_id:
        flash("Anda harus login untuk melihat riwayat pemesanan.", "warning")
        return redirect(url_for('masuk'))

    pesanan_user_list = []
    try:
        # Filter pesanan berdasarkan user_id_pemesan dan status 'Gagal Dikonfirmasi' atau 'Pesanan Dibatalkan'
        dibatalkan_statuses = ['Gagal Dikonfirmasi', 'Pesanan Dibatalkan', 'Pembayaran Kadaluarsa', 'Pembayaran Dibatalkan', 'Pembayaran Ditolak']
        pesanan_cursor = db.pesanan.find({
            "user_id_pemesan": ObjectId(user_id),
            "status_pesanan": {"$in": dibatalkan_statuses}
        }).sort('created_at', -1)

        layanan_map = {str(l['_id']): l['nama'] for l in db.layanan.find()}
        paket_map = {str(l['_id']): l['nama'] for l in db.paket.find()}
        lokasi_map = {str(l['_id']): l['nama'] for l in db.lokasi.find()}

        for pesanan in pesanan_cursor:
            pesanan['_id'] = str(pesanan['_id'])
            layanan_id = str(pesanan.get('layanan_id', ''))
            pesanan['layanan'] = layanan_map.get(layanan_id, 'Tidak ditemukan')

            paket_id = str(pesanan.get('paket_id', ''))
            pesanan['paket'] = paket_map.get(paket_id, 'Tidak ditemukan')

            lokasi_id = str(pesanan.get('lokasi_id', ''))
            if lokasi_id and lokasi_id != "None":
                pesanan['lokasi'] = lokasi_map.get(lokasi_id, 'Tidak ditemukan')
            else:
                pesanan['lokasi'] = 'Lokasi pilihan sendiri' if pesanan.get('alamat_lokasi_acara') else 'Tidak tersedia'

            if isinstance(pesanan.get('tanggal_mulai_acara'), datetime):
                pesanan['tanggal_mulai_acara_formatted'] = tanggal_id(pesanan['tanggal_mulai_acara'])
            else:
                pesanan['tanggal_mulai_acara_formatted'] = 'N/A'
            if isinstance(pesanan.get('tanggal_selesai_acara'), datetime):
                pesanan['tanggal_selesai_acara_formatted'] = tanggal_id(pesanan['tanggal_selesai_acara'])
            else:
                pesanan['tanggal_selesai_acara_formatted'] = 'N/A'

            # Add formatted creation date for display
            if isinstance(pesanan.get('created_at'), datetime):
                pesanan['created_at_formatted'] = pesanan['created_at'].strftime('%d %b %Y %H:%M')
            else:
                pesanan['created_at_formatted'] = 'N/A'
            
            # Tambahkan status pembayaran (penting untuk tab 'Telah Dikonfirmasi')
            pesanan['status_pembayaran_deposit'] = pesanan.get('status_pembayaran_deposit', 'Belum Bayar')
            pesanan['status_pembayaran_pelunasan'] = pesanan.get('status_pembayaran_pelunasan', 'Belum Bayar')

            pesanan_user_list.append(pesanan)

        return render_template('user/ripe_dibatalkan.html', pesanan=pesanan_user_list, current_route=request.path)

    except Exception as e:
        flash(f"Terjadi kesalahan saat mengambil riwayat pemesanan Anda: {e}", "danger")
        return render_template('user/ripe_dibatalkan.html', pesanan=[], current_route=request.path)






















# Admin - Tim Fotografi
@app.route("/admin_timFotografi")
def admin_timFotografi():
    tim = list(db.tim.find())
    return render_template(
        "admin/timFotografi.html", tim=tim, current_route=request.path
    )


@app.route("/admin_timFotografi_tambah", methods=["GET", "POST"])
def admin_timFotografi_tambah():
    tim_exists = False

    if request.method == "POST":
        nama = request.form["nama"]
        email = request.form["email"]
        telepon = request.form["telepon"]
        peran = request.form.getlist("peran[]")
        gambar = request.files.get("gambar")

        # Cek apakah nama tim sudah ada
        existing_tim = db.tim.find_one({"nama": nama})
        if existing_tim:
            tim_exists = True
        else:
            if gambar:
                nama_file_asli = gambar.filename
                nama_file_gambar = nama_file_asli.split("/")[-1]
                file_path = f"static/images/imgTim/{nama_file_gambar}"
                gambar.save(file_path)
            else:
                nama_file_gambar = None

            doc = {
                "nama": nama,
                "email": email,
                "telepon": telepon,
                "peran": peran,
                "gambar": nama_file_gambar,
            }
            db.tim.insert_one(doc)
            return redirect(url_for("admin_timFotografi"))

    return render_template("admin/timFotografi_tambah.html", tim_exists=tim_exists)


@app.route("/check_nama_tim", methods=["POST"])
def check_nama_tim():
    data = request.json
    nama_tim = data.get("nama", "")

    # Periksa apakah nama tim sudah ada di database MongoDB
    existing_tim = db.tim.find_one(
        {"nama": {"$regex": f"^{nama_tim}$", "$options": "i"}}
    )
    if existing_tim:
        return jsonify({"exists": True})
    else:
        return jsonify({"exists": False})


@app.route("/admin_timFotografi_ubah/<tim_id>", methods=["GET", "POST"])
def admin_timFotografi_ubah(tim_id):
    tim_exists = False
    tim = db.tim.find_one({"_id": ObjectId(tim_id)})

    if not tim:
        return redirect(url_for("admin_timFotografi"))

    if request.method == "POST":
        nama = request.form["nama"]
        email = request.form["email"]
        telepon = request.form["telepon"]
        peran = request.form.getlist("peran[]")
        gambar_baru = request.files.get("gambar")

        # Cek apakah nama tim sudah ada pada tim lain
        existing_tim = db.tim.find_one({
            'nama': nama,
            '_id': {'$ne': ObjectId(tim_id)}
        })

        if existing_tim:
            tim_exists = True
        else:
            doc = {
                'nama': nama,
                'email': email,
                'telepon': telepon,
                'peran': peran,
                'gambar': tim.get('gambar')  # default ke gambar lama
            }

            # Cek apakah user mengunggah gambar baru
            if gambar_baru and gambar_baru.filename != "":
                ekstensi = os.path.splitext(gambar_baru.filename)[1]
                timestamp = str(int(time.time()))
                nama_file_gambar = f"{sanitize_filename(nama)}_{timestamp}{ekstensi}"
                file_path = os.path.join('static/images/imgTim', nama_file_gambar)
                gambar_baru.save(file_path)
                doc['gambar'] = nama_file_gambar

                # Hapus gambar lama jika ada
                old_image_filename = tim.get('gambar')
                if old_image_filename and old_image_filename != nama_file_gambar:
                    old_image_path = os.path.join('static/images/imgTim', old_image_filename)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)

            # Update tim fotografi
            db.tim.update_one({"_id": ObjectId(tim_id)}, {"$set": doc})
            return redirect(url_for("admin_timFotografi"))

        # Jika nama sudah ada pada tim lain, tetap di halaman ubah dengan pesan error
        return render_template("admin/timFotografi_ubah.html", tim=tim, tim_exists=tim_exists)

    return render_template("admin/timFotografi_ubah.html", tim=tim, tim_exists=False)


@app.route("/toggle_tim_status/<tim_id>", methods=["POST"])
def toggle_tim_status(tim_id):
    try:
        tim = db.tim.find_one({"_id": ObjectId(tim_id)})
        if tim:
            current_status = tim.get("aktif", False)  # Default ke False jika tidak ada
            new_status = not current_status
            db.tim.update_one(
                {"_id": ObjectId(tim_id)}, {"$set": {"aktif": new_status}}
            )
            return jsonify({"success": True, "new_status": new_status})
        return jsonify({"success": False, "message": "Tim tidak ditemukan"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500







# User - Tentang Kami
@app.route("/tentang-kami")
def tentang_kami():
    # Hanya mengambil tim yang statusnya 'aktif': True
    tim_aktif = list(db.tim.find({"aktif": True}))
    return render_template(
        "user/tentang_kami.html", tim=tim_aktif, current_route=request.path
    )


# FAQ

# Koleksi FAQ
koleksi_faqs = db.faqs

@app.route("/admin_faq")
def admin_faq():
    """Menampilkan daftar semua FAQ (pending dan published) untuk admin."""
    
    # Tangkap parameter _sa_status dan _sa_message dari URL
    sa_status = request.args.get('_sa_status')
    sa_message = request.args.get('_sa_message')

    try:
        # Urutkan berdasarkan status (pending di atas) dan tanggal diajukan (terbaru di atas)
        daftar_faqs = list(
            koleksi_faqs.find().sort([("status", 1), ("tanggal_diajukan", -1)])
        )
        
        # Konversi ObjectId ke string untuk setiap item FAQ
        for faq_item in daftar_faqs:
            if '_id' in faq_item:
                faq_item['_id'] = str(faq_item['_id'])

    except Exception as e:
        logging.error(f"Error fetching FAQs for admin: {e}", exc_info=True)
        daftar_faqs = [] # Pastikan faqs kosong jika ada error
        sa_status = 'error'
        sa_message = "Terjadi kesalahan saat memuat daftar FAQ."

    return render_template(
        "admin/faq.html",
        faqs=daftar_faqs,
        _sa_status=sa_status, # Teruskan ke template
        _sa_message=sa_message # Teruskan ke template
    )


@app.route("/admin_faq_tambah", methods=["GET", "POST"])
def admin_faq_tambah():
    """Menampilkan dan memproses formulir tambah FAQ manual oleh admin."""
    if request.method == "POST":
        pertanyaan = request.form["pertanyaan"].strip()
        jawaban = request.form["jawaban"].strip()

        if not pertanyaan or not jawaban:
            # Menggunakan parameter URL untuk SweetAlert
            return redirect(url_for(
                "admin_faq_tambah",
                _sa_status='error',
                _sa_message="Pertanyaan dan jawaban tidak boleh kosong.",
                # Teruskan kembali input agar form tidak kosong setelah error
                pertanyaan_input=pertanyaan,
                jawaban_input=jawaban
            ))

        # Cek apakah pertanyaan sudah ada untuk menghindari duplikasi
        faq_sudah_ada = koleksi_faqs.find_one(
            {"pertanyaan": {"$regex": pertanyaan, "$options": "i"}}
        )
        if faq_sudah_ada:
            # Menggunakan parameter URL untuk SweetAlert
            return redirect(url_for(
                "admin_faq_tambah",
                _sa_status='warning', # Ganti ke 'warning' untuk duplikasi
                _sa_message="Pertanyaan ini sudah ada.",
                # Teruskan kembali input
                pertanyaan_input=pertanyaan,
                jawaban_input=jawaban
            ))

        dokumen_faq_baru = {
            "nama_pengaju": "Admin",
            "email_pengaju": "",
            "pertanyaan": pertanyaan,
            "jawaban": jawaban,
            "status": "published",
            "is_active": True,
            "tanggal_diajukan": datetime.now(),
            "tanggal_diperbarui": datetime.now(),
        }
        try:
            koleksi_faqs.insert_one(dokumen_faq_baru)
            # Menggunakan parameter URL untuk SweetAlert
            return redirect(url_for(
                "admin_faq",
                _sa_status='success',
                _sa_message="FAQ berhasil ditambahkan!"
            ))
        except Exception as e:
            logging.error(f"Error saving new FAQ: {e}", exc_info=True)
            # Menggunakan parameter URL untuk SweetAlert
            return redirect(url_for(
                "admin_faq_tambah",
                _sa_status='error',
                _sa_message="Terjadi kesalahan saat menambahkan FAQ.",
                # Teruskan kembali input
                pertanyaan_input=pertanyaan,
                jawaban_input=jawaban
            ))

    # Untuk GET request, ambil data input dari URL jika ada (setelah redirect error)
    pertanyaan_input = request.args.get('pertanyaan_input', '')
    jawaban_input = request.args.get('jawaban_input', '')
    
    return render_template(
        "admin/faq_tambah.html",
        pertanyaan_input=pertanyaan_input,
        jawaban_input=jawaban_input
    )


@app.route("/admin_faq_ubah/<id_faq>", methods=["GET", "POST"])
def admin_faq_ubah(id_faq):
    try:
        faq_untuk_diubah = koleksi_faqs.find_one({"_id": ObjectId(id_faq)})
        if not faq_untuk_diubah:
            # Menggunakan parameter URL untuk SweetAlert
            return redirect(url_for(
                "admin_faq",
                _sa_status='error',
                _sa_message="FAQ tidak ditemukan."
            ))
        # Konversi ObjectId ke string untuk digunakan di template
        faq_untuk_diubah['_id'] = str(faq_untuk_diubah['_id'])
    except Exception as e:
        # Menggunakan parameter URL untuk SweetAlert
        return redirect(url_for(
            "admin_faq",
            _sa_status='error',
            _sa_message=f"ID FAQ tidak valid: {e}"
        ))

    if request.method == "POST":
        jawaban_baru = request.form["jawaban"].strip()
        pertanyaan_baru = request.form["pertanyaan"].strip()

        if not pertanyaan_baru or not jawaban_baru:
            # Menggunakan parameter URL untuk SweetAlert
            # Tetap di halaman ubah dengan pesan error
            return redirect(url_for(
                "admin_faq_ubah",
                id_faq=id_faq, # Penting agar tetap di halaman ubah yang sama
                _sa_status='error',
                _sa_message="Pertanyaan dan jawaban tidak boleh kosong."
            ))

        # Cek duplikasi pertanyaan, kecuali FAQ yang sedang diubah
        existing_faq_with_same_question = koleksi_faqs.find_one({
            "pertanyaan": {"$regex": pertanyaan_baru, "$options": "i"},
            "_id": {"$ne": ObjectId(id_faq)} # Pastikan bukan FAQ yang sedang diubah
        })
        if existing_faq_with_same_question:
            return redirect(url_for(
                "admin_faq_ubah",
                id_faq=id_faq,
                _sa_status='warning',
                _sa_message="Pertanyaan ini sudah ada di FAQ lain."
            ))

        # Update FAQ di database
        try:
            koleksi_faqs.update_one(
                {"_id": ObjectId(id_faq)},
                {
                    "$set": {
                        "pertanyaan": pertanyaan_baru,
                        "jawaban": jawaban_baru,
                        "status": "published",
                        "tanggal_diperbarui": datetime.now(),
                    }
                },
            )
            # Menggunakan parameter URL untuk SweetAlert
            return redirect(url_for(
                "admin_faq",
                _sa_status='success',
                _sa_message="FAQ berhasil diperbarui!"
            ))
        except Exception as e:
            logging.error(f"Error updating FAQ ID {id_faq}: {e}", exc_info=True)
            return redirect(url_for(
                "admin_faq_ubah",
                id_faq=id_faq,
                _sa_status='error',
                _sa_message="Terjadi kesalahan saat memperbarui FAQ."
            ))

    # Untuk GET request (menampilkan form)
    return render_template("admin/faq_ubah.html", faq=faq_untuk_diubah)


@app.route("/admin_faq_toggle_status/<id_faq>", methods=["POST"])
def admin_faq_toggle_status(id_faq):
    """Mengubah status aktif/nonaktif FAQ."""
    try:
        faq = koleksi_faqs.find_one({"_id": ObjectId(id_faq)})
        if not faq:
            return jsonify({"success": False, "message": "FAQ tidak ditemukan."}), 404

        new_is_active = not faq.get("is_active", False) # Ambil status aktif saat ini
        new_status_text = "published" if new_is_active else "pending" # Sesuaikan status FAQ

        koleksi_faqs.update_one(
            {"_id": ObjectId(id_faq)},
            {"$set": {
                "is_active": new_is_active,
                "status": new_status_text, # Update status juga jika perlu
                "tanggal_diperbarui": datetime.now()
            }},
        )
        return jsonify(
            {
                "success": True,
                "new_is_active": new_is_active,
                "message": "Status berhasil diperbarui.",
            }
        )
    except Exception as e:
        logging.error(f"Error toggling FAQ status for ID {id_faq}: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {e}"}), 500



#FAQ - User
@app.route("/faqbb")
def faq_user():
    """Menampilkan daftar FAQ yang berstatus 'published' dan 'aktif' untuk user."""
    daftar_faqs = list(
        koleksi_faqs.find({"status": "published", "is_active": True}).sort(
            "tanggal_diperbarui", -1
        )
    )
    return render_template("user/faq.html", faqs=daftar_faqs)


@app.route('/formfaq', methods=['GET', 'POST'])
def form_faq_user():
    """Menampilkan dan memproses formulir pertanyaan dari user."""
    if request.method == 'POST':
        print("Menerima request POST untuk formfaq.")

        nama_pengaju = request.form.get('nama_klien')
        email_pengaju = request.form.get('email')
        pertanyaan = request.form.get('pertanyaan_user')

        print(f"Data form diterima: Nama='{nama_pengaju}', Email='{email_pengaju}', Pertanyaan='{pertanyaan}'")

        if not nama_pengaju or not email_pengaju or not pertanyaan:
            print("Validasi Gagal: Ada kolom yang kosong.")
            # Ubah flash menjadi parameter untuk SweetAlert
            return redirect(url_for('form_faq_user',
                                    _sa_status='error',
                                    _sa_message='Harap lengkapi semua kolom yang wajib diisi.',
                                    nama_klien=nama_pengaju, # Teruskan input kembali
                                    email=email_pengaju,
                                    pertanyaan_user=pertanyaan))

        # Cek format email dasar
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email_pengaju):
            print("Validasi Gagal: Format email tidak valid.")
            # Ubah flash menjadi parameter untuk SweetAlert
            return redirect(url_for('form_faq_user',
                                    _sa_status='error',
                                    _sa_message='Format email tidak valid.',
                                    nama_klien=nama_pengaju, # Teruskan input kembali
                                    email=email_pengaju,
                                    pertanyaan_user=pertanyaan))

        try:
            dokumen_faq_baru = {
                "nama_pengaju": nama_pengaju,
                "email_pengaju": email_pengaju,
                "pertanyaan": pertanyaan,
                "jawaban": "", # Kosongkan karena masih pending
                "status": "pending",
                "is_active": False, # Default nonaktif saat pertama kali diajukan oleh user
                "tanggal_diajukan": datetime.now(),
                "tanggal_diperbarui": datetime.now()
            }
            koleksi_faqs.insert_one(dokumen_faq_baru)
            print("FAQ user berhasil disimpan dengan ID:", dokumen_faq_baru.get('_id'))
            
            # Redirect ke halaman FAQ utama atau halaman lain dengan pesan sukses SweetAlert
            return redirect(url_for('faq_user', # Menggunakan faq_user yang sebelumnya Anda perbaiki
                                    _sa_status='success',
                                    _sa_message='Pertanyaan Anda berhasil dikirim! Harap tunggu 1x24 jam untuk mendapatkan jawaban.'))
        except Exception as e:
            print(f"Error saat menyimpan FAQ ke database: {e}")
            # Ubah flash menjadi parameter untuk SweetAlert
            return redirect(url_for('form_faq_user',
                                    _sa_status='error',
                                    _sa_message='Terjadi kesalahan saat mengirim pertanyaan. Silakan coba lagi.',
                                    nama_klien=nama_pengaju, # Teruskan input kembali
                                    email=email_pengaju,
                                    pertanyaan_user=pertanyaan))

    print("Menerima request GET untuk formfaq.")
    # Ambil data_input dari URL jika ada (setelah redirect dengan error)
    data_input = {
        'nama_klien': request.args.get('nama_klien', ''),
        'email': request.args.get('email', ''),
        'pertanyaan_user': request.args.get('pertanyaan_user', '')
    }
    return render_template('user/faq_form.html', data_input=data_input)





@app.route("/jadwal")
def jadwal():
    return render_template("user/jadwal.html")


@app.route("/pembayaran")
def pembayaran():
    return render_template("user/pembayaran.html")


# User - Ulasan
@app.route("/ulasan/form/<pesanan_id>")
@login_required
def formulasan(pesanan_id):
    user_id = session['user_id']
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash("Pengguna tidak ditemukan.", "danger")
        return redirect(url_for('ripe_selesai'))

    pesanan = db.pesanan.find_one({"_id": ObjectId(pesanan_id), "user_id_pemesan": ObjectId(user_id)})
    if not pesanan:
        flash("Pemesanan tidak ditemukan atau Anda tidak memiliki izin untuk mengulas pemesanan ini.", "danger")
        return redirect(url_for('ripe_selesai'))

    existing_review = reviews_collection.find_one({"pesanan_id": ObjectId(pesanan_id)})
    if existing_review:
        flash("Anda sudah memberikan ulasan untuk pemesanan ini.", "info")
        return redirect(url_for('ulasan'))

    full_name = user.get('full_name', '')
    masked_full_name = mask_name(full_name)
    profile_picture_url = user.get('profile_picture_url', DEFAULT_GCS_PROFILE_PIC_URL)

    layanan = db.layanan.find_one({"_id": pesanan['layanan_id']})
    paket = db.paket.find_one({"_id": pesanan['paket_id']})

    layanan_nama = layanan.get('nama', 'Layanan Tidak Ditemukan') if layanan else 'Layanan Tidak Ditemukan'
    paket_nama = paket.get('nama', 'Paket Tidak Ditemukan') if paket else 'Paket Tidak Ditemukan'
    
    # === PERUBAHAN DI SINI ===
    # Membuat format string yang baru
    service_package_string = f"Layanan {layanan_nama} - Paket {paket_nama}"

    booking_date = pesanan.get('tanggal_mulai_acara', datetime.now())
    formatted_booking_date = booking_date.strftime("%d/%m/%Y")

    return render_template(
        "user/ulasan_form.html",
        pesanan_id=pesanan_id,
        user_name=masked_full_name,
        profile_pic=profile_picture_url,
        service_package=service_package_string,  # Menggunakan format baru
        review_date=formatted_booking_date
    )


# NEW: API to Submit Review
@app.route("/api/ulasan/submit", methods=["POST"])
@login_required
def api_submit_ulasan():
    user_id = session['user_id']
    data = request.get_json()
    pesanan_id = data.get('pesanan_id')
    rating = data.get('rating')
    comment = data.get('comment')

    if not pesanan_id or not rating or not comment:
        return jsonify({"success": False, "message": "Rating, komentar, dan ID pemesanan harus diisi."}), 400

    try:
        # Validate pesanan_id and ensure user owns it
        pesanan = db.pesanan.find_one({"_id": ObjectId(pesanan_id), "user_id_pemesan": ObjectId(user_id)})
        if not pesanan:
            return jsonify({"success": False, "message": "Pemesanan tidak valid atau Anda tidak memiliki izin untuk mengulasnya."}), 403

        # Check if a review already exists for this order
        existing_review = reviews_collection.find_one({"pesanan_id": ObjectId(pesanan_id)})
        if existing_review:
            return jsonify({"success": False, "message": "Anda sudah memberikan ulasan untuk pemesanan ini."}), 409

        # Get service and package details for review storage
        layanan = db.layanan.find_one({"_id": pesanan['layanan_id']})
        paket = db.paket.find_one({"_id": pesanan['paket_id']})
        
        layanan_name = layanan.get('nama', 'Tidak Diketahui') if layanan else 'Tidak Diketahui'
        paket_name = paket.get('nama', 'Tidak Diketahui') if paket else 'Tidak Diketahui'

        review_data = {
            "user_id": ObjectId(user_id),
            "pesanan_id": ObjectId(pesanan_id),
            "rating": int(rating),
            "comment": comment,
            "layanan_id": pesanan['layanan_id'],
            "paket_id": pesanan['paket_id'],
            "service_package_name": f"{layanan_name} - {paket_name}", # Store combined name for quick display
            "created_at": datetime.now()
        }
        reviews_collection.insert_one(review_data)

        # Optionally, update the pesanan to mark it as reviewed
        db.pesanan.update_one(
            {"_id": ObjectId(pesanan_id)},
            {"$set": {"reviewed": True}}
        )

        return jsonify({"success": True, "message": "Ulasan berhasil dikirimkan!"}), 200

    except Exception as e:
        logging.error(f"Error submitting review: {e}")
        return jsonify({"success": False, "message": f"Gagal menyimpan ulasan: {e}"}), 500

# NEW: Kumpulan Ulasan (All Reviews) Page
@app.route("/ulasan")
def ulasan():
    # Mengurutkan ulasan terbaru di paling atas
    all_reviews = list(reviews_collection.find().sort('created_at', -1)) 
    processed_reviews = []

    for review in all_reviews:
        user = users_collection.find_one({"_id": review['user_id']})
        
        # === PERUBAHAN DIMULAI DI SINI ===
        nama_layanan = "Tidak Diketahui"
        nama_paket = "Tidak Diketahui"

        # Ambil nama layanan berdasarkan layanan_id dari review
        if 'layanan_id' in review:
            layanan = db.layanan.find_one({"_id": review['layanan_id']})
            if layanan:
                nama_layanan = layanan.get('nama', nama_layanan)
        
        # Ambil nama paket berdasarkan paket_id dari review
        if 'paket_id' in review:
            paket = db.paket.find_one({"_id": review['paket_id']})
            if paket:
                nama_paket = paket.get('nama', nama_paket)

        # Bangun string format baru
        service_package_string = f"Layanan {nama_layanan} - Paket {nama_paket}"
        # === PERUBAHAN SELESAI DI SINI ===

        masked_name = mask_name(user.get('full_name', '')) if user else 'Pengguna Anonim'
        profile_pic_url = user.get('profile_picture_url', DEFAULT_GCS_PROFILE_PIC_URL) if user else DEFAULT_GCS_PROFILE_PIC_URL
        formatted_date = tanggal_id(review.get('created_at', datetime.now()))

        processed_reviews.append({
            '_id': str(review['_id']),
            'user_name': masked_name,
            'profile_pic': profile_pic_url,
            'review_date': formatted_date,
            'rating': review['rating'],
            'service_package': service_package_string, # Menggunakan format baru
            'comment': review['comment']
        })
    
    return render_template("user/ulasan.html", reviews=processed_reviews)

# NEW: API to fetch reviews for homepage testimonial slider
@app.route("/api/reviews")
def api_get_reviews():
    try:
        latest_reviews = list(db.reviews.find().sort('created_at', -1).limit(10)) # Adjust limit as needed
        processed_reviews = []
        for review in latest_reviews:
            user = db.users.find_one({"_id": review['user_id']})
            if user:
                processed_reviews.append({
                    "name": mask_name(user.get('full_name', '')),
                    "date": review['created_at'].strftime("%d/%m/%Y"),
                    "stars": review['rating'],
                    "package": review.get('service_package_name', 'Layanan/Paket Tidak Ditemukan'),
                    "text": review['comment'],
                    "imgSrc": user.get('profile_picture_url', DEFAULT_GCS_PROFILE_PIC_URL),
                    "imgAlt": f"Foto profil {user.get('full_name', '')}"
                })
        return jsonify(processed_reviews)
    except Exception as e:
        logging.error(f"Error fetching reviews for API: {e}")
        return jsonify([]), 500 # Return empty array and 500 status on error




@app.route("/kontak")
def kontak():
    return render_template("user/kontak.html")






# Login User
@app.route("/masuk")
def masuk():
    return render_template("user/login_user.html")


@app.route("/daftar")
def daftar():
    return render_template("user/daftar.html")


@app.route("/lupa_kataSandi")
def lupa_kataSandi():
    return render_template("user/lupa_kataSandi.html")


@app.route("/reset_password/<token>")
def reset_password(token):
    try:
        payload = jwt.decode(token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
        email = payload.get("email")
        exp = payload.get("exp")

        if datetime.now().timestamp() > exp:
            return render_template(
                "user/reset_password.html",
                message="Tautan reset password sudah kadaluarsa. Silakan coba lagi.",
                error=True,
            )

        user = users_collection.find_one({"email": email})
        if not user:
            return render_template(
                "user/reset_password.html",
                message="Pengguna tidak ditemukan.",
                error=True,
            )

        return render_template("user/reset_password.html", token=token, email=email)
    except jwt.ExpiredSignatureError:
        return render_template(
            "user/reset_password.html",
            message="Tautan reset password sudah kadaluarsa. Silakan coba lagi.",
            error=True,
        )
    except jwt.InvalidTokenError:
        return render_template(
            "user/reset_password.html",
            message="Tautan reset password tidak valid.",
            error=True,
        )
    except Exception as e:
        print(f"Error accessing reset password page: {e}")
        return render_template(
            "user/reset_password.html",
            message="Terjadi kesalahan. Silakan coba lagi.",
            error=True,
        )


# --- API Routes user ---
@app.route('/api/daftar', methods=['POST'])
def api_daftar():
    """API untuk pendaftaran pengguna biasa."""
    data = request.get_json()
    full_name = data.get('namalengkap')
    username = data.get('username')
    email = data.get('alamatemail')
    password = data.get('password')
    konfirpassword = data.get('konfirpassword')

    if not all([full_name, username, email, password, konfirpassword]):
        return jsonify({"success": False, "message": "Semua field harus diisi."}), 400

    if not is_valid_email(email):
        return jsonify({"success": False, "message": "Format email tidak valid."}), 400

    if password != konfirpassword:
        return jsonify({"success": False, "message": "Konfirmasi kata sandi tidak cocok."}), 400

    if len(password) < 8:
        return jsonify({"success": False, "message": "Kata sandi harus minimal 8 karakter."}), 400

    if users_collection.find_one({"username": username}):
        return jsonify({"success": False, "message": "Nama pengguna sudah terdaftar."}), 409
    if users_collection.find_one({"email": email}):
        return jsonify({"success": False, "message": "Email sudah terdaftar."}), 409

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    try:
        users_collection.insert_one({
            "full_name": full_name,
            "username": username,
            "email": email,
            "password_hash": hashed_password,
            "created_at": datetime.now(),
            "profile_picture_url":  "https://storage.googleapis.com/a1aa/image/10b4ac45-2b8b-450f-888c-bd7182757e8a.jpg", # Default profile picture for general users
            "role": "user" # Default role for general users
        })
        return jsonify({"success": True, "message": "Pendaftaran berhasil! Silakan masuk."}), 201
    except Exception as e:
        print(f"Error during registration: {e}")
        return jsonify({"success": False, "message": "Terjadi kesalahan saat pendaftaran. Silakan coba lagi."}), 500

@app.route('/api/masuk', methods=['POST'])
def api_masuk():
    """API untuk login pengguna biasa."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "Nama pengguna dan kata sandi harus diisi."}), 400

    user = users_collection.find_one({"username": username})

    if user and check_password_hash(user['password_hash'], password):
        # Pengguna biasa tidak bisa login ke dashboard admin/pemilik dari sini
        if user.get('role') in ['admin', 'pemilik']:
            return jsonify({"success": False, "message": "Akun ini tidak dapat login melalui halaman ini. Silakan gunakan halaman login yang sesuai."}), 403

        session['user_id'] = str(user['_id'])
        session['username'] = user['username']
        session['full_name'] = user.get('full_name', '')
        session['email'] = user.get('email', '')
        # Pastikan profile_picture_url di-set, jika tidak ada, gunakan default_url
        session['profile_picture_url'] = user.get('profile_picture_url') if user.get('profile_picture_url') else DEFAULT_GCS_PROFILE_PIC_URL
        session['role'] = user.get('role', 'user') # Store role in session, default to 'user'

        return jsonify({"success": True, "message": "Login berhasil!"}), 200
    else:
        return jsonify({"success": False, "message": "Nama pengguna atau kata sandi salah."}), 401



@app.route("/api/lupa_kataSandi", methods=["POST"])
def api_lupa_kataSandi():
    data = request.get_json()
    email_dest = data.get("email")

    if not email_dest:
        return jsonify({"success": False, "message": "Email harus diisi."}), 400

    user = users_collection.find_one({"email": email_dest})

    if not user:
        return jsonify({"success": False, "message": "Email tidak terdaftar."}), 404

    user_display_name = user.get("full_name", user.get("username", "Pengguna"))

    payload = {
        "email": email_dest,
        "exp": datetime.utcnow()
        + timedelta(minutes=app.config["PASSWORD_RESET_TIMEOUT_MINUTES"]),
    }
    token = jwt.encode(payload, app.config["JWT_SECRET_KEY"], algorithm="HS256")

    reset_link = url_for("reset_password", token=token, _external=True)

    try:
        msg = Message(
            "Ubah Kata Sandi Akun Oval Photo Anda",
            sender=app.config["MAIL_DEFAULT_SENDER"],
            recipients=[email_dest],
        )

        msg.html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: sans-serif;
                    line-height: 1.6;
                    color: #black;
                }}
                p {{ margin-bottom: 1em; }}
                strong {{ font-weight: bold; }}
                a {{
                    color: #F7BF52;
                    text-decoration: none;
                    font-weight: bold;
                }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <p style="font-weight: bold; font-size: 1.2em;">Halo, {user_display_name}!</p>
            <p>Kami baru saja menerima permintaan untuk mengubah kata sandi akun kamu. Jika kamu mengajukan permintaan ini, kamu dapat mengklik tautan di bawah ini untuk mengubah kata sandi kamu.</p>
            <p><a href="{reset_link}">Klik di sini untuk mengubah kata sandi kamu</a></p>
            <p>Tautan ini akan kadaluarsa dalam {app.config['PASSWORD_RESET_TIMEOUT_MINUTES']} menit, jadi pastikan untuk menggunakannya sebelum waktu habis. Jika kamu tidak mengajukan permintaan untuk mengubah kata sandi, kamu bisa mengabaikan email ini.</p>
            <p>Terima kasih,</p>
            <p style="font-weight: bold;">Oval Photo</p>
        </body>
        </html>
        """

        mail.send(msg)
        print(
            f"--- Email reset password berhasil dikirim ke {email_dest} ({user_display_name}) ---"
        )
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Oval Photo telah mengirimkan tautan untuk mengubah atau mereset password yang dikirimkan melalui email.",
                }
            ),
            200,
        )
    except Exception as e:
        print(f"Error sending email: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Terjadi kesalahan saat mengirim email reset password. Silakan coba lagi nanti.",
                }
            ),
            500,
        )


@app.route('/api/reset_password', methods=['POST'])
def api_reset_password():
    data = request.get_json()
    token = data.get('token')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    if not all([token, new_password, confirm_password]):
        return jsonify({"success": False, "message": "Semua field harus diisi."}), 400

    if new_password != confirm_password:
        return jsonify({"success": False, "message": "Kata sandi baru dan konfirmasi tidak cocok."}), 400

    if len(new_password) < 8:
        return jsonify({"success": False, "message": "Kata sandi harus minimal 8 karakter."}), 400

    try:
        payload = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
        email = payload.get('email')

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "message": "Pengguna tidak ditemukan."}), 404

        hashed_new_password = generate_password_hash(new_password, method='pbkdf2:sha256')
        users_collection.update_one(
            {"email": email},
            {"$set": {"password_hash": hashed_new_password}}
        )
        return jsonify({"success": True, "message": "Kata sandi Anda berhasil diubah. Silakan masuk dengan kata sandi baru Anda."}), 200

    except jwt.ExpiredSignatureError:
        return jsonify({"success": False, "message": "Tautan reset password sudah kadaluarsa. Silakan coba lagi."}), 401
    except jwt.InvalidTokenError:
        return jsonify({"success": False, "message": "Tautan reset password tidak valid."}), 401
    except Exception as e:
        print(f"Error during password reset: {e}")
        return jsonify({"success": False, "message": "Terjadi kesalahan saat mengubah kata sandi. Silakan coba lagi."}), 500



@app.route('/logout')
def logout():
    # Simpan role sebelum menghapus sesi
    last_role = session.get('role', 'user') # Dapatkan role terakhir, default 'user'

    session.clear() # Hapus semua data sesi
    flash("Anda telah logout.", "info")

    if last_role == 'pemilik':
        return redirect(url_for('pemilik_login_page'))
    elif last_role == 'admin':
        return redirect(url_for('admin_login'))
    else: # Default untuk 'user' atau jika role tidak dikenal
        return redirect(url_for('masuk'))


# PROFIL USER
# --- API Get Profile ---
@app.route("/api/profil/update", methods=["POST"])
@login_required
def api_update_profil():
    user_id = session["user_id"]
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        print(f"DEBUG: User with ID {user_id} not found in DB.")  # Tambahkan ini
        return jsonify({"success": False, "message": "Pengguna tidak ditemukan."}), 404

    data = request.form
    full_name = data.get("name")
    username = data.get("username")
    email = data.get("email")
    photo = request.files.get("photo")

    print(f"DEBUG: Received update request for user {user_id}")  # Tambahkan ini
    print(
        f"DEBUG: Name: {full_name}, Username: {username}, Email: {email}"
    )  # Tambahkan ini

    if photo:
        print(f"DEBUG: Photo file received: {photo.filename}")  # Tambahkan ini
        if photo.filename == "":
            print("DEBUG: No filename provided for photo.")  # Tambahkan ini
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Tidak ada file yang dipilih untuk diunggah.",
                    }
                ),
                400,
            )
        if not allowed_file(photo.filename):
            print(
                f"DEBUG: File extension not allowed: {photo.filename}"
            )  # Tambahkan ini
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Format file tidak didukung. Gunakan PNG, JPG, JPEG, atau GIF.",
                    }
                ),
                400,
            )

        filename = secure_filename(f"{user_id}_{int(time.time())}_{photo.filename}")
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

        # DEBUG: Cek apakah folder upload benar-benar ada dan bisa ditulis
        if not os.path.exists(app.config["UPLOAD_FOLDER"]):
            print(
                f"DEBUG ERROR: UPLOAD_FOLDER does not exist: {app.config['UPLOAD_FOLDER']}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Folder penyimpanan tidak ditemukan di server.",
                    }
                ),
                500,
            )
        if not os.access(app.config["UPLOAD_FOLDER"], os.W_OK):
            print(
                f"DEBUG ERROR: UPLOAD_FOLDER is not writable: {app.config['UPLOAD_FOLDER']}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Folder penyimpanan tidak dapat ditulis.",
                    }
                ),
                500,
            )

        try:
            photo.save(filepath)
            print(f"DEBUG: Photo saved to: {filepath}")  # Tambahkan ini
            updates = {}  # Pastikan updates diinisialisasi
            updates["profile_picture_url"] = f"/gambar_profil_user/{filename}"
            print(
                f"DEBUG: Setting profile_picture_url to: {updates['profile_picture_url']}"
            )  # Tambahkan ini
        except Exception as e:
            print(f"DEBUG ERROR: Error saving image: {e}")  # Tambahkan ini
            return (
                jsonify({"success": False, "message": "Gagal menyimpan foto profil."}),
                500,
            )
    else:
        print("DEBUG: No photo file provided.")  # Tambahkan ini
        updates = {}  # Pastikan updates diinisialisasi untuk kasus tanpa foto

    # ... (bagian validasi nama, username, email seperti sebelumnya) ...
    if full_name and full_name != user.get("full_name"):
        updates["full_name"] = full_name
    if email and email != user.get("email"):
        if not is_valid_email(email):
            return (
                jsonify({"success": False, "message": "Format email tidak valid."}),
                400,
            )
        if users_collection.find_one(
            {"email": email, "_id": {"$ne": ObjectId(user_id)}}
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Email sudah terdaftar oleh pengguna lain.",
                    }
                ),
                409,
            )
        updates["email"] = email
    if username and username != user.get("username"):
        if users_collection.find_one(
            {"username": username, "_id": {"$ne": ObjectId(user_id)}}
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Username sudah digunakan oleh pengguna lain.",
                    }
                ),
                409,
            )
        updates["username"] = username

    if updates:
        print(f"DEBUG: Updating DB with: {updates}")  # Tambahkan ini
        try:
            users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
            updated_user = users_collection.find_one({"_id": ObjectId(user_id)})
            session["full_name"] = updated_user.get("full_name", "")
            session["username"] = updated_user.get("username", "")
            session["email"] = updated_user.get("email", "")
            session["profile_picture_url"] = (
                updated_user.get("profile_picture_url", "")
                or "/static/default_profile_pic.png"
            )
            print(
                f"DEBUG: Session profile_picture_url after update: {session['profile_picture_url']}"
            )  # Tambahkan ini
            return (
                jsonify({"success": True, "message": "Profil berhasil diperbarui."}),
                200,
            )
        except Exception as e:
            print(
                f"DEBUG ERROR: Error updating profile in database: {e}"
            )  # Tambahkan ini
            return (
                jsonify({"success": False, "message": "Gagal memperbarui profil."}),
                500,
            )
    else:
        print("DEBUG: No updates to perform (no changes detected).")  # Tambahkan ini
        return (
            jsonify(
                {"success": True, "message": "Tidak ada perubahan yang dilakukan."}
            ),
            200,
        )


# ... (pastikan juga di bagian api_get_profil) ...
@app.route("/api/profil", methods=["GET"])
@login_required
def api_get_profil():
    user_id = session["user_id"]
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if user:
        profile_pic_url = (
            user.get("profile_picture_url", "")
            or "https://storage.googleapis.com/a1aa/image/10b4ac45-2b8b-450f-888c-bd7182757e8a.jpg"
        )
        print(
            f"DEBUG: Sending profile data for {user_id}, photo_url: {profile_pic_url}"
        )
        return (
            jsonify(
                {
                    "success": True,
                    "full_name": user.get("full_name", ""),
                    "username": user.get("username", ""),
                    "email": user.get("email", ""),
                    "profile_picture_url": profile_pic_url,
                }
            ),
            200,
        )
    else:
        print(f"DEBUG: User {user_id} not found when fetching profile.")
        return jsonify({"success": False, "message": "Pengguna tidak ditemukan."}), 404


# --- API untuk Menghapus Foto Profil ---
@app.route("/api/profil/delete_photo", methods=["POST"])
@login_required
def api_delete_profile_photo():
    user_id = session["user_id"]
    user = users_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        return jsonify({"success": False, "message": "Pengguna tidak ditemukan."}), 404

    current_photo_url = user.get("profile_picture_url")

    # Periksa apakah foto saat ini adalah foto default GCS atau kosong
    if not current_photo_url or current_photo_url == DEFAULT_GCS_PROFILE_PIC_URL:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Tidak ada foto profil yang dapat dihapus.",
                }
            ),
            400,
        )

    # Ekstrak nama file dari URL
    # URL contoh: /gambar_profil_user/some_filename.png
    # Kita hanya perlu 'some_filename.png'
    filename_from_url = os.path.basename(current_photo_url)
    filepath_to_delete = os.path.join(app.config["UPLOAD_FOLDER"], filename_from_url)

    print(f"DEBUG: Mencoba menghapus file: {filepath_to_delete}")

    # Hapus file fisik dari server
    try:
        if os.path.exists(filepath_to_delete):
            os.remove(filepath_to_delete)
            print(f"DEBUG: File {filepath_to_delete} berhasil dihapus.")
        else:
            print(
                f"DEBUG: File {filepath_to_delete} tidak ditemukan, mungkin sudah dihapus atau URL salah."
            )
            # Kita tetap lanjutkan update DB meskipun file tidak ditemukan, anggap saja sudah tidak ada
    except Exception as e:
        print(f"DEBUG ERROR: Gagal menghapus file {filepath_to_delete}: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Terjadi kesalahan saat menghapus file: {e}",
                }
            ),
            500,
        )

    # Perbarui database dan sesi
    try:
        users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {"profile_picture_url": DEFAULT_GCS_PROFILE_PIC_URL}
            },  # Set kembali ke default GCS
        )
        session["profile_picture_url"] = DEFAULT_GCS_PROFILE_PIC_URL
        print(f"DEBUG: URL foto profil di DB dan sesi diubah ke default GCS.")
        return (
            jsonify({"success": True, "message": "Foto profil berhasil dihapus."}),
            200,
        )
    except Exception as e:
        print(f"DEBUG ERROR: Gagal memperbarui DB setelah menghapus foto: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Gagal memperbarui database setelah penghapusan foto.",
                }
            ),
            500,
        )


# ... (akhir kode) ...


# --- Route untuk menyajikan file dari folder upload ---
# --- PERUBAHAN DI SINI ---
@app.route("/gambar_profil_user/<filename>")
def uploaded_file(filename):
    safe_filename = secure_filename(filename)
    # Ini akan melayani file langsung dari direktori 'upload/profile_pictures'
    return send_from_directory(app.config["UPLOAD_FOLDER"], safe_filename)


# --- AKHIR PERUBAHAN ---


# --- Profil User (Tampilan HTML, Dilindungi Login) ---
@app.route("/profil")
@login_required
def profil_user():
    return render_template("user/profil_user.html")


@app.route("/profiledit")
@login_required
def profiledit():
    return render_template("user/profil_edit.html")





# Akun Klien - Admin
@app.route('/admin_akunKlien')
def admin_akunKlien():
    # Mengambil semua user dari koleksi 'users' di MongoDB
    users_data = list(db.users.find({"role": {"$nin": ["admin", "pemilik"]}}))

    print(f"DEBUG: Jumlah user yang ditemukan di database: {len(users_data)}") # --- TAMBAHKAN INI ---
    if users_data:
        print(f"DEBUG: Contoh data user pertama: {users_data[0]}") # --- TAMBAHKAN INI ---
    else:
        print("DEBUG: Tidak ada user ditemukan di database.") # --- TAMBAHKAN INI ---

    # Untuk setiap user, pastikan profile_picture_url diisi dengan default jika kosong di database
    for user in users_data:
        if not user.get('profile_picture_url'):
            user['profile_picture_url'] = DEFAULT_GCS_PROFILE_PIC_URL
        user['_id'] = str(user['_id']) # Pastikan _id diubah ke string

    # Mengirim data user ke template 'admin/akunKlien.html'
    return render_template('admin/akunKlien.html', users=users_data, current_route=request.path)




# Route untuk halaman admin -admin dashboard
@app.route('/admin_dashboard')
@role_required(['admin', 'pemilik']) # Pastikan decorator ini sudah didefinisikan
def admin_dashboard():
    """
    Menangani logika dan data untuk halaman dashboard admin.
    """

    # 1. LOGIKA FILTER TAHUN
    # Ambil parameter 'year' dari URL. Jika tidak ada, gunakan tahun saat ini.
    try:
        selected_year = int(request.args.get('year', datetime.now().year))
    except ValueError:
        selected_year = datetime.now().year

    # Buat daftar tahun yang tersedia untuk dropdown filter.
    # Cari tahun paling awal di database untuk menjadi titik awal.
    first_order_pipeline = [
        {"$group": {"_id": None, "minYear": {"$min": {"$year": "$created_at"}}}},
    ]
    first_year_result = list(db.pesanan.aggregate(first_order_pipeline))
    
    # Tentukan rentang tahun dari yang paling awal hingga 1 tahun ke depan.
    start_year_range = first_year_result[0]['minYear'] if first_year_result else datetime.now().year
    end_year_range = datetime.now().year + 2 
    
    # Buat daftar tahunnya dan urutkan dari terlama ke terbaru
    available_years = list(range(start_year_range, end_year_range))
    #available_years.sort(reverse=True) <-- kalau urutan terbaru ke terlama tinggal aktifkan ini aja

    # 2. LOGIKA DATA GRAFIK (BERDASARKAN TAHUN YANG DIPILIH) 
    # Tentukan rentang tanggal untuk query database berdasarkan tahun yang dipilih
    start_of_year = datetime(selected_year, 1, 1)
    end_of_year = datetime(selected_year + 1, 1, 1)

    # Pipeline agregasi untuk menghitung jumlah pesanan per bulan di tahun yang dipilih
    pipeline = [
        {
            "$match": {
                "created_at": {
                    "$gte": start_of_year,
                    "$lt": end_of_year
                }
            }
        },
        {
            "$group": {
                "_id": {"month": {"$month": "$created_at"}},
                "count": {"$sum": 1}
            }
        }
    ]
    pesanan_per_bulan_db = list(db.pesanan.aggregate(pipeline))
    
    # Ubah hasil query menjadi format yang mudah digunakan
    data_map = {d['_id']['month']: d['count'] for d in pesanan_per_bulan_db}

    # Siapkan data final untuk Chart.js
    chart_labels = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Ags", "Sep", "Okt", "Nov", "Des"]
    chart_data = [data_map.get(month, 0) for month in range(1, 13)]

    # 3. LOGIKA DATA UNTUK KARTU STATISTIK & TOTAL
    # Data untuk kartu "Selamat Datang" (pesanan hari ini)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    jumlah_pesanan_hari_ini = db.pesanan.count_documents({"created_at": {"$gte": today_start}})

    # Data untuk kartu "Jumlah Pesanan/bln" (pesanan bulan ini)
    this_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    jumlah_pesanan_bulan_ini = db.pesanan.count_documents({"created_at": {"$gte": this_month_start}})

    # Data untuk kartu "Jumlah Akun Klien"
    jumlah_akun_klien = db.users.count_documents({"role": {"$nin": ["admin", "pemilik"]}})

    # Data untuk Total per Tahun (Dinamis) - lebih efisien menjumlahkan hasil chart daripada query ulang
    total_pesanan_tahun_ini = sum(chart_data)

    # 4. RENDER TEMPLATE DENGAN SEMUA DATA
    return render_template(
        'admin/dashboard.html',
        
        # Data untuk kartu statistik
        jumlah_pesanan_hari_ini=jumlah_pesanan_hari_ini,
        jumlah_pesanan_bulan_ini=jumlah_pesanan_bulan_ini,
        jumlah_akun_klien=jumlah_akun_klien,
        
        # Data untuk filter
        available_years=available_years,
        selected_year=selected_year,
        
        # Data untuk grafik
        chart_labels=json.dumps(chart_labels),
        chart_data=json.dumps(chart_data),

        # Data untuk total di bawah grafik (dinamis)
        total_pesanan_tahun_ini=total_pesanan_tahun_ini
    )

@app.route('/admin_login')
def admin_login():
    return render_template('admin/login_admin.html')

@app.route('/api/admin_masuk', methods=['POST'])
def api_admin_masuk():
    """API untuk login admin."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "Nama pengguna dan kata sandi harus diisi."}), 400

    user = users_collection.find_one({"username": username})

    if user and check_password_hash(user['password_hash'], password):
        if user.get('role') not in ['admin', 'pemilik']: # Admin dan pemilik bisa login melalui halaman admin login
            return jsonify({"success": False, "message": "Akun ini tidak memiliki akses admin."}), 403

        session['user_id'] = str(user['_id'])
        session['username'] = user['username']
        session['full_name'] = user.get('full_name', '')
        session['email'] = user.get('email', '')
        session['profile_picture_url'] = user.get('profile_picture_url') # Admin/pemilik tidak perlu default PP
        session['role'] = user.get('role')

        # Redirect berdasarkan peran setelah login admin berhasil
        if session['role'] == 'pemilik':
            return jsonify({"success": True, "message": "Login berhasil!", "redirect": url_for('pemilik_dashboard')}), 200
        else: # role == 'admin'
            return jsonify({"success": True, "message": "Login berhasil!", "redirect": url_for('admin_dashboard')}), 200
    else:
        return jsonify({"success": False, "message": "Nama pengguna atau kata sandi salah."}), 401
    


@app.route('/admin_logout')
def admin_logout():
    session.clear()
    flash("Anda telah logout dari sisi admin.", "info")
    return redirect(url_for('admin_login'))





#Route untuk halaman pemilik
@app.route('/pemilik_dashboard')
@role_required(['pemilik'])
def pemilik_dashboard():
    return render_template('pemilik/dashboard.html')

@app.route('/pemilik_login')
def pemilik_login_page():
    return render_template('pemilik/login_pemilik.html')

@app.route('/api/pemilik_masuk', methods=['POST'])
def api_pemilik_masuk():
    """API untuk login pemilik."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "Nama pengguna dan kata sandi harus diisi."}), 400

    user = users_collection.find_one({"username": username})

    if user and check_password_hash(user['password_hash'], password):
        if user.get('role') != 'pemilik':
            return jsonify({"success": False, "message": "Akun ini tidak memiliki akses pemilik."}), 403

        session['user_id'] = str(user['_id'])
        session['username'] = user['username']
        session['full_name'] = user.get('full_name', '')
        session['email'] = user.get('email', '')
        session['profile_picture_url'] = user.get('profile_picture_url') # Admin/pemilik tidak perlu default PP
        session['role'] = user.get('role')
        return jsonify({"success": True, "message": "Login berhasil!", "redirect": url_for('pemilik_dashboard')}), 200
    else:
        return jsonify({"success": False, "message": "Nama pengguna atau kata sandi salah."}), 401


# Pemilik - Pesanan
@app.route("/pemilik_pesanan")
def pemilik_pesanan():
    pesanan = list(db.pesanan.find().sort("created_at", -1))
    layanan_map = {str(l["_id"]): l["nama"] for l in db.layanan.find()}

    # Tambahkan nama layanan ke dalam setiap dokumen pesanan
    for p in pesanan:
        layanan_id = str(p.get("layanan_id"))
        p["layanan"] = layanan_map.get(layanan_id, "Tidak ditemukan")

        if isinstance(p.get("tanggal_mulai_acara"), datetime):
            p["tanggal_mulai_acara_formatted"] = tanggal_id(p["tanggal_mulai_acara"])
        if isinstance(p.get("tanggal_selesai_acara"), datetime):
            p["tanggal_selesai_acara_formatted"] = tanggal_id(
                p["tanggal_selesai_acara"]
            )
    return render_template(
        "pemilik/pesanan.html", pesanan=pesanan, current_route=request.path
    )


@app.route("/pemilik_pesanan_detail")
def pemilik_pesanan_detail():
    pesanan_id = request.args.get("pesanan_id")

    if not pesanan_id:
        flash("ID Pesanan tidak ditemukan.", "danger")
        return redirect(url_for("admin_pesanan"))

    try:
        pesanan = db.pesanan.find_one({"_id": ObjectId(pesanan_id)})

        # Pengecekan jika pesanan tidak ditemukan di database
        if not pesanan:
            flash(f"Pesanan dengan ID '{pesanan_id}' tidak ditemukan.", "danger")
            return redirect(url_for("admin_pesanan"))

        # Buat map nama layanan, paket, dan lokasi berdasarkan _id
        layanan_map = {str(l["_id"]): l["nama"] for l in db.layanan.find()}
        paket_map = {str(l["_id"]): l["nama"] for l in db.paket.find()}
        lokasi_map = {str(l["_id"]): l["nama"] for l in db.lokasi.find()}

        # Konversi ObjectId pesanan ke string untuk digunakan di URL/form
        pesanan["_id"] = str(pesanan["_id"])

        # Layanan
        layanan_id = str(pesanan.get("layanan_id", ""))
        pesanan["layanan"] = layanan_map.get(layanan_id, "Tidak ditemukan")

        # Paket
        paket_id = str(pesanan.get("paket_id", ""))
        pesanan["paket"] = paket_map.get(paket_id, "Tidak ditemukan")

        # Lokasi (bisa None atau kosong jika input manual)
        lokasi_id = str(pesanan.get("lokasi_id", ""))
        if lokasi_id and lokasi_id != "None":
            pesanan["lokasi"] = lokasi_map.get(lokasi_id, "Tidak ditemukan")
        else:
            pesanan["lokasi"] = (
                "Lokasi pilihan sendiri"
                if pesanan.get("alamat_lokasi_acara")
                else "Tidak tersedia"
            )

        # Format tanggal
        if isinstance(pesanan.get("tanggal_pemesanan"), datetime):
            pesanan["tanggal_pemesanan_formatted"] = tanggal_id(
                pesanan["tanggal_pemesanan"]
            )
        if isinstance(pesanan.get("tanggal_mulai_acara"), datetime):
            pesanan["tanggal_mulai_acara_formatted"] = tanggal_id(
                pesanan["tanggal_mulai_acara"]
            )
        if isinstance(pesanan.get("tanggal_selesai_acara"), datetime):
            pesanan["tanggal_selesai_acara_formatted"] = tanggal_id(
                pesanan["tanggal_selesai_acara"]
            )

        return render_template(
            "pemilik/pesanan_detail.html", pesanan=[pesanan], current_route=request.path
        )

    except Exception as e:
        flash(f"Terjadi kesalahan saat mengambil detail pesanan: {e}", "danger")
        return redirect(url_for("pemilik_pesanan"))


# Route untuk halaman pemilik
@app.route('/pemilik_pendapatan')
def pemilik_pendapatan():
    return render_template('pemilik/pendapatan.html')

@app.route('/pemilik_pengguna')
@role_required(['pemilik']) # Pastikan route ini dilindungi
def pemilik_pengguna():
    """Halaman manajemen pengguna oleh pemilik, menampilkan daftar pengguna."""
    
    # Ambil hanya pengguna dengan role 'pemilik' atau 'admin'
    # Sortir berdasarkan created_at secara menurun (terbaru di atas)
    # Anda mungkin ingin menambahkan .sort([("created_at", -1)])
    # Tapi kita akan memisahkan 'pemilik_riyan' dan mengurutkan sisanya.
    management_users_cursor = users_collection.find({
        "role": {"$in": ["pemilik", "admin"]}
    }).sort("created_at", -1) # Urutkan terbaru di atas
    
    pemilik_riyan_account = None
    other_management_users = [] 
    
    for user in management_users_cursor:
        user['_id'] = str(user['_id']) # Konversi ObjectId ke string
        # Pastikan profile_picture_url diisi dengan default jika kosong dan role adalah user
        # (meskipun di sini kita hanya ambil admin/pemilik, antisipasi untuk data lama atau inkonsisten)
        if user.get('role') == 'user' and not user.get('profile_picture_url'):
            user['profile_picture_url'] = DEFAULT_GCS_PROFILE_PIC_URL
        
        if user.get('username') == "pemilik_riyan" and user.get('role') == "pemilik":
            pemilik_riyan_account = user
        else:
            other_management_users.append(user)
            
    # Gabungkan kembali: pemilik_riyan paling atas, diikuti oleh admin/pemilik lainnya yang sudah diurutkan
    sorted_users = []
    if pemilik_riyan_account:
        sorted_users.append(pemilik_riyan_account)
    sorted_users.extend(other_management_users) # other_management_users sudah terurut dari query

    print(f"DEBUG: Data pengguna yang dikirim ke template: {sorted_users}")

    return render_template('pemilik/pengguna.html', users=sorted_users)

# ... (Pastikan Anda memiliki route untuk menghapus pengguna) ...
# Contoh placeholder untuk route hapus (kita akan implementasikan nanti jika perlu)
@app.route('/api/pemilik_hapus_pengguna/<user_id>', methods=['DELETE'])
@role_required(['pemilik'])
def api_pemilik_hapus_pengguna(user_id):
    try:
        # Tambahkan konfirmasi bahwa yang dihapus bukan pemilik_riyan
        user_to_delete = users_collection.find_one({"_id": ObjectId(user_id)})
        if user_to_delete and user_to_delete.get('username') == "pemilik_riyan" and user_to_delete.get('role') == "pemilik":
            return jsonify({"success": False, "message": "Akun pemilik default tidak dapat dihapus."}), 403

        result = users_collection.delete_one({"_id": ObjectId(user_id)})
        if result.deleted_count == 1:
            return jsonify({"success": True, "message": "Pengguna berhasil dihapus."}), 200
        else:
            return jsonify({"success": False, "message": "Pengguna tidak ditemukan."}), 404
    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({"success": False, "message": "Terjadi kesalahan saat menghapus pengguna."}), 500


@app.route('/pemilik_tambah_pengguna')
def pemilik_tambah_pengguna_page():
    return render_template('pemilik/tambah_pengguna.html') 

@app.route('/api/pemilik_tambah_pengguna', methods=['POST'])
@role_required(['pemilik'])
def api_pemilik_tambah_pengguna():
    """API untuk pemilik menambahkan akun admin atau pemilik baru."""
    data = request.get_json()
    full_name = data.get('nama')
    username = data.get('nama_pengguna')
    password = data.get('kata_sandi')
    role = data.get('peran')
    email = data.get('email')

    if not all([full_name, username, password, role]):
        return jsonify({"success": False, "message": "Nama, Nama Pengguna, Kata Sandi, dan Peran harus diisi."}), 400

    if len(password) < 8:
        return jsonify({"success": False, "message": "Kata sandi harus minimal 8 karakter."}), 400

    if users_collection.find_one({"username": username}):
        return jsonify({"success": False, "message": "Nama pengguna sudah terdaftar."}), 409

    # Validasi email berdasarkan peran
    if role == 'pemilik':
        if not email:
            return jsonify({"success": False, "message": "Email harus diisi untuk peran Pemilik."}), 400
        if not is_valid_email(email):
            return jsonify({"success": False, "message": "Format email tidak valid."}), 400
        if users_collection.find_one({"email": email}):
            return jsonify({"success": False, "message": "Email sudah terdaftar."}), 409
    else: # role == 'admin'
        # Email opsional untuk admin, tapi jika diisi harus valid dan belum terdaftar
        if email and not is_valid_email(email):
            return jsonify({"success": False, "message": "Format email tidak valid."}), 400
        if email and users_collection.find_one({"email": email}):
            return jsonify({"success": False, "message": "Email sudah terdaftar."}), 409

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    # Atur profile_picture_url berdasarkan peran
    profile_pic_to_save = None # Default None untuk admin/pemilik yang baru ditambahkan
    if role == 'user': # Meskipun endpoint ini hanya untuk admin/pemilik, antisipasi jika logika berubah
        profile_pic_to_save = DEFAULT_GCS_PROFILE_PIC_URL

    try:
        users_collection.insert_one({
            "full_name": full_name,
            "username": username,
            "email": email if email else None, # Simpan email jika ada, selain itu None
            "password_hash": hashed_password,
            "created_at": datetime.now(),
            "profile_picture_url": profile_pic_to_save,
            "role": role
        })
        return jsonify({"success": True, "message": f"Pengguna {username} dengan peran {role} berhasil ditambahkan."}), 201
    except Exception as e:
        print(f"Error adding new user: {e}")
        return jsonify({"success": False, "message": "Terjadi kesalahan saat menambahkan pengguna baru. Silakan coba lagi."}), 500


@app.route('/pemilik_ubah_pengguna/<user_id>')
@role_required(['pemilik'])
def pemilik_ubah_pengguna(user_id):
    """Halaman untuk mengubah detail pengguna tertentu."""
    try:
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if user:
            user['_id'] = str(user['_id']) # Konversi ObjectId ke string
            return render_template('pemilik/ubah_pengguna.html', user=user)
        else:
            return redirect(url_for('pemilik_pengguna'))
    except Exception as e:
        print(f"Error fetching user for edit: {e}")
        return redirect(url_for('pemilik_pengguna'))

@app.route('/api/pemilik_update_pengguna/<user_id>', methods=['PUT'])
@role_required(['pemilik'])
def api_pemilik_update_pengguna(user_id):
    """API untuk pemilik mengubah detail pengguna (username, password, email)."""
    data = request.get_json()
    username = data.get('nama_pengguna') # Sekarang username bisa diubah
    password = data.get('kata_sandi')
    email = data.get('email')

    try:
        existing_user = users_collection.find_one({"_id": ObjectId(user_id)})
        if not existing_user:
            return jsonify({"success": False, "message": "Pengguna tidak ditemukan."}), 404

        # Pemeriksaan khusus untuk pemilik_riyan
        if existing_user.get('username') == "pemilik_riyan" and existing_user.get('role') == "pemilik":
            # Pemilik riyan hanya boleh mengubah email dan password, nama pengguna tetap tidak boleh diubah
            if username and username != existing_user.get('username'):
                 return jsonify({"success": False, "message": "Nama pengguna 'pemilik_riyan' tidak dapat diubah."}), 403

        update_fields = {}

        # Update username jika ada perubahan
        if username and username != existing_user.get('username'):
            # Cek apakah username sudah ada untuk pengguna lain
            if users_collection.find_one({"username": username, "_id": {"$ne": ObjectId(user_id)}}):
                return jsonify({"success": False, "message": "Nama pengguna sudah terdaftar oleh pengguna lain."}), 409
            update_fields['username'] = username

        # Perbarui password jika disediakan dan lebih dari 6 karakter
        if password:
            if len(password) < 8:
                return jsonify({"success": False, "message": "Kata sandi harus minimal 8 karakter."}), 400
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            update_fields['password_hash'] = hashed_password

        # Perbarui email jika ada perubahan
        # Validasi email berdasarkan peran tetap sama
        if existing_user.get('role') == 'pemilik':
            if not email:
                return jsonify({"success": False, "message": "Email harus diisi untuk peran Pemilik."}), 400
            if not is_valid_email(email):
                return jsonify({"success": False, "message": "Format email tidak valid."}), 400
            if email != existing_user.get('email'):
                if users_collection.find_one({"email": email, "_id": {"$ne": ObjectId(user_id)}}):
                    return jsonify({"success": False, "message": "Email sudah terdaftar oleh pengguna lain."}), 409
                update_fields['email'] = email
        elif existing_user.get('role') == 'admin':
            if email:
                if not is_valid_email(email):
                    return jsonify({"success": False, "message": "Format email tidak valid."}), 400
                if email != existing_user.get('email'):
                    if users_collection.find_one({"email": email, "_id": {"$ne": ObjectId(user_id)}}):
                        return jsonify({"success": False, "message": "Email sudah terdaftar oleh pengguna lain."}), 409
                    update_fields['email'] = email
            elif existing_user.get('email'): # Jika email sebelumnya ada dan sekarang dikosongkan
                update_fields['email'] = None

        # Nama Lengkap dan Peran tidak dapat diubah
        # Kita tidak perlu secara eksplisit memeriksa 'full_name' dari data request
        # karena kita tidak akan menggunakannya untuk update_fields di sini.
        # Role juga tidak boleh diubah.

        if update_fields:
            users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": update_fields})
            return jsonify({"success": True, "message": "Pengguna berhasil diperbarui."}), 200
        else:
            return jsonify({"success": False, "message": "Tidak ada perubahan yang terdeteksi."}), 200
    except Exception as e:
        print(f"Error updating user: {e}")
        return jsonify({"success": False, "message": "Terjadi kesalahan saat memperbarui pengguna."}), 500




# Function to initialize default owner account
def initialize_owner_account():
    owner_username = "pemilik_riyan"
    owner_email = "ovalphotoo@gmail.com"
    owner_password = "pemilikRY87654"
    owner_full_name = "Riyan"
    owner_role = "pemilik"

    existing_owner = users_collection.find_one({"username": owner_username, "role": owner_role})
    if not existing_owner:
        print(f"DEBUG: Attempting to create default owner account: {owner_username}")
        hashed_password = generate_password_hash(owner_password, method='pbkdf2:sha256')
        try:
            users_collection.insert_one({
                "full_name": owner_full_name,
                "username": owner_username,
                "email": owner_email,
                "password_hash": hashed_password,
                "created_at": datetime.now(),
                "profile_picture_url": None, # Pemilik default tidak punya profile picture
                "role": owner_role
            })
            print(f"DEBUG: Default owner account '{owner_username}' created successfully!")
        except Exception as e:
            print(f"ERROR: Failed to create default owner account '{owner_username}': {e}")
            print(f"ERROR Details: Check MongoDB connection string, user permissions, or duplicate key constraints.")
    else:
        print(f"DEBUG: Default owner account '{owner_username}' already exists. Skipping creation.")




@app.route('/pemilik_akunKlien')
def pemilik_akunKlien():
    # Mengambil user dari koleksi 'users' di MongoDB yang role-nya BUKAN 'admin' dan BUKAN 'pemilik'.
    users_data = list(db.users.find({"role": {"$nin": ["admin", "pemilik"]}}))

    print(f"DEBUG: Pemilik - Jumlah akun klien (bukan admin/pemilik) yang ditemukan di database: {len(users_data)}")
    if users_data:
        print(f"DEBUG: Pemilik - Contoh data akun klien pertama: {users_data[0]}")
    else:
        print("DEBUG: Pemilik - Tidak ada akun klien ditemukan di database.")

    # Untuk setiap user, pastikan profile_picture_url diisi dengan default jika kosong di database
    for user in users_data:
        if not user.get('profile_picture_url'):
            user['profile_picture_url'] = DEFAULT_GCS_PROFILE_PIC_URL
        user['_id'] = str(user['_id']) # Pastikan _id diubah ke string

    # Mengirim data user ke template 'pemilik/akunKlien.html'
    return render_template('pemilik/akunKlien.html', users=users_data, current_route=request.path)




















@app.template_filter('rupiah')
def rupiah_format(value):
    try:
        value = float(value)
        return "Rp {:,.0f}".format(value).replace(',', '.')
    except (ValueError, TypeError):
        return value
    









# --- Midtrans Configuration ---
MIDTRANS_SERVER_KEY = os.environ.get('MIDTRANS_SERVER_KEY', 'SB-Mid-server-rEpxd94AnaenmjNsX2qKrqMi')
MIDTRANS_CLIENT_KEY = os.environ.get('MIDTRANS_CLIENT_KEY', 'SB-Mid-client-JTsOBVyXkQtff82K')
MIDTRANS_IS_PRODUCTION = os.environ.get('MIDTRANS_IS_PRODUCTION', 'false').lower() == 'true' # Set True untuk sandbox, False untuk produksi

#  Inisialisasi Snap API untuk membuat transaksi Snap
snap_api = midtransclient.Snap(
    is_production=MIDTRANS_IS_PRODUCTION,
    server_key=MIDTRANS_SERVER_KEY
)

core_api_for_status = midtransclient.CoreApi(
    is_production=MIDTRANS_IS_PRODUCTION,
    server_key=MIDTRANS_SERVER_KEY
)


# --- Midtrans Transaction API ---
@app.route('/api/create_midtrans_transaction', methods=['POST'])
@login_required
def create_midtrans_transaction():
    try:
        data = request.get_json()
        pesanan_id = data.get('pesanan_id')
        payment_type = data.get('payment_type') # 'deposit' or 'pelunasan'

        if not pesanan_id or not payment_type:
            return jsonify({'success': False, 'message': 'ID Pesanan dan tipe pembayaran diperlukan.'}), 400

        pesanan = db.pesanan.find_one({'_id': ObjectId(pesanan_id)})
        if not pesanan:
            return jsonify({'success': False, 'message': 'Pesanan tidak ditemukan.'}), 404

        # Pastikan user yang login adalah pemilik pesanan
        if str(pesanan.get('user_id_pemesan')) != session.get('user_id'):
            return jsonify({'success': False, 'message': 'Anda tidak memiliki akses ke pesanan ini.'}), 403

        amount_to_pay = 0
        item_details = []
        order_id_prefix = ""

        # Retrieve mapped names for item details
        layanan_info = db.layanan.find_one({"_id": pesanan.get("layanan_id")})
        paket_info = db.paket.find_one({"_id": pesanan.get("paket_id")})
        layanan_name = layanan_info.get("nama", "N/A") if layanan_info else "N/A"
        paket_name = paket_info.get("nama", "N/A") if paket_info else "N/A"

        # Buat nama item yang ringkas (Max 80 characters for Midtrans)
        base_item_name = f"Pembayaran {payment_type.capitalize()} - {layanan_name} ({paket_name})"
        max_item_name_length = 80
        item_name = (base_item_name[:max_item_name_length] + '...') if len(base_item_name) > max_item_name_length else base_item_name

        if payment_type == 'deposit':
            amount_to_pay = pesanan.get('deposit', 0)
            if amount_to_pay <= 0:
                return jsonify({'success': False, 'message': 'Jumlah deposit harus lebih dari nol.'}), 400
            if pesanan.get('status_pembayaran_deposit') == 'Lunas':
                return jsonify({'success': False, 'message': 'Deposit sudah lunas.'}), 400
            order_id_prefix = "DEPOSIT-"
            item_details.append({
                "id": f"DEP-{pesanan_id}",
                "price": int(amount_to_pay),
                "quantity": 1,
                "name": item_name
            })
        elif payment_type == 'pelunasan':
            amount_to_pay = pesanan.get('total_harga', 0) - pesanan.get('deposit', 0)
            amount_to_pay = max(0, amount_to_pay) # Ensure amount is not negative

            if amount_to_pay <= 0:
                return jsonify({'success': False, 'message': 'Jumlah pelunasan harus lebih dari nol, atau pembayaran sudah lunas.'}), 400
            if pesanan.get('status_pembayaran_pelunasan') == 'Lunas':
                return jsonify({'success': False, 'message': 'Pelunasan sudah lunas.'}), 400
            order_id_prefix = "LUNAS-"
            item_details.append({
                "id": f"LUN-{pesanan_id}",
                "price": int(amount_to_pay),
                "quantity": 1,
                "name": item_name
            })
        else:
            return jsonify({'success': False, 'message': 'Tipe pembayaran tidak valid.'}), 400

        # Generate a unique order_id for Midtrans
        order_id = f"{order_id_prefix}{pesanan_id}-{uuid.uuid4().hex}" # Using uuid for higher uniqueness

        # Calculate gross_amount from item_details for consistency
        calculated_gross_amount = sum(item['price'] * item['quantity'] for item in item_details)

        transaction_details = {
            "order_id": order_id,
            "gross_amount": calculated_gross_amount
        }

        customer_details = {
            "first_name": pesanan.get('nama_klien', 'Client'),
            "email": pesanan.get('email_klien', 'no-email@example.com'),
            "phone": pesanan.get('telepon_klien', '08123456789')
        }

        params = {
            "transaction_details": transaction_details,
            "item_details": item_details,
            "customer_details": customer_details,
            "callbacks": {
                "finish": url_for('midtrans_payment_finish', _external=True)
            }
        }

        # Update order with Midtrans order ID and payment attempt details
        if payment_type == 'deposit':
            db.pesanan.update_one(
                {'_id': ObjectId(pesanan_id)},
                {'$set': {
                    'midtrans_deposit_order_id': order_id,
                    'last_deposit_attempt_amount': amount_to_pay,
                    'last_deposit_attempt_time': datetime.utcnow(),
                    'status_pembayaran_deposit': 'Menunggu Pembayaran',
                }}
            )
        elif payment_type == 'pelunasan':
            db.pesanan.update_one(
                {'_id': ObjectId(pesanan_id)},
                {'$set': {
                    'midtrans_pelunasan_order_id': order_id,
                    'last_pelunasan_attempt_amount': amount_to_pay,
                    'last_pelunasan_attempt_time': datetime.utcnow(),
                    'status_pembayaran_pelunasan': 'Menunggu Pembayaran',
                }}
            )

        snap_response = snap_api.create_transaction(params)
        return jsonify({'success': True, 'token': snap_response['token']}), 200

    except Exception as e:
        app.logger.error(f"Error creating Midtrans transaction: {e}", exc_info=True)
        if isinstance(e, midtransclient.http_client.APIError):
            app.logger.error(f"Midtrans API Error Response: {e.api_response}")
            return jsonify({'success': False, 'message': f'Gagal membuat transaksi Midtrans: {e.api_response}'}), 500
        return jsonify({'success': False, 'message': f'Gagal membuat transaksi Midtrans: {str(e)}'}), 500


@app.route('/midtrans_notification', methods=['POST'])
def midtrans_notification():
    try:
        notification_data = request.get_json()
        app.logger.info(f"Midtrans Notification Received: {notification_data}")

        # Verifikasi notifikasi dengan mengambil status langsung dari Midtrans
        # Ini adalah langkah keamanan penting untuk mencegah spoofing webhook
        transaction_id = notification_data.get('transaction_id')
        if not transaction_id:
            app.logger.error("Missing transaction_id in Midtrans notification.")
            return "Bad Request: Missing transaction_id", 400

        status_response = core_api_for_status.transaction.status(transaction_id)
        app.logger.info(f"Midtrans Transaction Status Response: {status_response}")

        order_id = status_response['order_id']
        transaction_status = status_response['transaction_status']
        fraud_status = status_response.get('fraud_status')
        gross_amount_midtrans = float(status_response['gross_amount']) # Midtrans sends amount as string, convert to float

        is_deposit_payment = False
        is_pelunasan_payment = False
        pesanan_id_internal = None # Menyimpan ObjectId dari pesanan kita
        query_field_to_match_midtrans_id = None # Bidang di DB yang menyimpan Order ID Midtrans

        # Ekstrak pesanan_id internal dan tentukan tipe pembayaran dari order_id Midtrans
        parts = order_id.split('-')
        if len(parts) >= 2: # Minimal "PREFIX-ID"
            # Asumsi: order_id Midtrans adalah "PREFIX-PESANAN_ID_INTERNAL-UUID/TIMESTAMP"
            # Kita perlu mengambil bagian PESANAN_ID_INTERNAL yang merupakan bagian kedua setelah split pertama
            try:
                # Ambil bagian ID internal (parts[1])
                pesanan_id_internal_str = parts[1]
                # Pastikan ini bisa menjadi ObjectId
                pesanan_id_internal = ObjectId(pesanan_id_internal_str)
            except Exception as e:
                app.logger.error(f"Failed to convert extracted pesanan_id '{parts[1]}' to ObjectId: {e}")
                return "Invalid Internal Pesanan ID Format", 400

            if order_id.startswith("DEPOSIT-"):
                is_deposit_payment = True
                query_field_to_match_midtrans_id = 'midtrans_deposit_order_id'
            elif order_id.startswith("LUNAS-"):
                is_pelunasan_payment = True
                query_field_to_match_midtrans_id = 'midtrans_pelunasan_order_id'
            else:
                app.logger.error(f"Unknown order_id prefix: {order_id}")
                return "Unknown Order ID prefix", 400
        else:
            app.logger.error(f"Could not extract internal pesanan_id from Midtrans order_id: {order_id}")
            return "Invalid Midtrans Order ID format", 400


        # Temukan dokumen pesanan di database
        # Gunakan query_field_to_match_midtrans_id untuk memastikan kita mencari pesanan yang benar
        # yang terkait dengan transaksi Midtrans ini.
        pesanan = db.pesanan.find_one({
            '_id': pesanan_id_internal,
            query_field_to_match_midtrans_id: order_id # Verifikasi bahwa order_id Midtrans cocok dengan yang kita simpan
        })

        if not pesanan:
            app.logger.warning(f"Pesanan dengan ID '{pesanan_id_internal}' dan Midtrans Order ID '{order_id}' tidak ditemukan atau tidak cocok.")
            return "Pesanan tidak ditemukan atau tidak cocok", 404

        expected_amount = 0
        if is_deposit_payment:
            expected_amount = pesanan.get('deposit', 0)
        elif is_pelunasan_payment:
            # Hitung sisa pelunasan
            expected_amount = pesanan.get('total_harga', 0) - pesanan.get('deposit', 0)
            expected_amount = max(0, expected_amount) # Pastikan tidak negatif

        # Validasi jumlah pembayaran untuk mencegah manipulasi
        if abs(gross_amount_midtrans - expected_amount) > 0.01: # Toleransi kecil untuk floating point
            app.logger.warning(f"Amount mismatch for Order ID {order_id}. Expected: {expected_amount}, Got: {gross_amount_midtrans}. Possible fraud/mismatch.")
            # Dalam kasus ini, Anda mungkin ingin menandai pesanan untuk peninjauan manual
            # atau mengirim notifikasi ke admin, tetapi tetap kembalikan 200 OK ke Midtrans.
            return "Amount mismatch but accepted for now", 200 # Accept but log warning

        update_fields = {}
        # Ambil status terkini dari database agar logika bisa berjalan dengan benar
        # jika webhook datang tidak berurutan atau ada perubahan lain.
        current_overall_status = pesanan.get('status_pesanan', 'Menunggu Konfirmasi')
        current_deposit_status = pesanan.get('status_pembayaran_deposit', 'Belum Bayar')
        current_pelunasan_status = pesanan.get('status_pembayaran_pelunasan', 'Belum Bayar')


        if transaction_status in ['capture', 'settlement']:
            if fraud_status == 'challenge':
                # Pembayaran butuh verifikasi lebih lanjut dari Midtrans (Fraud challenge)
                update_fields['status_pesanan'] = 'Pending (Challenge)'
            else:
                # Pembayaran berhasil dikonfirmasi
                if is_deposit_payment:
                    update_fields['status_pembayaran_deposit'] = 'Lunas'
                    update_fields['tanggal_pembayaran_deposit'] = datetime.utcnow()
                    update_fields['midtrans_deposit_status'] = transaction_status # Simpan status detail dari Midtrans
                    current_deposit_status = 'Lunas' # Update variable for subsequent logic
                elif is_pelunasan_payment:
                    update_fields['status_pembayaran_pelunasan'] = 'Lunas'
                    update_fields['tanggal_pembayaran_pelunasan'] = datetime.utcnow()
                    update_fields['midtrans_pelunasan_status'] = transaction_status # Simpan status detail dari Midtrans
                    current_pelunasan_status = 'Lunas' # Update variable for subsequent logic

                # Logika pembaruan status pesanan keseluruhan
                # Hanya ubah status_pesanan jika perubahan pembayaran ini memajukan status
                if current_deposit_status == 'Lunas' and current_pelunasan_status == 'Lunas':
                    # Jika kedua pembayaran sudah lunas, status menjadi 'Pembayaran Lunas'
                    if current_overall_status not in ['Pembayaran Lunas', 'Diproses', 'Sudah Pemotretan', 'Sudah Kirim File & Album', 'Selesai']:
                        update_fields['status_pesanan'] = 'Pembayaran Lunas'
                elif current_deposit_status == 'Lunas' and pesanan.get('deposit') > 0: # Pastikan ada deposit yang harus dibayar
                    # Jika hanya deposit yang lunas, dan sebelumnya belum di status 'Deposit Lunas'
                    if current_overall_status == 'Menunggu Konfirmasi' or current_overall_status == 'Pending Pembayaran':
                        update_fields['status_pesanan'] = 'Deposit Lunas'
                elif current_pelunasan_status == 'Lunas' and pesanan.get('total_harga') > pesanan.get('deposit'): # Pastikan ada pelunasan yang harus dibayar
                    # Jika hanya pelunasan yang lunas, dan sebelumnya belum di status yang lebih maju
                    if current_overall_status not in ['Pembayaran Lunas', 'Diproses', 'Sudah Pemotretan', 'Sudah Kirim File & Album', 'Selesai']:
                        update_fields['status_pesanan'] = 'Pelunasan Lunas'


        elif transaction_status == 'pending':
            # Jika status saat ini adalah "Lunas", jangan ditimpa menjadi "Pending"
            if is_deposit_payment and current_deposit_status != 'Lunas':
                update_fields['status_pembayaran_deposit'] = 'Pending'
                update_fields['midtrans_deposit_status'] = transaction_status
            elif is_pelunasan_payment and current_pelunasan_status != 'Lunas':
                update_fields['status_pembayaran_pelunasan'] = 'Pending'
                update_fields['midtrans_pelunasan_status'] = transaction_status

            # Perbarui status keseluruhan hanya jika belum pada status yang lebih maju
            if current_overall_status in ['Menunggu Konfirmasi', 'Pending Pembayaran']:
                 update_fields['status_pesanan'] = 'Pending Pembayaran'


        elif transaction_status == 'expire':
            if is_deposit_payment:
                update_fields['status_pembayaran_deposit'] = 'Kadaluarsa'
                update_fields['midtrans_deposit_status'] = transaction_status
            elif is_pelunasan_payment:
                update_fields['status_pembayaran_pelunasan'] = 'Kadaluarsa'
                update_fields['midtrans_pelunasan_status'] = transaction_status
            # Update status pesanan secara keseluruhan jika pembayaran utama kadaluarsa
            if current_overall_status not in ['Diproses', 'Sudah Pemotretan', 'Sudah Kirim File & Album', 'Selesai']:
                update_fields['status_pesanan'] = 'Pembayaran Kadaluarsa'

        elif transaction_status == 'cancel':
            if is_deposit_payment:
                update_fields['status_pembayaran_deposit'] = 'Dibatalkan'
                update_fields['midtrans_deposit_status'] = transaction_status
            elif is_pelunasan_payment:
                update_fields['status_pembayaran_pelunasan'] = 'Dibatalkan'
                update_fields['midtrans_pelunasan_status'] = transaction_status
            # Update status pesanan secara keseluruhan jika pembayaran utama dibatalkan
            if current_overall_status not in ['Diproses', 'Sudah Pemotretan', 'Sudah Kirim File & Album', 'Selesai']:
                update_fields['status_pesanan'] = 'Pembayaran Dibatalkan'

        elif transaction_status == 'deny':
            if is_deposit_payment:
                update_fields['status_pembayaran_deposit'] = 'Ditolak'
                update_fields['midtrans_deposit_status'] = transaction_status
            elif is_pelunasan_payment:
                update_fields['status_pembayaran_pelunasan'] = 'Ditolak'
                update_fields['midtrans_pelunasan_status'] = transaction_status
            # Update status pesanan secara keseluruhan jika pembayaran utama ditolak
            if current_overall_status not in ['Diproses', 'Sudah Pemotretan', 'Sudah Kirim File & Album', 'Selesai']:
                update_fields['status_pesanan'] = 'Pembayaran Ditolak'
        else:
            app.logger.info(f"Unhandled Midtrans transaction status: {transaction_status} for Order ID: {order_id}")
            return "Status tidak ditangani", 200

        if update_fields:
            db.pesanan.update_one(
                {'_id': pesanan_id_internal},
                {'$set': update_fields}
            )
            app.logger.info(f"Pesanan '{pesanan_id_internal}' updated with: {update_fields}")

        return "OK", 200

    except Exception as e:
        app.logger.error(f"Error processing Midtrans notification: {e}", exc_info=True)
        return "Internal Server Error", 500


@app.route("/midtrans_payment_finish", methods=["GET"])
def midtrans_payment_finish():
    transaction_status = request.args.get("transaction_status")
    order_id = request.args.get("order_id") # This order_id is the Midtrans order_id, not your internal pesanan_id

    if transaction_status == "settlement" or transaction_status == "capture":
        flash("Pembayaran berhasil diproses!", "success")
    elif transaction_status == "pending":
        flash("Pembayaran Anda sedang menunggu konfirmasi. Silakan selesaikan pembayaran Anda.", "info")
    else:
        flash("Pembayaran gagal atau dibatalkan. Silakan coba lagi.", "danger")

    # The actual database update for the payment status will happen via the `midtrans_notification` webhook.
    # The `midtrans_payment_finish` route is primarily for user feedback after they return from Midtrans.
    # We should always redirect to the general riwayat_pemesanan page here.
    return redirect(url_for("riwayat_pemesanan"))






if __name__ == '__main__':
    # Memastikan folder upload ada saat aplikasi dimulai
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    if app.config['SECRET_KEY'] == 'DANANDA34' or \
       app.config['JWT_SECRET_KEY'] == 'KILLING23':
        print("WARNING: Using default secret keys. Please set FLASK_SECRET_KEY and JWT_SECRET_KEY environment variables in production for security.")

    initialize_owner_account() # Ini harus dipanggil sebelum app.run()
    app.run('0.0.0.0', port=5000, debug=True)
