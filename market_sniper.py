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
    "search_queries": ["bici corsa"],
    "positive_criteria": ["road bike", "good condition", "not older than 2015"],
    "negative_criteria": ["rusty", "missing pedals", "broken", "kids bike"]
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
        f"pc:{sorted(CFG['positive_criteria'])}|"
        f"nc:{sorted(CFG['negative_criteria'])}"
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
        "🔍 <code>/add_search [text]</code> - Add site search query\n"
        "❌ <code>/del_search [text]</code> - Remove search query\n\n"
        
        "<b>[ AI SELECTION CRITERIA ]</b>\n"
        "✅ <code>/add_criteria [text]</code> - Add required condition\n"
        "➖ <code>/del_criteria [text]</code> - Remove condition\n"
        "🛑 <code>/add_exclude [text]</code> - Add exclusion/defect\n"
        "➖ <code>/del_exclude [text]</code> - Remove exclusion\n"
        "🧹 <code>/clear_all</code> - Reset all searches & criteria\n\n"
        
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
    
    sq = ', '.join(CFG['search_queries']) or "None"
    pc = ', '.join(CFG['positive_criteria']) or "None"
    nc = ', '.join(CFG['negative_criteria']) or "None"
    
    text = (
        f"📊 <b>STATUS:</b> {state}\n\n"
        f"💰 <b>Max Price:</b> {CFG['max_price']} EUR\n"
        f"🌐 <b>Active Sites:</b> {', '.join(CFG['active_sites'])}\n"
        f"📁 <b>Memory Profile ID:</b> {current_mem_hash}\n\n"
        f"🔑 <b>API Key:</b> {CFG['openrouter_api_key'][:8]}...***\n"
        f"🧠 <b>Text AI:</b> {CFG['text_ai_model']}\n"
        "👁 <b>Vision AI:</b> " + f"{CFG['vision_ai_model']}\n\n"
        f"🔍 <b>Site Search Queries:</b>\n{sq}\n\n"
        f"✅ <b>Required Criteria:</b>\n{pc}\n\n"
        f"🛑 <b>Exclusions (What to avoid):</b>\n{nc}"
    )
    bot.reply_to(message, text, parse_mode="HTML")

@bot.message_handler(commands=['price'])
def set_price(message):
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
    try:
        new_price = float(message.text.split(' ', 1)[1].replace(',', '.'))
        CFG['max_price'] = new_price
        save_config()
        bot.reply_to(message, f"✅ Max price updated to: {new_price} EUR", parse_mode="HTML")
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
        phrase = message.text.split(' ', 1)[1].lower().strip()
        if is_add:
            if phrase not in CFG[list_name]:
                CFG[list_name].append(phrase)
                save_config()
                bot.reply_to(message, f"✅ Added: {phrase}\n🔄 <i>Memory profile automatically switched.</i>", parse_mode="HTML")
            else: bot.reply_to(message, f"⚠️ Already exists: {phrase}")
        else:
            if phrase in CFG[list_name]:
                CFG[list_name].remove(phrase)
                save_config()
                bot.reply_to(message, f"🗑 Removed: {phrase}\n🔄 <i>Memory profile automatically switched.</i>", parse_mode="HTML")
            else: bot.reply_to(message, f"⚠️ Not found: {phrase}")
    except:
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
    if str(message.chat.id) != TELEGRAM_CHAT_ID: return
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
        
    save_config()
    bot.reply_to(message, f"{msg}\n🔄 <i>Memory profile automatically switched.</i>", parse_mode="HTML")

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
# =====================================================================
# AI EVALUATION MODULES
# =====================================================================
import base64

