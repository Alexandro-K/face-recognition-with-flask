from flask import Flask, render_template, Response, request, jsonify, send_file, redirect, url_for
from database.supabase_client import supabase
from openpyxl import Workbook
from io import BytesIO
from datetime import datetime

import cv2
import face_recognition
import json
import threading
import csv
import os

import base64
import numpy as np

# Instace flask utama
app = Flask(__name__, template_folder='templates', static_folder='static', static_url_path='/')


# Mengambil semua wajah dari database
def load_known_faces():
    # Query ke database
    user_data = (supabase.table('face-recognition-with-flask')
                .select("user_id", "encoding")
                .execute()
                )

    # Variabel untuk menampung id dan encoding
    known_ids = []
    known_encodings = []

    # Menyimpan setiap data kedalam variables
    for data in user_data.data:
        known_ids.append(data['user_id'])
        encoding = data['encoding']
        # Mengecek apabila pengambilan data dari database 
        # masih berbentuk string
        if isinstance(encoding, str): 
            encoding = json.loads(encoding) # Mengubahnya kedalam bentuk numpy array
        known_encodings.append(encoding)
        
    return known_ids, known_encodings

# Global variables 
last_recognition_data = [] # Untuk menyimpan hasil
last_unknown_encoding = None # Menyimpan encoding yang akan dimasukkan kedalam database
data_lock = threading.Lock() # Lock threading untuk mencegah bentrok antara pengambilan data dengan permintaan data

# Load id dan encoding menggunakan functionnya
with data_lock:
    known_ids, known_encodings = load_known_faces()

# Mengambil frame dari kamera
@app.route('/process_frame', methods=['POST'])
def process_frame():
    global last_recognition_data, last_unknown_encoding

    # Mengambil data dalam bentuk json
    data = request.json
    img_data = data['frame']

    # buang prefix "data:image/jpeg;base64,"
    if img_data.startswith("data:image"):
        img_data = img_data.split(",")[1]

    img_bytes = base64.b64decode(img_data) # Mengubah byte64 menjadi byte array 
    nparr = np.frombuffer(img_bytes, np.uint8) # Mengubah byte menjadi numpy array 1d uint8
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR) # Mengambil array dan mengubahnya kedalam bentuk 3D(H,W,C)

    if frame is None: # Jika decoding gagal
        return jsonify([]), 200 # Mengembalikan array kosong (tidak ada wajah untuk diproses)

    # Resize kecil untuk processing (meningkatkan kinerja dan efisiensi)
    frame_small = cv2.resize(frame, (0, 0), None, 0.25, 0.25)
    rgb_frame = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)

    # Face recognition dengan mencari face locations dan face encodingsnya
    face_locations = face_recognition.face_locations(rgb_frame) # Memberikan informasi bbox wajah
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations) # Mengubah semua wajah tadi kedalam bentuk encoding

    results = [] # Variable untuk menampung hasil

    for i, face_enc in enumerate(face_encodings):
        # Mengubah skala wajah kembali karena tadi sudah dikecilkan menjadi 1/4-nya
        top, right, bottom, left = face_locations[i]
        top *= 4
        right *= 4
        bottom *= 4
        left *= 4
        
        # Face_box untuk dikirimkan ke frontend
        face_box = {
            "x": left,
            "y": top,
            "width": right - left,
            "height": bottom - top
        }
        
        # Melakukan perbandingan wajah dengan yang ada di database
        matches = face_recognition.compare_faces(known_encodings, face_enc, tolerance=0.5)
        face_distance = face_recognition.face_distance(known_encodings, face_enc) # Mencari jarak terkecil(dimana artinya hasil terbaik didapatkan)

        index = None
        if len(face_distance) > 0:
            index = face_distance.argmin() # Mengambil jarak terkecilnya

        if index is not None and matches[index]: # Jika hasil ditemukan (matching dengan yang di database)
            # Mengambil id dan query ke database berdasarkan idnya
            user_id = known_ids[index]
            user_data = (supabase.table("face-recognition-with-flask")
                         .select("user_id, username, jenis_kelamin, jurusan")
                         .eq("user_id", user_id)
                         .execute())
            # Kalu datanya ada input hasilnya kedalam result
            if user_data.data:
                result = user_data.data[0]
                result["face_box"] = face_box
                result["is_known"] = True
                results.append(result)
        else:
            # Jika tidak ada (pengguna belum masuk kedalam database)
            results.append({
                "user_id": None,
                "username": "Unknown",
                "jenis_kelamin": "-",
                "jurusan": "-",
                "face_box": face_box,
                "is_known": False
            })
            # Menyimpan encoding terakhir dari pengguna yang tidak dikenali 
            last_unknown_encoding = json.dumps(face_enc.tolist())

    # Melakukan data_lock agar data diambil terlebih dahulu dan 
    # tidak bentrok dengan pengambilan data yang ada dibawah
    with data_lock:
        last_recognition_data = results

    return jsonify(results) 

