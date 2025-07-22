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
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, expect
from groq import Groq

try:
    import spacy
    import pandas as pd
    import mplfinance as mpf
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("FATAL ERROR: A required library is not installed. Run: pip install spacy pandas matplotlib mplfinance Pillow")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s] - %(message)s')
logger = logging.getLogger(__name__)

# --- ALL GLOBAL VARIABLES ---
CONFIG_FILE = "config.ini"
HYPE_HISTORY_FILE = "hype_history.txt" # New history file for this tweet style
AUTH_FILE = "auth_x.json"
CHART_FILE = "generated_chart.png"
GROQ_API_KEY = None
NLP_MODEL = None
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# Expanded handles for greater reach on the chart
TWITTER_HANDLES = {
    "Binance": "@binance", "Ethereum": "@ethereum", "Bitcoin": "@Bitcoin", "Solana": "@solana", "SEC": "@SECGov",
    "Coinbase": "@coinbase", "Vitalik Buterin": "@VitalikButerin", "Elon Musk": "@elonmusk", "MicroStrategy": "@MicroStrategy"
}
TICKER_MAP = {
    "bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "ripple": "XRP",
    "cardano": "ADA", "dogecoin": "DOGE", "binance coin": "BNB", "avalanche": "AVAX"
}

# --- HELPER FUNCTIONS (Some NEW, some UNCHANGED) ---
def setup_environment():
    global GROQ_API_KEY, NLP_MODEL
    if not os.path.exists(CONFIG_FILE): logger.error(f"FATAL: Config file '{CONFIG_FILE}' not found."); return False
    config = configparser.ConfigParser(); config.read(CONFIG_FILE)
    GROQ_API_KEY = config.get('API_KEYS', 'GROQ_API_KEY', fallback=None)
    if not GROQ_API_KEY: logger.error(f"FATAL: GROQ_API_KEY not found."); return False
    if not os.path.exists(AUTH_FILE): logger.error(f"FATAL: Auth file '{AUTH_FILE}' not found. Please run 'get_auth.py' to create it."); return False
    try: NLP_MODEL = spacy.load("en_core_web_sm")
    except OSError: logger.error("FATAL: spaCy model not found. Run 'python -m spacy download en_core_web_sm'"); return False
    logger.info("Environment setup successful."); return True

def load_processed_hype_posts():
    """Loads used (ticker, date) combinations to avoid repetition."""
    if not os.path.exists(HYPE_HISTORY_FILE): return set()
    with open(HYPE_HISTORY_FILE, 'r') as f: return {line.strip() for line in f if line.strip()}

def save_processed_hype_post(ticker, date_str):
    """Saves a used (ticker, date) combination to the history file."""
    with open(HYPE_HISTORY_FILE, 'a') as f: f.write(f"{ticker},{date_str}\n")
    logger.info(f"Saved new hype post to history: {ticker} from {date_str}")

def get_historical_data(ticker, days=1825): # Fetch 5 years of data
    """Fetches daily historical price data for a given crypto ticker."""
    try:
        url = f"https://min-api.cryptocompare.com/data/v2/histoday?fsym={ticker.upper()}&tsym=USD&limit={days}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()['Data']['Data']
        if not data:
            logger.warning(f"No historical data returned for {ticker}.")
            return None
        price_df = pd.DataFrame(data)
        price_df['time'] = pd.to_datetime(price_df['time'], unit='s')
        price_df = price_df.set_index('time')
        price_df = price_df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volumeto": "Volume"})
        # Filter out days with no volume, as they can have erroneous price data
        price_df = price_df[price_df['Volume'] > 0]
        logger.info(f"Successfully fetched {len(price_df)} days of historical data for {ticker}.")
        return price_df
    except Exception as e:
        logger.error(f"Failed to fetch historical data for {ticker}: {e}")
        return None

def find_significant_low(price_df, ticker, used_posts):
    """Analyzes price data to find a significant low point from the past."""
    if price_df is None or price_df.empty:
        return None
    # Look for a low point between 1 and 4 years ago
    start_date = datetime.now() - timedelta(days=365 * 4)
    end_date = datetime.now() - timedelta(days=365 * 1)
    relevant_period = price_df[(price_df.index >= start_date) & (price_df.index <= end_date)]

    if relevant_period.empty:
        logger.warning(f"No data for {ticker} in the desired period (1-4 years ago).")
        return None

    # Sort by low price and find a suitable candidate that hasn't been used
    for _, low_point in relevant_period.sort_values('Low', ascending=True).iterrows():
        date_str = low_point.name.strftime('%Y-%m-%d')
        if f"{ticker},{date_str}" not in used_posts:
            logger.info(f"Found significant low for {ticker}: ${low_point['Low']:.2f} on {date_str}")
            return low_point
    logger.warning(f"Could not find a unique significant low for {ticker}. All candidates have been posted.")
    return None

