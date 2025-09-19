# para rodar este programa: python .\teste_read.py
from pathlib import Path
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore

# caminho do JSON da conta de serviço
cred = credentials.Certificate(str(Path("thermosafehidraulico-firebase-adminsdk-fbsvc-1f30ae4b7a.json")))
firebase_admin.initialize_app(cred)
db = firestore.client()

# vamos ler leituras do medidor MTR-0001
f_medidor_id = "MTR-0001"
now = datetime.now(timezone.utc)
month = f"{now.year:04d}_{now.month:02d}"

# caminho: t_medidor/MTR-0001/t_leituras/AAAA_MM/items/*
items_ref = (
    db.collection("t_medidor")
      .document(f_medidor_id)
      .collection("t_leituras")
      .document(month)
      .collection("items")
      .order_by("f_ts_utc")
      .limit(10)
)

print(f"Buscando leituras de {f_medidor_id} no bucket {month}...")
docs = items_ref.stream()

for i, d in enumerate(docs, 1):
    data = d.to_dict()
    print(f"{i}: {data.get('f_ts_utc')} | {data.get('f_valor_m3')} m³ | pulsos={data.get('f_pulsos')}")
