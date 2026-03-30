from __future__ import annotations

import re
import time
from urllib.parse import quote_plus

import requests

from src.scrapers.base import BaseScraper
from src.config import REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT


class KabumScraper(BaseScraper):
    store_name = "Kabum"

    # API publica usada pelo front-end (JSON:API)
    _API_BASE = "https://servicespub.prod.api.aws.grupokabum.com.br"
    _SEARCH_PATH = "/catalog/v2/search"

    def build_search_url(self, product_name: str) -> str:
        query = quote_plus(product_name)
        return f"https://www.kabum.com.br/busca/{query}"

    def get_price(self, product_name: str) -> dict | None:
        """
        Kabum carrega resultados via API; HTML da busca pode vir sem cards de produto.
        """
        url = f"{self._API_BASE}{self._SEARCH_PATH}"
        try:
            time.sleep(REQUEST_DELAY_SECONDS)
            resp = self.session.get(
                url,
                params={"query": product_name, "page_size": 10},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            best = self._pick_best_product(product_name, data.get("data") or [])
            if not best:
                return None

            title = best["title"]
            price = best["price"]
            product_id = best["id"]
            product_url = f"https://www.kabum.com.br/produto/{product_id}"

            return {
                "name": title,
                "price": price,
                "url": product_url,
                "store": self.store_name,
                "search_query": product_name,
            }
        except requests.exceptions.RequestException as e:
            print(f"[{self.store_name}] Erro de rede para '{product_name}': {e}")
            return None
        except Exception as e:
            print(f"[{self.store_name}] Erro inesperado para '{product_name}': {e}")
            return None

    def parse_first_result(self, html: str) -> dict | None:
        # Nao usado (Kabum via API).
        return None

    def _pick_best_product(self, query: str, items: list[dict]) -> dict | None:
        best: dict | None = None
        best_score = -1

        for it in items:
            if not isinstance(it, dict):
                continue
            attrs = it.get("attributes") if isinstance(it.get("attributes"), dict) else None
            if not attrs:
                continue

            # Apenas disponiveis (quando o campo existe).
            if attrs.get("available") is False:
                continue

            title = str(attrs.get("title") or "")
            if not title:
                continue

            score, acceptable = self.match_score(query, title)
            if not acceptable:
                continue

            price_f = self._extract_best_price(attrs)
            if price_f is None:
                continue

            if score > best_score or (score == best_score and best and price_f < best["price"]):
                best_score = score
                best = {"id": str(it.get("id") or ""), "title": title, "price": price_f}

        return best

    @staticmethod
    def _extract_best_price(attrs: dict) -> float | None:
        """
        Extrai o menor preco "real" do item (normalmente `price_with_discount` para PIX/boleto).
        Evita usar `old_price` por ser maior; mas se so existir, ainda pode cair nela.
        """
        candidates: list[float] = []

        for key in ("price_with_discount", "price", "offer_price"):
            v = attrs.get(key)
            try:
                if v is not None:
                    candidates.append(float(v))
            except Exception:
                pass

        offer = attrs.get("offer")
        if isinstance(offer, dict):
            for key in ("price_with_discount", "price", "offer_price"):
                v = offer.get(key)
                try:
                    if v is not None:
                        candidates.append(float(v))
                except Exception:
                    pass

        candidates = [c for c in candidates if c > 0]
        return min(candidates) if candidates else None
