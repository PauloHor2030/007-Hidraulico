# Crie um arquivo export_readings.py na raiz do projeto com o conteúdo abaixo.
# Ele exporta via collection group items (ou seja, varre todas as subcoleções t_leituras/*/items), com filtros opcionais por período e medidor.
# --csv e/ou --json para escolher formatos
# --outdir para pasta de saída (padrão ./exports)
# --start e --end (opcional) para filtrar por período (UTC)
# --medidor (opcional, pode repetir) para filtrar um ou mais medidores
# Escreve em streaming (sem carregar tudo em memória)
# Cabeçalho CSV consistente e gerado na primeira linha válida

# order_by("f_medidor_id").order_by("f_ts_utc") quando você não filtra por medidor;
# quando filtra um ou vários medidores, ele faz 1 query por medidor, cada uma com order_by("f_ts_utc"), e emite já na ordem correta;
# parâmetro opcional --delimiter (padrão ,; para Excel PT-BR use --delimiter ";").
# Observação: ao usar order_by em collection group é comum o Firestore pedir um índice composto. Se aparecer o aviso no terminal/console com um link “Create index…”, clique e crie (demora só 1–2 min). Depois a consulta roda ordenada.

from __future__ import annotations

import os, json, csv, argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable, Optional, Dict, Any

from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# ---------- Credenciais ----------
def init_db() -> firestore.Client:
    load_dotenv()
    cred_env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not cred_env:
        raise RuntimeError("Defina GOOGLE_APPLICATION_CREDENTIALS no .env")
    cred_path = Path(cred_env)
    if not cred_path.is_absolute():
        cred_path = (Path(__file__).resolve().parent / cred_env).resolve()
    if not cred_path.exists():
        raise FileNotFoundError(f"Credencial não encontrada: {cred_path}")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(cred_path)))
    return firestore.client()

# ---------- Util ----------
def parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    # aceita "YYYY-MM-DD" ou "YYYY-MM-DDTHH:MM:SS"
    if "T" in s:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(s + "T00:00:00").replace(tzinfo=timezone.utc)

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

