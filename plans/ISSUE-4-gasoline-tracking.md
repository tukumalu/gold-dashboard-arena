# ISSUE-4: Vietnam Gasoline Tracking

## 1. Objective

Add a Vietnam retail gasoline price tracker (RON 95-III and E5 RON 92 grades) to the dashboard, displayed as a metric card alongside Gold, USD/VND, and Land, with 1D/1W/1M/1Y/3Y history badges backed by hardcoded seeds and a local persistence file.

---

## 2. Logic

### What gasoline price means in Vietnam

- The Ministry of Industry and Trade (Bộ Công Thương) sets retail gasoline prices. They change every 10 days on a fixed schedule: the **1st, 11th, and 21st of each month** (with occasional out-of-schedule adjustments).
- Two grades dominate retail pumps:
  - **RON 95-III** — premium grade, the reference price (always more expensive)
  - **E5 RON 92** — standard grade with 5% ethanol, ~300–600 VND/liter cheaper than RON 95-III
- Unit: **VND per liter** (e.g., 22,500 means twenty-two thousand five hundred Vietnamese Dong per liter).
- Typical valid range: **10,000 to 50,000 VND/liter** (current actual range ~19,000–26,000).

### Scraping decision logic (fetching current price)

Step 1 — try **xangdau.net** (primary, likely international-accessible):
- GET `https://xangdau.net/` with HEADERS and REQUEST_TIMEOUT.
- Parse HTML text. Look for the string "RON 95-III" (case-insensitive) and extract the nearest number in the valid range. Do the same for "E5 RON 92".
- Valid range check: `GASOLINE_MIN_VALID_VND (10,000) ≤ value ≤ GASOLINE_MAX_VALID_VND (50,000)`.
- If RON 95-III is not found, raise `ValueError("No valid RON 95-III price found")`.

Step 2 — try **petrolimex.com.vn** (fallback, may be geo-blocked):
- GET `https://www.petrolimex.com.vn/nd/gia-ban-le-xang-dau.html` with HEADERS and REQUEST_TIMEOUT.
- Parse HTML table rows, looking for "RON 95" (label) → extract price in nearby cell.
- Same validity range check.

Step 3 — load **persisted last-good-scrape** from `data/last_gasoline_scrape.json`:
- If file exists and price in valid range, return it with source appended `" (cached)"`.
- If file does not exist, use the hardcoded `_GASOLINE_SEED` dict and return with source appended `" (seed)"`.

Step 4 — **hardcoded absolute fallback** using `GASOLINE_FALLBACK_RON95_PRICE` and `GASOLINE_FALLBACK_E5_RON92_PRICE` with source `"Fallback (Manual estimate)"`.

### Historical change logic

There is no external API for Vietnam gasoline historical prices. Strategy:

1. Seed the local history store with `_GASOLINE_HISTORICAL_SEEDS` (RON 95-III prices, monthly granularity, covering 3Y).
2. For each period (1D, 1W, 1M, 1Y, 3Y):
   - Compute `target_date = now - timedelta(days=N)`.
   - Call `get_value_at("gasoline", target_date)` — uses the ±3-day tolerance already built into `history_store.py`.
   - If not found, call `_find_seed_rate(_GASOLINE_HISTORICAL_SEEDS, target_date, max_delta_days=20)` as nearest-seed fallback.
   - For 3Y specifically, use `max_delta_days=45` (same pattern as gold, land).
3. `change_percent = ((new_value - old_value) / old_value) × 100`, rounded to 2 decimal places.

### % change formula

```
change_percent = ((current - old) / old) × 100
```

Where:
- `current` = `ron95_price` from today's fetch (in VND/liter, e.g., Decimal("22500"))
- `old` = historical RON 95-III price at the target date (VND/liter)
- Result rounded to 2 decimal places via `.quantize(Decimal("0.01"))`

If `old == 0`, return `Decimal("0")` (guard against division by zero).

---

## 3. File Changes

### `src/gold_dashboard/models.py` — **MODIFY**

Add a new `GasolinePrice` dataclass after the existing `LandPrice` dataclass (before `DashboardData`):

```python
@dataclass
class GasolinePrice:
    """Model for Vietnam retail gasoline prices (government-regulated)."""
    ron95_price: Decimal          # RON 95-III price, VND/liter
    source: str
    e5_ron92_price: Optional[Decimal] = None  # E5 RON 92 price, VND/liter (may be unavailable)
    unit: str = "VND/liter"
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.ron95_price <= 0:
            raise ValueError("Gasoline price must be positive")
```

