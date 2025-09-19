# python .\teste_read_all.py

# Exportar JSONL do mês corrente:
# # python .\teste_read_all.py --dump-json                        #JSONL do mês corrente:
# → arquivo em: .\exports\leituras_<AAAA_MM>.jsonl


# python .\teste_read_all.py --month 2025_09 --dump-json        # mês específico (ex.: setembro/2025):



# python .\teste_read_all.py --dump-json --medidor MTR-0001     # Exportar apenas de um medidor:
# → arquivo em: .\exports\leituras_<AAAA_MM>_MTR-0001.jsonl


from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, timezone 
from typing import Optional
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, firestore


# ---------- Config de credenciais ----------
# Tenta carregar do .env (GOOGLE_APPLICATION_CREDENTIALS); se não houver, usa o arquivo abaixo.
load_dotenv()
CRED_ENV = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

# Troque pelo nome exato do seu JSON se não usar .env
DEFAULT_JSON = "thermosafehidraulico-firebase-adminsdk-fbsvc-1f30ae4b7a.json"

BASE_DIR = Path(__file__).resolve().parent
if CRED_ENV:
    cred_path = Path(CRED_ENV)
    if not cred_path.is_absolute():
        cred_path = (BASE_DIR / cred_path).resolve()
else:
    cred_path = (BASE_DIR / DEFAULT_JSON).resolve()

if not cred_path.exists():
    raise FileNotFoundError(f"Credencial não encontrada: {cred_path}")

# ---------- Init Firebase ----------
cred = credentials.Certificate(str(cred_path))
firebase_admin.initialize_app(cred)
db = firestore.client()


def hr(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_doc(doc_snap, max_field_len: int = 80) -> None:
    data = doc_snap.to_dict() or {}
    doc_id = doc_snap.id
    # imprime campos-chave, truncando para não poluir
    def trunc(v):
        s = str(v)
        return s if len(s) <= max_field_len else s[:max_field_len] + "…"
    pairs = ", ".join(f"{k}={trunc(v)}" for k, v in data.items())
    print(f"- {doc_id}: {pairs}")


# ---------- 1) t_condominio ----------
hr("Coleção: t_condominio")
cond_q = db.collection("t_condominio").limit(50).stream()
count = 0
for d in cond_q:
    print_doc(d)
    count += 1
if count == 0:
    print("(vazio)")

# ---------- 2) t_localizacao ----------
hr("Coleção: t_localizacao")
loc_q = db.collection("t_localizacao").limit(50).stream()
count = 0
for d in loc_q:
    print_doc(d)
    count += 1
if count == 0:
    print("(vazio)")

# ---------- 3) t_cliente ----------
hr("Coleção: t_cliente")
cli_q = db.collection("t_cliente").limit(50).stream()
count = 0
for d in cli_q:
    print_doc(d)
    count += 1
if count == 0:
    print("(vazio)")

# ---------- 4) t_medidor + subcoleções t_leituras ----------
hr("Coleção: t_medidor (com subcoleções t_leituras/AAAA_MM/items)")
med_q = db.collection("t_medidor").limit(50).stream()
med_count = 0
for med in med_q:
    med_count += 1
    print_doc(med)
    med_ref = db.collection("t_medidor").document(med.id)

    # lista os "buckets" mensais (documentos dentro de t_leituras, ex: 2025_09)
    print("  Subcoleções de leituras (buckets mensais):")
    buckets = med_ref.collection("t_leituras").stream()
    bucket_ids = [b.id for b in buckets]
    if not bucket_ids:
        print("   (sem leituras)")
        continue

    for b_id in sorted(bucket_ids):
        print(f"   - Bucket {b_id}:")
        items_ref = med_ref.collection("t_leituras").document(b_id).collection("items")
        # mostra até 10 leituras ordenadas por timestamp
        try:
            items_q = items_ref.order_by("f_ts_utc").limit(10).stream()
        except Exception:
            # se ainda não houver índice, tenta sem order_by
            items_q = items_ref.limit(10).stream()

        item_count = 0
        for it in items_q:
            item_count += 1
            data = it.to_dict() or {}
            print(f"      • {it.id} | f_ts_utc={data.get('f_ts_utc')} | f_valor_m3={data.get('f_valor_m3')} | f_pulsos={data.get('f_pulsos')}")
        if item_count == 0:
            print("      (sem items)")

if med_count == 0:
    print("(vazio)")

print("\n✅ Leitura concluída.")
