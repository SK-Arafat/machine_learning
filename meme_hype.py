meme_hype.py
# post_x_final_trusted_poster.py

import os
import logging
import requests
import configparser
import re
import sys
import random
import html
import json
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, expect
from groq import Groq

# Spacy is no longer needed, simplifying dependencies
try:
    from PIL import Image
except ImportError:
    print("FATAL ERROR: A required library is not installed. Run: pip install Pillow")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s] - %(message)s')
logger = logging.getLogger(__name__)

# --- ALL GLOBAL VARIABLES ---
CONFIG_FILE = "config.ini"
HISTORY_FILE = "processed_urls.txt"
AUTH_FILE = "auth_x.json"
MEME_FILE = "downloaded_meme.png" # We are using memes, not charts
GROQ_API_KEY = None
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
SEGMENT_SOURCES = { "Crypto": [{"name": "Cointelegraph", "url": "https://cointelegraph.com/rss"}, {"name": "The Block", "url": "https://www.theblock.co/feed"}, {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},] }
TWITTER_HANDLES = { "Binance": "@binance", "Ethereum": "@ethereum", "Bitcoin": "@Bitcoin", "Solana": "@solana", "SEC": "@SECGov" }
TICKER_MAP = { "bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "ripple": "XRP", "cardano": "ADA", "dogecoin": "DOGE", "binance coin": "BNB", "stellar": "XLM" }

# --- HELPER FUNCTIONS ---
def setup_environment():
    global GROQ_API_KEY
    if not os.path.exists(CONFIG_FILE): logger.error(f"FATAL: Config file '{CONFIG_FILE}' not found."); return False
    config = configparser.ConfigParser(); config.read(CONFIG_FILE)
    GROQ_API_KEY = config.get('API_KEYS', 'GROQ_API_KEY', fallback=None)
    if not GROQ_API_KEY: logger.error(f"FATAL: GROQ_API_KEY not found."); return False
    if not os.path.exists(AUTH_FILE): logger.error(f"FATAL: Auth file '{AUTH_FILE}' not found. Please run 'get_auth.py' to create it."); return False
    logger.info("Environment setup successful."); return True

def load_processed_urls():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, 'r') as f: return {line.strip() for line in f if line.strip()}

def save_processed_url(url):
    with open(HISTORY_FILE, 'a') as f: f.write(url + '\n')
    logger.info(f"Saved used URL to history to prevent re-posting: {url}")

def identify_crypto_ticker(text):
    text_lower = text.lower()
    for name, ticker in TICKER_MAP.items():
        # Check for whole word matches to avoid partial matches (e.g., 'art' in 'Cardano')
        if re.search(r'\b' + re.escape(name) + r'\b', text_lower):
            return ticker
    return None

# --- SCRAPING AND MEME FUNCTIONS (WITH THE FIX) ---