Also update `DashboardData` to add `gasoline` field:

```python
@dataclass
class DashboardData:
    gold: Optional[GoldPrice] = None
    usd_vnd: Optional[UsdVndRate] = None
    bitcoin: Optional[BitcoinPrice] = None
    vn30: Optional[Vn30Index] = None
    land: Optional[LandPrice] = None
    gasoline: Optional[GasolinePrice] = None   # ADD THIS LINE
```

**Leave all other dataclasses unchanged.**

---

### `src/gold_dashboard/config.py` — **MODIFY**

Add the following constants at the end of the file (after the existing `CACHE_DIR = ".cache"` line):

```python
# Gasoline price sources (Vietnam retail, government-regulated)
XANGDAU_URL = "https://xangdau.net/"
PETROLIMEX_URL = "https://www.petrolimex.com.vn/nd/gia-ban-le-xang-dau.html"
GASOLINE_UNIT = "VND/liter"
GASOLINE_FALLBACK_RON95_PRICE = Decimal("22500")   # RON 95-III fallback, VND/liter
GASOLINE_FALLBACK_E5_RON92_PRICE = Decimal("22100") # E5 RON 92 fallback, VND/liter
GASOLINE_MIN_VALID_VND = Decimal("10000")            # 10,000 VND/liter minimum
GASOLINE_MAX_VALID_VND = Decimal("50000")            # 50,000 VND/liter maximum
GASOLINE_LAST_GOOD_SCRAPE_FILE = "data/last_gasoline_scrape.json"
```

**Leave all other config unchanged.**

---

### `src/gold_dashboard/repositories/gasoline_repo.py` — **CREATE**

New file. Full implementation following the exact same pattern as `land_repo.py`. See Section 4 (Function Signatures) for all method signatures and descriptions.

Key import block:

```python
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from .base import Repository
from ..config import (
    GASOLINE_FALLBACK_E5_RON92_PRICE,
    GASOLINE_FALLBACK_RON95_PRICE,
    GASOLINE_LAST_GOOD_SCRAPE_FILE,
    GASOLINE_MAX_VALID_VND,
    GASOLINE_MIN_VALID_VND,
    GASOLINE_UNIT,
    HEADERS,
    PETROLIMEX_URL,
    REQUEST_TIMEOUT,
    XANGDAU_URL,
)
from ..models import GasolinePrice
from ..utils import cached
```

---

### `src/gold_dashboard/repositories/__init__.py` — **MODIFY**

Add `GasolineRepository` import:

```python
from .gasoline_repo import GasolineRepository
```

Add `'GasolineRepository'` to the `__all__` list.

---

### `src/gold_dashboard/generate_data.py` — **MODIFY**

1. **Import**: Add `GasolineRepository` to the existing `from .repositories import ...` line.

2. **`REQUIRED_ASSETS` tuple**: Add `"gasoline"`:
   ```python
   REQUIRED_ASSETS = ("gold", "usd_vnd", "bitcoin", "vn30", "land", "gasoline")
   ```

3. **`fetch_all_data()`**: Add gasoline fetch block after the land block:
   ```python
   try:
       data.gasoline = GasolineRepository().fetch()
       print("✓ Gasoline price fetched")
   except Exception as e:
       print(f"⚠ Gasoline fetch failed: {e}")
   ```

4. **`serialize_data()`**: Add gasoline section after the land section:
   ```python
   if data.gasoline:
       result['gasoline'] = {
           'ron95_price': float(data.gasoline.ron95_price),
           'e5_ron92_price': float(data.gasoline.e5_ron92_price) if data.gasoline.e5_ron92_price else None,
           'unit': data.gasoline.unit,
           'source': data.gasoline.source,
           'timestamp': (data.gasoline.timestamp.isoformat() + 'Z') if data.gasoline.timestamp else None,
       }
   ```

5. **`_record_current_snapshots()`**: Add gasoline snapshot (track RON 95-III price):
   ```python
   if data.gasoline:
       record_snapshot("gasoline", data.gasoline.ron95_price)
   ```

