# AGENTS.md

This file defines the static context and roadmap for the Vietnam Gold Dashboard project. It captures domain rules, tech stack choices, and the required workflow/coding standards.

## 🎯 Domain Context
- **Vietnam Gold (SJC) ≠ World Gold:**
  - **MUST NOT** use generic APIs (Yahoo Finance, Kitco) for the "Gold" price.
  - **MUST** scrape local Vietnamese sources (e.g., **SJC**, **Mihong**, or others) because SJC gold carries a premium over the global spot price.
- **USD/VND Reality:**
  - Bank rates (Vietcombank) differ from the "Black Market" (Free Market) rates.
  - Unless specified, target **black market** for official rates.
- **VN30 Index:**
  - Top 30 stocks in Vietnam; available on sites like **Vietstock** or **CafeF**.
- **Formatting Rules:**
  - Vietnam uses `.` for thousands (e.g., `80.000.000`) and `,` for decimals.
  - **Action:** create a robust utility to sanitize strings before casting to `float`/`int`.

## 🛠️ Tech Stack
- **Core:** Python
- **Fetching:** `requests` (with strict header management)
- **Parsing:** `beautifulsoup4` (HTML), `lxml` (faster parser)
- **UI:** `rich` (Live Dashboard, Tables, Panels)
- **Validation:** `pydantic` (strict schema validation before UI rendering)
- **Caching:** `diskcache` or `json` (prevent bans by caching results for 5–10 minutes)

## 📋 The 4-Phase Workflow

### Phase 1: Research (Context & Defense)
1. **Network Inspection**
2. **Anti-Bot Strategy**
3. **Output:** create `research.md` containing specific URLs, detected internal APIs, or CSS selectors.

### Phase 2: Specification (Blueprint)
1. **Architecture**
2. **Repository Pattern:** the UI must not know *how* data is fetched, only *that* it is available.

### Phase 3: Implementation (The Build)
1. **Normalization First**
2. **Resilient Fetching**
   - Implement a **Cache Decorator**. If a scrape fails, return the last known good value from cache/file rather than crashing.
   - Use `try/except` blocks specifically for `requests.exceptions`.
3. **Iterative Build**

### Phase 4: Verification
1. **Sanity Check Script**
2. **Visual Check:** ensure rich table columns align correctly and colors indicate up/down trends (if historical data is available).

## � Project Structure
```
gold-dashboard-arena/
├── AGENTS.md                          # Project laws & standards
├── README_DEPLOYMENT.md               # Firebase deployment guide
├── pyproject.toml                     # Python packaging (src layout)
├── requirements.txt                   # Pinned dependencies
├── firebase.json / .firebaserc        # Firebase config
├── .github/workflows/                 # GitHub Actions (auto-deploy)
├── public/                            # Firebase static assets (HTML/CSS/JS)
│   ├── index.html, styles.css, app.js
│   └── data.json (auto-generated)
├── src/gold_dashboard/                # Main Python package
│   ├── __init__.py
│   ├── config.py                      # URLs, headers, selectors
│   ├── models.py                      # Dataclasses (Decimal-based)
│   ├── utils.py                       # VN number sanitization, caching
│   ├── dashboard.py                   # Rich terminal UI
│   ├── main.py                        # Terminal dashboard entry point
│   ├── generate_data.py               # Static JSON export for Firebase
│   └── repositories/                  # Repository pattern (data fetching)
│       ├── base.py, gold_repo.py, currency_repo.py
│       ├── crypto_repo.py, stock_repo.py
│       └── __init__.py
├── tests/                             # Test scripts
├── scripts/                           # Debug & analysis scripts
└── docs/                              # research.md, activeContext.md
```

- **Install:** `pip install -e .` (editable mode, resolves `gold_dashboard` package)
- **Run terminal dashboard:** `python -m gold_dashboard.main`
- **Generate data.json:** `python -m gold_dashboard.generate_data`

## �🚨 Coding Standards & Anti-Patterns
- **NO Generic Requests:** do not use `requests.get(url)` without headers; it will be blocked by Vietnamese firewalls.
- **NO Float Errors:** use `Decimal` from `decimal` for currency calculations (avoid floating point errors like `0.1 + 0.2`).
- **NO "N/A" Crashes:** if a source is down, UI should show "Unavailable" or cached timestamp, not crash.
- **Type Hints:** every function must have Python type hints.
- **Config:** all URLs and CSS selectors must live in `config.py`.

## 🎯 Project Goal
Deploy a Firebase-backed dashboard that scrapes Vietnamese gold price (SJC/local sources) alongside USD/VND, Bitcoin, and VN30 index data.