def image_url_to_base64(img_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        r = requests.get(img_url, headers=headers, timeout=10)
        if r.status_code == 200:
            mime = r.headers.get("Content-Type", "image/jpeg")
            b64 = base64.b64encode(r.content).decode("utf-8")
            return f"data:{mime};base64,{b64}"
    except:
        pass
    return img_url

def call_openrouter_api(model_name, messages):
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {CFG['openrouter_api_key']}", "Content-Type": "application/json"}
    data = {"model": model_name, "messages": messages}
    
    response = requests.post(api_url, headers=headers, json=data, timeout=45)
    # Если модель выдала ошибку 400/404/429, автоматически переключаемся на openrouter/free
    if response.status_code in [400, 404, 429] and model_name != "openrouter/free":
        print(f"  └── [AI FALLBACK] Status {response.status_code} on '{model_name}'. Switching to 'openrouter/free'...")
        data["model"] = "openrouter/free"
        response = requests.post(api_url, headers=headers, json=data, timeout=45)
        
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def evaluate_with_text_ai(raw_text, extracted_price):
    categories_str = ", ".join(CFG["search_queries"]) or "General item"
    pos_str = ", ".join(CFG["positive_criteria"]) or "Any good condition item"
    neg_str = ", ".join(CFG["negative_criteria"]) or "None"
    max_price = CFG["max_price"]
    
    prompt = f"""
    You are a strict appraiser evaluating a raw web page scrape.
    Target Item Category: {categories_str}
    Required Criteria (MUST match): {pos_str}
    Exclusion Criteria (MUST NOT have): {neg_str}
    Maximum Allowed Price: {max_price} EUR.
    Listing Text: "{raw_text}"
    
    CRITICAL RULES:
    1. If the text clearly violates any Exclusion Criteria, sells only a minor accessory/spare part, or is a "wanted to buy" ("cerco") ad, output "MATCH: NO".
    2. If the text clearly fails to meet the Required Criteria (for example, wrong year, wrong type), output "MATCH: NO".
    3. If the text lacks details to verify the Required Criteria OR if visual inspection of photos is needed to check physical condition / Exclusion Criteria (like rust, missing parts, or visual type), output "MATCH: NEED_VISION".
    4. If the text alone completely confirms all Required Criteria and rules out all Exclusion Criteria, output "MATCH: YES".
    
    Respond EXACTLY in this format:
    MATCH: [YES, NO, or NEED_VISION]
    REASON: 1 short sentence explaining why.
    """
    
    messages = [{"role": "user", "content": prompt}]
    try:
        return call_openrouter_api(CFG["text_ai_model"], messages)
    except requests.exceptions.HTTPError as err:
        error_details = err.response.text if err.response is not None else str(err)
        return f"MATCH: NEED_VISION\nREASON: API HTTP Error: {error_details[:120]}"
    except Exception as e:
        return f"MATCH: NEED_VISION\nREASON: API Connection Failed: {str(e)[:120]}"

def evaluate_with_vision_ai(raw_text, image_urls):
    categories_str = ", ".join(CFG["search_queries"]) or "General item"
    pos_str = ", ".join(CFG["positive_criteria"]) or "Any good condition item"
    neg_str = ", ".join(CFG["negative_criteria"]) or "None"
    
    prompt = f"""
    You are an expert visual appraiser inspecting product photos and text.
    Target Item Category: {categories_str}
    Required Criteria (MUST match): {pos_str}
    Exclusion Criteria (MUST NOT have): {neg_str}
    Listing Text: "{raw_text}"
    
    1. Inspect the photos carefully. If the item shows any Exclusion Criteria (e.g., visual defects, rust, missing parts, wrong style) or shows ONLY spare parts/boxes, respond MATCH: NO.
    2. If the item in the photos and text matches the Required Criteria, respond MATCH: YES.
    3. Otherwise, respond MATCH: NO.
    
    Respond EXACTLY:
    MATCH: YES or NO
    REASON: 1 short sentence describing what you see and why it matches or fails.
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
        return f"MATCH: NO\nREASON: API HTTP Error: {error_details[:120]}"
    except Exception as e:
        return f"MATCH: NO\nREASON: API Connection Failed: {str(e)[:120]}"

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