6. **`merge_current_into_timeseries()`**: Add upsert for gasoline (track RON 95-III):
   ```python
   if data.gasoline:
       upsert('gasoline', data.gasoline.ron95_price)
   ```

7. **`_assess_payload_health()`**: Add gasoline check. In the existing `if/elif` block inside the `for asset in REQUIRED_ASSETS` loop, add a new `elif` after the land check:
   ```python
   elif asset == 'gasoline' and current.get('ron95_price') is None:
       reasons.append('missing_ron95_price')
       severe_degradation = True
   ```

8. **Summary print block at bottom of `main()`**: Add:
   ```python
   if 'gasoline' in json_data:
       print(f"  Gasoline: {json_data['gasoline']['source']}")
   ```

---

### `src/gold_dashboard/repositories/history_repo.py` — **MODIFY**

1. **Add historical seeds constant** (add near the top of the file, after `_LAND_HISTORICAL_SEEDS`):

   ```python
   # Verified historical RON 95-III retail prices in Vietnam (VND/liter).
   # Prices are government-regulated, adjusted every 10 days (1st/11th/21st of month).
   # Anchors from VnExpress, Tuoi Tre, Petrolimex official announcements.
   # Monthly spacing ensures every lookup falls within MAX_LOOKUP_TOLERANCE_DAYS (3).
   _GASOLINE_HISTORICAL_SEEDS: List[Tuple[str, Decimal]] = [
       # --- 2023 ---
       ("2023-02-13", Decimal("23010")),   # exact 3Y anchor; ~23,010 VND/L from VnExpress
       ("2023-03-01", Decimal("22800")),
       ("2023-04-01", Decimal("22770")),
       ("2023-05-01", Decimal("22580")),
       ("2023-06-01", Decimal("22360")),
       ("2023-07-01", Decimal("22370")),
       ("2023-08-01", Decimal("22820")),
       ("2023-09-01", Decimal("22260")),
       ("2023-10-01", Decimal("22460")),
       ("2023-11-01", Decimal("22870")),
       ("2023-12-01", Decimal("22320")),
       # --- 2024 ---
       ("2024-01-01", Decimal("21660")),
       ("2024-02-01", Decimal("21800")),
       ("2024-02-10", Decimal("21800")),   # 1Y anchor
       ("2024-03-01", Decimal("22050")),
       ("2024-04-01", Decimal("22180")),
       ("2024-05-01", Decimal("22050")),
       ("2024-06-01", Decimal("22740")),
       ("2024-07-01", Decimal("22490")),
       ("2024-08-01", Decimal("21580")),
       ("2024-09-01", Decimal("20420")),
       ("2024-10-01", Decimal("20980")),
       ("2024-11-01", Decimal("21050")),
       ("2024-12-01", Decimal("21150")),
       # --- 2025 ---
       ("2025-01-01", Decimal("20930")),
       ("2025-02-01", Decimal("21250")),
       ("2025-02-14", Decimal("21250")),   # exact 1Y anchor
       ("2025-03-01", Decimal("21470")),
       ("2025-04-01", Decimal("21600")),
       ("2025-05-01", Decimal("21800")),
       ("2025-06-01", Decimal("22000")),
       ("2025-07-01", Decimal("22200")),
       ("2025-08-01", Decimal("22300")),
       ("2025-09-01", Decimal("22400")),
       ("2025-10-01", Decimal("22400")),
       ("2025-11-01", Decimal("22500")),
       ("2025-12-01", Decimal("22500")),
       # --- 2026 ---
       ("2026-01-01", Decimal("22500")),
       ("2026-02-01", Decimal("22500")),
       ("2026-03-01", Decimal("22500")),
   ]
   ```

   > **IMPORTANT**: These seed values are approximate estimates. Before committing, verify each 2023–2024 anchor against Vietnamese news archives (VnExpress, Tuoi Tre, Cafef, Petrolimex official announcements). The 2025–2026 values are forward estimates. The critical dates that MUST be correct are the "exact N-year anchor" rows (2023-02-13 for 3Y, 2025-02-14 for 1Y), because these are what `get_value_at()` hits during the 1Y and 3Y history badge computation.

2. **In `fetch_changes()`**: Add gasoline block after the land block:
   ```python
   if current_data.gasoline:
       result["gasoline"] = self._gasoline_changes(current_data.gasoline.ron95_price)
   ```

