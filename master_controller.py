import time
import random
import subprocess
import logging
import sys
from datetime import datetime, timedelta
import pytz  # Required for timezone handling

# --- CONFIGURATION ---
# All settings are now in a single dictionary for easier management.
CONFIG = {
    # File containing the list of scripts to run (one per line).
    "SCRIPTS_CONFIG_FILE": "scripts_to_run.txt",

    # --- Human Behavior Settings ---
    "TIMEZONE": "America/New_York",  # IMPORTANT: Set to your local timezone.
                                     # List of timezones: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
    
    # The bot will be most active between these hours (24-hour format).
    "ACTIVE_HOURS_START": 7,  # 7 AM
    "ACTIVE_HOURS_END": 23, # 11 PM

    # --- Posting Target Settings ---
    "DAILY_POST_TARGET": 350,
    # The actual target for the day will be +/- this percentage. (e.g., 5% of 350 is 17.5)
    # So the target will be between ~332 and ~368.
    "TARGET_VARIATION_PERCENT": 5,

    # --- Wait Time Settings ---
    # Short, random pause between running scripts within a single cycle.
    "MIN_WAIT_BETWEEN_SCRIPTS_SECONDS": 5,
    "MAX_WAIT_BETWEEN_SCRIPTS_SECONDS": 25,
    
    # Long wait time used during "quiet hours" (e.g., overnight).
    "MIN_WAIT_QUIET_HOURS_MINUTES": 20,
    "MAX_WAIT_QUIET_HOURS_MINUTES": 45,
}

# --- SCRIPT ---
# Set up basic logging to see the runner's activity.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [Controller] - %(message)s')

def get_scripts_to_run():
    """Reads the list of scripts from the configuration file."""
    try:
        with open(CONFIG["SCRIPTS_CONFIG_FILE"], 'r') as f:
            scripts = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        if not scripts:
            logging.warning(f"'{CONFIG['SCRIPTS_CONFIG_FILE']}' is empty. No scripts to run.")
        return scripts
    except FileNotFoundError:
        logging.critical(f"FATAL: Config file '{CONFIG['SCRIPTS_CONFIG_FILE']}' not found. Please create it.")
        sys.exit(1)

def run_script(script_name):
    """Executes a single script, returns True on success, False on failure."""
    logging.info(f"--- Starting run of '{script_name}' ---")
    try:
        subprocess.run(
            [sys.executable, script_name],
            check=True, capture_output=True, text=True, timeout=300 # 5-minute timeout
        )
        logging.info(f"'{script_name}' completed successfully.")
        return True
    except FileNotFoundError:
        logging.error(f"Could not find '{script_name}'. Skipping.")
        return False
    except subprocess.CalledProcessError as e:
        logging.error(f"'{script_name}' failed with an error.")
        logging.error(f"--- Error output from '{script_name}' ---\n" + e.stderr.strip())
        return False
    except subprocess.TimeoutExpired:
        logging.error(f"'{script_name}' timed out after 5 minutes. Skipping.")
        return False

def get_current_time():
    """Returns the current time in the configured timezone."""
    return datetime.now(pytz.timezone(CONFIG["TIMEZONE"]))

def is_active_time(current_time):
    """Checks if the current time is within the active hours."""
    return CONFIG["ACTIVE_HOURS_START"] <= current_time.hour < CONFIG["ACTIVE_HOURS_END"]