def get_llm_hype_tweet(ticker, roi, years, low_price, current_price, client):
    """Generates a hype-focused tweet using an LLM."""
    logger.info("Requesting LLM for a new HYPE tweet...")
    system_prompt = "You are 'Alpha Intel', a crypto analyst known for viral, hype-generating tweets. Your goal is to create a tweet that shows the massive potential of holding cryptocurrencies. Focus on a 'what if' scenario. Be exciting and forward-looking. Output ONLY the tweet text, under 260 characters."
    user_content = f"Create a tweet for ${ticker}. A $1,000 investment at the low of ${low_price:,.2f} about {years:.1f} years ago would now be worth over ${1000 * roi:,.0f}. The ROI is over {roi:,.0f}x. Make it punchy and add a bold prediction or a question about where it's going next."

    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            model="llama3-8b-8192"
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM request failed: {e}")
        return f"${ticker} has shown incredible growth. What's next for the crypto giant?"

def create_hype_chart(ticker, price_df, low_point, your_x_handle):
    """Generates a chart proving the 'what if' scenario, designed for social media."""
    try:
        # Prepare data for plotting
        plot_data = price_df[price_df.index >= low_point.name]
        current_price = plot_data.iloc[-1]
        low_date = low_point.name.strftime('%Y-%m-%d')
        current_date = current_price.name.strftime('%Y-%m-%d')
        roi = current_price['Close'] / low_point['Low']

        # Add plot elements to highlight the key points
        buy_marker = [float('nan')] * len(plot_data)
        buy_marker[0] = plot_data['Low'][0] * 0.95 # Place marker slightly below the low
        ap0 = mpf.make_addplot(buy_marker, type='scatter', marker='^', color='lime', markersize=200)

        # Create the plot style
        style = mpf.make_mpf_style(base_mpf_style='nightclouds',
                                   marketcolors=mpf.make_marketcolors(up='#00b386', down='#ff4d4d', inherit=True),
                                   gridstyle='-.')

        # Generate the main plot
        fig, axes = mpf.plot(plot_data, type='candle', style=style,
                             title=f"\n${ticker}/USD: The Power of Holding",
                             volume=True, addplot=ap0,
                             figratio=(18, 10), returnfig=True,
                             savefig=dict(fname=CHART_FILE, dpi=120))

        # --- Add custom text and watermarks with PIL ---
        image = Image.open(CHART_FILE)
        draw = ImageDraw.Draw(image)
        w, h = image.size
        try:
            title_font = ImageFont.truetype("arialbd.ttf", 32)
            label_font = ImageFont.truetype("arial.ttf", 22)
            watermark_font = ImageFont.truetype("arial.ttf", 18)
        except IOError:
            title_font = label_font = watermark_font = ImageFont.load_default()

        # Add ROI text
        draw.text((w * 0.05, h * 0.15), f"{roi:,.0f}x Return!", font=title_font, fill="yellow")

        # Add "Buy Here" annotation
        draw.text((w * 0.1, h * 0.75), f"Bought Here\n{low_date}\n@ ${low_point['Low']:.2f}", font=label_font, fill="lime")

        # Add "Value Now" annotation
        draw.text((w * 0.75, h * 0.3), f"Worth Now\n{current_date}\n@ ${current_price['Close']:.2f}", font=label_font, fill="#00b386")

        # Add watermarks for reach
        draw.text((30, h - 40), your_x_handle, font=watermark_font, fill="rgba(255, 255, 255, 100)")
        handles_to_tag = random.sample(list(TWITTER_HANDLES.values()), k=min(3, len(TWITTER_HANDLES)))
        draw.text((w - 200, h - 40), ' '.join(handles_to_tag), font=watermark_font, fill="rgba(255, 255, 255, 80)")

        image.save(CHART_FILE)
        logger.info(f"Hype chart for {ticker} generated at {CHART_FILE}")
        return CHART_FILE
    except Exception as e:
        logger.error(f"Failed during hype chart generation for {ticker}: {e}")
        return None

def generate_hashtags(text, ticker):
    """Generates relevant hashtags for the tweet."""
    hashtags = {f"#{ticker}", "#Crypto", "#HODL", "#Investing", "#CryptoNews", "#Blockchain"}
    doc = NLP_MODEL(text)
    keywords = {ent.text.strip() for ent in doc.ents if ent.label_ in ['ORG', 'GPE']}
    for word in list(keywords)[:2]:
        hashtags.add(f"#{''.join(filter(str.isalnum, word))}")
    return " ".join(list(hashtags)[:6])

def generate_mentions(text, max_mentions=2):
    """Generates mentions based on keywords in the text."""
    mentions = {handle for name, handle in TWITTER_HANDLES.items() if name.lower() in text.lower()}
    return " ".join(list(mentions)[:max_mentions])

