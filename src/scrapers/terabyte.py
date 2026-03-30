from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
import requests

from src.scrapers.base import BaseScraper
from src.config import REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT


def _make_soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


class TerabyteScraper(BaseScraper):
    store_name = "Terabyte"

    def build_search_url(self, product_name: str) -> str:
        query = quote_plus(product_name)
        return f"https://www.terabyteshop.com.br/busca?str={query}"

    def get_price(self, product_name: str) -> dict | None:
        url = self.build_search_url(product_name)
        try:
            time.sleep(REQUEST_DELAY_SECONDS)
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            result = self._parse_first_result_for_query(response.text, product_name)
            if result:
                result["store"] = self.store_name
                result["search_query"] = product_name
            return result
        except requests.exceptions.HTTPError as e:
            print(f"[{self.store_name}] HTTP error para '{product_name}': {e}")
        except requests.exceptions.Timeout:
            print(f"[{self.store_name}] Timeout para '{product_name}'")
        except requests.exceptions.RequestException as e:
            print(f"[{self.store_name}] Erro de rede para '{product_name}': {e}")
        except Exception as e:
            print(f"[{self.store_name}] Erro inesperado para '{product_name}': {e}")
        return None

    def parse_first_result(self, html: str) -> dict | None:
        # Nao usado diretamente: aqui falta a query para validar o match.
        return None

    def _parse_first_result_for_query(self, html: str, query: str) -> dict | None:
        soup = _make_soup(html)

        best: dict | None = None
        best_score = -1

        # Lista de cards. (A estrutura mudou; `.product-item` existe hoje.)
        cards = soup.select(".product-item") or soup.select(".pbox, [class*='product-box']")
        for card in cards:
            text = card.get_text(" ", strip=True)
            if re.search(r"\b(esgotado|indispon)\b", text.lower()):
                continue

            link_tag = card.select_one("a[href*='/produto/']") or card.select_one("a[href]")
            url = ""
            if link_tag and link_tag.get("href"):
                href = link_tag["href"]
                url = href if href.startswith("http") else f"https://www.terabyteshop.com.br{href}"

            name = ""
            if link_tag:
                name = (link_tag.get("title") or "").strip()
            if not name:
                name_tag = card.select_one(".prod-name, h2, [class*='prod-name'], [class*='name'], [class*='title']")
                name = name_tag.get_text(strip=True) if name_tag else "N/A"

            score, acceptable = self.match_score(query, name)
            if not acceptable:
                continue

            price = self._min_total_price(text)
            if price is None:
                continue

            if score > best_score or (score == best_score and best and price < best["price"]):
                best_score = score
                best = {"name": name, "price": price, "url": url}

        if best:
            return best

        ld = self._first_jsonld_product(soup)
        if ld:
            score, acceptable = self.match_score(query, str(ld.get("name") or ""))
            if acceptable:
                return ld

        return None

    def _parse_price(self, text: str) -> float | None:
        cleaned = re.sub(r"[R$\s]", "", text).replace(".", "").replace(",", ".")
        match = re.search(r"\d+\.\d{2}", cleaned)
        return float(match.group()) if match else None

    def _min_total_price(self, text: str) -> float | None:
        """
        Encontra o menor valor total (a vista) no texto.
        Ignora matches que parecem ser valor de parcela (ex: '10x de R$ 138,99').
        """
        # Normaliza espacos
        t = re.sub(r"\s+", " ", text)
        prices: list[float] = []

        for m in re.finditer(r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}", t):
            start = m.start()
            ctx = t[max(0, start - 20) : start].lower()
            if re.search(r"\d+\s*x\s*de\s*$", ctx) or re.search(r"\d+x\s*de\s*$", ctx):
                continue
            p = self._parse_price(m.group(0))
            if p is not None and p > 0:
                prices.append(p)

        return min(prices) if prices else None

    def _first_jsonld_product(self, soup: BeautifulSoup) -> dict | None:
        for s in soup.select("script[type='application/ld+json']"):
            raw = s.get_text(strip=True)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            got = self._extract_first_product_from_jsonld(data)
            if got:
                return got
        return None

    def _extract_first_product_from_jsonld(self, data: Any) -> dict | None:
        if isinstance(data, list):
            for item in data:
                got = self._extract_first_product_from_jsonld(item)
                if got:
                    return got
            return None

        if not isinstance(data, dict):
            return None

        typ = str(data.get("@type") or "")
        if typ.lower() == "itemlist" and isinstance(data.get("itemListElement"), list):
            first = data["itemListElement"][0]
            if isinstance(first, dict) and isinstance(first.get("item"), dict):
                return self._product_from_jsonld_obj(first["item"])

        if isinstance(data.get("@graph"), list):
            for node in data["@graph"]:
                got = self._extract_first_product_from_jsonld(node)
                if got:
                    return got

        return None

    def _product_from_jsonld_obj(self, obj: dict[str, Any]) -> dict | None:
        name = obj.get("name") or "N/A"
        url = obj.get("url") or ""
        offers = obj.get("offers") or {}
        price = None
        if isinstance(offers, dict):
            price = offers.get("price")
        if price is None:
            return None
        try:
            return {"name": str(name), "price": float(price), "url": str(url)}
        except Exception:
            return None
