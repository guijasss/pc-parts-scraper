from __future__ import annotations

import json
import re
import time
from urllib.parse import quote_plus

import requests

from src.scrapers.base import BaseScraper
from src.config import REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT


class PichauScraper(BaseScraper):
    store_name = "Pichau"

    @staticmethod
    def _looks_like_cpu(query: str) -> bool:
        q = BaseScraper.norm_text(query)
        return ("ryzen" in q) or ("intel" in q) or ("core" in q)

    def build_search_url(self, product_name: str) -> str:
        query = quote_plus(product_name)
        return f"https://www.pichau.com.br/search?q={query}"

    def get_price(self, product_name: str) -> dict | None:
        url = self.build_search_url(product_name)
        # React Flight payload chunks: self.__next_f.push([<id>,"..."])
        pattern = re.compile(r'self\.__next_f\.push\(\[\d+,"(.*?)"\]\)', re.S)

        for attempt in range(2):
            try:
                time.sleep(REQUEST_DELAY_SECONDS)
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                html = resp.text

                # A busca da Pichau e client-rendered e o HTML traz o payload do React/Next em
                # "React Flight" (self.__next_f.push). Em vez de depender de uma substring
                # exata, tentamos parsear cada bloco ate achar o que contem `products.items`.
                items: list[dict] | None = None
                best_len = -1

                for m in pattern.finditer(html):
                    try:
                        decoded = json.loads('"' + m.group(1) + '"')
                    except Exception:
                        continue
                    if ":" not in decoded:
                        continue

                    _prefix, rest = decoded.split(":", 1)
                    rest = rest.strip()
                    start = rest.find("[")
                    if start == -1:
                        continue

                    try:
                        data, _end = json.JSONDecoder().raw_decode(rest[start:])
                    except Exception:
                        continue

                    products_block = None
                    for it in data:
                        if isinstance(it, dict) and isinstance(it.get("products"), dict):
                            products_block = it.get("products")
                            break

                    if not isinstance(products_block, dict):
                        continue

                    cand_items = products_block.get("items")
                    if not isinstance(cand_items, list) or not cand_items:
                        continue

                    if len(cand_items) > best_len:
                        best_len = len(cand_items)
                        items = cand_items

                if not items:
                    # As vezes o payload vem incompleto ou o desafio anti-bot atrapalha;
                    # tenta mais uma vez.
                    if attempt == 0:
                        continue
                    return None

                # Escolhe o item que melhor bate com a query (evita sugestoes irrelevantes).
                best_item = None
                best_score = -1
                best_kind = -1
                best_price = None
                prefer_cpu = self._looks_like_cpu(product_name)

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    title = str(item.get("name") or "")
                    score, acceptable = self.match_score(product_name, title)
                    if not acceptable:
                        continue

                    pichau_prices = (
                        item.get("pichau_prices")
                        if isinstance(item.get("pichau_prices"), dict)
                        else {}
                    )
                    price = (
                        pichau_prices.get("avista")
                        or pichau_prices.get("final_price")
                        or pichau_prices.get("base_price")
                    )
                    if price is None:
                        continue

                    kind = 0
                    if prefer_cpu and "processador" in self.norm_text(title):
                        kind = 1

                    better = False
                    if score > best_score:
                        better = True
                    elif score == best_score:
                        if kind > best_kind:
                            better = True
                        elif kind == best_kind:
                            try:
                                if best_price is None or float(price) < float(best_price):
                                    better = True
                            except Exception:
                                pass

                    if better:
                        best_score = score
                        best_kind = kind
                        best_price = price
                        best_item = item

                if not isinstance(best_item, dict):
                    if attempt == 0:
                        continue
                    return None

                name = str(best_item.get("name") or "N/A")
                url_key = str(best_item.get("url_key") or "").lstrip("/")
                product_url = f"https://www.pichau.com.br/{url_key}" if url_key else ""

                pichau_prices = (
                    best_item.get("pichau_prices")
                    if isinstance(best_item.get("pichau_prices"), dict)
                    else {}
                )
                # "avista" (PIX) costuma ser o menor preco total.
                price = (
                    pichau_prices.get("avista")
                    or pichau_prices.get("final_price")
                    or pichau_prices.get("base_price")
                )
                if price is None:
                    if attempt == 0:
                        continue
                    return None

                return {
                    "name": name,
                    "price": float(price),
                    "url": product_url,
                    "store": self.store_name,
                    "search_query": product_name,
                }
            except requests.exceptions.RequestException as e:
                if attempt == 0:
                    continue
                print(f"[{self.store_name}] Erro de rede para '{product_name}': {e}")
                return None
            except Exception as e:
                print(f"[{self.store_name}] Erro inesperado para '{product_name}': {e}")
                return None

        return None

    def parse_first_result(self, html: str) -> dict | None:
        # Nao usado (Pichau e muito client-rendered; usamos o payload React Flight).
        return None
