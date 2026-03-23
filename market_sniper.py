import os
import time
import re
import json
import threading
import hashlib
import requests
import urllib.parse
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import telebot

# =====================================================================
# SYSTEM & TOKENS (TELEGRAM ONLY)
# =====================================================================
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"

CONFIG_FILE = os.path.abspath("config.json")
PROFILE_FOLDER = os.path.abspath("browser_profile")
MEMORY_DIR = os.path.abspath("memory_profiles")

os.makedirs(MEMORY_DIR, exist_ok=True)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# =====================================================================
# CONFIGURATION MANAGER
# =====================================================================
DEFAULT_CONFIG = {
    "is_active": False,  
    "max_price": 200.0,
    "active_sites": ["subito", "facebook"],
    "openrouter_api_key": "YOUR_OPENROUTER_API_KEY_HERE",
    "text_ai_model": "stepfun/step-3.5-flash:free",
    "vision_ai_model": "nvidia/nemotron-nano-12b-v2-vl:free",
    "search_queries": ["metal detector", "nokta"],
    "target_models": ["nokta", "simplex"],
    "negative_words": ["sunpow","headphones"]
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            loaded_cfg = json.load(f)
            needs_save = False
            for key, value in DEFAULT_CONFIG.items():
                if key not in loaded_cfg:
                    loaded_cfg[key] = value
                    needs_save = True
            
            if needs_save:
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(loaded_cfg, f, indent=4)
                    
            return loaded_cfg
    except json.JSONDecodeError:
        return DEFAULT_CONFIG.copy() 

def save_config():
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(CFG, f, indent=4)

CFG = load_config()

# =====================================================================
# DYNAMIC CONTEXTUAL MEMORY (HASH-BASED)
# =====================================================================
def get_memory_file():
    state_str = (
        f"sq:{sorted(CFG['search_queries'])}|"
        f"tm:{sorted(CFG['target_models'])}|"
        f"nw:{sorted(CFG['negative_words'])}"
    )
    state_hash = hashlib.md5(state_str.encode()).hexdigest()[:12]
    return os.path.join(MEMORY_DIR, f"seen_{state_hash}.txt")

def load_processed_links():
    mem_file = get_memory_file()
    if not os.path.exists(mem_file): return []
    with open(mem_file, "r") as f: return [line.strip() for line in f.readlines()]

def save_processed_link(url):
    mem_file = get_memory_file()
    with open(mem_file, "a") as f: f.write(f"{url}\n")

# =====================================================================
# TELEGRAM BOT INTERFACE (CHATOPS)
# =====================================================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    text = (
        "🤖 <b>AI Sniper Control Panel</b>\n\n"
        "<b>[ ENGINE CONTROLS ]</b>\n"
        "🟢 <code>/run</code> - Start scanning\n"
        "🔴 <code>/stop</code> - Pause scanning\n"
        "📊 <code>/status</code> - Show full configuration\n\n"
        
        "<b>[ FILTERS & SEARCH ]</b>\n"
        "💰 <code>/price [num]</code> - Max allowed price\n"
        "🌐 <code>/sites [subito/facebook/both]</code> - Set targets\n"
        "🔍 <code>/add_search [word]</code> - Add site search query\n"
        "❌ <code>/del_search [word]</code> - Remove search query\n\n"
        
        "<b>[ AI VALIDATION ]</b>\n"
        "🎯 <code>/add_model [word]</code> - Add AI target model\n"
        "❌ <code>/del_model [word]</code> - Remove AI target model\n"
        "🛑 <code>/add_stop [word]</code> - Add ban word\n"
        "❌ <code>/del_stop [word]</code> - Remove ban word\n\n"
        
        "<b>[ API & MODELS ]</b>\n"
        "🔑 <code>/api_key [key]</code> - Set OpenRouter API key\n"
        "🧠 <code>/text_model [name]</code> - Set Text AI model\n"
        "👁 <code>/vision_model [name]</code> - Set Vision AI model\n"
    )
    bot.reply_to(message, text, parse_mode="HTML")

@bot.message_handler(commands=['run', 'stop'])
def toggle_bot(message):
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    is_start = message.text.startswith('/run')
    CFG['is_active'] = is_start
    save_config()
    state_msg = "🟢 <b>Sniper is RUNNING.</b>" if is_start else "🔴 <b>Sniper is PAUSED.</b>"
    bot.reply_to(message, state_msg, parse_mode="HTML")