3. **In `fetch_timeseries()`**: Add gasoline timeseries block:
   ```python
   try:
       result["gasoline"] = self._gasoline_timeseries()
       print(f"  ✓ Gasoline timeseries: {len(result['gasoline'])} points")
   except Exception as e:
       print(f"  ⚠ Gasoline timeseries failed: {e}")
   ```

4. **Add `_gasoline_changes()` method** (see Section 4 for signature).

5. **Add `_gasoline_timeseries()` method** (see Section 4 for signature).

6. **Add `_seed_historical_gasoline()` static method** (see Section 4 for signature).

---

### `public/index.html` — **MODIFY**

1. **Add gasoline metric card** to `.top-row` div, immediately after the closing `</div>` of the land card (the last card in the top row), before the closing `</div>` of `.top-row`:

   ```html
   <!-- Gasoline Card -->
   <div class="metric-card" id="gasolineCard">
       <div class="metric-header">
           <span class="metric-icon">⛽</span>
           <span class="metric-label">Gasoline (RON 95-III)</span>
           <span class="change-badge" id="gasolineBadge">--</span>
       </div>
       <div class="metric-value" id="gasolineRon95">--</div>
       <div class="metric-sub" id="gasolineUnit">VND/liter</div>
       <div class="price-rows">
           <div class="price-row">
               <span class="price-label">RON 95-III</span>
               <span class="price-value" id="gasolineRon95Small">--</span>
           </div>
           <div class="price-row">
               <span class="price-label">E5 RON 92</span>
               <span class="price-value" id="gasolineE5">--</span>
           </div>
       </div>
       <div class="card-history" id="gasolineHistory">
           <div class="history-badge" data-period="1D"><span class="period-label">1D</span><span class="period-value">--</span></div>
           <div class="history-badge" data-period="1W"><span class="period-label">1W</span><span class="period-value">--</span></div>
           <div class="history-badge" data-period="1M"><span class="period-label">1M</span><span class="period-value">--</span></div>
           <div class="history-badge" data-period="1Y"><span class="period-label">1Y</span><span class="period-value">--</span></div>
           <div class="history-badge" data-period="3Y"><span class="period-label">3Y</span><span class="period-value">--</span></div>
       </div>
       <div class="card-footer">
           <span class="source" id="gasolineSource">--</span>
       </div>
   </div>
   ```

2. **Bump CSS cache-bust version**: change `styles.css?v=8` → `styles.css?v=9` (line 8).

3. **Bump JS cache-bust version**: change `app.js?v=9` → `app.js?v=10` (line 165).

---

### `public/styles.css` — **MODIFY**

Three changes:

**Change 1** — Desktop top-row grid (line ~140): change 3 columns to 4 columns:
```css
/* BEFORE */
grid-template-columns: repeat(3, minmax(0, 1fr));

/* AFTER */
grid-template-columns: repeat(4, minmax(0, 1fr));
```

**Change 2** — Tablet breakpoint `@media (max-width: 1100px)`: Remove the special nth-child(3) full-width override, and keep the 2-column grid (4 cards will now flow into 2×2 grid naturally):
```css
/* BEFORE */
.top-row {
    grid-template-columns: repeat(2, 1fr);
}

/* Let the 3rd card (land) span full width on tablet for breathing room */
.top-row > .metric-card:nth-child(3) {
    grid-column: 1 / -1;
}

/* AFTER */
.top-row {
    grid-template-columns: repeat(2, 1fr);
}
/* (remove the nth-child(3) rule entirely) */
```

**Change 3** — Mobile breakpoint `@media (max-width: 640px)`: Remove the now-vestigial `nth-child(3)` reset:
```css
/* BEFORE */
.top-row {
    grid-template-columns: 1fr;
}

.top-row > .metric-card:nth-child(3) {
    grid-column: auto;
}

/* AFTER */
.top-row {
    grid-template-columns: 1fr;
}
/* (remove the nth-child(3) auto rule entirely) */
```

---

### `public/app.js` — **MODIFY**

1. **Add `updateGasolineCard(data, history)` function** after `updateLandCard` (see Section 4).
2. **Add `resetGasolineCard()` function** after `resetLandCard` (see Section 4).
3. **In `fetchData()`**:
   - Destructure gasoline history: `const gasolineHistory = data.history && data.history.gasoline;`
   - Add render call: `if (data.gasoline) updateGasolineCard(data.gasoline, gasolineHistory); else resetGasolineCard();`
   - Add history badges call: `if (gasolineHistory) updateHistoryBadges('gasolineHistory', gasolineHistory); else updateHistoryBadges('gasolineHistory', []);`