def calculate_dynamic_wait(posts_today, daily_target):
    """Calculates wait time to intelligently meet the daily target."""
    now = get_current_time()
    
    if not is_active_time(now):
        logging.info("It's quiet time. Taking a long break.")
        return random.randint(CONFIG["MIN_WAIT_QUIET_HOURS_MINUTES"] * 60, CONFIG["MAX_WAIT_QUIET_HOURS_MINUTES"] * 60)

    if posts_today >= daily_target:
        logging.info(f"Daily target of {daily_target} met! Resting until next active period.")
        return random.randint(CONFIG["MIN_WAIT_QUIET_HOURS_MINUTES"] * 60, CONFIG["MAX_WAIT_QUIET_HOURS_MINUTES"] * 60)

    # --- Dynamic Pacing Logic ---
    posts_left = daily_target - posts_today
    
    # Calculate remaining seconds in the active window for today
    end_of_active_day = now.replace(hour=CONFIG["ACTIVE_HOURS_END"], minute=0, second=0, microsecond=0)
    seconds_left_in_window = (end_of_active_day - now).total_seconds()

    if seconds_left_in_window <= 0:
        logging.warning("Ran out of active time for today. Resting.")
        return random.randint(CONFIG["MIN_WAIT_QUIET_HOURS_MINUTES"] * 60, CONFIG["MAX_WAIT_QUIET_HOURS_MINUTES"] * 60)

    # Calculate the average time we have for each remaining post
    # Add 1 to posts_left to prevent division by zero on the last post
    avg_seconds_per_post = seconds_left_in_window / (posts_left + 1)
    
    # Create a random wait time centered around the calculated average
    # This makes the bot speed up if it's behind and slow down if it's ahead
    min_wait = max(1, avg_seconds_per_post * 0.75) # At least 1 second
    max_wait = avg_seconds_per_post * 1.25
    
    wait_time = random.uniform(min_wait, max_wait)
    
    logging.info(f"Posts remaining: {posts_left}. Time left: {timedelta(seconds=int(seconds_left_in_window))}. Pacing wait to ~{wait_time:.2f}s.")
    return wait_time


if __name__ == "__main__":
    logging.info(f"Master Controller started. Timezone: {CONFIG['TIMEZONE']}. Press Ctrl+C to stop.")
    
    posts_today = 0
    current_day = get_current_time().date()
    todays_target = 0

    while True:
        try:
            # --- Daily Reset Logic ---
            now = get_current_time()
            if now.date() != current_day:
                logging.info(f"--- New Day ({now.date()}) ---")
                current_day = now.date()
                posts_today = 0
                
                # Calculate a new varied target for the day
                variation = int(CONFIG["DAILY_POST_TARGET"] * (CONFIG["TARGET_VARIATION_PERCENT"] / 100))
                todays_target = random.randint(CONFIG["DAILY_POST_TARGET"] - variation, CONFIG["DAILY_POST_TARGET"] + variation)
                logging.info(f"Today's post target set to: {todays_target}")

            # If todays_target hasn't been set yet (first run)
            if todays_target == 0:
                variation = int(CONFIG["DAILY_POST_TARGET"] * (CONFIG["TARGET_VARIATION_PERCENT"] / 100))
                todays_target = random.randint(CONFIG["DAILY_POST_TARGET"] - variation, CONFIG["DAILY_POST_TARGET"] + variation)
                logging.info(f"Today's post target set to: {todays_target}")

            # --- Script Execution Cycle ---
            scripts_to_execute = get_scripts_to_run()
            
            if scripts_to_execute and posts_today < todays_target and is_active_time(now):
                logging.info(f"Starting new cycle. Progress: {posts_today}/{todays_target} posts.")
                for script in scripts_to_execute:
                    if run_script(script):
                        posts_today += 1 # Only count successful posts
                    
                    # Add human-like "jitter" between scripts in a cycle
                    if len(scripts_to_execute) > 1:
                        jitter = random.uniform(CONFIG["MIN_WAIT_BETWEEN_SCRIPTS_SECONDS"], CONFIG["MAX_WAIT_BETWEEN_SCRIPTS_SECONDS"])
                        time.sleep(jitter)
            
            # --- Wait for Next Cycle ---
            wait_seconds = calculate_dynamic_wait(posts_today, todays_target)
            next_run_time = datetime.now() + timedelta(seconds=wait_seconds)
            logging.info(f"--- Cycle finished. Waiting for {wait_seconds / 60:.2f} minutes. Next run at: {next_run_time.strftime('%H:%M:%S')} ---")
            time.sleep(wait_seconds)

        except KeyboardInterrupt:
            logging.info("Controller stopped by user. Exiting.")
            break
        except Exception as e:
            logging.critical(f"An unexpected error occurred in the main loop: {e}")
            logging.info("Restarting loop after a 5-minute wait...")
            time.sleep(300)
