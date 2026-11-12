import os
import time
import re
import json
import base64
import threading
import hashlib
import urllib.parse
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import telebot

# =====================================================================
# SYSTEM & TOKENS (Hardcoded Constants)
# =====================================================================
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"

CONFIG_FILE = os.path.abspath("config.json")
PROFILE_FOLDER = os.path.abspath("browser_profile")
MEMORY_DIR = os.path.abspath("memory_profiles")
CACHE_FILE = os.path.abspath("items_cache.json")
MAX_CACHE_SIZE = 1000

if not os.path.exists(MEMORY_DIR):
    os.makedirs(MEMORY_DIR)

# Persistent HTTP session for faster API requests and image downloading
HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"})

# Event trigger to wake up or restart scan immediately when filters/price/city change
FILTER_CHANGED_EVENT = threading.Event()

# Mapping of Italian cities to their Subito.it region slugs
SUBITO_CITY_REGIONS = {
    "agrigento": "sicilia", "caltanissetta": "sicilia", "catania": "sicilia", "enna": "sicilia",
    "messina": "sicilia", "palermo": "sicilia", "ragusa": "sicilia", "siracusa": "sicilia", "trapani": "sicilia",
    "milano": "lombardia", "bergamo": "lombardia", "brescia": "lombardia", "como": "lombardia",
    "cremona": "lombardia", "lecco": "lombardia", "lodi": "lombardia", "mantova": "lombardia",
    "monza": "lombardia", "pavia": "lombardia", "sondrio": "lombardia", "varese": "lombardia",
    "roma": "lazio", "frosinone": "lazio", "latina": "lazio", "rieti": "lazio", "viterbo": "lazio",
    "torino": "piemonte", "alessandria": "piemonte", "asti": "piemonte", "biella": "piemonte",
    "cuneo": "piemonte", "novara": "piemonte", "verbania": "piemonte", "vercelli": "piemonte",
    "bologna": "emilia-romagna", "ferrara": "emilia-romagna", "forli-cesena": "emilia-romagna",
    "modena": "emilia-romagna", "parma": "emilia-romagna", "piacenza": "emilia-romagna",
    "ravenna": "emilia-romagna", "reggio-emilia": "emilia-romagna", "rimini": "emilia-romagna",
    "firenze": "toscana", "arezzo": "toscana", "grosseto": "toscana", "livorno": "toscana",
    "lucca": "toscana", "massa-carrara": "toscana", "pisa": "toscana", "pistoia": "toscana",
    "prato": "toscana", "siena": "toscana",
    "napoli": "campania", "avellino": "campania", "benevento": "campania", "caserta": "campania", "salerno": "campania",
    "venezia": "veneto", "belluno": "veneto", "padova": "veneto", "rovigo": "veneto",
    "treviso": "veneto", "verona": "veneto", "vicenza": "veneto",
    "bari": "puglia", "brindisi": "puglia", "foggia": "puglia", "lecce": "puglia", "taranto": "puglia",
    "genova": "liguria", "imperia": "liguria", "la-spezia": "liguria", "savona": "liguria",
    "reggio-calabria": "calabria", "catanzaro": "calabria", "cosenza": "calabria", "crotone": "calabria", "vibo-valentia": "calabria",
    "cagliari": "sardegna", "nuoro": "sardegna", "oristano": "sardegna", "sassari": "sardegna",
    "perugia": "umbria", "terni": "umbria",
    "ancona": "marche", "ascoli-piceno": "marche", "fermo": "marche", "macerata": "marche", "pesaro-urbino": "marche",
    "laquila": "abruzzo", "chieti": "abruzzo", "pescara": "abruzzo", "teramo": "abruzzo",
    "trieste": "friuli-venezia-giulia", "gorizia": "friuli-venezia-giulia", "pordenone": "friuli-venezia-giulia", "udine": "friuli-venezia-giulia",
    "trento": "trentino-alto-adige", "bolzano": "trentino-alto-adige",
    "potenza": "basilicata", "matera": "basilicata",
    "campobasso": "molise", "isernia": "molise",
    "aosta": "valle-daosta"
}

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# =====================================================================
# CONFIGURATION MANAGER
# =====================================================================
DEFAULT_CONFIG = {
    "is_active": False,
    "city": "messina",
    "max_items": 24,
    "max_price": 200.0,
    "active_sites": ["subito", "facebook"],
    "openrouter_api_key": "YOUR_OPENROUTER_API_KEY_HERE",
    "text_ai_model": "stepfun/step-3.5-flash:free",
    "vision_ai_model": "nvidia/nemotron-nano-12b-v2-vl:free",
    "search_queries": ["bici corsa"],
    "positive_criteria": ["road bike", "good condition", "not older than 2015"],
    "negative_criteria": ["rusty", "missing pedals", "broken", "kids bike"]
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded_cfg = json.load(f)
            needs_save = False
            for key, value in DEFAULT_CONFIG.items():
                if key not in loaded_cfg:
                    loaded_cfg[key] = value
                    needs_save = True
            
            if needs_save:
                with open(CONFIG_FILE, "w", encoding="utf-8") as fw:
                    json.dump(loaded_cfg, fw, indent=4)
                    
            return loaded_cfg
    except json.JSONDecodeError:
        return DEFAULT_CONFIG.copy()

def save_config(trigger_rescan=False):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CFG, f, indent=4)
    if trigger_rescan and CFG.get("is_active", False):
        FILTER_CHANGED_EVENT.set()

