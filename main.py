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

    data = request.json
    img_data = data['frame']

    # buang prefix "data:image/jpeg;base64,"
    if img_data.startswith("data:image"):
        img_data = img_data.split(",")[1]

    img_bytes = base64.b64decode(img_data)
    nparr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        print("Decode gagal!")
        return jsonify([]), 200  

    # Resize kecil untuk processing
    frame_small = cv2.resize(frame, (0, 0), None, 0.25, 0.25)
    rgb_frame = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)

    # Face recognition
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    results = []

    for i, face_enc in enumerate(face_encodings):
        # Scale face location kembali ke ukuran asli
        top, right, bottom, left = face_locations[i]
        top *= 4
        right *= 4
        bottom *= 4
        left *= 4
        
        # Convert ke format yang mudah digunakan di frontend
        face_box = {
            "x": left,
            "y": top,
            "width": right - left,
            "height": bottom - top
        }
        
        matches = face_recognition.compare_faces(known_encodings, face_enc, tolerance=0.70)
        face_distance = face_recognition.face_distance(known_encodings, face_enc)

        index = None
        if len(face_distance) > 0:
            index = face_distance.argmin()

        if index is not None and matches[index]:
            user_id = known_ids[index]
            user_data = (supabase.table("face-recognition-with-flask")
                         .select("user_id, username, jenis_kelamin, jurusan")
                         .eq("user_id", user_id)
                         .execute())
            if user_data.data:
                result = user_data.data[0]
                result["face_box"] = face_box
                result["is_known"] = True
                results.append(result)
        else:
            results.append({
                "user_id": None,
                "username": "Unknown",
                "jenis_kelamin": "-",
                "jurusan": "-",
                "face_box": face_box,
                "is_known": False
            })
            last_unknown_encoding = json.dumps(face_enc.tolist())

    with data_lock:
        last_recognition_data = results

    return jsonify(results)

# ==============================
# Routes
# ==============================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/recognition_data')
def recognition_data():
    with data_lock: # Making sure data exist before using it
        return jsonify(last_recognition_data)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    global last_unknown_encoding

    if request.method == 'POST':
        username = request.form.get('username')
        jenis_kelamin = request.form.get("jenis-Kelamin")
        jurusan = request.form.get('jurusan')

        # Save new user to database
        supabase.table("face-recognition-with-flask").insert({
            "username": username,
            "jenis_kelamin": jenis_kelamin,
            "encoding": last_unknown_encoding,
            "jurusan": jurusan,
            "time_added": datetime.now().isoformat()
        }).execute()

        # Refresh known faces
        global known_ids, known_encodings
        with data_lock:
            known_ids, known_encodings = load_known_faces()

        last_unknown_encoding = None
        return redirect(url_for("index"))

    return redirect(url_for("index"))

@app.route('/users')
def users():
    # Take all data from database
    user_data = (supabase.table("face-recognition-with-flask")
                 .select("user_id, username, jenis_kelamin, jurusan")
                 .execute())
    return jsonify(user_data.data)

@app.route('/delete_user/<user_id>', methods=['POST'])
def delete_user(user_id):
    # Hapus user berdasarkan id
    supabase.table("face-recognition-with-flask").delete().eq("user_id", user_id).execute()

    # Refresh known faces
    global known_ids, known_encodings
    with data_lock:
        known_ids, known_encodings = load_known_faces()

    return jsonify({"message": f"User {user_id} deleted successfully"})

@app.route('/download_users_csv')
def download_users():
    # Query semua user dari Supabase
    response = supabase.table("face-recognition-with-flask").select("*").execute()
    users = response.data

    if not users:
        return "No users found", 404

    # Buat response CSV
    def generate():
        data = csv.StringIO()
        writer = csv.DictWriter(data, fieldnames=users[0].keys())
        writer.writeheader()
        for user in users:
            writer.writerow(user)
        yield data.getvalue()

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=users.csv"}
    )

@app.route('/download_users_excel')
def download_users_excel():
    # Ambil data dari Supabase
    response = supabase.table("face-recognition-with-flask").select("*").execute()
    users = response.data

    if not users:
        return "No users found", 404

    # Buat workbook baru
    wb = Workbook()
    ws = wb.active
    ws.title = "Users"

    # Tulis header
    headers = list(users[0].keys())
    ws.append(headers)

    # Tulis data baris demi baris
    for user in users:
        ws.append(list(user.values()))

    # Simpan ke memory (BytesIO)
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="users.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ) 
# ==============================
# Run App
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug_mode = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
