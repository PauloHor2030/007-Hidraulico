from __future__ import annotations
import os, time, json
from flask import Flask, request, jsonify
from waitress import serve

# Firebase Admin
import firebase_admin
from firebase_admin import credentials, firestore

# Init Firebase (Service Account via env GOOGLE_APPLICATION_CREDENTIALS)
if not firebase_admin._apps:
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        firebase_admin.initialize_app(credentials.Certificate(cred_path))
    else:
        # attempt ADC if running with service account in VM
        firebase_admin.initialize_app()
db = firestore.client()

app = Flask(__name__)

@app.get("/healthz")
def healthz():
    return "ok\n", 200, {"Content-Type":"text/plain; charset=utf-8"}

def write_raw(doc: dict, ip: str|None):
    try:
        db.collection("t_ingest_raw").add({
            "f_received_at_ms": int(time.time()*1000),
            "f_source_ip": ip,
            "f_payload": doc
        })
    except Exception as e:
        # don't crash ingestion if Firestore fails
        print("Firestore error:", e)

def _ingest_core():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:
        try:
            payload = json.loads(request.data.decode("utf-8"))
        except Exception:
            return jsonify({"ok": False, "err": "invalid json"}), 400

    write_raw(payload or {}, ip)
    return jsonify({"ok": True}), 200

# Primary route required by the device
@app.post("/api/caminho")
def ingest_caminho():
    return _ingest_core()

# Legacy compatibility (optional)
@app.post("/api/temperatura")
def ingest_legacy():
    return _ingest_core()

# Short route (optional)
@app.post("/i/<device_id>")
def ingest_short(device_id):
    data = request.get_json(silent=True) or {}
    data["device_id_path"] = device_id
    request._cached_json = data
    return _ingest_core()

if __name__ == "__main__":
    PORT = int(os.getenv("FLASK_RUN_PORT", os.getenv("PORT", 5000)))
    HOST = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    print(f"Starting ThermoSafe Hidraulico FAST on http://{HOST}:{PORT}")
    serve(app, host=HOST, port=PORT, threads=8)