def scrape_news(processed_urls):
    """
    Scrapes RSS feeds for the FIRST available article that has not been processed yet.
    THIS FUNCTION CONTAINS THE PRIMARY BUG FIX.
    """
    sources = list(SEGMENT_SOURCES["Crypto"]); random.shuffle(sources)
    for source in sources:
        try:
            logger.info(f"Scraping {source['name']} for meme-worthy articles...")
            time.sleep(random.uniform(1, 2))
            response = requests.get(source['url'], headers={"User-Agent": USER_AGENT}, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml-xml')

            for item in soup.find_all('item', limit=10):
                link = item.find('link').text.strip() if item.find('link') else None
                if link and link not in processed_urls:
                    title = item.find('title').text.strip()
                    logger.info(f"Found new article to process: '{title}'")
                    # Found a valid article, return it immediately.
                    return {"title": title, "link": link}
            
            # If the loop finishes, it means all articles from this source were already in the history file.
            logger.info(f"No new articles found from {source['name']}. Moving to next source.")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.warning(f"Could not scrape {source['name']}: 403 Forbidden. This is common; the site is blocking scripts. Skipping.")
            else:
                logger.warning(f"Could not scrape {source['name']}: {e}")
        except Exception as e:
            logger.warning(f"An unexpected error occurred while scraping {source['name']}: {e}")
            
    # If we get through all sources and find nothing new, return None.
    return None

def get_relevant_meme():
    """Fetches a trending meme from r/cryptomemes."""
    try:
        api_url = "https://meme-api.com/gimme/cryptomemes/1"
        logger.info(f"Requesting a fresh meme from {api_url}...")
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()

        if not data or 'memes' not in data or not data['memes']:
            logger.error("Meme API did not return any memes.")
            return None, None

        meme = data['memes'][0]
        meme_url = meme.get('url')
        meme_title = meme.get('title')

        image_response = requests.get(meme_url, stream=True)
        image_response.raise_for_status()
        
        with open(MEME_FILE, 'wb') as f:
            for chunk in image_response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Successfully downloaded meme: '{meme_title}'")
        return MEME_FILE, meme_title
    except Exception as e:
        logger.error(f"Failed to get a relevant meme: {e}")
        return None, None

def get_llm_tweet(news_title, meme_title, client):
    """Generates a funny tweet connecting the news to the meme."""
    logger.info("Requesting LLM for a FUNNY tweet...")
    system_prompt = (
        "You are 'Coiny The Meme-Lord', a legendary crypto twitter personality. You are hilarious, witty, and a bit cynical. "
        "Your gift is connecting boring crypto news to a random, funny meme to create comedic gold. "
        "Keep it short, punchy, and under 280 characters. Output ONLY the tweet text."
    )
    user_content = (
        f"Ok, Meme-Lord, work your magic. \n"
        f"The boring news headline is: \"{news_title}\"\n"
        f"The meme you HAVE to use is titled: \"{meme_title}\"\n\n"
        f"Combine them. Make it funny. Make them laugh. Go."
    )
    
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
            model="llama3-70b-8192"
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM request failed: {e}")
        return f"When you read that '{news_title}' but all you can think about is this meme. #crypto"

def generate_hashtags(ticker):
    tags = {"#Crypto", "#CryptoMemes", "#DeFi", "#Altcoins", "#Investing"}
    if ticker:
        tags.add(f"#{ticker}")
    return " ".join(list(tags)[:5])

# --- UNCHANGED POSTING FUNCTION ---
def post_final_tweet(tweet_content, meme_path=None):
    logger.info("--- Initiating Tweet Posting Sequence ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = None
        try:
            context = browser.new_context()
            page = context.new_page()
            logger.info("Reading auth file to restore session...")
            with open(AUTH_FILE, 'r') as f: cookies = json.load(f)
            context.add_cookies(cookies)
            page.goto("https://x.com/home")
            logger.info("Waiting for main page to load...")
            expect(page.locator('a[data-testid="SideNav_NewTweet_Button"]')).to_be_visible(timeout=30000)
            logger.info("✅ Login successful.")
            page.locator('a[data-testid="SideNav_NewTweet_Button"]').click()
            text_editor = page.get_by_role("textbox", name="Post text")
            expect(text_editor).to_be_visible(timeout=15000)
            text_editor.fill(tweet_content)
            if meme_path and os.path.exists(meme_path):
                logger.info(f"Attaching meme: {meme_path}")
                page.locator('input[type="file"]').first.set_input_files(meme_path)
                page.wait_for_timeout(5000) # Wait for upload
            post_button = page.locator('button[data-testid="tweetButton"]')
            expect(post_button).to_be_enabled(timeout=15000)
            logger.info(">>> Pausing script for final review. Press 'Resume' (▶) to publish.")
            # page.pause() # Uncomment for manual review before every post
            post_button.dispatch_event('click')
            success_toast = page.locator('div[data-testid="toast"]:has-text("Your post was sent")')
            expect(success_toast).to_be_visible(timeout=10000)
            logger.info("✅ Tweet posted successfully!")
            return True
        except Exception as e:
            logger.error(f"❌ An error occurred during posting: {e}")
            if page: page.screenshot(path="error_posting_meme.png")
            return False
        finally:
            if browser.is_connected():
                browser.close()

def main():
    if not setup_environment(): sys.exit(1)
    llm_client = Groq(api_key=GROQ_API_KEY)
    processed_urls = load_processed_urls()
    
    article = scrape_news(processed_urls)
    if not article:
        logger.error("Failed to find any new articles to make fun of after checking all sources. Exiting.")
        sys.exit(0) # Exit gracefully, not as an error
        
    meme_path, meme_title = get_relevant_meme()
    if not meme_path:
        logger.error("Could not get a meme. Cannot proceed.")
        sys.exit(1)
        
    tweet_body = get_llm_tweet(article['title'], meme_title, llm_client)
    
    ticker = identify_crypto_ticker(article['title'])
    hashtags = generate_hashtags(ticker)
    
    final_tweet = f"{tweet_body}\n\n{hashtags}"
    
    logger.info(f"\n--- FINAL TWEET ---\n{final_tweet}\n---------------------\n")
    
    if post_final_tweet(final_tweet, meme_path):
        # Only save the URL AFTER a successful post
        save_processed_url(article['link'])
        logger.info("Process completed successfully.")
    else:
        logger.error("Failed to post tweet. The URL will not be saved, allowing a retry on the next run.")
        sys.exit(1)

if __name__ == "__main__":
    main()