# ---------- Iteradores ordenados ----------
def iter_items_all_sorted(
    db: firestore.Client,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> Iterable[Dict[str, Any]]:
    """
    Sem filtro de medidor:
    Ordena por f_medidor_id (1ª chave) e f_ts_utc (2ª).
    Pode exigir índice composto no Firestore.
    """
    q = db.collection_group("items")
    if start_dt:
        q = q.where("f_ts_utc", ">=", start_dt)
    if end_dt:
        q = q.where("f_ts_utc", "<=", end_dt)

    # Ordenação principal e secundária
    q = q.order_by("f_medidor_id").order_by("f_ts_utc")

    for snap in q.stream():
        d = snap.to_dict() or {}
        d["_doc_id"] = snap.id
        yield d

def iter_items_by_medidor_sorted(
    db: firestore.Client,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    medidores: list[str],
) -> Iterable[Dict[str, Any]]:
    """
    Com filtro de medidores: emite blocos já ordenados por f_ts_utc dentro de cada medidor.
    Mantém a ordem dos medidores conforme a lista recebida.
    """
    for mid in medidores:
        q = db.collection_group("items").where("f_medidor_id", "==", mid)
        if start_dt:
            q = q.where("f_ts_utc", ">=", start_dt)
        if end_dt:
            q = q.where("f_ts_utc", "<=", end_dt)
        q = q.order_by("f_ts_utc")
        for snap in q.stream():
            d = snap.to_dict() or {}
            d["_doc_id"] = snap.id
            yield d

# ---------- Exporters ----------
BASE_FIELDS = [
    "f_medidor_id","f_cliente_id","f_ts_utc","f_ano_mes_ref","f_valor_m3",
    "f_pulsos","f_status_sensor","f_flag_vazamento","f_ingested_at","f_archived_at","_doc_id"
]

def export_jsonl(rows: Iterable[Dict[str, Any]], out_path: Path) -> int:
    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            n += 1
    return n

def export_csv(rows: Iterable[Dict[str, Any]], out_path: Path, delimiter: str = ",") -> int:
    n = 0
    fieldnames = None
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = None
        for r in rows:
            if fieldnames is None:
                fieldnames = BASE_FIELDS + [k for k in r.keys() if k not in BASE_FIELDS]
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
                writer.writeheader()
            writer.writerow({k: (r.get(k) if not isinstance(r.get(k), datetime) else r.get(k).isoformat()) for k in fieldnames})
            n += 1
    return n

# ---------- CLI ----------
def build_name(ext: str, meds: Optional[list[str]], start_dt: Optional[datetime], end_dt: Optional[datetime]) -> str:
    parts = ["leituras_all_sorted"]
    if start_dt: parts.append(start_dt.date().isoformat())
    if end_dt:   parts.append(end_dt.date().isoformat())
    if meds:
        parts += meds
    return "_".join(parts) + f".{ext}"

def main():
    ap = argparse.ArgumentParser(description="Exporta leituras (ordenadas por medidor e timestamp) em CSV/JSONL")
    ap.add_argument("--outdir", default="./exports", help="Diretório de saída (padrão ./exports)")
    ap.add_argument("--csv", action="store_true", help="Exportar CSV")
    ap.add_argument("--json", action="store_true", help="Exportar JSONL")
    ap.add_argument("--delimiter", default=",", help="Delimitador do CSV (use ';' para Excel PT-BR)")
    ap.add_argument("--start", help="UTC início (YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS)")
    ap.add_argument("--end",   help="UTC fim (YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS)")
    ap.add_argument("--medidor", action="append", help="Filtrar por f_medidor_id (pode repetir)")
    args = ap.parse_args()

    if not args.csv and not args.json:
        print("Nada para fazer: use --csv e/ou --json.")
        return

    start_dt = parse_dt(args.start)
    end_dt   = parse_dt(args.end)
    outdir = Path(args.outdir).resolve()
    ensure_dir(outdir)

    db = init_db()

    # Fonte de dados já ORDENADA:
    if args.medidor:
        rows = iter_items_by_medidor_sorted(db, start_dt, end_dt, args.medidor)
    else:
        rows = iter_items_all_sorted(db, start_dt, end_dt)

    # JSON e CSV simultâneos (stream em dois arquivos mantendo a ordem)
    if args.json and args.csv:
        json_path = outdir / build_name("jsonl", args.medidor, start_dt, end_dt)
        csv_path  = outdir / build_name("csv",   args.medidor, start_dt, end_dt)

        n = 0
        fieldnames = None
        with json_path.open("w", encoding="utf-8") as fj, csv_path.open("w", newline="", encoding="utf-8") as fc:
            writer = None
            for r in rows:
                # JSONL
                fj.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
                # CSV
                if fieldnames is None:
                    fieldnames = BASE_FIELDS + [k for k in r.keys() if k not in BASE_FIELDS]
                    writer = csv.DictWriter(fc, fieldnames=fieldnames, delimiter=args.delimiter)
                    writer.writeheader()
                writer.writerow({k: (r.get(k) if not isinstance(r.get(k), datetime) else r.get(k).isoformat()) for k in fieldnames})
                n += 1
        print(f"✅ JSONL: {n} linhas → {json_path}")
        print(f"✅ CSV  : {n} linhas → {csv_path}")
        return

    # Formato único
    if args.json:
        out = outdir / build_name("jsonl", args.medidor, start_dt, end_dt)
        n = export_jsonl(rows, out)
        print(f"✅ JSONL: {n} linhas → {out}")
    if args.csv:
        out = outdir / build_name("csv", args.medidor, start_dt, end_dt)
        n = export_csv(rows, out, delimiter=args.delimiter)
        print(f"✅ CSV  : {n} linhas → {out}")

if __name__ == "__main__":
    main()


# Como usar
# =========
# Exportar tudo, ordenado por medidor → timestamp, em CSV para abrir direto no Excel PT-BR:
# python .\export_readings.py --csv --delimiter ";" 

# Exportar CSV + JSONL, filtrando período:
# python .\export_readings.py --csv --json --delimiter ";" --start 2024-03-11 --end 2025-09-18

# Exportar apenas de certos medidores (mantém ordem por f_ts_utc dentro de cada um):
# python .\export_readings.py --csv --delimiter ";" --medidor MTR-000001 --medidor MTR-000002

# Se o Firestore pedir índice composto, aceite criar no link sugerido (uma vez) e rode de novo.
