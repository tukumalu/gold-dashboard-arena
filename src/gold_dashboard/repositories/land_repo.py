"""Land price repository for Vietnam Gold Dashboard."""

import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .base import Repository
from ..config import (
    ALONHADAT_Q11_URL,
    HEADERS,
    HOMEDY_HONG_BANG_URL,
    LAND_FALLBACK_PRICE_PER_M2,
    LAND_LAST_GOOD_SCRAPE_FILE,
    LAND_LOCATION,
    LAND_MAX_VALID_VND_PER_M2,
    LAND_MIN_VALID_VND_PER_M2,
    LAND_UNIT,
    REQUEST_TIMEOUT,
)
from ..models import LandPrice
from ..utils import cached


def _parse_vn_number(raw: str) -> str:
    """Convert a Vietnamese-formatted number string to a Python-parseable decimal string.

    Vietnamese convention: dot = thousands separator, comma = decimal.
    Heuristic for ambiguous dot-only values:
      - dot followed by exactly 3 digits → thousands separator (e.g. "1.200" → "1200")
      - dot followed by 1-2 digits → decimal point (e.g. "95.5" → "95.5")
    """
    has_comma = "," in raw
    has_dot = "." in raw

    if has_comma and has_dot:
        # Full Vietnamese format: "1.200,5" → "1200.5"
        return raw.replace(".", "").replace(",", ".")
    if has_comma:
        # Comma-only: "180,9" → "180.9"
        return raw.replace(",", ".")
    if has_dot:
        # Dot-only: decide via digit count after the dot
        parts = raw.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            # Thousands separator: "1.200" → "1200"
            return raw.replace(".", "")
        # Decimal point: "95.5" → "95.5"  (keep as-is)
        return raw
    # No separator at all: "200" → "200"
    return raw