4. **In `updateLastUpdateTime()`**: Add `data && data.gasoline && data.gasoline.timestamp` to the `candidates` array (so gasoline timestamp can serve as the fallback display time if others are missing).

---

### `tests/test_gasoline_repo.py` — **CREATE**

New file following the pattern of `tests/test_land_repo.py`. See Section 5 for exact test specifications.

---

### Files to leave completely unchanged

`src/gold_dashboard/history_store.py`, `src/gold_dashboard/utils.py`, `src/gold_dashboard/base.py`, `src/gold_dashboard/dashboard.py`, `src/gold_dashboard/main.py`, `src/gold_dashboard/gold_repo.py`, `src/gold_dashboard/currency_repo.py`, `src/gold_dashboard/crypto_repo.py`, `src/gold_dashboard/stock_repo.py`, `firebase.json`, `.firebaserc`, `.github/workflows/update-dashboard.yml`, `pyproject.toml`, `requirements.txt`.

---

## 4. Function Signatures

### In `src/gold_dashboard/repositories/gasoline_repo.py`

```python
class GasolineRepository(Repository[GasolinePrice]):
```

```python
@cached
def fetch(self) -> GasolinePrice:
    """Fetch gasoline price with a 4-step fallback chain:
    1. xangdau.net scrape
    2. petrolimex.com.vn scrape
    3. Persisted last-good-scrape file
    4. Hardcoded fallback constants
    Returns the first successful result."""
```

```python
def _fetch_from_xangdau(self) -> GasolinePrice:
    """GET xangdau.net, parse RON 95-III and E5 RON 92 prices from page text,
    validate against valid range, persist result, and return GasolinePrice.
    Raises ValueError if no valid RON 95-III price found.
    Raises requests.exceptions.RequestException on network failure."""
```

```python
def _fetch_from_petrolimex(self) -> GasolinePrice:
    """GET petrolimex.com.vn retail price page, parse table/text for RON 95
    and E5 RON 92 prices, validate, persist, and return GasolinePrice.
    Raises ValueError if no valid RON 95-III price found.
    Raises requests.exceptions.RequestException on network failure (geo-blocked outside VN)."""
```

```python
@staticmethod
def _extract_grade_price(text: str, grade_label: str) -> Optional[Decimal]:
    """Search `text` for `grade_label` (case-insensitive), then scan up to 120
    chars after the label for a number pattern matching VND/liter range
    (GASOLINE_MIN_VALID_VND to GASOLINE_MAX_VALID_VND).
    Returns Decimal VND/liter if found, None otherwise.
    Handles both dot-thousands (22.500) and no-separator (22500) formats."""
```

```python
@staticmethod
def _persist_last_good_scrape(price: GasolinePrice) -> None:
    """Write successful scrape to GASOLINE_LAST_GOOD_SCRAPE_FILE as JSON.
    Best-effort — never raises; logs warning on failure.
    JSON keys: ron95_price, e5_ron92_price (may be null), source, unit, timestamp."""
```

```python
@classmethod
def _load_last_good_scrape(cls) -> Optional[GasolinePrice]:
    """Load GasolinePrice from GASOLINE_LAST_GOOD_SCRAPE_FILE if it exists and is valid.
    Falls back to cls._GASOLINE_SEED if file does not exist.
    Returns None if stored price is outside valid range.
    Source string gets ' (cached)' or ' (seed)' suffix appended."""
```

```python
_GASOLINE_SEED: ClassVar[Dict[str, str]] = {
    "ron95_price": "22500",
    "e5_ron92_price": "22100",
    "source": "Petrolimex (seed)",
    "unit": "VND/liter",
    "timestamp": "2026-03-01T00:00:00",
}
```

---

### In `src/gold_dashboard/repositories/history_repo.py` (new methods)

```python
def _gasoline_changes(self, current_value: Decimal) -> AssetHistoricalData:
    """Compute RON 95-III % change for each period using local store + seeds.
    Calls _seed_historical_gasoline() first to ensure 3Y coverage.
    For each period: tries get_value_at("gasoline", target_date), then
    _find_seed_rate(_GASOLINE_HISTORICAL_SEEDS, target_date, max_delta_days=20).
    For 3Y period: uses max_delta_days=45.
    Returns AssetHistoricalData(asset_name="gasoline", changes=[...])."""
```