CFG = load_config()

# =====================================================================
# DYNAMIC CONTEXTUAL MEMORY (O(1) SET) & BOUNDED ITEM CACHE
# =====================================================================
def get_memory_file():
    """Generates a unique memory filename based on city, max_price, search queries, and AI criteria."""
    city_str = CFG.get("city", "messina").lower().strip()
    price_str = str(float(CFG.get("max_price", 200.0)))
    state_str = (
        f"city:{city_str}|"
        f"price:{price_str}|"
        f"sq:{sorted(CFG['search_queries'])}|"
        f"pc:{sorted(CFG['positive_criteria'])}|"
        f"nc:{sorted(CFG['negative_criteria'])}"
    )
    state_hash = hashlib.md5(state_str.encode()).hexdigest()[:12]
    return os.path.join(MEMORY_DIR, f"seen_{state_hash}.txt")

def load_processed_links():
    mem_file = get_memory_file()
    if not os.path.exists(mem_file):
        return set()
    with open(mem_file, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}

def save_processed_link(url):
    mem_file = get_memory_file()
    with open(mem_file, "a", encoding="utf-8") as f:
        f.write(url + "\n")

def load_items_cache():
    """Loads cached item text, image URLs, and detected price to avoid re-opening browser pages."""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_item_to_cache(cache_dict, url, raw_text, images, price=None):
    existing_price = cache_dict.get(url, {}).get("price") if url in cache_dict else None
    cache_dict[url] = {
        "text": raw_text[:3500],
        "images": images[:5],
        "price": price if price is not None else existing_price
    }
    if len(cache_dict) > MAX_CACHE_SIZE:
        oldest_key = next(iter(cache_dict))
        del cache_dict[oldest_key]
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_dict, f)
    except Exception:
        pass

# =====================================================================
# TELEGRAM BOT INTERFACE (CHATOPS)
# =====================================================================
def is_authorized(message):
    return str(message.chat.id) == str(TELEGRAM_CHAT_ID)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_authorized(message): return
    text = (
        "🤖 <b>AI Sniper Control Panel</b>\n\n"
        "<b>[ ENGINE CONTROLS ]</b>\n"
        "🟢 <code>/run</code> - Start scanning\n"
        "🔴 <code>/stop</code> - Pause scanning\n"
        "📊 <code>/status</code> - Show full configuration\n\n"
        "<b>[ FILTERS & LOCATION ]</b>\n"
        "📍 <code>/city [name/all]</code> - Set target city (e.g. messina, milano, all)\n"
        "🔢 <code>/limit [num]</code> - Max new listings per cycle (e.g. 24, 50, 100)\n"
        "💰 <code>/price [num]</code> - Max allowed price\n"
        "🌐 <code>/sites [subito/facebook/both]</code> - Set targets\n"
        "🔍 <code>/add_search [text]</code> - Add site search query\n"
        "❌ <code>/del_search [text]</code> - Remove search query\n\n"
        "<b>[ AI SELECTION CRITERIA ]</b>\n"
        "✅ <code>/add_criteria [text]</code> - Add required condition\n"
        "➖ <code>/del_criteria [text]</code> - Remove condition\n"
        "🛑 <code>/add_exclude [text]</code> - Add exclusion/defect\n"
        "➖ <code>/del_exclude [text]</code> - Remove exclusion\n"
        "🧹 <code>/clear_all</code> - Reset all searches & criteria\n"
        "🧹 <code>/clear_search</code> | <code>/clear_criteria</code> | <code>/clear_exclude</code>\n\n"
        "<b>[ API & MODELS ]</b>\n"
        "🔑 <code>/api_key [key]</code> - Set OpenRouter API key\n"
        "🧠 <code>/text_model [name]</code> - Set Text AI model\n"
        "👁 <code>/vision_model [name]</code> - Set Vision AI model\n"
    )
    bot.reply_to(message, text, parse_mode="HTML")

