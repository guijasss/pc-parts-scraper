"""
Registry de scrapers disponíveis.

Para adicionar uma nova loja:
  1. Crie um arquivo em `src/scrapers/minhaloja.py` herdando de BaseScraper
  2. Importe e registre abaixo com a chave usada no Sheets/CSV
"""

from __future__ import annotations

from src.scrapers.base import BaseScraper
from src.scrapers.kabum import KabumScraper
from src.scrapers.pichau import PichauScraper
from src.scrapers.terabyte import TerabyteScraper

# Chave = identificador da loja (usado no Sheets/CSV)
# Valor = instância do scraper
SCRAPERS: dict[str, BaseScraper] = {
    "kabum": KabumScraper(),
    "pichau": PichauScraper(),
    "terabyte": TerabyteScraper(),
}
