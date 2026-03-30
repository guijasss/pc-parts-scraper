from __future__ import annotations

import json
import os
from pathlib import Path

# --- Google Sheets ---
_ROOT_DIR = Path(__file__).resolve().parent.parent
_APP_CONFIG_FILE = _ROOT_DIR / "config.json"

if not _APP_CONFIG_FILE.exists():
    raise FileNotFoundError(
        f"Arquivo de configuracao nao encontrado: {_APP_CONFIG_FILE}. "
        "Crie um config.json na raiz com {\"spreadsheet_id\": \"...\", \"sheet_name\": \"...\"}."
    )

with _APP_CONFIG_FILE.open("r", encoding="utf-8") as f:
    _APP_CONFIG = json.load(f)

SPREADSHEET_ID = _APP_CONFIG.get("spreadsheet_id")
SHEET_NAME = _APP_CONFIG.get("sheet_name")
EXCLUDED_TYPES = _APP_CONFIG.get("excluded_types", [])
INCLUDED_TYPES = _APP_CONFIG.get("included_types", [])
STORAGE_BACKEND = _APP_CONFIG.get("storage_backend", "local")
POSTGRES_CONFIG = _APP_CONFIG.get("postgres", {})

if not isinstance(SPREADSHEET_ID, str) or not SPREADSHEET_ID.strip():
    raise ValueError('config.json: campo "spreadsheet_id" invalido.')
if not isinstance(SHEET_NAME, str) or not SHEET_NAME.strip():
    raise ValueError('config.json: campo "sheet_name" invalido.')

if not isinstance(EXCLUDED_TYPES, list) or not all(isinstance(x, str) for x in EXCLUDED_TYPES):
    raise ValueError('config.json: campo "excluded_types" deve ser uma lista de strings.')
if not isinstance(INCLUDED_TYPES, list) or not all(isinstance(x, str) for x in INCLUDED_TYPES):
    raise ValueError('config.json: campo "included_types" deve ser uma lista de strings.')

if STORAGE_BACKEND not in ("local", "postgres"):
    raise ValueError('config.json: campo "storage_backend" deve ser "local" ou "postgres".')

if not isinstance(POSTGRES_CONFIG, dict):
    raise ValueError('config.json: campo "postgres" deve ser um objeto JSON.')

# Colunas da planilha (indice base 0)
# Estrutura real: Peca, Valor, Tipo, URL, Observacoes/Notas
COL_PIECE = 0  # A - Peca
COL_VALUE = 1  # B - Valor (melhor preco do dia)
COL_TYPE = 2  # C - Tipo
COL_URL = 3  # D - URL (da loja mais barata)
COL_NOTES = 4  # E - Observacoes/Notas

# --- Credenciais Google ---
# Baixe o JSON da sua conta de servico.
# Se GOOGLE_CREDENTIALS_FILE nao for absoluto, resolvemos relativo a raiz do repo.
_GOOGLE_CREDENTIALS_RAW = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
_cred_path = Path(_GOOGLE_CREDENTIALS_RAW)
if not _cred_path.is_absolute():
    _cred_path = (_ROOT_DIR / _cred_path).resolve()

# Compat: alguns setups deixam o arquivo dentro de src/.
if not _cred_path.exists():
    alt = (_ROOT_DIR / "src" / Path(_GOOGLE_CREDENTIALS_RAW).name).resolve()
    if alt.exists():
        _cred_path = alt

GOOGLE_CREDENTIALS_FILE = str(_cred_path)

# --- Storage ---
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
HISTORY_DIR = os.path.join(_DATA_DIR, "history")
DAILY_DIR = os.path.join(_DATA_DIR, "daily")

# Timezone (usado para nome do CSV diario e timestamps)
TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")

# --- Postgres (Supabase) ---
# Use um DSN do Postgres do Supabase:
#   postgresql://USER:PASSWORD@HOST:PORT/postgres
# Recomendado: armazenar o DSN em env var e referenciar via config.json: {"postgres": {"dsn_env": "SUPABASE_DB_DSN"}}
POSTGRES_DSN: str | None = None
if STORAGE_BACKEND == "postgres":
    dsn = POSTGRES_CONFIG.get("dsn")
    dsn_env = POSTGRES_CONFIG.get("dsn_env")
    if isinstance(dsn_env, str) and dsn_env.strip():
        POSTGRES_DSN = os.getenv(dsn_env.strip())
    elif isinstance(dsn, str) and dsn.strip():
        POSTGRES_DSN = dsn.strip()

    if not POSTGRES_DSN:
        raise ValueError(
            "storage_backend=postgres exige postgres.dsn ou postgres.dsn_env (env var com o DSN)."
        )

# --- Scraping ---
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "2"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}