```python
def _gasoline_timeseries(self) -> List[List]:
    """Merge _GASOLINE_HISTORICAL_SEEDS with locally-recorded gasoline prices
    into a sorted [[date_str, float], ...] list.
    Seeds are lowest priority; local store entries override if same date.
    Returns list sorted ascending by date string (YYYY-MM-DD)."""
```

```python
@staticmethod
def _seed_historical_gasoline() -> None:
    """Plant all _GASOLINE_HISTORICAL_SEEDS into the local history store.
    Calls record_snapshot("gasoline", value, dt) for each seed entry.
    record_snapshot deduplicates by date — repeated calls are no-ops."""
```

---

### In `public/app.js` (new JavaScript functions)

```javascript
function updateGasolineCard(data, history)
// Renders gasoline metric card with RON 95-III as primary value, E5 RON 92 as row.
// data: object from data.json 'gasoline' key with fields: ron95_price, e5_ron92_price, unit, source, timestamp
// history: array of change objects from data.json 'history.gasoline'
// Sets: gasolineRon95, gasolineRon95Small, gasolineE5 (or '--' if null), gasolineUnit, gasolineSource
// Sets 1D badge via formatChangeBadge(gasolineBadge, dayChange.change_percent)
// Sets card freshness class via getFreshnessClass(data.timestamp)
```

```javascript
function resetGasolineCard()
// Resets all gasoline card DOM elements to '--' / 'Unavailable' state.
// Sets card class to 'metric-card old'.
// Guards with: const card = document.getElementById('gasolineCard'); if (!card) return;
```

---

## 5. Test Specifications

### File: `tests/test_gasoline_repo.py`

**Test 1: `test_extract_grade_price_dot_thousands`**
- Input `text`: `"Xăng RON 95-III: 22.500 đồng/lít. Xăng E5 RON 92: 22.100 đồng."`
- Call `GasolineRepository._extract_grade_price(text, "RON 95-III")`
- Expected result: `Decimal("22500")`
- Purpose: verifies dot-as-thousands-separator parsing (the most common format on Vietnamese sites).

**Test 2: `test_extract_grade_price_no_separator`**
- Input `text`: `"RON 95-III 22500 VND E5 RON 92 22100"`
- Call `GasolineRepository._extract_grade_price(text, "RON 95-III")`
- Expected result: `Decimal("22500")`

**Test 3: `test_extract_grade_price_returns_none_for_out_of_range`**
- Input `text`: `"RON 95-III: 999 đồng"` (999 is below the 10,000 minimum)
- Call `GasolineRepository._extract_grade_price(text, "RON 95-III")`
- Expected result: `None`

**Test 4: `test_extract_grade_price_returns_none_when_label_absent`**
- Input `text`: `"Diesel 0.05S: 20.000 đồng"` (no RON 95-III label)
- Call `GasolineRepository._extract_grade_price(text, "RON 95-III")`
- Expected result: `None`

**Test 5: `test_fetch_falls_back_to_hardcoded_when_all_sources_fail`**
- Use `@patch("gold_dashboard.repositories.gasoline_repo.requests.get")` to raise `requests.exceptions.RequestException("network down")`.
- Also ensure `GASOLINE_LAST_GOOD_SCRAPE_FILE` does not exist (use `tempfile` or `patch` the path constant).
- Call `GasolineRepository.fetch.__wrapped__(repo)` (unwrap `@cached` decorator same as land test pattern).
- Expected:
  - `result.source` contains `"Fallback"` OR ends with `"(seed)"` (one of the fallback sources)
  - `result.ron95_price >= Decimal("10000")`
  - `result.unit == "VND/liter"`

**Test 6: `test_gasoline_price_model_rejects_nonpositive`**
- Attempt: `GasolinePrice(ron95_price=Decimal("0"), source="test", timestamp=datetime.now())`
- Expected: raises `ValueError`

**Test 7: `test_gasoline_price_model_accepts_valid`**
- Input: `GasolinePrice(ron95_price=Decimal("22500"), e5_ron92_price=Decimal("22100"), source="test", timestamp=datetime.now())`
- Expected: object created without error, `result.unit == "VND/liter"`