@bot.message_handler(commands=['run', 'stop'])
def toggle_bot(message):
    if not is_authorized(message): return
    is_start = message.text.startswith('/run')
    CFG['is_active'] = is_start
    save_config(trigger_rescan=is_start)
    state_msg = "🟢 <b>Sniper is RUNNING.</b>" if is_start else "🔴 <b>Sniper is PAUSED.</b>"
    bot.reply_to(message, state_msg, parse_mode="HTML")

@bot.message_handler(commands=['status'])
def send_status(message):
    if not is_authorized(message): return
    state = "🟢 RUNNING" if CFG.get('is_active') else "🔴 PAUSED"
    current_mem_hash = get_memory_file().split('_')[-1].replace('.txt', '')
    seen_count = len(load_processed_links())
    cached_count = len(load_items_cache())
    
    sq = ', '.join(CFG['search_queries']) if CFG['search_queries'] else "None"
    pc = ', '.join(CFG['positive_criteria']) if CFG['positive_criteria'] else "None"
    nc = ', '.join(CFG['negative_criteria']) if CFG['negative_criteria'] else "None"
    
    text = (
        f"📊 <b>STATUS:</b> {state}\n"
        f"📍 <b>City:</b> {CFG.get('city', 'messina').capitalize()}\n"
        f"🔢 <b>Scan Limit:</b> {CFG.get('max_items', 24)} items/cycle\n"
        f"💰 <b>Max Price:</b> {CFG['max_price']} EUR\n"
        f"🌐 <b>Active Sites:</b> {', '.join(CFG['active_sites'])}\n"
        f"📁 <b>Memory Profile:</b> <code>{current_mem_hash}</code> ({seen_count} seen | {cached_count}/{MAX_CACHE_SIZE} cached)\n\n"
        f"🔑 <b>API Key:</b> {CFG['openrouter_api_key'][:8]}...***\n"
        f"🧠 <b>Text AI:</b> {CFG['text_ai_model']}\n"
        f"👁 <b>Vision AI:</b> {CFG['vision_ai_model']}\n\n"
        f"🔍 <b>Site Search Queries:</b>\n{sq}\n\n"
        f"✅ <b>Required Criteria:</b>\n{pc}\n\n"
        f"🛑 <b>Exclusions (What to avoid):</b>\n{nc}"
    )
    bot.reply_to(message, text, parse_mode="HTML")

@bot.message_handler(commands=['city'])
def set_city(message):
    if not is_authorized(message): return
    try:
        city_val = message.text.split(' ', 1)[1].lower().strip()
        CFG['city'] = city_val
        save_config(trigger_rescan=True)
        bot.reply_to(
            message,
            f"📍 Target city updated to: <b>{city_val.capitalize()}</b>\n🔄 <i>Memory profile switched & re-scanning now...</i>",
            parse_mode="HTML"
        )
    except Exception:
        bot.reply_to(message, "❌ Invalid format. Use: /city messina (or /city milano, /city all)")

@bot.message_handler(commands=['limit'])
def set_limit(message):
    if not is_authorized(message): return
    try:
        new_limit = int(message.text.split(' ', 1)[1].strip())
        if new_limit < 1 or new_limit > 500:
            raise ValueError
        CFG['max_items'] = new_limit
        save_config(trigger_rescan=False)
        bot.reply_to(
            message,
            f"🔢 Scan limit updated to: <b>{new_limit} new listings per cycle</b>.",
            parse_mode="HTML"
        )
    except Exception:
        bot.reply_to(message, "❌ Invalid format. Use a number between 1 and 500 (e.g. /limit 50 or /limit 100)")

@bot.message_handler(commands=['price'])
def set_price(message):
    if not is_authorized(message): return
    try:
        new_price = float(message.text.split(' ', 1)[1].replace(',', '.'))
        CFG['max_price'] = new_price
        save_config(trigger_rescan=True)
        bot.reply_to(
            message,
            f"✅ Max price updated to: <b>{new_price} EUR</b>\n🔄 <i>Memory profile switched & re-scanning now...</i>",
            parse_mode="HTML"
        )
    except Exception:
        bot.reply_to(message, "❌ Invalid format. Use: /price 150")

@bot.message_handler(commands=['sites'])
def set_sites(message):
    if not is_authorized(message): return
    try:
        choice = message.text.split(' ', 1)[1].lower().strip()
        if choice == 'subito': CFG['active_sites'] = ['subito']
        elif choice == 'facebook': CFG['active_sites'] = ['facebook']
        elif choice == 'both': CFG['active_sites'] = ['subito', 'facebook']
        else: raise ValueError
        save_config(trigger_rescan=True)
        bot.reply_to(message, f"✅ Active sites updated: {', '.join(CFG['active_sites'])}\n⚡ <i>Triggering immediate re-scan...</i>", parse_mode="HTML")
    except Exception:
        bot.reply_to(message, "❌ Invalid format. Use: /sites subito (or facebook, both)")

