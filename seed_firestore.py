from __future__ import annotations

import os
import sys
import math
import argparse
from pathlib import Path
from typing import Dict, Any, Iterable, Tuple, Optional
from datetime import datetime, timedelta, timezone

import pandas as pd
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import Increment


# =============== util & init ===============

BASE_DIR = Path(__file__).resolve().parent

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def parse_bool(x) -> bool:
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    return s in ("true", "1", "sim", "yes", "y", "t")

def init_db() -> firestore.Client:
    load_dotenv()
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not cred_path:
        raise RuntimeError("Defina GOOGLE_APPLICATION_CREDENTIALS no .env")
    cred_path = str((BASE_DIR / cred_path).resolve() if not os.path.isabs(cred_path) else Path(cred_path))
    if not Path(cred_path).exists():
        raise FileNotFoundError(f"Credencial não encontrada: {cred_path}")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(cred_path))
    return firestore.client()

def month_bucket(ts: datetime) -> str:
    return f"{ts.year:04d}_{ts.month:02d}"

# =============== leitura do excel ===============

REQUIRED_SHEETS = ["t_localizacao", "t_condominio", "t_cliente", "t_medidor"]

def load_xlsx(xlsx_path: Path) -> Dict[str, pd.DataFrame]:
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Arquivo Excel não encontrado: {xlsx_path}")
    xls = pd.ExcelFile(xlsx_path)
    dfs: Dict[str, pd.DataFrame] = {}
    for sheet in REQUIRED_SHEETS:
        if sheet not in xls.sheet_names:
            raise ValueError(f"Planilha '{sheet}' ausente no Excel.")
        df = pd.read_excel(xlsx_path, sheet_name=sheet, dtype=str)
        df = df.fillna("")
        if "_id" not in df.columns:
            raise ValueError(f"Planilha '{sheet}' precisa da coluna '_id'.")
        dfs[sheet] = df
    return dfs

# =============== writers por coleção ===============

def upsert_localizacao(db: firestore.Client, row: Dict[str, Any]) -> str:
    _id = row["_id"].strip()
    if not _id:
        raise ValueError("t_localizacao: _id obrigatório")
    doc = {
        "f_logradouro": row.get("f_logradouro", ""),
        "f_numero": row.get("f_numero", ""),
        "f_bairro": row.get("f_bairro", ""),
        "f_cidade": row.get("f_cidade", ""),
        "f_uf": row.get("f_uf", ""),
        "f_cep": row.get("f_cep", ""),
        "f_complemento": row.get("f_complemento", "") or None,
        "f_geo": None,
        "f_created_at": now_utc(),
        "f_ativo": True,
    }
    # coordenadas opcionais
    lat = row.get("f_geo_lat", "")
    lon = row.get("f_geo_lon", "")
    try:
        if str(lat).strip() != "" and str(lon).strip() != "":
            doc["f_geo"] = {"lat": float(lat), "lon": float(lon)}
    except Exception:
        pass

    db.collection("t_localizacao").document(_id).set(doc, merge=True)
    return _id

def upsert_condominio(db: firestore.Client, row: Dict[str, Any]) -> str:
    _id = row["_id"].strip()
    if not _id:
        raise ValueError("t_condominio: _id obrigatório")
    doc = {
        "f_nome_condominio": row.get("f_nome_condominio", ""),
        "f_tipo": row.get("f_tipo", "condominio"),
        "f_localizacao": row.get("f_localizacao", "") or None,
        "f_nome_resp": row.get("f_nome_resp", "") or None,
        "f_fone_resp": row.get("f_fone_resp", "") or None,
        "f_email_resp": row.get("f_email_resp", "") or None,
        "f_created_at": now_utc(),
        "f_ativo": True,
    }
    db.collection("t_condominio").document(_id).set(doc, merge=True)
    return _id

def upsert_cliente(db: firestore.Client, row: Dict[str, Any]) -> str:
    _id = row["_id"].strip()
    if not _id:
        raise ValueError("t_cliente: _id obrigatório")
    cpf = str(row.get("f_cpf", "")).replace(".", "").replace("-", "").strip()
    doc = {
        "f_nome_cliente": row.get("f_nome_cliente", ""),
        "f_cpf": cpf,
        "f_condominio_id": row.get("f_condominio_id", "") or None,
        "f_bloco": row.get("f_bloco", "") or None,
        "f_apto": row.get("f_apto", "") or None,
        "f_localizacao": row.get("f_localizacao", "") or None,
        "f_email": row.get("f_email", "") or None,
        "f_telefone": row.get("f_telefone", "") or None,
        "f_created_at": now_utc(),
        "f_ativo": True,
    }
    db.collection("t_cliente").document(_id).set(doc, merge=True)
    return _id

def upsert_medidor(db: firestore.Client, row: Dict[str, Any]) -> str:
    _id = row["_id"].strip()
    if not _id:
        raise ValueError("t_medidor: _id obrigatório (ex.: MTR-000001)")
    doc = {
        "f_cliente_id": row.get("f_cliente_id", "") or None,
        "f_condominio_id": row.get("f_condominio_id", "") or None,
        "f_tem_valvula": parse_bool(row.get("f_tem_valvula", False)),
        "f_valvula_status": row.get("f_valvula_status", "") or None,
        "f_modelo_hw": row.get("f_modelo_hw", "") or None,
        "f_fw_version": row.get("f_fw_version", "") or None,
        "f_nota_instalacao": row.get("f_nota_instalacao", "") or None,
        "f_created_at": now_utc(),
        "f_ativo": True,
        "f_last_ts_utc": None,
        "f_last_valor_m3": None,
        "f_monthly_total_m3": {},
    }
    db.collection("t_medidor").document(_id).set(doc, merge=True)
    return _id

