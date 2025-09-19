# python .\purge_firestore.py

from __future__ import annotations
import os, time
from pathlib import Path
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Config
COLS_ROOT = ["t_condominio", "t_localizacao", "t_cliente", "t_medidor"]

def init_db():
    load_dotenv()
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not cred_path:
        raise RuntimeError("Defina GOOGLE_APPLICATION_CREDENTIALS no .env")
    cred_path = str(Path(cred_path).resolve())
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(cred_path))
    return firestore.client()

def delete_collection(coll_ref, batch_size=500):
    docs = list(coll_ref.limit(batch_size).stream())
    deleted = 0
    for doc in docs:
        doc.reference.delete()
        deleted += 1
    return deleted

def purge_readings(db):
    # apaga por collection group "items" (subcoleção de leituras)
    print("Apagando collection group: t_leituras/*/items …")
    group = db.collection_group("items")
    count = 0
    for snap in group.stream():
        snap.reference.delete()
        count += 1
        if count % 1000 == 0:
            print(f"  deletados {count} docs de leitura…")
    print(f"  total leituras apagadas: {count}")

    # apaga os documentos "bucket" (YYYY_MM) nas subcoleções t_leituras
    print("Apagando documentos de bucket (t_leituras/AAAA_MM)…")
    meds = db.collection("t_medidor").stream()
    buckets_deleted = 0
    for m in meds:
        for b in db.collection("t_medidor").document(m.id).collection("t_leituras").stream():
            b.reference.delete()
            buckets_deleted += 1
    print(f"  buckets apagados: {buckets_deleted}")

def purge_roots(db):
    for name in COLS_ROOT:
        print(f"Apagando coleção raiz: {name}")
        total = 0
        while True:
            d = delete_collection(db.collection(name))
            total += d
            if d == 0:
                break
            print(f"  +{d} (acumulado {total})")
        print(f"  total apagado em {name}: {total}")

if __name__ == "__main__":
    db = init_db()
    # ordem: leituras primeiro (subcoleções), depois coleções raiz
    purge_readings(db)
    purge_roots(db)
    print("✅ Purge completo.")
