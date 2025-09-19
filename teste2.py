import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("./thermosafehidraulico-firebase-adminsdk-fbsvc-1f30ae4b7a.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

# insere corretamente na coleção t_teste
doc_ref = db.collection("t_teste2").document()
doc_ref.set({"f_msg": "olá, firestore2!"})

print(f"Gravado em {doc_ref.path} ✅")