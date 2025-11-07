# src/utils/persistence.py

import json
import os
import logging
import sys
from concurrent.futures import ThreadPoolExecutor # For thread-safe saving
import time # Zamanla ilgili fonksiyonlar için (sleep gibi)
import csv # CSV dosyalarıyla çalışmak için

# Proje kök dizinindeki src klasörünü Python yoluna ekle
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.append(src_path)

# Config import for file paths (ensure config is loaded first in main)
try:
    from src.config import ALPHA_CACHE_FILE, OPEN_POSITIONS_FILE, TRADE_HISTORY_FILE, DATA_DIR
except ImportError:
    # This might happen if run directly, handle gracefully or rely on main orchestrator's path setup
    print("Warning: Could not import config paths from src.config in persistence.py")
    # Define fallback paths or raise error depending on desired behavior
    DATA_DIR = os.path.join(project_root, 'data')
    ALPHA_CACHE_FILE = os.path.join(DATA_DIR, 'alpha_cache.json')
    OPEN_POSITIONS_FILE = os.path.join(DATA_DIR, 'open_positions.json')
    TRADE_HISTORY_FILE = os.path.join(DATA_DIR, 'trades_history.csv')
    os.makedirs(DATA_DIR, exist_ok=True) # Ensure data dir exists

# Loglamayı ayarla
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')
logger = logging.getLogger(__name__)

# Thread pool for non-blocking file writes
# max_workers=1 ensures only one write operation happens at a time per executor instance,
# preventing race conditions for the same file if called rapidly from different threads.
# However, using locks (like open_positions_lock in main) is still the primary safety mechanism.
executor = ThreadPoolExecutor(max_workers=1)

# --- File Loading Function ---
def load_from_disk(filepath: str, default=None):
    """
    Loads data from a JSON file. If the file doesn't exist or is invalid,
    returns the default value.

    Args:
        filepath (str): Path to the JSON file.
        default: Value to return if loading fails.

    Returns:
        The loaded data (usually dict or list) or the default value.
    """
    if not os.path.exists(filepath):
        logger.warning(f"💾 File not found: {filepath}. Returning default value.")
        return default
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"💾 Data successfully loaded from: {filepath}")
            return data
    except json.JSONDecodeError:
        logger.error(f"❌ Error decoding JSON from: {filepath}. File might be corrupted. Returning default value.")
        # Optionally: Backup corrupted file here
        # os.rename(filepath, filepath + ".corrupted")
        return default
    except Exception as e:
        logger.error(f"❌ Unexpected error loading data from {filepath}: {e}", exc_info=True)
        return default

