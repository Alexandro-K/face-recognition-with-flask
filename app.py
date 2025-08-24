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

CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "0")  # "0" atau URL RTSP/MJPEG
def open_camera():
    try:
        src = int(CAMERA_SOURCE)
    except ValueError:
        src = CAMERA_SOURCE
    return cv2.VideoCapture(src)

# ==============================
# Load Known Faces
# ==============================
def load_known_faces():
    # Taking data from database
    user_data = (supabase.table('face-recognition-with-flask')
                .select("user_id", "encoding")
                .execute()
                )

    known_ids = []
    known_encodings = []

    # Saving data to known ids and encodings
    for data in user_data.data:
        known_ids.append(data['user_id'])
        encoding = data['encoding']
        if isinstance(encoding, str): 
            encoding = json.loads(encoding) # Change into py list/array
        known_encodings.append(encoding)
        
    return known_ids, known_encodings

# ==============================
# Flask Instance
# ==============================
app = Flask(__name__, template_folder='templates', static_folder='static', static_url_path='/')

known_ids, known_encodings = load_known_faces()

# Global variables
last_recognition_data = []
last_unknown_encoding = None
data_lock = threading.Lock()
frame_count = 0
process_this_frame = True

# ==============================
# Video Streaming & Recognition
# ==============================
def gen_frames_recog():
    global last_recognition_data, last_unknown_encoding, frame_count

    camera = open_camera()
    while True:
        ret, frame = camera.read()
        frame_count += 1
        
        if frame_count % 3 == 0:
            process_this_frame = True
        else:
            process_this_frame = False
            
        if process_this_frame:
            if frame is None:
                break
            else:
                frame_small = cv2.resize(frame, (0, 0), None, 0.25, 0.25)
                rgb_frame = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_frame)
                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                
                results = []  # Save all known faces
                
                for face_enc, (top, right, bottom, left) in zip(face_encodings, face_locations):
                    matches = face_recognition.compare_faces(known_encodings, face_enc, tolerance=0.6)
                    face_distance = face_recognition.face_distance(known_encodings, face_enc)
                                    
                    index = None
                    if len(face_distance) > 0:
                        index = face_distance.argmin()
                        
                    is_known = False
                    # If face is known
                    if index is not None and matches[index]:
                        user_id = known_ids[index]
                        user_data = (supabase.table("face-recognition-with-flask")
                                    .select("user_id, username, jenis_kelamin, jurusan")
                                    .eq("user_id", user_id)
                                    .execute())  
                        if user_data.data:
                            text = user_data.data[0]['username']   
                            jenis_kelamin = user_data.data[0]['jenis_kelamin']
                            jurusan = user_data.data[0]['jurusan']
                            results.append({
                                "user_id": user_id,
                                "username": text,
                                "jenis_kelamin": jenis_kelamin,
                                "jurusan": jurusan
                            })
                            is_known = True
                    # If face is unknown
                    else:
                        text = "Unknown"
                        jenis_kelamin = "-"
                        jurusan = "-"
                        results.append({
                            "user_id": None,
                            "username": text,
                            "jenis_kelamin": jenis_kelamin,
                            "jurusan": jurusan,
                        })
                        last_unknown_encoding = json.dumps(face_enc.tolist()) # Always save the encoding if face is unknown

                    # Draw rectangle and label
                    top, right, bottom, left = top * 4, right * 4, bottom * 4, left * 4
                    if is_known:
                        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                        cv2.putText(frame, text, (left, top - 10),
                                    cv2.FONT_HERSHEY_COMPLEX, 0.7, (0, 255, 0), 2)
                    else:    
                        cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
                        cv2.putText(frame, text, (left, top - 10),
                                    cv2.FONT_HERSHEY_COMPLEX, 0.7, (0, 0, 255), 2)

                                
                # Update data to global variable
                with data_lock:
                    last_recognition_data = results
                
                # Encode frame
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()
                
                yield(b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# ==============================
# Routes
# ==============================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames_recog(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

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

        # if last_unknown_encoding is None:
        #     return "No unknown face to save", 400

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
    port = int(os.environ.get("PORT", 8080))  # Railway kasih PORT env
    app.run(host="0.0.0.0", port=port)


