from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import pandas as pd
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

def init_db():
    load_dotenv()
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not cred_path:
        raise RuntimeError("Defina GOOGLE_APPLICATION_CREDENTIALS no .env")
    cred_path = str(Path(cred_path).resolve())
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(cred_path))
    return firestore.client()

def now_utc(): return datetime.now(timezone.utc)

def coerce_bool(x):
    if isinstance(x, bool): return x
    s = str(x).strip().lower()
    return s in ("true","1","sim","yes","y","t")

def load_xlsx(path: Path) -> Dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(path)
    dfs = {}
    for sheet in ["t_localizacao","t_condominio","t_cliente","t_medidor"]:
        if sheet in xls.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet)
            dfs[sheet] = df.fillna("")
        else:
            dfs[sheet] = pd.DataFrame()
    return dfs

def insert_localizacao(db, row: Dict[str, Any]) -> str:
    doc = {
        "f_logradouro": row.get("f_logradouro",""),
        "f_numero": row.get("f_numero",""),
        "f_bairro": row.get("f_bairro",""),
        "f_cidade": row.get("f_cidade",""),
        "f_uf": row.get("f_uf",""),
        "f_cep": row.get("f_cep",""),
        "f_complemento": row.get("f_complemento","") or "",
        "f_geo": None if not row.get("f_geo_lat") else {"lat": float(row["f_geo_lat"]), "lon": float(row.get("f_geo_lon",0) or 0)},
        "f_created_at": now_utc(),
        "f_ativo": True,
    }
    ref = db.collection("t_localizacao").add(doc)[1]
    return ref.id

def insert_condominio(db, row: Dict[str, Any]) -> str:
    doc = {
        "f_nome_condominio": row.get("f_nome_condominio",""),
        "f_tipo": row.get("f_tipo","condominio"),
        "f_localizacao": row.get("f_localizacao","") or None,
        "f_nome_resp": row.get("f_nome_resp","") or None,
        "f_fone_resp": row.get("f_fone_resp","") or None,
        "f_email_resp": row.get("f_email_resp","") or None,
        "f_created_at": now_utc(),
        "f_ativo": True,
    }
    ref = db.collection("t_condominio").add(doc)[1]
    return ref.id

def insert_cliente(db, row: Dict[str, Any]) -> str:
    doc = {
        "f_nome_cliente": row.get("f_nome_cliente",""),
        "f_cpf": str(row.get("f_cpf","")).replace(".","").replace("-","").strip(),
        "f_condominio_id": row.get("f_condominio_id","") or None,
        "f_bloco": row.get("f_bloco","") or None,
        "f_apto": row.get("f_apto","") or None,
        "f_localizacao": row.get("f_localizacao","") or None,
        "f_email": row.get("f_email","") or None,
        "f_telefone": row.get("f_telefone","") or None,
        "f_created_at": now_utc(),
        "f_ativo": True,
    }
    ref = db.collection("t_cliente").add(doc)[1]
    return ref.id

def insert_medidor(db, row: Dict[str, Any]) -> str:
    f_medidor_id = row.get("f_medidor_id") or ""
    if not f_medidor_id:
        raise ValueError("f_medidor_id é obrigatório na aba t_medidor")
    doc = {
        "f_cliente_id": row.get("f_cliente_id") or None,
        "f_condominio_id": row.get("f_condominio_id") or None,
        "f_tem_valvula": coerce_bool(row.get("f_tem_valvula", False)),
        "f_valvula_status": row.get("f_valvula_status") or None,
        "f_modelo_hw": row.get("f_modelo_hw") or None,
        "f_fw_version": row.get("f_fw_version") or None,
        "f_nota_instalacao": row.get("f_nota_instalacao") or None,
        "f_created_at": now_utc(),
        "f_ativo": True,
        "f_last_ts_utc": None,
        "f_last_valor_m3": None,
        "f_monthly_total_m3": {},
    }
    db.collection("t_medidor").document(f_medidor_id).set(doc)
    return f_medidor_id

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Carga inicial Firestore via XLSX")
    p.add_argument("--xlsx", required=True, help="Caminho do arquivo Excel com abas t_*")
    args = p.parse_args()

    db = init_db()
    xlsx_path = Path(args.xlsx).resolve()
    dfs = load_xlsx(xlsx_path)

    print("Carregando: t_localizacao …")
    loc_ids = []
    for _, r in dfs["t_localizacao"].iterrows():
        loc_ids.append(insert_localizacao(db, r.to_dict()))
    print(f"  ok ({len(loc_ids)})")

    print("Carregando: t_condominio …")
    cond_ids = []
    for _, r in dfs["t_condominio"].iterrows():
        cond_ids.append(insert_condominio(db, r.to_dict()))
    print(f"  ok ({len(cond_ids)})")

    print("Carregando: t_cliente …")
    cli_ids = []
    for _, r in dfs["t_cliente"].iterrows():
        cli_ids.append(insert_cliente(db, r.to_dict()))
    print(f"  ok ({len(cli_ids)})")

    print("Carregando: t_medidor …")
    med_ids = []
    for _, r in dfs["t_medidor"].iterrows():
        med_ids.append(insert_medidor(db, r.to_dict()))
    print(f"  ok ({len(med_ids)})")

    print("✅ Carga concluída.")