class LandRepository(Repository[LandPrice]):
    """Repository for land price per m2 around Hong Bang street, District 11."""

    @cached
    def fetch(self) -> LandPrice:
        """Fetch land price with a 4-step fallback chain.

        1. alonhadat.com.vn  (best source, may be geo-blocked outside VN)
        2. homedy.com         (international-friendly, pre-calculated tr/m2)
        3. Persisted last-good-scrape file  (survives CI restarts)
        4. Hardcoded 255M VND/m2           (absolute last resort)
        """
        # --- Attempt 1: alonhadat ---
        try:
            result = self._fetch_from_alonhadat()
            self._persist_last_good_scrape(result)
            return result
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"[land] alonhadat failed: {e}")

        # --- Attempt 2: homedy ---
        try:
            result = self._fetch_from_homedy()
            self._persist_last_good_scrape(result)
            return result
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"[land] homedy failed: {e}")

        # --- Attempt 3: persisted last-good-scrape ---
        try:
            result = self._load_last_good_scrape()
            if result is not None:
                print(f"[land] Using persisted last-good scrape from {result.source}")
                return result
        except Exception as e:
            print(f"[land] Failed to load persisted scrape: {e}")

        # --- Attempt 4: hardcoded fallback ---
        print("[land] All sources exhausted, using hardcoded fallback")
        return LandPrice(
            price_per_m2=LAND_FALLBACK_PRICE_PER_M2,
            source="Fallback (Manual estimate)",
            location=LAND_LOCATION,
            unit=LAND_UNIT,
            timestamp=datetime.now(),
        )

    def _fetch_from_alonhadat(self) -> LandPrice:
        """Extract listing-derived VND/m2 values from Quận 11 page and return a robust median."""
        response = requests.get(
            ALONHADAT_Q11_URL,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        unit_prices = self._extract_hong_bang_unit_prices(response.text)
        valid_prices = [
            p for p in unit_prices
            if LAND_MIN_VALID_VND_PER_M2 <= p <= LAND_MAX_VALID_VND_PER_M2
        ]

        if not valid_prices:
            raise ValueError("No valid Hong Bang listing prices parsed from alonhadat")

        return LandPrice(
            price_per_m2=Decimal(str(round(median(valid_prices)))),
            source="alonhadat.com.vn",
            location=LAND_LOCATION,
            unit=LAND_UNIT,
            timestamp=datetime.now(),
        )

    def _extract_hong_bang_unit_prices(self, html: str) -> List[Decimal]:
        """Parse snippets around Hong Bang mentions and compute VND/m2 from (price, area)."""
        text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        prices: List[Decimal] = []

        for match in re.finditer(r"h[oồ]ng\s*b[aà]ng", text, flags=re.IGNORECASE):
            start = max(0, match.start() - 25)
            end = min(len(text), match.end() + 180)
            snippet = text[start:end]

            area = self._extract_area_m2(snippet)
            price_billion = self._extract_price_billion(snippet)
            if area is None or area <= 0 or price_billion is None:
                continue

            price_vnd = price_billion * Decimal("1000000000")
            prices.append((price_vnd / area).quantize(Decimal("0.01")))

        return prices

    @staticmethod
    def _extract_area_m2(snippet: str) -> Optional[Decimal]:
        """Parse dimensions like 4x12 or 12 x 20m and return area in m2."""
        dim_match = re.search(r"(\d+(?:[.,]\d+)?)\s*[xX]\s*(\d+(?:[.,]\d+)?)", snippet)
        if dim_match:
            width = Decimal(dim_match.group(1).replace(",", "."))
            length = Decimal(dim_match.group(2).replace(",", "."))
            return width * length

        area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m\s*²", snippet, flags=re.IGNORECASE)
        if area_match:
            return Decimal(area_match.group(1).replace(",", "."))

        return None

    @staticmethod
    def _extract_price_billion(snippet: str) -> Optional[Decimal]:
        """Parse prices like 12 tỷ 5, 9 tỷ 98, or 45 tỷ into billion-VND units."""
        price_match = re.search(
            r"(\d+(?:[.,]\d+)?)\s*t(?:ỷ|y)(?:\s*(\d{1,3}))?",
            snippet,
            flags=re.IGNORECASE,
        )
        if not price_match:
            return None

        major = Decimal(price_match.group(1).replace(",", "."))
        minor_part = price_match.group(2)
        if not minor_part:
            return major

        minor = Decimal(minor_part)
        scale = Decimal("10") ** len(minor_part)
        return major + (minor / scale)

    # ------------------------------------------------------------------
    # Homedy.com scraper (international-friendly fallback)
    # ------------------------------------------------------------------

    def _fetch_from_homedy(self) -> LandPrice:
        """Scrape homedy.com Hong Bang listings for pre-calculated 'X tr/m2' values.

        Homedy conveniently displays price-per-m2 directly in listing cards,
        e.g. '180,9 tr/m2'. We extract those, convert from triệu (million)
        to raw VND, filter valid range, and return the median.
        """
        response = requests.get(
            HOMEDY_HONG_BANG_URL,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        unit_prices = self._extract_homedy_unit_prices(response.text)
        valid_prices = [
            p for p in unit_prices
            if LAND_MIN_VALID_VND_PER_M2 <= p <= LAND_MAX_VALID_VND_PER_M2
        ]

        if not valid_prices:
            raise ValueError(
                f"No valid Hong Bang prices parsed from homedy "
                f"({len(unit_prices)} raw values extracted)"
            )

        return LandPrice(
            price_per_m2=Decimal(str(round(median(valid_prices)))),
            source="homedy.com",
            location=LAND_LOCATION,
            unit=LAND_UNIT,
            timestamp=datetime.now(),
        )

    @staticmethod
    def _extract_homedy_unit_prices(html: str) -> List[Decimal]:
        """Parse 'X tr/m2' or 'X triệu/m2' values from homedy listing HTML.

        Homedy shows values like '180,9 tr/m2' or '239,1 triệu/m²' inside
        listing card elements. We use regex on the full page text.
        """
        text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        prices: List[Decimal] = []

        # Match patterns like "180,9 tr/m2", "239,1 triệu/m²", "95.5 tr/m²"
        pattern = re.compile(
            r"(\d+(?:[.,]\d+)?)\s*(?:tr|triệu)\s*/\s*m\s*[²2]",
            flags=re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            try:
                million_vnd = Decimal(_parse_vn_number(match.group(1)))
                vnd_per_m2 = million_vnd * Decimal("1000000")
                prices.append(vnd_per_m2)
            except (InvalidOperation, ValueError):
                continue

        return prices

    # ------------------------------------------------------------------
    # Persistence: save/load last good scrape to survive CI restarts
    # ------------------------------------------------------------------

    @staticmethod
    def _persist_last_good_scrape(land_price: LandPrice) -> None:
        """Save a successful scrape result to a JSON file for later fallback."""
        try:
            path = Path(LAND_LAST_GOOD_SCRAPE_FILE)
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "price_per_m2": str(land_price.price_per_m2),
                "source": land_price.source,
                "location": land_price.location,
                "unit": land_price.unit,
                "timestamp": land_price.timestamp.isoformat(),
            }
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            # Persistence is best-effort; never crash the pipeline
            print(f"[land] Warning: could not persist last good scrape: {e}")

    # Hardcoded seed: used when the persisted file doesn't exist yet (e.g. fresh
    # CI clone before any successful scrape).  Value from homedy.com 2026-02-28.
    _LAND_SEED = {
        "price_per_m2": "183800000",
        "source": "homedy.com (seed)",
        "location": LAND_LOCATION,
        "unit": LAND_UNIT,
        "timestamp": "2026-02-28T10:20:34",
    }

    @staticmethod
    def _load_last_good_scrape() -> Optional[LandPrice]:
        """Load persisted scrape from disk, falling back to the hardcoded seed."""
        path = Path(LAND_LAST_GOOD_SCRAPE_FILE)

        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            label = "cached"
        else:
            data = LandRepository._LAND_SEED
            label = "seed"

        price = Decimal(data["price_per_m2"])

        if not (LAND_MIN_VALID_VND_PER_M2 <= price <= LAND_MAX_VALID_VND_PER_M2):
            print(f"[land] Persisted price {price} outside valid range, ignoring")
            return None

        return LandPrice(
            price_per_m2=price,
            source=f"{data['source']} ({label})",
            location=data.get("location", LAND_LOCATION),
            unit=data.get("unit", LAND_UNIT),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )
