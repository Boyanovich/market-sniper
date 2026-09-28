# Market Sniper

This script automates the monitoring, filtering, and AI-based evaluation of listings from Subito and Facebook Marketplace.

## Features

* Continually monitors Subito and FB Marketplace for new items based on dynamic search queries.
* Evaluates items using a universal dual-layer AI pipeline (OpenRouter Text LLM + Vision LLM with Base64 image encoding) to verify item condition and filter out accessories, spare parts, or "wanted" ads.
* Built-in API resilience: automatically switches to the `openrouter/free` fallback router if the primary model hits rate limits (HTTP 400/404/429).
* Controlled entirely via a Telegram bot (ChatOps) interface: change max price, search queries, required criteria, exclusions, and AI models on the fly.
* Uses a dynamic contextual memory system (MD5 hashing) to automatically adapt and re-evaluate listings when search queries or criteria change.
* Bypasses basic bot-protection using `undetected-chromedriver`.
* Sends the approved listing links and AI summaries directly as notifications to a Telegram bot.

## Telegram Commands

* `/run`, `/stop`, `/status` — Control the scanner and view current configuration.
* `/price [num]` — Set maximum allowed price in EUR.
* `/sites [subito/facebook/both]` — Select target marketplaces.
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