@bot.message_handler(commands=['api_key'])
def set_api(message):
    if not is_authorized(message): return
    try:
        key = message.text.split(' ', 1)[1].strip()
        CFG['openrouter_api_key'] = key
        save_config(trigger_rescan=False)
        bot.reply_to(message, "✅ OpenRouter API Key updated.")
    except Exception:
        bot.reply_to(message, "❌ Provide key. Example: /api_key sk-or-v1...")

@bot.message_handler(commands=['text_model'])
def set_text_model(message):
    if not is_authorized(message): return
    try:
        model = message.text.split(' ', 1)[1].strip()
        CFG['text_ai_model'] = model
        save_config(trigger_rescan=False)
        bot.reply_to(message, f"✅ Text Model set to: {model}")
    except Exception:
        bot.reply_to(message, "❌ Provide model name.")

@bot.message_handler(commands=['vision_model'])
def set_vision_model(message):
    if not is_authorized(message): return
    try:
        model = message.text.split(' ', 1)[1].strip()
        CFG['vision_ai_model'] = model
        save_config(trigger_rescan=False)
        bot.reply_to(message, f"✅ Vision Model set to: {model}")
    except Exception:
        bot.reply_to(message, "❌ Provide model name.")

def modify_list(message, list_name, is_add=True):
    if not is_authorized(message): return
    try:
        phrase = message.text.split(' ', 1)[1].lower().strip()
        if is_add:
            if phrase not in CFG[list_name]:
                CFG[list_name].append(phrase)
                save_config(trigger_rescan=True)
                bot.reply_to(message, f"✅ Added: {phrase}\n🔄 <i>Memory profile switched & re-scanning now...</i>", parse_mode="HTML")
            else:
                bot.reply_to(message, f"⚠️ Already exists: {phrase}")
        else:
            if phrase in CFG[list_name]:
                CFG[list_name].remove(phrase)
                save_config(trigger_rescan=True)
                bot.reply_to(message, f"🗑 Removed: {phrase}\n🔄 <i>Memory profile switched & re-scanning now...</i>", parse_mode="HTML")
            else:
                bot.reply_to(message, f"⚠️ Not found: {phrase}")
    except Exception:
        bot.reply_to(message, "❌ Error. Please provide text after the command.")

@bot.message_handler(commands=['add_search'])
def add_sq(m): modify_list(m, 'search_queries', True)

@bot.message_handler(commands=['del_search'])
def del_sq(m): modify_list(m, 'search_queries', False)

@bot.message_handler(commands=['add_criteria'])
def add_pc(m): modify_list(m, 'positive_criteria', True)

@bot.message_handler(commands=['del_criteria'])
def del_pc(m): modify_list(m, 'positive_criteria', False)

@bot.message_handler(commands=['add_exclude'])
def add_nc(m): modify_list(m, 'negative_criteria', True)

@bot.message_handler(commands=['del_exclude'])
def del_nc(m): modify_list(m, 'negative_criteria', False)

@bot.message_handler(commands=['clear_all', 'clear_search', 'clear_criteria', 'clear_exclude'])
def clear_filters(message):
    if not is_authorized(message): return
    cmd = message.text.split()[0].lower()
    
    if cmd == '/clear_all':
        CFG['search_queries'] = []
        CFG['positive_criteria'] = []
        CFG['negative_criteria'] = []
        msg = "🧹 <b>All searches, criteria, and exclusions have been completely reset!</b>"
    elif cmd == '/clear_search':
        CFG['search_queries'] = []
        msg = "🧹 <b>Search queries cleared!</b>"
    elif cmd == '/clear_criteria':
        CFG['positive_criteria'] = []
        msg = "🧹 <b>Required criteria cleared!</b>"
    elif cmd == '/clear_exclude':
        CFG['negative_criteria'] = []
        msg = "🧹 <b>Exclusions cleared!</b>"
        
    save_config(trigger_rescan=True)
    bot.reply_to(message, f"{msg}\n🔄 <i>Memory profile switched & re-scanning now...</i>", parse_mode="HTML")

def start_telegram_bot():
    print("[SYSTEM] Telegram ChatOps Interface running...")
    try:
        bot.send_message(TELEGRAM_CHAT_ID, "⚙️ <b>System Online.</b> Send /run to start scanning.", parse_mode="HTML")
    except Exception:
        pass
    bot.infinity_polling()

