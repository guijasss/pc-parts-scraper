from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import psycopg

from src.config import POSTGRES_DSN, TIMEZONE

TABLE = "pricing_history"
KNOWN_STORES = ("kabum", "terabyte", "pichau")

_conn: psycopg.Connection | None = None


def _get_conn() -> psycopg.Connection:
    global _conn
    if _conn is None or _conn.closed:
        if not POSTGRES_DSN:
            raise RuntimeError("POSTGRES_DSN nao configurado.")
        _conn = psycopg.connect(POSTGRES_DSN, autocommit=True)
    return _conn


def _ensure_schema() -> None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
              SELECT 1
              FROM information_schema.tables
              WHERE table_schema = current_schema()
                AND table_name = %s
            )
            """,
            (TABLE,),
        )
        table_exists = bool(cur.fetchone()[0])

        if not table_exists:
            cur.execute(
                f"""
                CREATE TABLE {TABLE} (
                  part TEXT NOT NULL,
                  snapshot_date DATE NOT NULL,
                  price NUMERIC NULL,
                  url TEXT NULL,
                  store TEXT NOT NULL,
                  PRIMARY KEY (snapshot_date, part, store)
                );
                """
            )
            return

        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (TABLE,),
        )
        columns = {row[0] for row in cur.fetchall()}

        normalized_columns = {"part", "snapshot_date", "price", "url", "store"}
        legacy_columns = {
            "piece",
            "snapshot_date",
            "kabum_price",
            "kabum_url",
            "terabyte_price",
            "terabyte_url",
            "pichau_price",
            "pichau_url",
        }

        if normalized_columns.issubset(columns):
            return

        if not legacy_columns.issubset(columns):
            raise RuntimeError(
                f"Schema inesperado na tabela {TABLE}. Colunas encontradas: {sorted(columns)}"
            )

        cur.execute(
            f"""
            CREATE TABLE {TABLE}_new (
              part TEXT NOT NULL,
              snapshot_date DATE NOT NULL,
              price NUMERIC NULL,
              url TEXT NULL,
              store TEXT NOT NULL,
              PRIMARY KEY (snapshot_date, part, store)
            );
            """
        )
        cur.execute(
            f"""
            INSERT INTO {TABLE}_new (part, snapshot_date, price, url, store)
            SELECT piece, snapshot_date, kabum_price, kabum_url, 'kabum'
            FROM {TABLE}
            WHERE kabum_price IS NOT NULL OR NULLIF(kabum_url, '') IS NOT NULL
            UNION ALL
            SELECT piece, snapshot_date, terabyte_price, terabyte_url, 'terabyte'
            FROM {TABLE}
            WHERE terabyte_price IS NOT NULL OR NULLIF(terabyte_url, '') IS NOT NULL
            UNION ALL
            SELECT piece, snapshot_date, pichau_price, pichau_url, 'pichau'
            FROM {TABLE}
            WHERE pichau_price IS NOT NULL OR NULLIF(pichau_url, '') IS NOT NULL
            """
        )
        cur.execute(f"DROP TABLE {TABLE}")
        cur.execute(f"ALTER TABLE {TABLE}_new RENAME TO {TABLE}")


def _upsert_offer(
    *,
    snapshot_date: date,
    part: str,
    store: str,
    price=None,
    url=None,
) -> None:
    if store not in KNOWN_STORES:
        return

    _ensure_schema()
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {TABLE} (
              snapshot_date, part, store, price, url
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (snapshot_date, part, store) DO UPDATE SET
              price = COALESCE(EXCLUDED.price, {TABLE}.price),
              url = COALESCE(EXCLUDED.url, {TABLE}.url)
            """,
            (snapshot_date, part, store, price, url),
        )


def _today_snapshot_date(now: datetime | None = None) -> date:
    tz = ZoneInfo(TIMEZONE)
    now = now.astimezone(tz) if now is not None else datetime.now(tz)
    return now.date()


def save_price(piece: str, store: str, price: float, url: str = "") -> None:
    """
    Grava/atualiza uma oferta no snapshot diario do Postgres.
    """
    snap = _today_snapshot_date()
    part = (piece or "").strip()
    if not part:
        return

    url = (url or "").strip() or None
    _upsert_offer(snapshot_date=snap, part=part, store=store, price=price, url=url)


def save_daily_snapshot(rows: list[dict], now: datetime | None = None) -> str:
    """
    Escreve (UPSERT) o snapshot do dia com uma linha por peca/loja.
    Espera o formato do agent:
      {peca, kabum_valor, kabum_url, terabyte_valor, terabyte_url, pichau_valor, pichau_url}
    """
    snap = _today_snapshot_date(now)
    _ensure_schema()

    for row in rows:
        part = (row.get("peca") or "").strip()
        if not part:
            continue

        for store in KNOWN_STORES:
            price = row.get(f"{store}_valor")
            url = (row.get(f"{store}_url") or "").strip() or None
            if price is None and not url:
                continue
            _upsert_offer(
                snapshot_date=snap,
                part=part,
                store=store,
                price=price,
                url=url,
            )

    return f"postgres:{TABLE}/{snap.isoformat()}"


def load_history(piece: str) -> list[dict]:
    """
    Retorna o historico por peca a partir da tabela diaria normalizada.
    (Compat com a assinatura antiga de storage.py)
    """
    _ensure_schema()
    conn = _get_conn()
    part = (piece or "").strip()
    if not part:
        return []

    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            f"""
            SELECT snapshot_date, store, price, url
            FROM {TABLE}
            WHERE part = %s
            ORDER BY snapshot_date ASC, store ASC
            """,
            (part,),
        )
        rows = cur.fetchall()

    return [
        {
            "timestamp": r["snapshot_date"].isoformat(),
            "store": r["store"],
            "product_name": part,
            "price": r["price"],
            "url": r["url"] or "",
        }
        for r in rows
    ]
