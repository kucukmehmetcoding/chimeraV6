# ChimeraBot AI Coding Agent Instructions

## Project Overview
ChimeraBot is a **cryptocurrency trading bot** that combines technical analysis, sentiment analysis, and risk management to generate and manage trading signals on Binance. The bot is written in Turkish (comments/logs) but code patterns follow Python standards.

**Key Architecture:** Multi-threaded orchestrator pattern with scheduled scanning cycles and continuous position monitoring.

## Core Components & Data Flow

### 1. Main Orchestrator (`src/main_orchestrator.py`)
**Central control hub** - Runs scheduled scans every `SCAN_INTERVAL_MINUTES` (default: 10 min).

**Scan Cycle Flow:**
1. **Regime Detection**: Analyzes BTC 1D data → determines strategy mode (`PULLBACK`, `MEAN_REVERSION`, `BREAKOUT`, `STOP`)
2. **Coin Scanning**: Iterates through `CORRELATION_GROUPS` symbols (max 50)
3. **Alpha Updates**: Refreshes sentiment cache (Fear & Greed, news, Reddit, Google Trends)
4. **Signal Generation**: Each coin → multi-timeframe analysis (1D/4H/1H) → strategy application
5. **Quality Grading**: Alpha analyzer assigns A-D grades based on sentiment alignment with signal direction
6. **Risk Filtering**: Checks RR ratio, group risk limits, position limits → calculates position sizing
7. **Position Opening**: Valid signals saved to `OpenPosition` table in SQLite

**Threading Model:**
- Main thread: Scheduled scans via `schedule` library
- `TradeManagerThread` (daemon): Continuously monitors open positions for SL/TP hits

**Critical Lock:** `open_positions_lock` protects DB operations during concurrent access by main thread (writing new positions) and trade manager thread (closing positions).

### 2. Database Layer (`src/database/models.py`)
**SQLAlchemy ORM** with SQLite backend (`data/chimerabot.db`).

**Tables:**
- `OpenPosition`: Active trades with entry, SL, TP, quality grade, sentiment scores at signal time
- `TradeHistory`: Closed positions with PnL calculations
- `AlphaCache`: Sentiment data cache (Fear & Greed, news headlines, Reddit posts, Google Trends)

**Session Management:** Use `scoped_session` via `db_session()` - **always call `db_session.remove()` in `finally` blocks** to prevent connection leaks.

### 3. Strategy System (`src/technical_analyzer/`)

**Indicators (`indicators.py`):**
Uses TA-Lib for: EMA5/20/50, SMA50/200, RSI14, MACD histogram, ADX14, ATR14, Bollinger Bands + BBW (custom).

**Strategies (`strategies.py`):**
- `PULLBACK`: Long if 1D/4H both above EMA50>SMA200, then 1H shows RSI oversold (<40) or bullish MACD. Short if opposite.
- `MEAN_REVERSION`: 4H price touches BB extremes, 1H confirms reversal
- `BREAKOUT`: High volume + BB expansion + 1H closes above SMA200

**Strategy Selection:** Determined by BTC's ADX14 and BBW on 1D timeframe (see `determine_regime()`).

### 4. Risk Management (`src/risk_manager/calculator.py`)

**SL/TP Calculation:** 
- `find_recent_swing_levels()`: Identifies support/resistance from last N candles (default: 50)
- `calculate_structural_sl_tp()`: Places SL beyond swing level with buffer (default: 0.5%), TP at opposite level minus buffer
- `calculate_rr()`: Must meet `MIN_RR_RATIO` (default: 1.0) to proceed

**Position Sizing:**
```python
risk_usd = portfolio_usd * (planned_risk_percent / 100.0)
position_size = risk_usd / abs(entry_price - sl_price)
```

**Risk Limits:**
- `MAX_OPEN_POSITIONS`: Total concurrent positions (default: 5)
- `MAX_RISK_PER_GROUP`: Sum of `planned_risk_percent` per correlation group (default: 5.0%)
- `MAX_POSITIONS_PER_SYMBOL`: Prevents duplicate entries (default: 1)
- `QUALITY_MULTIPLIERS`: {'A': 1.2, 'B': 1.0, 'C': 0.5, 'D': 0.0} - D signals never open

### 5. Alpha Engine (`src/alpha_engine/`)

**Sentiment Sources (`sentiment_analyzer.py`):**
- Fear & Greed Index (cached hourly)
- RSS news feeds (CoinTelegraph, CoinDesk, etc.) - analyzed with Google Gemini API
- Reddit posts (r/CryptoCurrency, r/Bitcoin, etc.) - title/body sentiment scoring
- Google Trends (pytrends) - search interest for crypto keywords

**Quality Grading (`analyzer.py`):**
Weighted scoring system that considers **signal direction**:
- **LONG signals**: Favor low F&G (<25), positive news, bullish Reddit sentiment
- **SHORT signals**: Favor high F&G (>75), negative news, bearish Reddit sentiment
- **Penalties**: Missing news data incurs `-0.5 * news_weight` penalty
- Final score buckets: A (>2.0), B (0.5-2.0), C (-1.0-0.5), D (<-1.0)

### 6. Trade Manager (`src/trade_manager/manager.py`)

**Continuous Monitoring Loop:**
1. Acquires `open_positions_lock` → fetches `OpenPosition` records → releases lock
2. For each position: `get_current_price()` from Binance
3. Checks SL/TP conditions (LONG: price <= sl or >= tp, SHORT: opposite)
4. On trigger: Calculates PnL → moves to `TradeHistory` → deletes from `OpenPosition` → sends Telegram alert