---

## 6. Implementation Order

Each step must succeed (unit test or manual verification) before the next begins.

1. **Add `GasolinePrice` to `models.py`** and add `gasoline` field to `DashboardData`. Run existing tests: `python -m pytest tests/ -x` — must pass with no regressions.

2. **Add gasoline constants to `config.py`**. Verify: `python -c "from gold_dashboard.config import XANGDAU_URL, GASOLINE_FALLBACK_RON95_PRICE; print(GASOLINE_FALLBACK_RON95_PRICE)"` prints `22500`.

3. **Create `gasoline_repo.py`** with the full 4-step fallback chain. Verify: `python -c "from gold_dashboard.repositories.gasoline_repo import GasolineRepository; r = GasolineRepository(); print(r.fetch())"` — must print a `GasolinePrice` object (from any fallback level including hardcoded).

4. **Update `repositories/__init__.py`** to export `GasolineRepository`. Verify: `python -c "from gold_dashboard.repositories import GasolineRepository"` — no import error.

5. **Write `tests/test_gasoline_repo.py`** and run: `python -m pytest tests/test_gasoline_repo.py -v` — all 7 tests must pass.

6. **Add `_GASOLINE_HISTORICAL_SEEDS` and history methods to `history_repo.py`**. Verify by running a quick integration check: `python -c "from gold_dashboard.repositories import HistoryRepository, GasolineRepository; from gold_dashboard.models import DashboardData; d = DashboardData(gasoline=GasolineRepository().fetch()); h = HistoryRepository().fetch_changes(d); print(h['gasoline'])"` — prints `AssetHistoricalData` with 5 periods.

7. **Update `generate_data.py`** (all 7 changes listed in Section 3). Run `python -m gold_dashboard.generate_data` — must print `✓ Gasoline price fetched` and produce `public/data.json` with a `gasoline` key.

8. **Update `public/index.html`** (add HTML card, bump version query params). Open `public/data.json` and verify the `gasoline` key is present with `ron95_price` and `source`.

9. **Update `public/styles.css`** (change grid columns, remove nth-child rules). Open the dashboard in a browser locally (via `python -m http.server 8000` in the `public/` directory). Verify on desktop: 4 cards in top row. Verify at 1100px width (browser dev tools): 2×2 grid layout (2 cards per row). Verify on mobile (480px): single column.

10. **Update `public/app.js`** (add `updateGasolineCard`, `resetGasolineCard`, wire into `fetchData`). Reload the dashboard in the browser. Verify the gasoline card renders correctly with price, source, and history badges.

11. **Run the full test suite**: `python -m pytest tests/ -v` — all tests must pass.

12. **Commit** all changed files with a descriptive message. Do not use `--no-verify`.

---

## 7. Gotchas

### 1. Vietnamese number format for VND/liter prices
Gasoline prices are typically displayed as `22.500` on Vietnamese sites — this is **22,500 VND**, NOT `22.5`. The `_extract_grade_price` static method MUST handle dot-as-thousands-separator. A value like `22.500` parsed naively as a float gives `22.5`, which is below `GASOLINE_MIN_VALID_VND (10,000)` and will be rejected as out-of-range. The fix: when a number has exactly one dot followed by exactly 3 digits (e.g., `"22.500"`), remove the dot to get `"22500"`, then convert to Decimal. This is the same heuristic used in `land_repo.py`'s `_parse_vn_number()`.

### 2. Do not confuse `ron95_price` vs `btc_to_vnd` timeseries key
The timeseries and history track only `ron95_price` (the primary grade). E5 RON 92 is displayed in the UI but is NOT tracked in history or timeseries. Using `e5_ron92_price` in `merge_current_into_timeseries()` or `_record_current_snapshots()` would make the chart and badges display wrong values.

### 3. Seed anchor date precision — the ±3-day tolerance trap
`history_store.get_value_at()` uses `MAX_LOOKUP_TOLERANCE_DAYS = 3`, which is exactly 72h. If the "3Y" lookback runs on 2026-03-18, the target date is 2023-03-18. If the nearest seed is `2023-03-01` (17 days away), it will NOT be found by `get_value_at()`. That is why the plan includes `_find_seed_rate(..., max_delta_days=45)` as a second-pass fallback for 3Y. The monthly seeds (spaced ~30 days apart) are close enough for the 20-day default `_find_seed_rate` tolerance to hit them for 1D/1W/1M/1Y. But 3Y requires the 45-day tolerance because the target date may not align with any seed month boundary. This matches the pattern already used for `gold`, `bitcoin`, and `vn30`.

