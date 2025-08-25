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
import time
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

import base64
import numpy as np

# Instace flask utama
app = Flask(__name__, template_folder='templates', static_folder='static', static_url_path='/')

# Configuration untuk optimasi
FACE_RECOGNITION_TOLERANCE = 0.6  # Turunkan toleransi untuk speed
FRAME_SCALE = 0.2  # Lebih kecil lagi untuk processing
MAX_CONCURRENT_PROCESSING = 2  # Batasi concurrent processing
PROCESSING_INTERVAL = 2  # Naikkan interval jadi 2 detik

# Thread pool untuk async processing
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_PROCESSING)

# Queue untuk frame processing
frame_queue = Queue(maxsize=3)  # Buffer terbatas untuk mencegah memory leak

# Cache untuk known faces dengan TTL
face_cache = {
    'data': None,
    'last_update': 0,
    'ttl': 300  # 5 menit cache
}

def load_known_faces():
    """Load faces with caching mechanism"""
    current_time = time.time()
    
    # Check cache validity
    if (face_cache['data'] is not None and 
        current_time - face_cache['last_update'] < face_cache['ttl']):
        return face_cache['data']['known_ids'], face_cache['data']['known_encodings']
    
    try:
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
            known_encodings.append(np.array(encoding))
        
        # Update cache
        face_cache['data'] = {
            'known_ids': known_ids,
            'known_encodings': known_encodings
        }
        face_cache['last_update'] = current_time
        
        return known_ids, known_encodings
    except Exception as e:
        print(f"Error loading faces: {e}")
        # Return empty lists if error
        return [], []

# Global variables 
last_recognition_data = []
last_unknown_encoding = None
data_lock = threading.Lock()
processing_lock = threading.Lock()  # Untuk mencegah concurrent processing
is_processing = False

# Load id dan encoding menggunakan functionnya
with data_lock:
    known_ids, known_encodings = load_known_faces()

def process_frame_async(frame_data):
    """Async frame processing function"""
    global last_recognition_data, last_unknown_encoding, is_processing
    
    # Check if already processing
    with processing_lock:
        if is_processing:
            return
        is_processing = True
    
    try:
        # Decode frame
        if frame_data.startswith("data:image"):
            frame_data = frame_data.split(",")[1]
        
        img_bytes = base64.b64decode(frame_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return

        # Resize lebih kecil untuk processing yang lebih cepat
        frame_small = cv2.resize(frame, (0, 0), None, FRAME_SCALE, FRAME_SCALE)
        rgb_frame = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)

        # Face recognition dengan optimasi
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")  # HOG lebih cepat dari CNN
        
        if not face_locations:  # Skip encoding jika tidak ada wajah
            with data_lock:
                last_recognition_data = []
            return

        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations, num_jitters=1)  # Kurangi jitters

        results = []
        current_known_ids, current_known_encodings = load_known_faces()

        for i, face_enc in enumerate(face_encodings):
            # Scale face location kembali ke ukuran asli
            top, right, bottom, left = face_locations[i]
            scale_factor = 1 / FRAME_SCALE
            top = int(top * scale_factor)
            right = int(right * scale_factor)
            bottom = int(bottom * scale_factor)
            left = int(left * scale_factor)
            
            face_box = {
                "x": left,
                "y": top,
                "width": right - left,
                "height": bottom - top
            }
            
            if current_known_encodings:
                matches = face_recognition.compare_faces(
                    current_known_encodings, face_enc, 
                    tolerance=FACE_RECOGNITION_TOLERANCE
                )
                face_distance = face_recognition.face_distance(current_known_encodings, face_enc)

                index = None
                if len(face_distance) > 0:
                    index = face_distance.argmin()

                if index is not None and matches[index]:
                    user_id = current_known_ids[index]
                    # Cache user data untuk menghindari query berulang
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
            else:
                results.append({
                    "user_id": None,
                    "username": "Unknown",
                    "jenis_kelamin": "-",
                    "jurusan": "-",
                    "face_box": face_box,
                    "is_known": False
                })

        with data_lock:
            last_recognition_data = results
            
    except Exception as e:
        print(f"Error in face recognition: {e}")
    finally:
        with processing_lock:
            is_processing = False

@app.route('/process_frame', methods=['POST'])
def process_frame():
    """Endpoint untuk menerima frame dan memproses secara async"""
    data = request.json
    frame_data = data['frame']
    
    # Add frame to queue (non-blocking)
    try:
        if not frame_queue.full():
            frame_queue.put_nowait(frame_data)
            # Process async
            executor.submit(process_frame_async, frame_data)
    except:
        pass  # Ignore if queue is full
    
    # Return current results immediately
    with data_lock:
        return jsonify(last_recognition_data)

# ==============================
# Routes (sama seperti sebelumnya)
# ==============================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/recognition_data')
def recognition_data():
    with data_lock:
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

        # Clear cache to force refresh
        face_cache['data'] = None
        
        last_unknown_encoding = None
        return redirect(url_for("index"))

    return redirect(url_for("index"))

@app.route('/users')
def users():
    user_data = (supabase.table("face-recognition-with-flask")
                 .select("user_id, username, jenis_kelamin, jurusan")
                 .execute())
    return jsonify(user_data.data)

@app.route('/delete_user/<user_id>', methods=['POST'])
def delete_user(user_id):
    supabase.table("face-recognition-with-flask").delete().eq("user_id", user_id).execute()
    
    # Clear cache
    face_cache['data'] = None
    
    return jsonify({"message": f"User {user_id} deleted successfully"})

@app.route('/download_users_csv')
def download_users():
    response = supabase.table("face-recognition-with-flask").select("*").execute()
    users = response.data

    if not users:
        return "No users found", 404

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
    response = supabase.table("face-recognition-with-flask").select("*").execute()
    users = response.data

    if not users:
        return "No users found", 404

    wb = Workbook()
    ws = wb.active
    ws.title = "Users"

    headers = list(users[0].keys())
    ws.append(headers)

    for user in users:
        ws.append(list(user.values()))

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="users.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Cleanup on shutdown
@app.teardown_appcontext
def cleanup(error):
    executor.shutdown(wait=False)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug_mode = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug_mode, threaded=True)