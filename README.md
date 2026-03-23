# Market Sniper

This script automates the monitoring, filtering, and AI-based evaluation of listings from Subito and Facebook Marketplace.

## Features

* Continually monitors Subito and FB Marketplace for new items based on dynamic search queries.
* Evaluates items using a dual-layer AI pipeline (OpenRouter Text LLM + Vision LLM fallback) to filter out accessories or irrelevant brands.
* Controlled entirely via a Telegram bot interface (change max price, target models, and stop-words on the fly).
* Uses a dynamic contextual memory system (MD5 hashing) to automatically adapt and re-evaluate listings when filter rules change.
* Bypasses basic bot-protection using undetected-chromedriver.
* Sends the approved listing links and AI summaries directly as notifications to a Telegram bot.
* Maintains local memory profiles to prevent duplicate processing.

## Setup & Run

1. Install required dependencies: `pip install -r requirements.txt`
2. Update the `SYSTEM & TOKENS` block inside `market_sniper.py` with your Telegram credentials, and configure your OpenRouter API key inside the bot.
3. Execute the script: `python market_sniper.py`
4. On the very first run, manually log into Facebook in the opened browser window and press ENTER in the console to save your session.