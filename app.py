from flask import Flask, render_template, Response, request, jsonify
from database.supabase_client import supabase

import cv2
import face_recognition
import json
import threading

# ==============================
# Load Known Faces
# ==============================
def load_known_faces():
    user_data = (supabase.table('face-recognition-with-flask')
                .select("user_id", "encoding")
                .execute()
                )

    known_ids = []
    known_encodings = []

    for data in user_data.data:
        known_ids.append(data['user_id'])
        encoding = data['encoding']
        if isinstance(encoding, str):
            encoding = json.loads(encoding)
        known_encodings.append(encoding)
        
    return known_ids, known_encodings


# ==============================
# Flask Instance
# ==============================
app = Flask(__name__, template_folder='templates', static_folder='static', static_url_path='/')

known_ids, known_encodings = load_known_faces()

# Variabel global utk komunikasi data
last_recognition_data = []
last_unknown_encoding = None
data_lock = threading.Lock()


# ==============================
# Video Streaming & Recognition
# ==============================
def gen_frames_recog():
    global last_recognition_data, last_unknown_encoding

    camera = cv2.VideoCapture(0)

    while True:
        ret, frame = camera.read()
        if frame is None:
            break
        else:
            frame_small = cv2.resize(frame, (0, 0), None, 0.25, 0.25)
            rgb_frame = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            
            results = []  # simpan semua wajah yang dikenali
            
            for face_enc, (top, right, bottom, left) in zip(face_encodings, face_locations):
                matches = face_recognition.compare_faces(known_encodings, face_enc, tolerance=0.5)
                face_distance = face_recognition.face_distance(known_encodings, face_enc)
                
                index = None
                if len(face_distance) > 0:
                    index = face_distance.argmin()
                    
                is_known = False
                if index is not None and matches[index]:
                    user_id = known_ids[index]
                    user_data = (supabase.table("face-recognition-with-flask")
                                .select("user_id, username, major")
                                .eq("user_id", user_id)
                                .execute())  
                    if user_data.data:
                        text = user_data.data[0]['username']   
                        major = user_data.data[0]['major']
                        results.append({
                            "user_id": user_id,
                            "username": text,
                            "major": major
                        })
                        is_known = True
                else:
                    # wajah tidak dikenal
                    text = "Unknown"
                    major = "-"
                    results.append({
                        "user_id": None,
                        "username": text,
                        "major": major
                    })
                    last_unknown_encoding = json.dumps(face_enc.tolist())

                # Draw rectangle and label
                top, right, bottom, left = top * 4, right * 4, bottom * 4, left * 4
                if is_known:
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(frame, text, (left, top - 10),
                                cv2.FONT_HERSHEY_COMPLEX, 0.7, (0, 255, 0), 2)
                else:    
                    cv2.rectangle(frame, (left, top), (right, bottom), (255, 0, 0), 2)
                    cv2.putText(frame, text, (left, top - 10),
                                cv2.FONT_HERSHEY_COMPLEX, 0.7, (255, 0, 0), 2)

                            
            # update hasil ke variabel global
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
    with data_lock:
        return jsonify(last_recognition_data)


@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    global last_unknown_encoding

    if request.method == 'POST':
        username = request.form.get('username')
        major = request.form.get('major')

        if last_unknown_encoding is None:
            return "No unknown face to save", 400

        # Simpan ke Supabase
        supabase.table("face-recognition-with-flask").insert({
            "username": username,
            "major": major,
            "encoding": last_unknown_encoding
        }).execute()

        # refresh known faces
        global known_ids, known_encodings
        known_ids, known_encodings = load_known_faces()

        last_unknown_encoding = None
        return render_template("index.html")

    return render_template("add_user.html")

@app.route('/users')
def users():
    # Ambil semua data dari Supabase
    user_data = (supabase.table("face-recognition-with-flask")
                 .select("user_id, username, major")
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


# ==============================
# Run App
# ==============================
if __name__ == '__main__':
    app.run(debug=True)