@bot.message_handler(commands=['status'])
def send_status(message):
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    state = "🟢 RUNNING" if CFG.get('is_active') else "🔴 PAUSED"
    current_mem_hash = get_memory_file().split('_')[-1].replace('.txt', '')
    
    text = (
        f"📊 <b>STATUS:</b> {state}\n\n"
        f"💰 <b>Max Price:</b> {CFG['max_price']} EUR\n"
        f"🌐 <b>Active Sites:</b> {', '.join(CFG['active_sites'])}\n"
        f"📁 <b>Memory Profile ID:</b> {current_mem_hash}\n\n"
        f"🔑 <b>API Key:</b> {CFG['openrouter_api_key'][:8]}...***\n"
        f"🧠 <b>Text AI:</b> {CFG['text_ai_model']}\n"
        f"👁 <b>Vision AI:</b> {CFG['vision_ai_model']}\n\n"
        f"🔍 <b>Site Search Queries:</b>\n{', '.join(CFG['search_queries'])}\n\n"
        f"🎯 <b>AI Target Models:</b>\n{', '.join(CFG['target_models'])}\n\n"
        f"🛑 <b>Stop Words:</b>\n{', '.join(CFG['negative_words'])}"
    )
    bot.reply_to(message, text, parse_mode="HTML")

@bot.message_handler(commands=['price'])
def set_price(message):
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    try:
        new_price = float(message.text.split(' ', 1)[1].replace(',', '.'))
        CFG['max_price'] = new_price
        save_config()
        bot.reply_to(message, f"✅ Max price updated to: {new_price} EUR\n<i>(Note: Changing price does not reset memory, old items will be dynamically re-evaluated if price allows).</i>", parse_mode="HTML")
    except:
        bot.reply_to(message, "❌ Invalid format. Use: /price 150")

@bot.message_handler(commands=['sites'])
def set_sites(message):
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    try:
        choice = message.text.split(' ', 1)[1].lower().strip()
        if choice == 'subito': CFG['active_sites'] = ['subito']
        elif choice == 'facebook': CFG['active_sites'] = ['facebook']
        elif choice == 'both': CFG['active_sites'] = ['subito', 'facebook']
        else: raise ValueError
        save_config()
        bot.reply_to(message, f"✅ Active sites updated: {', '.join(CFG['active_sites'])}")
    except:
        bot.reply_to(message, "❌ Invalid format. Use: /sites subito (or facebook, both)")

@bot.message_handler(commands=['api_key'])
def set_api(message):
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    try:
        key = message.text.split(' ', 1)[1].strip()
        CFG['openrouter_api_key'] = key
        save_config()
        bot.reply_to(message, "✅ OpenRouter API Key updated.")
    except:
        bot.reply_to(message, "❌ Provide key. Example: /api_key sk-or-v1...")

@bot.message_handler(commands=['text_model'])
def set_text_model(message):
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    try:
        model = message.text.split(' ', 1)[1].strip()
        CFG['text_ai_model'] = model
        save_config()
        bot.reply_to(message, f"✅ Text Model set to: {model}")
    except:
        bot.reply_to(message, "❌ Provide model name.")

@bot.message_handler(commands=['vision_model'])
def set_vision_model(message):
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    try:
        model = message.text.split(' ', 1)[1].strip()
        CFG['vision_ai_model'] = model
        save_config()
        bot.reply_to(message, f"✅ Vision Model set to: {model}")
    except:
        bot.reply_to(message, "❌ Provide model name.")

def modify_list(message, list_name, is_add=True):
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    try:
        word = message.text.split(' ', 1)[1].lower().strip()
        if is_add:
            if word not in CFG[list_name]:
                CFG[list_name].append(word)
                save_config()
                bot.reply_to(message, f"✅ Added: {word}\n🔄 <i>Memory profile automatically switched.</i>", parse_mode="HTML")
            else: bot.reply_to(message, f"⚠️ Already exists: {word}")
        else:
            if word in CFG[list_name]:
                CFG[list_name].remove(word)
                save_config()
                bot.reply_to(message, f"🗑 Removed: {word}\n🔄 <i>Memory profile automatically switched.</i>", parse_mode="HTML")
            else: bot.reply_to(message, f"⚠️ Not found: {word}")
    except:
        bot.reply_to(message, "❌ Error. Please provide a word.")

@bot.message_handler(commands=['add_search'])
def add_sq(m): modify_list(m, 'search_queries', True)
@bot.message_handler(commands=['del_search'])
def del_sq(m): modify_list(m, 'search_queries', False)
@bot.message_handler(commands=['add_model'])
def add_m(m): modify_list(m, 'target_models', True)
@bot.message_handler(commands=['del_model'])
def del_m(m): modify_list(m, 'target_models', False)
@bot.message_handler(commands=['add_stop'])
def add_st(m): modify_list(m, 'negative_words', True)
@bot.message_handler(commands=['del_stop'])
def del_st(m): modify_list(m, 'negative_words', False)

def start_telegram_bot():
    print("[SYSTEM] Telegram ChatOps Interface running...")
    bot.send_message(TELEGRAM_CHAT_ID, "⚙️ System Online. Send /run to start background scanning.")
    bot.infinity_polling()