# Routing ke root / home
@app.route('/')
def index():
    return render_template('index.html')

# Routing ke recognition_data untuk mengambil data
@app.route('/recognition_data')
def recognition_data():
    with data_lock: # Agar tidak bentrok
        return jsonify(last_recognition_data)

# Routing untuk menambahkan user
@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    global last_unknown_encoding, known_ids, known_encodings # Global variables agar berguna secara keseluruhan

    if request.method == 'POST':
        # Mengambil data dari form di index.html
        username = request.form.get('username')
        jenis_kelamin = request.form.get("jenis-Kelamin")
        jurusan = request.form.get('jurusan')

        # Query untuk menyimpan data pengguna baru kedalam database
        supabase.table("face-recognition-with-flask").insert({
            "username": username,
            "jenis_kelamin": jenis_kelamin,
            "encoding": last_unknown_encoding,
            "jurusan": jurusan,
            "time_added": datetime.now().isoformat()
        }).execute()

        with data_lock: # Melakukan data_lock sebelum meload ulang data 
            known_ids, known_encodings = load_known_faces() # Meload ulang data sehingga data yang baru dimasukkan bisa langsung dimunculkkan

        last_unknown_encoding = None # Disetting ke none karena pengguna baru sudah dimasukkan
        return redirect(url_for("index")) # Dikembalikan ke index (redirect / refresh)

    return redirect(url_for("index")) # Dikembalikan ke index (redirect / refresh)

# Route untuk mengambil semua data yang ada di database (untuk ditampilkan di tabel)
@app.route('/users')
def users():
    # Query untuk mengambil data
    user_data = (supabase.table("face-recognition-with-flask")
                 .select("user_id, username, jenis_kelamin, jurusan")
                 .execute())
    
    return jsonify(user_data.data) # Mengembalikan data dalam bentuk json

# Route untuk mengapus pengguna berdasarkan id
@app.route('/delete_user/<user_id>', methods=['POST'])
def delete_user(user_id):
    global known_ids, known_encodings # Global vars untuk ids dan encodings
    
    # Query untuk menghapus user berdasarkan id
    supabase.table("face-recognition-with-flask").delete().eq("user_id", user_id).execute()

    # Refresh known faces
    with data_lock:
        known_ids, known_encodings = load_known_faces()

    return jsonify({"message": f"User {user_id} deleted successfully"})

# Route untuk mendownload dalam bentuk csv
@app.route('/download_users_csv')
def download_users():
    # Query semua user dari Supabase
    response = supabase.table("face-recognition-with-flask").select("*").execute()
    users = response.data # Mengambil hasilnya

    if not users: # Kalau tabel kosong
        return "No users found", 404

    # Buat response CSV
    def generate():
        data = csv.StringIO() # Membuat file csv (sebagai penampung)
        writer = csv.DictWriter(data, fieldnames=users[0].keys()) # Mengambil semua keys
        writer.writeheader() # Menjadikan keys tersebut sebagai header
        for user in users: # Looping tiap user
            writer.writerow(user) # Menulis tiap user tersebut kedalam file csv
        yield data.getvalue() # Mengembalikan isi cvs sebagai string

    return Response(
        generate(), # Membuat respon http manual
        mimetype="text/csv", # Bertipe csv
        headers={"Content-Disposition": "attachment;filename=users.csv"} # Nama file untuk di download = users.csv
    )

@app.route('/download_users_excel')
def download_users_excel():
    # Ambil data dari Supabase
    response = supabase.table("face-recognition-with-flask").select("*").execute()
    users = response.data # Mengambil hasilnya

    if not users: # Kalau tabel kosong
        return "No users found", 404

    wb = Workbook() # Buat workbook baru
    ws = wb.active # Ambil worksheet aktifnya (defaultnya yang pertama)
    ws.title = "Users" # Memberi nama worksheetnya menjadi Users

    headers = list(users[0].keys()) # Mengambil keysnya
    ws.append(headers) # Menjadikan headers

    # Tulis data semua user
    for user in users:
        ws.append(list(user.values()))

    output = BytesIO() # Menyimpan data ke virtual memory (tidak langsung ke disk)
    wb.save(output) # Menyimpan workbook kedalam memory object tersebut
    output.seek(0) # Mengembalikan pointer ke awal, karena kita sudah menggunakannya untuk menulis hingga akhir

    return send_file(
        output, 
        as_attachment=True, # Otomatis download
        download_name="users.xlsx", # Nama file
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" # Tipe file (.xlsx)
    ) 

# Untuk running aplikasi
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug_mode = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