# =====================================================================
# CORE PIPELINE FUNCTIONS
# =====================================================================
def generate_target_urls():
    urls = []
    city_slug = CFG.get("city", "messina").lower().strip()

    if "subito" in CFG["active_sites"]:
        for query in CFG["search_queries"]:
            q_fmt = urllib.parse.quote_plus(query)
            if city_slug in SUBITO_CITY_REGIONS:
                region_slug = SUBITO_CITY_REGIONS[city_slug]
                urls.append(f"https://www.subito.it/annunci-{region_slug}/vendita/usato/{city_slug}/?q={q_fmt}&sort=datedesc")
            else:
                urls.append(f"https://www.subito.it/annunci-italia/vendita/usato/?q={q_fmt}&sort=datedesc")
            
    if "facebook" in CFG["active_sites"]:
        fb_city = "roma" if city_slug in ["all", "italia", "italy", ""] else urllib.parse.quote(city_slug)
        for query in CFG["search_queries"]:
            q_fmt = urllib.parse.quote(query)
            urls.append(f"https://www.facebook.com/marketplace/{fb_city}/search/?sortBy=creation_time_descend&query={q_fmt}&exact=false")
            
    return list(dict.fromkeys(urls))

def extract_exact_price(text_content):
    """Checks ONLY the first 40 lines (header area) to avoid scraping related ads at the bottom."""
    lines = text_content.split('\n')
    for line in lines[:40]:
        clean_line = (
            line.replace('€', '')
            .replace('EUR', '')
            .replace('euro', '')
            .replace('$', '')
            .replace('USD', '')
            .strip()
        )
        if re.match(r'^\d{1,3}(\.\d{3})*(,\d{1,2})?$', clean_line) or re.match(r'^\d+([.,]\d{1,2})?$', clean_line):
            try:
                if re.match(r'^\d{1,3}(\.\d{3})+(,\d{1,2})?$', clean_line):
                    normalized = clean_line.replace('.', '').replace(',', '.')
                else:
                    normalized = clean_line.replace(',', '.')
                val = float(normalized)
                if 10 <= val <= 15000:
                    return val
            except ValueError:
                continue
    return None

def parse_ai_price(ai_response_text, fallback_price=None):
    """Extracts the PRICE field returned by the AI if the header regex missed it."""
    if fallback_price is not None:
        return fallback_price
    match = re.search(r'PRICE:\s*([0-9]+(?:[.,][0-9]+)?)', ai_response_text, re.IGNORECASE)
    if match:
        try:
            raw_num = match.group(1)
            if re.match(r'^\d{1,3}\.\d{3}$', raw_num):
                raw_num = raw_num.replace('.', '')
            else:
                raw_num = raw_num.replace(',', '.')
            return float(raw_num)
        except ValueError:
            pass
    return None

# =====================================================================
# AI EVALUATION MODULES
# =====================================================================
def image_url_to_base64(img_url):
    try:
        r = HTTP_SESSION.get(img_url, timeout=10)
        if r.status_code == 200:
            mime = r.headers.get("Content-Type", "image/jpeg")
            b64 = base64.b64encode(r.content).decode("utf-8")
            return f"data:{mime};base64,{b64}"
    except Exception:
        pass
    return img_url

def call_openrouter_api(model_name, messages):
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {CFG['openrouter_api_key']}",
        "Content-Type": "application/json"
    }
    data = {"model": model_name, "messages": messages}
    
    response = HTTP_SESSION.post(api_url, headers=headers, json=data, timeout=45)
    
    if response.status_code in [400, 404, 429] and model_name != "openrouter/free":
        print(f"  └── [AI FALLBACK] Error {response.status_code} on '{model_name}'. Switching to 'openrouter/free'...")
        data["model"] = "openrouter/free"
        response = HTTP_SESSION.post(api_url, headers=headers, json=data, timeout=45)
        
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def evaluate_with_text_ai(raw_text, extracted_price):
    categories_str = ", ".join(CFG["search_queries"]) if CFG["search_queries"] else "General item"
    pos_str = ", ".join(CFG["positive_criteria"]) if CFG["positive_criteria"] else "Any good condition item"
    neg_str = ", ".join(CFG["negative_criteria"]) if CFG["negative_criteria"] else "None"
    max_price = CFG["max_price"]
    price_hint = f"{extracted_price} EUR" if extracted_price is not None else "Not detected by regex (extract actual item price from text)"

    prompt = f"""
    You are a strict appraiser evaluating a raw web page scrape.
    Target Item Category: {categories_str}
    Required Criteria (MUST match): {pos_str}
    Exclusion Criteria (MUST NOT have): {neg_str}
    Header Detected Price: {price_hint} (Maximum Allowed Price: {max_price} EUR).
    Listing Text: "{raw_text[:3500]}"
    
    CRITICAL RULES:
    1. If the text clearly violates any Exclusion Criteria, exceeds Maximum Allowed Price ({max_price} EUR), sells only a minor accessory/spare part, or is a "wanted to buy" ("cerco") ad, output "MATCH: NO".
    2. If the text clearly fails to meet the Required Criteria (for example, wrong year, wrong type), output "MATCH: NO".
    3. If the text lacks details to verify the Required Criteria OR if visual inspection of photos is needed to check physical condition / Exclusion Criteria (like rust, missing parts, or visual type), output "MATCH: NEED_VISION".
    4. If the text alone completely confirms all Required Criteria and rules out all Exclusion Criteria, output "MATCH: YES".
    5. Do NOT repeat the price inside REASON (put it only in the PRICE field).
    
    Respond EXACTLY in this 3-line format:
    MATCH: [YES, NO, or NEED_VISION]
    PRICE: [numeric price of the main item only, e.g. 150, or UNKNOWN]
    REASON: [1 short sentence explaining why, without mentioning the price]
    """
    
    messages = [{"role": "user", "content": prompt}]
    try:
        return call_openrouter_api(CFG["text_ai_model"], messages)
    except requests.exceptions.HTTPError as err:
        error_details = err.response.text if err.response is not None else str(err)
        return f"MATCH: API_ERROR\nPRICE: UNKNOWN\nREASON: API HTTP Error: {error_details[:120]}"
    except Exception as e:
        return f"MATCH: API_ERROR\nPRICE: UNKNOWN\nREASON: API Connection Failed: {str(e)[:120]}"

