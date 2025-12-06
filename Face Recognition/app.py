# app.py
import os
import time
import base64
import math
from datetime import datetime
from flask import Flask, render_template, Response, request, jsonify
import cv2
import numpy as np
import pickle
import face_recognition
import firebase_admin
from firebase_admin import credentials, db
import mediapipe as mp

#  CONFIG
DB_NODE = "students"              # Firebase node
SERVICE_ACCOUNT = "serviceAccountKey.json"
ENCODE_FILE = "EncodeFile.p"
IMAGES_DIR = "Images"             # Folder containing student images

ALLOWED_LAT = 19.85486            # Campus latitude
ALLOWED_LON = 75.25178            # Campus longitude
RADIUS_KM = 0.1                   # 100 meters radius allowed

SHOW_DURATION = 5                 # Duration to show status
BLINK_EAR_THRESHOLD = 0.22
BLINK_CONSEC_FRAMES = 2

# DEMO MODE: if True, attendance will be marked even outside timetable slots
DEMO_MODE = False
DEMO_SLOT = "10:00-11:00"
DEMO_SUBJECT = "Demo Lecture"
DEMO_DAY = "DemoDay"

#  Firebase Initialization
cred = credentials.Certificate(SERVICE_ACCOUNT)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://faceattendancerealtime-8d6d4-default-rtdb.firebaseio.com/'
})

# Test Firebase connection
try:
    test_ref = db.reference("connection_test")
    test_ref.set({"status": "connected"})
    print(" Firebase connection test successful!")
except Exception as e:
    print(" Firebase connection failed:", e)

# Load Encodings
with open(ENCODE_FILE, "rb") as f:
    encodeListKnown, studentIds = pickle.load(f)

studentIds = [str(sid) for sid in studentIds]
print("Loaded student IDs:", studentIds)

#  Mediapipe Setup
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(refine_landmarks=True, max_num_faces=1)
LEFT_EYE_LANDMARKS = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_LANDMARKS = [362, 385, 387, 263, 373, 380]

def EAR(eye):
    A = np.linalg.norm(eye[1] - eye[5])
    B = np.linalg.norm(eye[2] - eye[4])
    C = np.linalg.norm(eye[0] - eye[3])
    if C == 0:
        return 0
    return (A + B) / (2.0 * C)

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def is_location_ok(client_loc):
    if client_loc is None:
        return False
    dist = haversine_km(client_loc['lat'], client_loc['lon'], ALLOWED_LAT, ALLOWED_LON)
    return dist <= RADIUS_KM

#  Flask App Setup =
app = Flask(__name__)
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

client_location = None

last_status = {
    "id": None,
    "name": "",
    "major": "",
    "photo_data": None,
    "status": "Idle",
    "timestamp": 0,
    "demo": DEMO_MODE
}

blink_state = {}
cooldown = {}
student_cache = {}