# --- File Saving Function (Thread-safe approach) ---
def _save_to_disk_sync(filepath: str, data):
    """Synchronous part of saving data to JSON file."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        # Write atomically: first to temp file, then rename
        temp_filepath = filepath + ".tmp"
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4) # Use indent for readability
        os.replace(temp_filepath, filepath) # Atomic rename operation
        logger.info(f"💾 Data successfully saved to: {filepath}")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving data to {filepath}: {e}", exc_info=True)
        # Attempt to remove temp file if it exists
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except Exception as remove_e:
                logger.error(f"Failed to remove temp file {temp_filepath}: {remove_e}")
        return False

def save_to_disk(filepath: str, data):
    """
    Asynchronously saves data to a JSON file using a thread pool executor
    to avoid blocking the main thread.

    Args:
        filepath (str): Path to the JSON file.
        data: The data to save (must be JSON serializable).
    """
    logger.debug(f"💾 Submitting save task for: {filepath}")
    # Submit the synchronous save function to the executor
    future = executor.submit(_save_to_disk_sync, filepath, data)
    # Optional: Add callback for completion or error handling if needed
    # future.add_done_callback(lambda f: logger.info(f"Save task completed for {filepath} with result: {f.result()}"))
    return future # Return the future object if caller needs to wait/check status

# --- CSV Saving Function (Append Mode) ---
def append_to_csv(filepath: str, record: dict):
    """
    Appends a dictionary record as a new row to a CSV file.
    Creates the file and header if it doesn't exist.

    Args:
        filepath (str): Path to the CSV file.
        record (dict): Dictionary representing the row to append. Keys become headers.
    """
    try:
        file_exists = os.path.exists(filepath)
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, 'a', newline='', encoding='utf-8') as f:
           
            fieldnames = record.keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if not file_exists or os.path.getsize(filepath) == 0:
                writer.writeheader() # Write header only if file is new/empty

            writer.writerow(record)
        logger.info(f"💾 Record successfully appended to: {filepath}")
        return True
    except Exception as e:
        logger.error(f"❌ Error appending record to {filepath}: {e}", exc_info=True)
        return False

# --- Test Code ---
if __name__ == "__main__":
    logger.info("--- persistence.py functions test ---")

    test_cache_file = os.path.join(DATA_DIR, 'test_cache.json')
    test_positions_file = os.path.join(DATA_DIR, 'test_positions.json')
    test_history_file = os.path.join(DATA_DIR, 'test_history.csv')

    # 1. Test Loading (file shouldn't exist initially)
    print("\n--- Testing Load (Initial) ---")
    initial_cache = load_from_disk(test_cache_file, default={'a': 1})
    print(f"Initial cache content: {initial_cache}") # Should be default {'a': 1}
    initial_pos = load_from_disk(test_positions_file, default=[])
    print(f"Initial positions content: {initial_pos}") # Should be default []

    # 2. Test Saving
    print("\n--- Testing Save ---")
    test_data_cache = {'btc': {'score': 50}, 'eth': {'score': -20}}
    save_future = save_to_disk(test_cache_file, test_data_cache)
    test_data_pos = [{'id': 'pos1', 'symbol': 'BTCUSDT'}, {'id': 'pos2', 'symbol': 'ETHUSDT'}]
    save_pos_future = save_to_disk(test_positions_file, test_data_pos)

    # Wait for saves to complete (important for testing)
    save_future.result()
    save_pos_future.result()
    print("Save operations submitted (check log for success/error)")
    time.sleep(0.1) # Give a moment for logs to appear

    # 3. Test Loading Again (should load saved data)
    print("\n--- Testing Load (After Save) ---")
    loaded_cache = load_from_disk(test_cache_file, default={})
    print(f"Loaded cache content: {loaded_cache}") # Should match test_data_cache
    loaded_pos = load_from_disk(test_positions_file, default=[])
    print(f"Loaded positions content: {loaded_pos}") # Should match test_data_pos

    # 4. Test Appending to CSV
    print("\n--- Testing Append to CSV ---")
    trade1 = {'id': 't1', 'symbol': 'BTCUSDT', 'pnl_usd': 50.5, 'status': 'SUCCESS'}
    trade2 = {'id': 't2', 'symbol': 'ETHUSDT', 'pnl_usd': -20.0, 'status': 'FAILED', 'reason': 'SL Hit'} # Test extra field
    append_to_csv(test_history_file, trade1)
    # For the second trade, ensure all columns are written even if keys don't match exactly
    # Get headers from file if it exists, otherwise use keys from record
    try:
        with open(test_history_file, 'r', newline='', encoding='utf-8') as f_read:
            reader = csv.reader(f_read)
            headers = next(reader) # Read the header row
    except (FileNotFoundError, StopIteration):
        headers = trade2.keys() # Use keys from current record if file is empty/new

    # Prepare record with all headers, filling missing ones with empty string
    record_to_write = {h: trade2.get(h, '') for h in headers}
    append_to_csv(test_history_file, record_to_write)
    print(f"Appended records to {test_history_file} (check file content)")

    # Clean up test files
    print("\n--- Cleaning up test files ---")
    # try:
    #     os.remove(test_cache_file)
    #     os.remove(test_positions_file)
    #     os.remove(test_history_file)
    #     print("Test files removed.")
    # except OSError as e:
    #     print(f"Error removing test files: {e}")

    print("\n--- Test tamamlandı ---")