# --- UNCHANGED POSTING FUNCTION ---
def post_final_tweet(tweet_content, chart_path=None):
    """Launches Playwright in DEBUG mode to diagnose the posting issue."""
    logger.info("--- Initiating Tweet Posting Sequence in INTERACTIVE DEBUG MODE ---")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = None # Define here to access in the 'except' block
        try:
            context = browser.new_context()
            page = context.new_page()
            
            logger.info("Reading auth file to restore session...")
            with open(AUTH_FILE, 'r') as f: cookies = json.load(f)
            context.add_cookies(cookies)
            
            page.goto("https://x.com/home")
            logger.info("Waiting for the main page to load and confirm login...")
            expect(page.locator('a[data-testid="SideNav_NewTweet_Button"]')).to_be_visible(timeout=30000)
            logger.info("✅ Login successful and home page loaded.")
            
            page.locator('a[data-testid="SideNav_NewTweet_Button"]').click()
            text_editor = page.get_by_role("textbox", name="Post text")
            expect(text_editor).to_be_visible(timeout=15000)
            text_editor.fill(tweet_content)

            if chart_path and os.path.exists(chart_path):
                logger.info(f"Attaching media: {chart_path}")
                # Use .first to resolve ambiguity
                page.locator('input[type="file"]').first.set_input_files(chart_path)
                
                # --- THIS IS THE FIX ---
                # Remove the unreliable wait for a preview, replace with a simple pause
                logger.info("Waiting 5 seconds for image to process...")
                page.wait_for_timeout(5000)
                # --- END OF FIX ---
            
            post_button = page.locator('button[data-testid="tweetButton"]')
            expect(post_button).to_be_enabled(timeout=15000)
            
            logger.info(">>> SCRIPT PAUSED. Browser is ready. Review and click 'Resume' (▶) to post.")
            #page.pause()
            
            logger.info(">>> Resumed. Attempting a low-level JavaScript click...")
            post_button.dispatch_event('click')
            
            logger.info(">>> SCRIPT PAUSED AGAIN. Observe the result. Click 'Resume' to finish.")
            #page.pause()
            
            logger.info(">>> Resumed. Checking for success confirmation...")
            success_toast = page.locator('div[data-testid="toast"]:has-text("Your post was sent")')
            expect(success_toast).to_be_visible(timeout=10000)
            logger.info("✅ DEBUGGER CONFIRMED SUCCESS.")
            return True
                
        except Exception as e:
            logger.error(f"❌ An error occurred during the interactive debug session: {e}")
            if page: page.screenshot(path="error_interactive_debug.png")
            return False
        finally:
            if browser.is_connected():
                browser.close()

def main():
    if not setup_environment(): sys.exit(1)
    llm_client = Groq(api_key=GROQ_API_KEY)
    processed_posts = load_processed_hype_posts()
    
    selected_ticker = None
    chart_path = None
    tweet_info = {}
    
    # Try a few random tickers until we find one that works
    available_tickers = list(TICKER_MAP.values())
    random.shuffle(available_tickers)

    for ticker in available_tickers:
        logger.info(f"--- Attempting to generate hype post for {ticker} ---")
        price_data = get_historical_data(ticker)
        if price_data is None:
            continue
            
        low_point = find_significant_low(price_data, ticker, processed_posts)
        # --- THIS IS THE FIX ---
        # Changed 'if not low_point:' to 'if low_point is None:' to avoid the ValueError.
        if low_point is None:
            continue
        # --- END OF FIX ---
        
        current_price = price_data.iloc[-1]['Close']
        low_price = low_point['Low']
        
        # Ensure there's meaningful growth to talk about
        if current_price <= low_price:
            logger.warning(f"Current price for {ticker} is not higher than the historical low. Skipping.")
            continue
            
        years_diff = (datetime.now() - low_point.name).days / 365.25
        roi_multiple = current_price / low_price
        
        chart_path = create_hype_chart(ticker, price_data, low_point, "@AlphaIntel")
        if not chart_path:
            logger.error(f"Failed to generate chart for {ticker}, trying next ticker.")
            continue
            
        tweet_info = {
            "ticker": ticker,
            "roi": roi_multiple,
            "years": years_diff,
            "low_price": low_price,
            "current_price": current_price,
            "low_date_str": low_point.name.strftime('%Y-%m-%d')
        }
        selected_ticker = ticker
        break # Found a valid ticker and generated a chart

    if not selected_ticker or not chart_path:
        logger.error("Failed to find any suitable cryptocurrency for a hype post after several attempts. Exiting.")
        sys.exit(1)
        
    tweet_body = get_llm_hype_tweet(
        selected_ticker, tweet_info['roi'], tweet_info['years'],
        tweet_info['low_price'], tweet_info['current_price'], llm_client
    )
    
    hashtags = generate_hashtags(tweet_body, selected_ticker)
    mentions = generate_mentions(tweet_body)
    extras = f"{mentions}\n\n{hashtags}" if mentions else hashtags
    final_tweet = f"{tweet_body}\n\n{extras}"
    
    logger.info(f"\n--- FINAL TWEET ---\n{final_tweet}\n---------------------\n")
    
    if post_final_tweet(final_tweet, chart_path):
        save_processed_hype_post(selected_ticker, tweet_info['low_date_str'])
        logger.info("Process completed successfully.")
    else:
        logger.error("Failed to post tweet. Hype post history will not be updated.")
        sys.exit(1)

if __name__ == "__main__":
    main()
