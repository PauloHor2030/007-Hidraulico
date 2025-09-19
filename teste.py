import firebase_admin
from firebase_admin import credentials, firestore

# caminho para o JSON da conta de serviço (na mesma pasta do teste.py)
cred = credentials.Certificate("./thermosafehidraulico-firebase-adminsdk-fbsvc-1f30ae4b7a.json")

# inicializa o app Firebase
firebase_admin.initialize_app(cred)

# conecta no Firestore
db = firestore.client()

# insere um documento simples
db.collection("t_teste").add({"f_msg": "olá, firestore!"})

print("Consegui gravar no Firestore ✅")
