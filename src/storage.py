"""
Storage:
  1) Historico: um unico CSV em `src/data/history/history.csv`
  2) Snapshot diario: um CSV por dia em `src/data/daily/YYYY_MM_DD.csv`
"""

from __future__ import annotations

import csv
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import DAILY_DIR, HISTORY_DIR, STORAGE_BACKEND, TIMEZONE

if STORAGE_BACKEND == "postgres":
    from src import postgres_storage as _pg  # lazy import when enabled


def _slug(product_name: str) -> str:
    slug = product_name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_") or "produto"

def _history_filepath() -> str:
    os.makedirs(HISTORY_DIR, exist_ok=True)
    return os.path.join(HISTORY_DIR, "history.csv")


HISTORY_FIELDNAMES = ["timestamp", "store", "product_name", "price", "url"]


def save_price(product_name: str, store: str, price: float, url: str = "") -> None:
    if STORAGE_BACKEND == "postgres":
        # Em Postgres gravamos em lote em `save_daily_snapshot` (1 linha por peca/loja/dia).
        # Mantemos esta funcao como no-op para evitar 1 escrita por loja.
        return
    """Acrescenta uma linha ao historico (arquivo unico)."""
    filepath = _history_filepath()
    file_exists = os.path.isfile(filepath)

    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "store": store,
                "product_name": product_name,
                "price": price,
                "url": url or "",
            }
        )


def load_history(product_name: str) -> list[dict]:
    if STORAGE_BACKEND == "postgres":
        return _pg.load_history(product_name)
    """Carrega todo o historico de uma peca a partir do arquivo unico."""
    filepath = _history_filepath()
    if not os.path.isfile(filepath):
        return []
    with open(filepath, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    # Filtra por peca (mantem compat com chamadas antigas).
    return [r for r in rows if (r.get("product_name") or "") == product_name]


DAILY_FIELDNAMES = [
    "peca",
    "kabum_valor",
    "kabum_url",
    "pichau_valor",
    "pichau_url",
    "terabyte_valor",
    "terabyte_url",
]


def _daily_filepath(now: datetime | None = None) -> str:
    os.makedirs(DAILY_DIR, exist_ok=True)
    tz = ZoneInfo(TIMEZONE)
    now = now.astimezone(tz) if now is not None else datetime.now(tz)
    filename = now.strftime("%Y_%m_%d") + ".csv"
    return os.path.join(DAILY_DIR, filename)


def save_daily_snapshot(rows: list[dict], now: datetime | None = None) -> str:
    if STORAGE_BACKEND == "postgres":
        return _pg.save_daily_snapshot(rows, now=now)
    """
    Salva (sobrescrevendo) o snapshot do dia. Retorna o caminho do arquivo.
    Espera rows no formato gerado pelo agent:
      {peca, kabum_valor, kabum_url, pichau_valor, pichau_url, terabyte_valor, terabyte_url}
    """
    filepath = _daily_filepath(now)
    # Ordena para estabilidade do arquivo
    rows_sorted = sorted(rows, key=lambda r: (r.get("peca") or "").lower())

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DAILY_FIELDNAMES)
        writer.writeheader()
        for row in rows_sorted:
            out = {k: row.get(k, "") for k in DAILY_FIELDNAMES}
            # Normaliza None -> ""
            for k, v in list(out.items()):
                if v is None:
                    out[k] = ""
            writer.writerow(out)

    return filepath
