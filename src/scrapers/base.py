from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod

import requests

from src.config import HEADERS, REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT

try:
    import cloudscraper  # type: ignore
except Exception:  # pragma: no cover
    cloudscraper = None


class BaseScraper(ABC):
    """
    Classe base para scrapers de lojas.
    """

    store_name: str = ""

    def __init__(self) -> None:
        # Alguns sites (ex: Cloudflare "under attack mode") retornam 403 no requests puro.
        # cloudscraper consegue resolver o desafio JS e retorna HTML normal.
        if cloudscraper is not None:
            self.session = cloudscraper.create_scraper(
                browser={"custom": HEADERS.get("User-Agent", "")}
            )
        else:
            self.session = requests.Session()

        self.session.headers.update(HEADERS)

    @abstractmethod
    def build_search_url(self, product_name: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def parse_first_result(self, html: str) -> dict | None:
        raise NotImplementedError

    def get_price(self, product_name: str) -> dict | None:
        """
        Orquestra: monta URL -> request -> parse.
        Retorna:
          { "name": str, "price": float, "url": str, "store": str, "search_query": str }
        ou None.
        """
        url = self.build_search_url(product_name)
        try:
            time.sleep(REQUEST_DELAY_SECONDS)
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            result = self.parse_first_result(response.text)
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

    @staticmethod
    def norm_text(text: str) -> str:
        text = (text or "").lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _capacity_tokens(text: str) -> set[str]:
        """
        Extract capacity tokens like '1tb', '500gb' from raw text.
        Helps match queries like '1 TB' against titles like '1TB'.
        """
        raw = (text or "").lower()
        out: set[str] = set()
        for m in re.finditer(r"\b(\d+)\s*(tb|gb)\b", raw):
            out.add(f"{m.group(1)}{m.group(2)}")
        return out

    @classmethod
    def match_score(cls, query: str, title: str) -> tuple[int, bool]:
        """
        Retorna (score, acceptable). A heuristica tenta:
        - garantir que tokens fortes (ex: 5600, b650, rtx4070, 2280, 1tb) estejam presentes
        - aceitar matches quando ~60% dos tokens relevantes aparecem no titulo
        """
        q_raw = query or ""
        t_raw = title or ""
        q = cls.norm_text(q_raw)
        t = cls.norm_text(t_raw)
        if not q or not t:
            return (0, False)

        if q in t:
            return (100, True)

        stop = {
            "de",
            "da",
            "do",
            "das",
            "dos",
            "com",
            "sem",
            "para",
            "e",
            "ou",
            "a",
            "o",
            "em",
            # units/noise
            "tb",
            "gb",
            # noise from things like "M.2" -> "m 2"
            "m",
        }
        q_tokens = [tok for tok in q.split(" ") if tok and tok not in stop]

        if not q_tokens:
            return (0, False)

        cap_q = cls._capacity_tokens(q_raw)
        cap_t = cls._capacity_tokens(t_raw)

        # "Must" tokens: capacity + strong digit-bearing tokens.
        must: list[str] = []
        must.extend(sorted(cap_q))

        for tok in q_tokens:
            if tok == "0":
                continue
            if tok in cap_q:
                continue
            if not any(ch.isdigit() for ch in tok):
                continue

            if tok.isdigit():
                # Require only multi-digit numbers (5600, 2280). Single digits are too noisy.
                if len(tok) >= 2:
                    must.append(tok)
                continue

            # Require alphanumeric model tokens (nv3, b650, rtx4070); skip very short ones like x4.
            if len(tok) >= 3:
                must.append(tok)

        for tok in must:
            if tok in cap_q:
                if tok not in cap_t and tok not in t:
                    return (0, False)
            else:
                if tok not in t:
                    return (0, False)

        scoring_tokens = list(q_tokens)
        for tok in cap_q:
            if tok not in scoring_tokens:
                scoring_tokens.append(tok)

        matched = 0
        for tok in scoring_tokens:
            if tok in t:
                matched += 1
                continue
            if tok in cap_q and tok in cap_t:
                matched += 1

        ratio = matched / max(1, len(scoring_tokens))

        score = matched * 10 + len(must) * 5
        acceptable = (matched >= 3 and ratio >= 0.6) or (len(must) >= 2 and matched >= 2)
        return (score, acceptable)