# =============== bootstrap a partir do excel ===============

def cmd_bootstrap(db: firestore.Client, xlsx: Path) -> None:
    dfs = load_xlsx(xlsx)

    print("→ Carregando t_localizacao …")
    for _, r in dfs["t_localizacao"].iterrows():
        upsert_localizacao(db, r.to_dict())

    print("→ Carregando t_condominio …")
    for _, r in dfs["t_condominio"].iterrows():
        upsert_condominio(db, r.to_dict())

    print("→ Carregando t_cliente …")
    for _, r in dfs["t_cliente"].iterrows():
        upsert_cliente(db, r.to_dict())

    print("→ Carregando t_medidor …")
    for _, r in dfs["t_medidor"].iterrows():
        upsert_medidor(db, r.to_dict())

    print("✅ bootstrap concluído (IDs respeitados).")

# =============== simulação de leituras ===============

def write_reading(db: firestore.Client, f_medidor_id: str, f_cliente_id: Optional[str], ts: datetime, m3_delta: float, pulsos: int):
    month = month_bucket(ts)
    med_ref = db.collection("t_medidor").document(f_medidor_id)

    # garante o "bucket" visível no console
    month_doc = med_ref.collection("t_leituras").document(month)
    month_doc.set({"f_bucket": month, "f_created_at": ts}, merge=True)

    # grava item
    items_ref = month_doc.collection("items")
    doc = {
        "f_medidor_id": f_medidor_id,
        "f_cliente_id": f_cliente_id,
        "f_ts_utc": ts,
        "f_ano_mes_ref": month.replace("_","-"),
        "f_valor_m3": float(m3_delta),
        "f_pulsos": int(pulsos),
        "f_status_sensor": 1,
        "f_flag_vazamento": False,
        "f_ingested_at": firestore.SERVER_TIMESTAMP,
        "f_archived_at": None,
    }
    items_ref.add(doc)

    # agrega no medidor
    med_ref.update({
        "f_last_ts_utc": ts,
        "f_last_valor_m3": float(m3_delta),
        f"f_monthly_total_m3.{month}": Increment(float(m3_delta)),
    })

def iter_medidores(db: firestore.Client, only_ids: Optional[Iterable[str]], limit: Optional[int]) -> Iterable[Tuple[str, Optional[str]]]:
    if only_ids:
        for mid in only_ids:
            snap = db.collection("t_medidor").document(mid).get()
            if snap.exists:
                d = snap.to_dict() or {}
                yield (snap.id, d.get("f_cliente_id"))
        return
    meds = list(db.collection("t_medidor").stream())
    if limit is not None:
        meds = meds[:limit]
    for m in meds:
        d = m.to_dict() or {}
        yield (m.id, d.get("f_cliente_id"))

def minutes_for(freq: str) -> int:
    m = {"5m": 5, "15m": 15, "1h": 60, "6h": 360, "1d": 1440}
    if freq not in m:
        raise ValueError("freq inválida; use 5m | 15m | 1h | 6h | 1d")
    return m[freq]

def cmd_simulate(db: firestore.Client, start: str, end: str, freq: str, limit_medidores: int | None, medidor_ids: list[str] | None):
    step_min = minutes_for(freq)
    t0 = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    t1 = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    delta = timedelta(minutes=step_min)

    med_list = list(iter_medidores(db, medidor_ids, limit_medidores))
    if not med_list:
        print("Nenhum medidor encontrado para simular.")
        return

    print(f"→ Gerando leituras {start} .. {end} freq={freq} para {len(med_list)} medidor(es)…")
    total = 0
    for mid, cli in med_list:
        ts = t0
        # consumo base por passo (delta), com pequena variação
        base = 0.010  # ~10 litros/pass
        while ts <= t1:
            noise = (os.urandom(1)[0] / 255.0 - 0.5) * 0.006  # ~±3 litros
            m3 = max(0.0, base + noise)
            pulsos = int(round(m3 * 1000))  # 1 pulso = 1 litro (exemplo)
            write_reading(db, mid, cli, ts, m3, pulsos)
            total += 1
            ts += delta
        print(f"   {mid}: ok")

    print(f"✅ leituras geradas: {total}")

# =============== main cli ===============

def main():
    ap = argparse.ArgumentParser(description="Seed/Simulação Firestore (IDs fixos via Excel)")
    ap.add_argument("--mode", required=True, choices=["bootstrap", "simulate"], help="bootstrap (carga via Excel) ou simulate (gerar leituras)")
    ap.add_argument("--xlsx", help="Caminho do Excel (obrigatório no bootstrap)")
    # simulate
    ap.add_argument("--start", default="2024-03-11", help="YYYY-MM-DD (default 2024-03-11)")
    ap.add_argument("--end",   default="2025-09-18", help="YYYY-MM-DD (default 2025-09-18)")
    ap.add_argument("--freq",  default="1h", choices=["5m","15m","1h","6h","1d"], help="Frequência entre leituras (default 1h)")
    ap.add_argument("--limit-medidores", type=int, default=5, help="Limita nº de medidores (apenas simulate)")
    ap.add_argument("--medidor", action="append", help="IDs específicos (pode repetir a flag) ex.: --medidor MTR-000001 --medidor MTR-000002")
    args = ap.parse_args()

    db = init_db()

    if args.mode == "bootstrap":
        if not args.xlsx:
            print("→ use --xlsx para apontar o template (ex.: Template_Carga_Firestore_v2.xlsx)")
            sys.exit(2)
        xlsx = Path(args.xlsx).resolve()
        cmd_bootstrap(db, xlsx)
    elif args.mode == "simulate":
        cmd_simulate(db, args.start, args.end, args.freq, args.limit_medidores, args.medidor)

if __name__ == "__main__":
    main()
