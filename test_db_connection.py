from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg

ROOT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = ROOT_DIR / "config.json"
TABLE = "pricing_history"


def _load_dsn() -> str:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Arquivo de configuracao nao encontrado: {CONFIG_FILE}. "
            "Crie um config.json na raiz do projeto."
        )

    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        config = json.load(f)

    storage_backend = config.get("storage_backend", "local")
    if storage_backend != "postgres":
        raise ValueError(
            'config.json: campo "storage_backend" deve estar como "postgres" para testar a conexao.'
        )

    postgres_config = config.get("postgres", {})
    if not isinstance(postgres_config, dict):
        raise ValueError('config.json: campo "postgres" deve ser um objeto JSON.')

    dsn = postgres_config.get("dsn")
    dsn_env = postgres_config.get("dsn_env")

    if isinstance(dsn_env, str) and dsn_env.strip():
        resolved = os.getenv(dsn_env.strip())
        if resolved:
            return resolved
        raise ValueError(
            f'Env var "{dsn_env.strip()}" nao encontrada ou vazia. '
            "Defina a variavel com o DSN do Postgres."
        )

    if isinstance(dsn, str) and dsn.strip():
        return dsn.strip()

    raise ValueError(
        "config.json: informe postgres.dsn ou postgres.dsn_env para testar a conexao."
    )


def main() -> int:
    try:
        dsn = _load_dsn()

        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user, now()")
                database_name, current_user, current_time = cur.fetchone()

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
    except (FileNotFoundError, ValueError, psycopg.Error) as exc:
        print(f"Falha ao testar conexao com o Postgres: {exc}", file=sys.stderr)
        return 1

    print("Conexao com Postgres OK.")
    print(f"database: {database_name}")
    print(f"user: {current_user}")
    print(f"time: {current_time.isoformat()}")
    print(f"table_{TABLE}: {'found' if table_exists else 'not_found'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