# =====================================================================
# CORE PIPELINE FUNCTIONS
# =====================================================================
def generate_target_urls():
    urls = []
    if "subito" in CFG["active_sites"]:
        for query in CFG["search_queries"]:
            q_fmt = query.replace(" ", "+")
            urls.append(f"https://www.subito.it/annunci-italia/vendita/usato/?q={q_fmt}&sort=datedesc")
            
    if "facebook" in CFG["active_sites"]:
        for query in CFG["search_queries"]:
            q_fmt = urllib.parse.quote(query)
            urls.append(f"https://www.facebook.com/marketplace/search/?sortBy=creation_time_descend&query={q_fmt}&exact=false")
            
    return list(set(urls))

def extract_exact_price(text_content):
    lines = text_content.split('\n')
    for line in lines[:50]:
        line = line.strip().lower()
        clean_line = line.replace('€', '').replace('euro', '').replace('eur', '').strip()
        
        if re.match(r'^\d+([.,]\d{1,2})?$', clean_line):
            try:
                price_val = float(clean_line.replace(',', '.'))
                if 10 <= price_val <= 10000: return price_val
            except: continue
    return None

# =====================================================================
# AI EVALUATION MODULES
# =====================================================================
def evaluate_with_text_ai(raw_text, extracted_price):
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {CFG['openrouter_api_key']}", "Content-Type": "application/json"}
    
    models_str = ", ".join(CFG["target_models"])
    max_price = CFG["max_price"]
    
    prompt = f"""
    You are a strict appraiser evaluating a raw web page scrape.
    Target Items: Professional metal detectors from these lines: {models_str}
    Maximum Allowed Price: {max_price} EUR.
    Listing Text: "{raw_text}"
    
    CRITICAL RULES:
    1. If the text clearly identifies a target model from our list as the main item being sold, output "MATCH: YES".
    2. If the text is long (over 30 words) but DOES NOT mention any of our target brands/models, output "MATCH: NO".
    3. You are FORBIDDEN from outputting "MATCH: NEED_VISION" unless the text is extremely short (under 30 words) AND lacks a brand name. 
    4. If it's an accessory (only coil/headphones), output "MATCH: NO".
    
    Respond EXACTLY in this format:
    MATCH: [YES, NO, or NEED_VISION]
    REASON: 1 short sentence explaining why.
    """
    
    data = {"model": CFG["text_ai_model"], "messages": [{"role": "user", "content": prompt}]}
    try:
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as err:
        error_details = err.response.text if err.response else str(err)
        return f"MATCH: NEED_VISION\nREASON: API HTTP Error: {error_details}"
    except Exception as e:
        return f"MATCH: NEED_VISION\nREASON: API Connection Failed: {str(e)}"

def evaluate_with_vision_ai(raw_text, image_urls):
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {CFG['openrouter_api_key']}", "Content-Type": "application/json"}
    models_str = ", ".join(CFG["target_models"])
    
    prompt = f"""
    You are an expert appraiser. Text was vague, rely on images.
    Target Items: {models_str}
    Listing Text: "{raw_text}"
    
    1. If images show ONLY accessories, respond MATCH: NO.
    2. If you see a metal detector from our Target Items list, respond MATCH: YES.
    3. If you see unbranded junk, respond MATCH: NO.
    
    Respond EXACTLY:
    MATCH: YES or NO
    REASON: 1 short sentence.
    """

    content_array = [{"type": "text", "text": prompt}]
    for img in image_urls: content_array.append({"type": "image_url", "image_url": {"url": img}})

    data = {"model": CFG["vision_ai_model"], "messages": [{"role": "user", "content": content_array}]}
    try:
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as err:
        error_details = err.response.text if err.response else str(err)
        return f"MATCH: NO\nREASON: API HTTP Error: {error_details}"
    except Exception as e:
        return f"MATCH: NO\nREASON: API Connection Failed: {str(e)}"

def notify_success(url, analysis_reason, source_type):
    clean_reason = analysis_reason.replace("*", "").replace("MATCH: YES", "").replace("MATCH: NEED_VISION", "").strip()
    message = (
        f"🎯 <b>NEW TARGET FOUND!</b>\n\n"
        f"<b>{source_type}:</b>\n"
        f"{clean_reason}\n\n"
        f"🔗 <a href='{url}'>View Listing</a>"
    )
    bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode="HTML")

