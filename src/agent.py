"""
Agente de monitoramento de precos.

Uso recomendado:
  python -m src.agent            # roda uma vez (ideal para agendar)
  python -m src.agent --dry-run  # testa scrapers sem gravar no Sheets/CSV
"""

from __future__ import annotations

import argparse
import sys

from src.config import STORAGE_BACKEND
from src.scrapers import SCRAPERS
from src.sheets import get_products, update_best_offer
from src.storage import save_daily_snapshot, save_price


def run(*, dry_run: bool = False) -> None:
    print("=" * 60)
    print(("[DRY RUN] " if dry_run else "") + "Iniciando coleta de precos")
    print("=" * 60)

    products = get_products()
    if not products:
        print("Nenhum produto encontrado na planilha. Verifique o Sheets.")
        sys.exit(0)

    print(f"{len(products)} produto(s) encontrado(s).\n")

    daily_rows: list[dict] = []

    for product in products:
        piece_name = product["name"]
        row_index = product["row_index"]

        print(f"-> {piece_name}")

        row_results: dict[str, dict | None] = {}
        row_prices: dict[str, float | None] = {}

        for store_key, scraper in SCRAPERS.items():
            result = scraper.get_price(piece_name)
            row_results[store_key] = result

            if result:
                price = float(result["price"])
                url = result.get("url", "") or ""
                row_prices[store_key] = price
                print(
                    f"   [{scraper.store_name}] R$ {price:,.2f} - {result.get('name', '')[:60]}"
                )

                if not dry_run:
                    # No Postgres, a persistencia e feita em lote no final (1 linha por peca/dia).
                    if STORAGE_BACKEND == "local":
                        save_price(piece_name, store_key, price, url)
            else:
                row_prices[store_key] = None
                print(f"   [{scraper.store_name}] Nao encontrado / erro")

        # Atualiza a planilha apenas com o menor preco e a URL da loja mais barata.
        if not dry_run:
            best_store = None
            best_price: float | None = None
            best_url: str | None = None

            for store_key, result in row_results.items():
                if not result:
                    continue
                p = result.get("price")
                if p is None:
                    continue
                p = float(p)
                if best_price is None or p < best_price:
                    best_price = p
                    best_store = store_key
                    best_url = str(result.get("url") or "")

            update_best_offer(row_index, best_price, best_url)

        # CSV diario: uma linha por produto com preco+URL por loja.
        def _store_val(store_key: str) -> float | None:
            r = row_results.get(store_key) or None
            return None if not r else r.get("price")

        def _store_url(store_key: str) -> str:
            r = row_results.get(store_key) or None
            if not r:
                return "Não identificado"
            u = (r.get("url") or "").strip()
            return u if u else "Não identificado"

        daily_rows.append(
            {
                "peca": piece_name,
                "kabum_valor": _store_val("kabum"),
                "kabum_url": _store_url("kabum"),
                "pichau_valor": _store_val("pichau"),
                "pichau_url": _store_url("pichau"),
                "terabyte_valor": _store_val("terabyte"),
                "terabyte_url": _store_url("terabyte"),
            }
        )

        print()

    if not dry_run:
        save_daily_snapshot(daily_rows)

    print("Coleta finalizada.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agente de monitoramento de precos")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa os scrapers mas nao grava no Sheets nem no CSV/historico",
    )
    args = parser.parse_args(argv)
    run(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