def evaluate_with_vision_ai(raw_text, image_urls):
    categories_str = ", ".join(CFG["search_queries"]) if CFG["search_queries"] else "General item"
    pos_str = ", ".join(CFG["positive_criteria"]) if CFG["positive_criteria"] else "Any good condition item"
    neg_str = ", ".join(CFG["negative_criteria"]) if CFG["negative_criteria"] else "None"

    prompt = f"""
    You are an expert visual appraiser inspecting product photos and text.
    Target Item Category: {categories_str}
    Required Criteria (MUST match): {pos_str}
    Exclusion Criteria (MUST NOT have): {neg_str}
    Listing Text: "{raw_text[:2500]}"
    
    1. Inspect the photos carefully. If the item shows any Exclusion Criteria (e.g., visual defects, rust, missing parts, wrong style) or shows ONLY spare parts/boxes, respond MATCH: NO.
    2. If the item in the photos and text matches the Required Criteria, respond MATCH: YES.
    3. Otherwise, respond MATCH: NO.
    4. Do NOT mention the price in REASON.
    
    Respond EXACTLY:
    MATCH: YES or NO
    REASON: [1 short sentence describing what you see and why it matches or fails]
    """
    
    content_array = [{"type": "text", "text": prompt}]
    for img in image_urls[:2]: 
        b64_img = image_url_to_base64(img)
        content_array.append({"type": "image_url", "image_url": {"url": b64_img}})
        
    messages = [{"role": "user", "content": content_array}]
    try:
        return call_openrouter_api(CFG["vision_ai_model"], messages)
    except requests.exceptions.HTTPError as err:
        error_details = err.response.text if err.response is not None else str(err)
        return f"MATCH: API_ERROR\nREASON: API HTTP Error: {error_details[:120]}"
    except Exception as e:
        return f"MATCH: API_ERROR\nREASON: API Connection Failed: {str(e)[:120]}"

def notify_success(url, analysis_reason, source_type, detected_price=None):
    cleaned_lines = []
    for line in analysis_reason.split('\n'):
        line_clean = line.replace('*', '').strip()
        if not line_clean:
            continue
        if line_clean.upper().startswith("MATCH:") or line_clean.upper().startswith("PRICE:"):
            continue
        line_clean = re.sub(r'^REASON:\s*', '', line_clean, flags=re.IGNORECASE)
        cleaned_lines.append(line_clean)
        
    clean_reason = " ".join(cleaned_lines).strip()
    price_str = f"{int(detected_price) if detected_price and detected_price.is_integer() else detected_price} EUR" if detected_price is not None else "Not specified"
    
    message = (
        f"🎯 <b>NEW TARGET FOUND!</b>\n\n"
        f"💰 <b>Price:</b> {price_str}\n"
        f"<b>{source_type}:</b>\n"
        f"{clean_reason}\n\n"
        f"🔗 <a href='{url}'>View Listing</a>"
    )
    bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode="HTML")

# =====================================================================
# HEADLESS SCRAPER ENGINE
# =====================================================================
def create_headless_driver():
    run_options = uc.ChromeOptions()
    run_options.page_load_strategy = 'eager'
    run_options.add_argument(f"--user-data-dir={PROFILE_FOLDER}")
    run_options.add_argument("--headless=new") 
    run_options.add_argument("--window-size=1920,1080")
    run_options.add_argument("--disable-gpu")
    run_options.add_argument("--no-sandbox")
    run_options.add_argument("--disable-dev-shm-usage")
    run_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36")
    return uc.Chrome(options=run_options)

