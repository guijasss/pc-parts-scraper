"""
Integracao com Google Sheets via gspread.

Setup (uma vez so):
  1. Ative Google Sheets API no Google Cloud Console
  2. Crie uma Service Account e baixe o JSON
  3. Compartilhe a planilha com o email da Service Account (Editor)
  4. Defina GOOGLE_CREDENTIALS_FILE e SPREADSHEET_ID (env vars)
"""

from __future__ import annotations

import gspread
from google.oauth2.service_account import Credentials

from src.config import (
    COL_PIECE,
    COL_TYPE,
    COL_URL,
    COL_VALUE,
    EXCLUDED_TYPES,
    INCLUDED_TYPES,
    GOOGLE_CREDENTIALS_FILE,
    SHEET_NAME,
    SPREADSHEET_ID,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

def _get_sheet():
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)


def get_products() -> list[dict]:
    """
    Le a planilha e retorna uma lista de dicts:
      [{ "row_index": int, "name": str }, ...]

    row_index e o indice real na planilha (base 1), util para update direto.
    """
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()

    products: list[dict] = []
    excluded = {t.strip().casefold() for t in EXCLUDED_TYPES if t.strip()}
    included = {t.strip().casefold() for t in INCLUDED_TYPES if t.strip()}

    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # cabecalho
        if not row:
            continue
        piece = row[COL_PIECE].strip() if len(row) > COL_PIECE else ""
        if not piece:
            continue

        tipo = row[COL_TYPE].strip() if len(row) > COL_TYPE else ""
        tipo_key = tipo.casefold()
        if included and tipo_key not in included:
            continue
        if excluded and tipo_key in excluded:
            continue

        products.append({"row_index": i + 1, "name": piece})
    return products


def _format_brl(price: float | None) -> str:
    if price is None:
        return "N/A"
    # Formata 1,234.56 -> 1.234,56
    return f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def update_best_offer(row_index: int, best_price: float | None, best_url: str | None) -> None:
    """Atualiza na planilha apenas o menor preco (coluna Valor) e a URL correspondente."""
    sheet = _get_sheet()

    price_str = _format_brl(best_price)
    url_str = (best_url or "").strip() or "Não identificado"

    sheet.update_cell(row_index, COL_VALUE + 1, price_str)
    sheet.update_cell(row_index, COL_URL + 1, url_str)
