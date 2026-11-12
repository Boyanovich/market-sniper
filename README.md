# Market Sniper

This script automates the monitoring, filtering, and AI-based evaluation of listings from Subito.it and Facebook Marketplace.

## Features

* **Location-Aware Continuous Monitoring:** Continually monitors Subito.it (with regional routing & multi-page pagination) and Facebook Marketplace (with city-level geolocation) for new listings based on dynamic search queries and customizable batch limits (`/limit`).
* **Two-Stage Multimodal AI Pipeline:** Evaluates items using a dual-layer AI pipeline (OpenRouter Text LLM + Vision LLM with Base64 image encoding) to verify item condition, extract accurate item pricing, and filter out accessories, spare parts, or "wanted" ads.
* **Built-in API Resilience & Quota Protection:** Uses persistent HTTP sessions (`requests.Session`), automatically switches to the `openrouter/free` fallback router on HTTP 400/404/429 errors, and preserves uninspected listings in cache without marking them as seen if daily API rate limits are exhausted.
* **Instant Reactive ChatOps Interface:** Controlled entirely via a Telegram bot; changes to city, max price, search queries, or AI criteria automatically switch the contextual memory profile, interrupt sleep/active loops, and trigger an immediate re-scan.
* **Contextual MD5 Memory & Bounded Item Cache:** Combines `O(1)` set-based MD5 profile tracking with a bounded local item cache (`items_cache.json`, up to 1,000 listings with cached prices) so filter or price adjustments re-evaluate previously scraped listings in 0 seconds without re-opening the browser.
* **Anti-Bot Bypass:** Bypasses bot protections using `undetected-chromedriver` with `eager` DOM loading strategy.

## Telegram Commands

* `/run`, `/stop`, `/status` — Control the scanner and view current configuration & cache metrics.
* `/city [name/all]` — Set target city (e.g., `messina`, `milano`, `roma`, or `all` for nationwide Italy; switches memory profile & triggers instant re-scan).
* `/price [num]` — Set maximum allowed price in EUR (switches memory profile & triggers instant re-scan).
* `/limit [num]` — Set maximum number of new listings to scan per cycle (e.g., `24`, `50`, `100`; updates batch size without resetting memory or interrupting the current scan).
* `/sites [subito/facebook/both]` — Select target marketplaces (triggers instant re-scan).
* `/add_search [text]`, `/del_search [text]` — Manage marketplace search queries.
* `/add_criteria [text]`, `/del_criteria [text]` — Manage required item conditions for AI validation.
* `/add_exclude [text]`, `/del_exclude [text]` — Manage exclusions/defects to reject.
* `/clear_all`, `/clear_search`, `/clear_criteria`, `/clear_exclude` — Reset filters.
* `/api_key [key]`, `/text_model [name]`, `/vision_model [name]` — Configure OpenRouter API and LLM models.

## Setup & Run

1. Install required dependencies: `pip install -r requirements.txt`
2. Update the `SYSTEM & TOKENS` block inside `market_sniper.py` with your Telegram credentials, and configure your OpenRouter API key inside `config.json` or via the `/api_key` bot command.
3. Execute the script: `python market_sniper.py`
4. On the very first run, manually log into Facebook in the opened browser window and press ENTER in the console to save your session.

## Active Development Roadmap (v2.0)

Current engineering milestones in active development:
- [ ] **Cross-Platform Web & App UI (FastAPI + React / Tauri):** Replacing CLI and Telegram-only setup with an accessible Web Dashboard and standalone desktop/mobile app where non-technical users can visually manage filters, inspect matched item cards, and store their own API keys locally (BYOK privacy model).
- [ ] **Self-Healing Universal Scraper Engine:** Expanding beyond Subito and Facebook Marketplace to Amazon Warehouse, Vinted, eBay, and Wallapop using an AI-generated CSS/XPath selector cache that invokes an LLM only once per site layout change, preserving native scraping speed.
- [ ] **Automated Multimodal Model Router:** Integrating dynamic benchmark polling and multi-provider rotation to automatically select the highest-performing free Text and Vision LLMs without manual model string configuration.
- [ ] **AI Fair Market Value & Deal Scoring:** Leveraging cached historical listings in SQLite to compute average category prices, flag underpriced arbitrage deals (e.g., "% below market average"), and generate automated first-contact negotiation messages for sellers.