def extract_item_details(driver, url):
    driver.get(url)
    time.sleep(2)
    driver.execute_script("window.scrollTo(0, 600);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 1100);")
    time.sleep(1)
    
    text_content = ""
    image_urls = []
    
    try:
        text_content = driver.find_element(By.TAG_NAME, "body").text
        images = driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            src = img.get_attribute('src')
            if not src or "http" not in src:
                continue
            
            is_valid = False
            if "subito" in url and ("subito.it" in src or "sbito.it" in src):
                if not src.endswith(".svg") and "avatar" not in src.lower() and "logo" not in src.lower():
                    is_valid = True
            elif "facebook" in url and "fbcdn.net" in src:
                if any(k in src for k in ["s720", "p720", "t39.30808", "t31.18172"]):
                    is_valid = True
                    
            if is_valid and src not in image_urls:
                image_urls.append(src)
    except Exception:
        pass
    return text_content, image_urls[:5]

def extract_links_from_dom(driver, processed_links, new_urls):
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        href = link.get_attribute('href')
        if not href:
            continue
        if "promosso" in href.lower() or "impresapiu" in href.lower():
            continue
            
        is_valid = False
        if "subito.it" in href and re.search(r'-\d+\.htm$', href):
            is_valid = True
        elif "/marketplace/item/" in href:
            is_valid = True
        
        if is_valid:
            clean_href = href.split('?')[0] if "marketplace" in href else href
            if clean_href not in processed_links and clean_href not in new_urls:
                new_urls.append(clean_href)