**Sleep Interval:** `TRADE_MANAGER_SLEEP_SECONDS` (default: 10s)

### 7. Data Fetcher (`src/data_fetcher/binance_fetcher.py`)

**API Client:** `python-binance` library, initialized with `BINANCE_API_KEY`/`BINANCE_SECRET_KEY` from `.env`

**Retry Logic:** Uses `tenacity` - retries 3 times with 5s wait on:
- `BinanceRequestException` (network errors)
- Rate limit errors (code -1003, status 429/418)

**Rate Limit Handling:** Global `rate_limit_status` dict tracks multiplier (1.0-16.0x) to dynamically adjust `SCAN_DELAY_SECONDS` between API calls.

### 8. Notifications (`src/notifications/telegram.py`)

**Library:** `python-telegram-bot` v20+ (async API)

**Message Formatting:** All messages use MarkdownV2 → **must escape special chars** with `escape_markdown_v2()` before sending.

**Key Functions:**
- `initialize_bot(config)`: Creates Bot instance and Application
- `send_message(text)`: Wraps async send in `asyncio.run()` with event loop handling
- `send_new_signal_alert(signals)`: Formats multi-signal announcements
- `send_position_closed_alert(position)`: Shows PnL in USD and %

## Configuration (`src/config.py`)

**Environment Variables:** Loaded from `.env` file (create from `.env.example` if missing):
```env
BINANCE_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
REDDIT_CLIENT_ID=...  # Optional
```

**Key Settings:**
- `CORRELATION_GROUPS`: Dict mapping symbols to groups (MAJOR, MEME, AI, L1, L2, etc.)
- `STRATEGY_REQUIRED_INDICATORS`: Defines which indicators must be present per strategy/timeframe
- `SENTIMENT_RSS_FEEDS`: List of news feed URLs
- `SENTIMENT_SYMBOL_KEYWORDS`: Maps base symbols to search keywords for news/trends

## Development Workflows

### Running the Bot
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # Edit with real API keys

# Run main bot
python src/main_orchestrator.py
```

### Testing Components
```bash
# Test Telegram notifications
python test_telegram.py

# Test individual modules (many have __main__ blocks)
python src/technical_analyzer/strategies.py
python src/risk_manager/calculator.py
```

### Database Operations
```python
# Always use this pattern for DB access:
db = db_session()
try:
    positions = db.query(OpenPosition).all()
    # ... operations ...
    db.commit()
except Exception as e:
    db.rollback()
    logger.error(f"DB error: {e}")
finally:
    db_session.remove()  # Critical for cleanup
```

### Adding New Strategies
1. Add strategy function to `strategies.py` (return dict with direction/metadata)
2. Add required indicators to `STRATEGY_REQUIRED_INDICATORS` in `config.py`
3. Add regime condition to `determine_regime()` 
4. Add strategy case to `main_scan_cycle()` Step 4 logic

## Common Patterns

### NaN Handling
**Always check indicators** before strategy logic:
```python
if df.empty or len(df) < 2:
    return None
required_cols = ['rsi14', 'macd_hist']
if not all(col in df.columns for col in required_cols):
    return None
last_row = df.iloc[-1]
if last_row[required_cols].isna().any():
    return None
```

### Logging Best Practices
- Use module-level logger: `logger = logging.getLogger(__name__)`
- Debug: Internal state/loop iterations
- Info: Major steps/confirmations
- Warning: Recoverable issues (missing data, skipped signals)
- Error: Exceptions with `exc_info=True`
- Turkish OK for logs, English for docstrings

### Error Recovery
- **Binance API errors**: Caught in main scan loop, skip coin, continue
- **Rate limits**: Increase delay multiplier, auto-decays after 5min
- **DB errors**: Rollback transaction, notify via Telegram, continue to next cycle
- **Trade Manager**: Errors logged but thread keeps running (daemon=True ensures clean shutdown)

## Critical Gotchas

1. **Thread Safety**: Only modify `OpenPosition` inside `open_positions_lock` context
2. **TA-Lib Dependency**: Requires C libraries - installation often fails, see platform-specific guides
3. **Telegram Event Loop**: Must use `asyncio.run()` in sync contexts, avoid `RuntimeError` with loop policy checks
4. **SQLite Concurrency**: `check_same_thread=False` required, but locks still essential for writes
5. **Test Mode Active**: `determine_regime()` currently hardcoded to return `PULLBACK` (see line 56 warning comment)
6. **JSON vs DB**: Old persistence.py exists for legacy JSON files, **primary storage is now SQLite**

## Integration Points

**External APIs:**
- Binance: Market data, current prices (public + authenticated endpoints)
- Alternative.me: Fear & Greed Index (public, no auth)
- Reddit: PRAW library (requires OAuth app credentials)
- Google Gemini: News sentiment analysis (`google-generativeai` package)
- Google Trends: pytrends (unofficial, rate limited)

**Data Persistence:**
- SQLite database: All position/trade/cache data
- Logs: `logs/chimerabot.log` (UTF-8 encoding, append mode)
- Legacy JSON: `data/` directory (transitional, avoid direct use)

## When Extending This Codebase

- **New sentiment sources**: Add to `sentiment_analyzer.py`, update `AlphaCache` schema if needed
- **New exchange support**: Create `<exchange>_fetcher.py`, standardize DataFrame output format
- **Backtesting**: Requires mock `binance_fetcher` with historical data replay, freeze alpha cache
- **Paper trading mode**: Already virtual (no real orders) - simulation is default behavior
- **Live trading**: Would require implementing `binance_client.order_limit()` calls in trade_manager (NOT CURRENTLY IMPLEMENTED)