#  Firebase Helpers
def fetch_student_info_from_db(student_id):
    """Fetch student info and photo (local image)."""
    if student_id in student_cache:
        return student_cache[student_id]

    ref = db.reference(f"{DB_NODE}/{student_id}")
    info = ref.get()
    if not info:
        return None

    photo_data = None
    local_path = os.path.join(IMAGES_DIR, f"{student_id}.jpg")
    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            photo_data = "data:image/jpeg;base64," + b64
    else:
        local_path_png = os.path.join(IMAGES_DIR, f"{student_id}.png")
        if os.path.exists(local_path_png):
            with open(local_path_png, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
                photo_data = "data:image/png;base64," + b64

    info["_photo_data"] = photo_data
    student_cache[student_id] = info
    return info

#  Timetable Logic
def get_timetable_for_day(day_name):
    ref = db.reference(f"Timetable/{day_name}")
    t = ref.get()
    return t or {}

def parse_time_str(tstr):
    h, m = map(int, tstr.split(":"))
    return h * 60 + m

def get_current_slot_and_subject(now=None):
    if now is None:
        now = datetime.now()
    day_name = now.strftime("%A")
    timetable = get_timetable_for_day(day_name)
    if not timetable:
        return None, None, day_name

    now_min = now.hour * 60 + now.minute
    for slot, subject in timetable.items():
        try:
            start, end = slot.split("-")
            if parse_time_str(start) <= now_min < parse_time_str(end):
                return slot, subject, day_name
        except Exception:
            continue
    return None, None, day_name

def mark_attendance_in_slot(student_id, slot, subject, day_name):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Lecture-wise attendance node
    ref = db.reference(f"Attendance/{date_str}/{day_name}/{slot}/{subject}/{student_id}")
    ref.set({
        "status": "Present",
        "time": time_str
    })

    # Update student summary
    student_ref = db.reference(f"{DB_NODE}/{student_id}")
    info = student_ref.get() or {}
    total = int(info.get("total_attendance", 0)) + 1
    student_ref.update({
        "last_attendance": time_str,
        "total_attendance": total
    })
    print(f" Attendance recorded for {student_id} in {subject} ({slot}) on {day_name}")

#  Routes (Home/Status/Location) =
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/update_location", methods=["POST"])
def update_location():
    global client_location
    data = request.get_json()
    if not data:
        return jsonify({"ok": False}), 400
    lat = data.get("lat")
    lon = data.get("lon")
    if lat is None or lon is None:
        return jsonify({"ok": False}), 400
    client_location = {"lat": float(lat), "lon": float(lon)}
    return jsonify({"ok": True})

@app.route("/status")
def status():
    # also report current demo mode to UI
    last_status["demo"] = DEMO_MODE
    return jsonify(last_status)

#  Timetable Dashboard
@app.route("/timetable")
def timetable_page():
    return render_template("timetable.html")

@app.route("/get_timetable_data")
def get_timetable_data():
    ref = db.reference("Timetable")
    data = ref.get() or {}
    return jsonify(data)

@app.route("/update_timetable", methods=["POST"])
def update_timetable():
    try:
        payload = request.get_json()
        day = payload["day"]
        slot = payload["slot"]
        subject = payload["subject"]
        ref = db.reference(f"Timetable/{day}/{slot}")
        ref.set(subject)
        return jsonify({"success": True, "message": "Timetable updated successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

#  Demo Mode Toggles
@app.route("/demo/on")
def demo_on():
    global DEMO_MODE
    DEMO_MODE = True
    print("🟢 Demo Mode ENABLED")
    return jsonify({"ok": True, "demo": DEMO_MODE})

@app.route("/demo/off")
def demo_off():
    global DEMO_MODE
    DEMO_MODE = False
    print(" Demo Mode DISABLED")
    return jsonify({"ok": True, "demo": DEMO_MODE})

#  Video Feed
def serve_mjpeg():
    global last_status, client_location
    show_until = 0

    while True:
        success, frame = camera.read()
        if not success:
            time.sleep(0.1)
            continue

        small = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        face_locs = face_recognition.face_locations(rgb_small)
        encodes = face_recognition.face_encodings(rgb_small, face_locs)

        for encodeFace, faceLoc in zip(encodes, face_locs):
            matches = face_recognition.compare_faces(encodeListKnown, encodeFace, tolerance=0.6)
            faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
            if len(faceDis) == 0:
                continue
            matchIndex = np.argmin(faceDis)
            if matches[matchIndex]:
                student_id = str(studentIds[matchIndex])
                print(f" Recognized student ID: {student_id}")

                # Draw bounding box
                y1, x2, y2, x1 = [val * 4 for val in faceLoc]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Blink Detection
                if student_id not in blink_state:
                    blink_state[student_id] = {"closed_frames": 0, "blinked": False}

                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(img_rgb)
                if results.multi_face_landmarks:
                    mesh_points = np.array([[p.x * frame.shape[1], p.y * frame.shape[0]]
                                            for p in results.multi_face_landmarks[0].landmark])
                    left_eye = mesh_points[LEFT_EYE_LANDMARKS]
                    right_eye = mesh_points[RIGHT_EYE_LANDMARKS]
                    leftEAR = EAR(left_eye)
                    rightEAR = EAR(right_eye)
                    ear_avg = (leftEAR + rightEAR) / 2.0

                    if ear_avg < BLINK_EAR_THRESHOLD:
                        blink_state[student_id]["closed_frames"] += 1
                    else:
                        if blink_state[student_id]["closed_frames"] >= BLINK_CONSEC_FRAMES:
                            blink_state[student_id]["blinked"] = True
                        blink_state[student_id]["closed_frames"] = 0

                location_ok = is_location_ok(client_location)
                last_mark = cooldown.get(student_id, 0)

                #  Attendance marking logic
                if (time.time() - last_mark > 5):  # cooldown
                    slot, subject, day_name = get_current_slot_and_subject()

                    if slot and subject:
                        # Normal case: valid timetable slot
                        mark_attendance_in_slot(student_id, slot, subject, day_name)
                        status_message = f" Attendance marked for {subject} ({slot})"
                    else:
                        if DEMO_MODE:
                            # Demo bypass: allow marking even outside timetable
                            mark_attendance_in_slot(student_id, DEMO_SLOT, DEMO_SUBJECT, DEMO_DAY)
                            status_message = f" Attendance marked [Demo Mode] for {DEMO_SUBJECT} ({DEMO_SLOT})"
                        else:
                            status_message = "⚠️ No active lecture slot right now."
                            print(status_message)

                    cooldown[student_id] = time.time()
                    blink_state[student_id]["blinked"] = False

                    info = fetch_student_info_from_db(student_id)
                    last_status.update({
                        "id": student_id,
                        "name": info.get("name", student_id) if info else student_id,
                        "major": info.get("major", "") if info else "",
                        "photo_data": info.get("_photo_data") if info else None,
                        "status": status_message,
                        "timestamp": time.time(),
                        "demo": DEMO_MODE
                    })
                    show_until = time.time() + SHOW_DURATION

                else:
                    # Instant feedback while in cooldown
                    info = fetch_student_info_from_db(student_id)
                    slot, subject, day_name = get_current_slot_and_subject()
                    if slot and subject:
                        status_text = f"Please blink to verify for {subject} ({slot})"
                    else:
                        status_text = "️ No active lecture slot right now." if not DEMO_MODE else \
                                      f" Demo Mode: ready to mark for {DEMO_SUBJECT} ({DEMO_SLOT})"
                    last_status.update({
                        "id": student_id,
                        "name": info.get("name", student_id) if info else student_id,
                        "major": info.get("major", "") if info else "",
                        "photo_data": info.get("_photo_data") if info else None,
                        "status": status_text,
                        "timestamp": time.time(),
                        "demo": DEMO_MODE
                    })
                break

        if show_until and time.time() > show_until:
            last_status.update({"id": None, "name": "", "major": "", "photo_data": None, "status": "Idle", "demo": DEMO_MODE})
            show_until = 0

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route("/video_feed")
def video_feed():
    return Response(serve_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")

#  Run App
if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
    finally:
        if camera.isOpened():
            camera.release()
            print(" Camera released safely.")