def get_new_listings(driver, source_url, processed_links, per_source_limit=12):
    print(f"\n[SCAN] Requesting: {source_url}")
    new_urls = []

    if "subito.it" in source_url:
        page_num = 1
        max_pages = max(1, (per_source_limit // 20) + 2)
        while len(new_urls) < per_source_limit and page_num <= max_pages:
            page_url = source_url if page_num == 1 else f"{source_url}&o={page_num}"
            if page_num > 1:
                print(f"  └── [PAGINATION] Loading Subito page {page_num}: {page_url}")
            driver.get(page_url)
            time.sleep(3)
            
            if page_num == 1:
                try:
                    cookie_btn = driver.find_element(By.ID, "didomi-notice-agree-button")
                    driver.execute_script("arguments[0].click();", cookie_btn)
                    time.sleep(1)
                except Exception:
                    pass

            for _ in range(2):
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(0.8)
                
            before_count = len(new_urls)
            try:
                extract_links_from_dom(driver, processed_links, new_urls)
            except Exception:
                pass
            if len(new_urls) == before_count and page_num > 1:
                break
            page_num += 1
    else:
        driver.get(source_url)
        time.sleep(4)
        max_scrolls = max(2, (per_source_limit // 5) + 1)
        for _ in range(max_scrolls):
            try:
                extract_links_from_dom(driver, processed_links, new_urls)
            except Exception:
                pass
            if len(new_urls) >= per_source_limit:
                break
            driver.execute_script("window.scrollBy(0, 1200);")
            time.sleep(1)

    return new_urls[:per_source_limit]

# =====================================================================
# MAIN ENGINE
# =====================================================================
if __name__ == "__main__":
    print("--- STARTING CHATOPS AI SNIPER ---")
    
    bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()
    
    needs_setup = not os.path.exists(PROFILE_FOLDER)
    if needs_setup:
        print("\n[FIRST RUN] Launching visible browser for Initial Login...")
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={PROFILE_FOLDER}")
        driver = uc.Chrome(options=options)
        driver.get("https://www.facebook.com/login")
        input("\n>>> Log into Facebook manually, then press ENTER here...")
        driver.quit()
        time.sleep(2)
        
    while True:
        CFG = load_config()
        
        if not CFG.get("is_active", False):
            print(f"[{time.strftime('%H:%M:%S')}] Sniper is PAUSED. Awaiting /run in Telegram.")
            while not CFG.get("is_active", False):
                time.sleep(1)
                CFG = load_config()
            continue

        FILTER_CHANGED_EVENT.clear()
        mem_hash = get_memory_file().split('_')[-1].replace('.txt', '')
        max_items_cycle = int(CFG.get("max_items", 24))
        print(f"\n[CYCLE START] {time.strftime('%Y-%m-%d %H:%M:%S')} | City: {CFG.get('city', 'messina')} | Max Price: {CFG['max_price']} EUR | Limit: {max_items_cycle} | Memory Profile: {mem_hash}")
        
        TARGET_URLS = generate_target_urls()
        driver = None
        
        try:
            driver = create_headless_driver()
            processed_links = load_processed_links()
            items_cache = load_items_cache()
            
            target_urls = []
            if TARGET_URLS:
                for idx, url in enumerate(TARGET_URLS):
                    if not CFG.get("is_active", False) or FILTER_CHANGED_EVENT.is_set():
                        break
                    remaining_sources = len(TARGET_URLS) - idx
                    needed_items = max(1, max_items_cycle - len(target_urls))
                    per_source_quota = max(1, (needed_items + remaining_sources - 1) // remaining_sources)
                    
                    found_links = get_new_listings(driver, url, processed_links, per_source_quota)
                    for link in found_links:
                        if link not in target_urls:
                            target_urls.append(link)
                target_urls = target_urls[:max_items_cycle]
            
            print(f"---> Found {len(target_urls)} NEW unique listings for current memory profile (Cycle Limit: {max_items_cycle}).")
            
            for item_url in target_urls:
                if not CFG.get("is_active", False):
                    print("[STOP] /stop command received. Interrupting item processing...")
                    break
                if FILTER_CHANGED_EVENT.is_set():
                    print("[RELOAD] Filter change detected in Telegram! Restarting scan immediately...")
                    break
                    
                if item_url in processed_links:
                    continue
                    
                print(f"\n[EVALUATING] {item_url}")
                cached_price = None
                if item_url in items_cache:
                    print("  └── [CACHE HIT] Loaded item text and images from local cache (0s browser load).")
                    raw_text = items_cache[item_url]["text"]
                    images = items_cache[item_url]["images"]
                    cached_price = items_cache[item_url].get("price")
                else:
                    raw_text, images = extract_item_details(driver, item_url)
                    if len(raw_text) > 50:
                        save_item_to_cache(items_cache, item_url, raw_text, images)
                
                if len(raw_text) > 50:
                    detected_price = extract_exact_price(raw_text)
                    if detected_price is None and cached_price is not None:
                        detected_price = cached_price
                    current_max = CFG["max_price"]
                    
                    if detected_price is not None and detected_price > current_max:
                        print(f"  └── [REJECTED] Price {detected_price} EUR > {current_max} EUR")
                        save_processed_link(item_url)
                        processed_links.add(item_url)
                        continue 
                    
                    text_ai_verdict = evaluate_with_text_ai(raw_text, detected_price)
                    safe_text_verdict = text_ai_verdict.replace('\n', ' | ')
                    print(f"  └── [TEXT AI] {safe_text_verdict}")
                    
                    if "MATCH: API_ERROR" in text_ai_verdict.upper():
                        print("  └── [API RATE LIMIT / ERROR] Skipping Vision AI and keeping item unseen for next cycle.")
                        if "429" in text_ai_verdict or "RATE LIMIT" in text_ai_verdict.upper():
                            print("  └── [QUOTA REACHED] Stopping current evaluation batch until API quota resets.")
                            break
                        continue
                        
                    final_price = parse_ai_price(text_ai_verdict, detected_price)
                    if final_price is not None and cached_price is None:
                        save_item_to_cache(items_cache, item_url, raw_text, images, final_price)
                    
                    if final_price is not None and final_price > current_max:
                        print(f"  └── [REJECTED BY AI PRICE] Price {final_price} EUR > {current_max} EUR")
                        save_processed_link(item_url)
                        processed_links.add(item_url)
                        continue
                    
                    if "MATCH: YES" in text_ai_verdict.upper():
                        notify_success(item_url, text_ai_verdict, "📝 TEXT AI", final_price)
                        
                    elif "MATCH: NEED_VISION" in text_ai_verdict.upper() and len(images) > 0:
                        vision_ai_verdict = evaluate_with_vision_ai(raw_text, images)
                        safe_vision_verdict = vision_ai_verdict.replace('\n', ' | ')
                        print(f"  └── [VISION AI] {safe_vision_verdict}")
                        
                        if "MATCH: API_ERROR" in vision_ai_verdict.upper():
                            print("  └── [API RATE LIMIT / ERROR] Keeping item unseen for next cycle.")
                            if "429" in vision_ai_verdict or "RATE LIMIT" in vision_ai_verdict.upper():
                                break
                            continue
                        
                        if "MATCH: YES" in vision_ai_verdict.upper():
                            notify_success(item_url, vision_ai_verdict, "👁️ VISION AI", final_price)
                
                save_processed_link(item_url)
                processed_links.add(item_url)
                
        except Exception as e:
            print(f"[CRITICAL ERROR] Pipeline failed: {e}")
        finally:
            if driver:
                driver.quit()
                
        if FILTER_CHANGED_EVENT.is_set():
            continue

        print("\nCycle finished. Sleeping for 20 minutes (any filter update will wake sniper immediately)...")
        for _ in range(20 * 60):
            if not CFG.get("is_active", False) or FILTER_CHANGED_EVENT.is_set():
                break
            time.sleep(1)