# =====================================================================
# HEADLESS SCRAPER ENGINE
# =====================================================================
def extract_item_details(driver, url):
    driver.get(url)
    time.sleep(2) 
    driver.execute_script("window.scrollTo(0, 500);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 1000);")
    time.sleep(1)
    
    text_content = ""
    image_urls = []
    
    try:
        text_content = driver.find_element(By.TAG_NAME, "body").text
        images = driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            src = img.get_attribute('src')
            if not src or "http" not in src: continue
            
            is_valid = False
            if "subito" in url and ("subito.it" in src or "sbito.it" in src):
                if not src.endswith(".svg") and "avatar" not in src.lower() and "logo" not in src.lower(): is_valid = True
            elif "facebook" in url and "fbcdn.net" in src:
                if "s720" in src or "p720" in src or "t39.30808" in src or "t31.18172" in src: is_valid = True

            if is_valid and src not in image_urls: image_urls.append(src)
    except: pass
    return text_content, image_urls[:5]

def get_new_listings(driver, source_url, processed_links):
    print(f"\n[SCAN] Requesting: {source_url}")
    driver.get(source_url)
    time.sleep(4)
    
    if "subito.it" in source_url:
        try:
            cookie_btn = driver.find_element(By.ID, "didomi-notice-agree-button")
            driver.execute_script("arguments[0].click();", cookie_btn)
            time.sleep(1)
        except: pass

    for _ in range(2):
        driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(1)
    
    new_urls = []
    try:
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute('href')
            if not href: continue
            if "promosso" in href.lower() or "impresapiu" in href.lower(): continue 

            is_valid = False
            if "subito.it" in href and re.search(r'-\d+\.htm$', href): is_valid = True
            elif "/marketplace/item/" in href: is_valid = True

            if is_valid:
                clean_href = href.split('?')[0] if "marketplace" in href else href
                if clean_href not in processed_links and clean_href not in new_urls: new_urls.append(clean_href)
    except: pass
    return new_urls[:10]

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
            print(f"[{time.strftime('%H:%M:%S')}] Sniper is PAUSED. Awaiting /run command in Telegram.")
            while not CFG.get("is_active", False):
                time.sleep(1) 
            continue
            
        mem_hash = get_memory_file().split('_')[-1].replace('.txt', '')
        print(f"\n[CYCLE START] {time.strftime('%Y-%m-%d %H:%M:%S')} | Memory Profile: {mem_hash}")
        
        TARGET_URLS = generate_target_urls()
        
        run_options = uc.ChromeOptions()
        run_options.add_argument(f"--user-data-dir={PROFILE_FOLDER}")
        run_options.add_argument("--headless=new") 
        run_options.add_argument("--window-size=1920,1080")
        run_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36")
        
        driver = None
        try:
            driver = uc.Chrome(options=run_options)
            processed_links = load_processed_links()
            
            target_urls = []
            for url in TARGET_URLS: 
                if not CFG.get("is_active", False): break
                target_urls.extend(get_new_listings(driver, url, processed_links))
            target_urls = list(set(target_urls))
            
            print(f"---> Found {len(target_urls)} NEW unique listings for current memory profile.")
            
            for item_url in target_urls:
                if not CFG.get("is_active", False):
                    print("[STOP] /stop command received. Interrupting item processing...")
                    break 
                    
                if item_url in processed_links: continue
                
                print(f"\n[EVALUATING] {item_url}")
                    
                raw_text, images = extract_item_details(driver, item_url)
                text_lower = raw_text.lower()
                
                if len(raw_text) > 50:
                    price = extract_exact_price(raw_text)
                    current_max = CFG["max_price"]
                    if price is None: price = current_max
                    
                    if price > current_max:
                        print(f"  └── [REJECTED] Price {price} > {current_max}")
                        continue
                        
                    has_negative = any(word in text_lower for word in CFG["negative_words"])
                    if has_negative:
                        print(f"  └── [REJECTED] Found Stop Word")
                        save_processed_link(item_url)
                        continue

                    text_ai_verdict = evaluate_with_text_ai(raw_text, price)
                    safe_text_verdict = text_ai_verdict.replace('\n', ' | ')
                    print(f"  └── [TEXT AI] {safe_text_verdict}")
                    
                    if "MATCH: YES" in text_ai_verdict.upper():
                        notify_success(item_url, text_ai_verdict, "📝 TEXT AI")
                    
                    elif "MATCH: NEED_VISION" in text_ai_verdict.upper() and len(images) > 0:
                        vision_ai_verdict = evaluate_with_vision_ai(raw_text, images)
                        safe_vision_verdict = vision_ai_verdict.replace('\n', ' | ')
                        print(f"  └── [VISION AI] {safe_vision_verdict}")
                        
                        if "MATCH: YES" in vision_ai_verdict.upper():
                            notify_success(item_url, vision_ai_verdict, "👁️ VISION AI")
                        
                save_processed_link(item_url)
                
        except Exception as e: print(f"[CRITICAL ERROR] Pipeline failed: {e}")
        finally:
            if driver: driver.quit()
            
        print(f"\nCycle finished. Sleeping for 20 minutes...")
        for _ in range(20 * 60):
            if not CFG.get("is_active", False):
                break
            time.sleep(1)