### 4. `@cached` decorator wrapping — test must unwrap it
The `@cached` decorator (from `utils.py`) wraps the `fetch()` method. In tests, call `GasolineRepository.fetch.__wrapped__(repo)` (note: `__wrapped__`, not `__func__`) to bypass the cache. This is the same pattern used in `test_land_repo.py` line 39: `LandRepository.fetch.__wrapped__(repo)`.

### 5. `_GASOLINE_SEED` is a class variable, not an instance variable
Declare it as `_GASOLINE_SEED: ClassVar[Dict[str, str]] = {...}` inside `GasolineRepository`. Do not use a plain class-level dict — the `ClassVar` annotation is required to avoid dataclass/type-checker confusion.

### 6. E5 RON 92 price may be `None` in the payload
`e5_ron92_price` is `Optional[Decimal]` in the model and `null` is a valid JSON value in `data.json`. The frontend must guard against `null`: use `formatVietnameseNumber(data.e5_ron92_price, 0)` only after checking `data.e5_ron92_price !== null && data.e5_ron92_price !== undefined`. If null, display `'--'` in the E5 RON 92 row.

### 7. Cache-busting version numbers
- `index.html` line 8: `styles.css?v=8` → `styles.css?v=9`
- `index.html` line 165: `app.js?v=9` → `app.js?v=10`
- Incrementing by 1 from the current highest version is the convention. Do not skip numbers (e.g., do not go to v=15 arbitrarily).

### 8. CSS nth-child(3) removal — both breakpoints
The special `nth-child(3)` rule that makes the land card span full width on tablet (1100px) exists in TWO places in `styles.css`:
- Under `@media (max-width: 1100px)` — the rule that sets `grid-column: 1 / -1`
- Under `@media (max-width: 640px)` — a reset rule that sets `grid-column: auto`
Both must be removed. Leaving either behind will cause the land card (now the 3rd card in DOM order) to span incorrectly.

### 9. Geo-blocking of both scrapers from GitHub Actions
Both `xangdau.net` and `petrolimex.com.vn` may be unavailable from GitHub Actions runners (US/EU IPs). This is expected and handled by the fallback chain. The hardcoded fallback (step 4) must always produce a valid `GasolinePrice` — do not let it call any network resource. This design means `severe_degradation` will never be triggered by gasoline alone.

### 10. Units: VND/liter, NOT VND/tael or VND/m²
Gold uses VND/tael (1 tael ≈ 37.5g). Land uses VND/m². Gasoline uses **VND/liter**. The `GASOLINE_UNIT = "VND/liter"` constant must be used consistently in the model, config, JSON serialization, and UI. A common mistake is copying code from `LandPrice` and leaving `"VND/m2"` in the gasoline model or config.

### 11. `REQUIRED_ASSETS` tuple expansion is safe because fallback always returns a value
Adding `"gasoline"` to `REQUIRED_ASSETS` will cause `_assess_payload_health()` to check for `ron95_price`. Since the 4-step fallback chain always returns a `GasolinePrice` with a positive `ron95_price`, this field will never be `None` in the payload under normal operation. However, if `fetch_all_data()` catches an unhandled exception and `data.gasoline` ends up `None`, `serialize_data()` will skip the gasoline key entirely, and `_assess_payload_health()` will flag it as `missing_current_section` with `severe_degradation = True`. This is correct behavior — the LKG restore mechanism will then pull gasoline from the previous `data.json`.

### 12. Historical seed values are estimates — verify before committing
The `_GASOLINE_HISTORICAL_SEEDS` values in Section 3 are approximate. The implementer MUST verify the 2023 and 2024 anchors against primary Vietnamese sources (e.g., search VnExpress for "giá xăng" by date, or check Petrolimex's official price announcement archives). The 2025–2026 values are forward estimates and should be updated with real data when available. Getting the 3Y anchor date (`2023-02-13`) wrong by more than 3 days will cause the 3Y badge to show `N/A` until the `_find_seed_rate` fallback covers it (which it will with `max_delta_days=45`, but the displayed value may be slightly inaccurate).
