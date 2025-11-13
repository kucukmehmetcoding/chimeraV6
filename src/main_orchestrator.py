# src/main_orchestrator.py
"""
ChimeraBot v10.9 - Hybrid System: Scheduled Scan + WebSocket Monitoring
========================================================================

Multi-Timeframe EMA Strategy (15m + 30m) with Real-time Crossover Detection

Workflow:
1. Scheduled Full Market Scan (every 15 minutes)
   - Scans all USDT futures for 15m EMA crossover
   - Validates with 30m trend confirmation
   - Opens positions with confidence >= 0.5

2. Proximity Detection
   - Identifies coins within 1% of crossover
   - Updates proximity watchlist

3. WebSocket Monitoring (Hybrid Component)
   - Subscribes to proximity coins
   - Detects instant crossover
   - Opens position immediately with 30m validation

4. Trade Manager
   - Monitors open positions
   - Executes TP/SL
"""

import logging
import time
import sys
import os
import threading
import signal
import pandas as pd  # 🆕 v10.9: For WebSocket callback
from datetime import datetime
from binance.exceptions import BinanceAPIException, BinanceRequestException

# --- Proje Kök Dizinini Ayarla ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.append(src_path)

# --- Loglamayı Ayarla ---
try:
    from src import config
    log_level_enum = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    log_file_path = getattr(config, 'LOG_FILE', os.path.join(project_root, 'logs', 'chimerabot.log'))
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    logging.basicConfig(
        level=log_level_enum,
        format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path, mode='a', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info(f"--- ChimeraBot v{config.BOT_VERSION} Başlatılıyor ---")
    
except ImportError:
    print("KRİTİK HATA: src/config.py bulunamadı!")
    sys.exit(1)
except Exception as e:
    print(f"KRİTİK HATA: Loglama ayarlanırken hata: {e}")
    sys.exit(1)

# --- Modülleri İçe Aktar ---
try:
    from src.data_fetcher import binance_fetcher
    from src.trade_manager import manager as trade_manager
    from src.risk_manager import calculator as risk_calculator
    from src.alpha_engine import analyzer as alpha_analyzer
    from src.alpha_engine import sentiment_analyzer
    from src.notifications import telegram as telegram_notifier
    from src.database.models import db_session, init_db, OpenPosition, TradeHistory, AlphaCache
    from src.utils.emergency_stop import check_emergency_stop, is_emergency_stop_active
    
    # 🆕 v11.0: HTF-LTF Strategy
    from src.technical_analyzer.htf_ltf_strategy import analyze_htf_ltf_signal
    from src.technical_analyzer.indicators import add_htf_indicators, add_ltf_indicators
    
    # 🆕 v11.3: Confluence Scoring System
    from src.technical_analyzer.confluence_scorer import get_confluence_scorer
    
    # 🆕 v10.8: Multi-Timeframe Analyzer (DEPRECATED - using HTF-LTF now)
    # from src.technical_analyzer.multi_timeframe_analyzer import (
    #     check_multi_timeframe_entry,
    #     detect_proximity_coins  # 🆕 v10.9: Hybrid system
    # )
    
    # Trade manager thread fonksiyonunu import et
    from src.trade_manager.manager import continuously_check_positions, place_real_order
    
except ImportError as e:
    logger.critical(f"❌ Gerekli modül import edilemedi: {e}", exc_info=True)
    sys.exit(1)

# --- Global Değişkenler ---
open_positions_lock = threading.Lock()
stop_event = threading.Event()
trade_manager_thread = None
scanner_thread = None  # 🆕 v10.8: Multi-timeframe scanner thread
websocket_thread = None  # 🆕 v10.9: Hybrid WebSocket thread

# 🆕 v10.9: Hybrid System - Proximity Watchlist
proximity_watchlist = {}  # {symbol: {distance_percent, direction_bias, ema5, ema20, close}}
proximity_watchlist_lock = threading.Lock()

# Statistics
hybrid_stats = {
    'total_crossovers': 0,
    'total_signals': 0,
    'market_executions': 0,
    'partial_executions': 0,
    'limit_executions': 0,
    'avg_score': 0.0,
    'rejected_signals': 0,
}


# ═══════════════════════════════════════════════════════════════════════
# POSITION RISK MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

def can_open_position(symbol: str) -> bool:
    """Pozisyon açılabilir mi kontrol et"""
    with open_positions_lock:
        db = db_session()
        try:
            total_open = db.query(OpenPosition).count()
            if total_open >= config.MAX_OPEN_POSITIONS:
                logger.warning(f"Max pozisyon limiti: {total_open}/{config.MAX_OPEN_POSITIONS}")
                return False
            
            symbol_count = db.query(OpenPosition).filter(OpenPosition.symbol == symbol).count()
            max_per_symbol = getattr(config, 'MAX_POSITIONS_PER_SYMBOL', 1)
            if symbol_count >= max_per_symbol:
                logger.warning(f"{symbol} için max pozisyon: {symbol_count}/{max_per_symbol}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Pozisyon kontrolü hatası: {e}")
            return False
        finally:
            db_session.remove()


def get_sentiment_scores(symbol: str) -> dict:
    """Sentiment skorlarını al"""
    try:
        fng = sentiment_analyzer.fetch_fear_and_greed_index()
        
        news_score = 0.0
        try:
            news_data = sentiment_analyzer.get_recent_news_sentiment(symbol)
            if news_data:
                news_score = news_data.get('avg_sentiment', 0.0)
        except:
            pass
        
        reddit_score = 0.0
        try:
            reddit_data = sentiment_analyzer.get_reddit_sentiment(symbol)
            if reddit_data:
                reddit_score = reddit_data.get('avg_sentiment', 0.0)
        except:
            pass
        
        return {
            'fear_greed_index': fng,
            'news_sentiment': news_score,
            'reddit_sentiment': reddit_score
        }
    except Exception as e:
        logger.warning(f"Sentiment skorları alınamadı: {e}")
        return {'fear_greed_index': 50, 'news_sentiment': 0.0, 'reddit_sentiment': 0.0}


def adjust_score_with_sentiment(score: float, direction: str, sentiment: dict) -> float:
    """Score'u sentiment ile ağırlıklandır"""
    try:
        fng = sentiment.get('fear_greed_index', 50)
        
        if direction == 'bullish':
            if fng < 25:
                score += 5
                logger.info(f"   Sentiment boost: +5 (Extreme Fear: {fng})")
            elif fng > 75:
                score -= 5
                logger.info(f"   Sentiment penalty: -5 (Extreme Greed: {fng})")
        else:
            if fng > 75:
                score += 5
                logger.info(f"   Sentiment boost: +5 (Extreme Greed: {fng})")
            elif fng < 25:
                score -= 5
                logger.info(f"   Sentiment penalty: -5 (Extreme Fear: {fng})")
        
        return max(0, min(100, score))
    except:
        return score


def calculate_atr_based_sl_tp(symbol: str, direction: str, entry_price: float, score: float) -> tuple:
    """
    v10.10 ATR BAZLI DYNAMIK TP/SL SİSTEMİ
    
    Volatilite bazlı TP/SL hesaplama:
    - ATR (Average True Range) kullanarak dinamik seviyeler
    - TP: Entry ± (ATR × 2.0) - Volatiliteye göre hedef
    - SL: Entry ± (ATR × 1.0) - Risk-Reward: 2:1
    
    Config'den değerler:
    - ATR_PERIOD: 14
    - ATR_TP_MULTIPLIER: 2.0
    - ATR_SL_MULTIPLIER: 1.0
    - MAX_SL_USD: 2.0 (ATR çok büyükse limit)
    - MIN_TP_USD: 2.0 (ATR çok küçükse limit)
    """
    try:
        from src.data_fetcher.binance_fetcher import get_binance_klines
        from src.technical_analyzer.indicators import calculate_atr
        
        # Config değerleri
        MARGIN_USD = config.FIXED_MARGIN_USD
        LEVERAGE = config.FUTURES_LEVERAGE
        ATR_PERIOD = config.ATR_PERIOD
        TP_MULTIPLIER = config.ATR_TP_MULTIPLIER
        SL_MULTIPLIER = config.ATR_SL_MULTIPLIER
        MAX_SL_USD = config.MAX_SL_USD
        MIN_TP_USD = config.MIN_TP_USD
        MIN_SL_USD = getattr(config, 'MIN_SL_USD', 1.5)  # Yeni: Minimum SL limiti
        
        # 1. ATR hesapla (15m timeframe)
        df = get_binance_klines(symbol, '15m', limit=50)
        if df is None or df.empty or len(df) < ATR_PERIOD:
            logger.warning(f"⚠️ {symbol} ATR hesaplanamadı, sabit TP/SL'ye geçiliyor")
            return calculate_fixed_sl_tp(symbol, direction, entry_price, score)
        
        atr = calculate_atr(df, period=ATR_PERIOD)
        
        if atr <= 0:
            logger.warning(f"⚠️ {symbol} ATR=0, sabit TP/SL'ye geçiliyor")
            return calculate_fixed_sl_tp(symbol, direction, entry_price, score)
        
        # 2. Pozisyon büyüklüğü
        position_size = (MARGIN_USD * LEVERAGE) / entry_price
        
        # 3. ATR bazlı TP/SL fiyatları
        if direction.upper() == 'LONG':
            tp_price = entry_price + (atr * TP_MULTIPLIER)
            sl_price = entry_price - (atr * SL_MULTIPLIER)
        else:  # SHORT
            tp_price = entry_price - (atr * TP_MULTIPLIER)
            sl_price = entry_price + (atr * SL_MULTIPLIER)
        
        # 4. USD kar/zarar hesapla
        tp_usd = abs(tp_price - entry_price) * position_size
        sl_usd = abs(sl_price - entry_price) * position_size
        rr_ratio = tp_usd / sl_usd if sl_usd > 0 else 0
        
        # 5. Limit kontrolleri
        adjusted = False
        
        # SL çok küçükse (noise'a yakalanır) limitele
        if sl_usd < MIN_SL_USD:
            logger.warning(f"   ⚠️ SL çok küçük (${sl_usd:.2f}), ${MIN_SL_USD}'ye ayarlanıyor")
            sl_usd = MIN_SL_USD
            if direction.upper() == 'LONG':
                sl_price = entry_price - (sl_usd / position_size)
            else:
                sl_price = entry_price + (sl_usd / position_size)
            adjusted = True
        
        # SL çok büyükse limitele
        if sl_usd > MAX_SL_USD:
            logger.warning(f"   ⚠️ SL çok büyük (${sl_usd:.2f}), ${MAX_SL_USD}'ye ayarlanıyor")
            sl_usd = MAX_SL_USD
            if direction.upper() == 'LONG':
                sl_price = entry_price - (sl_usd / position_size)
            else:
                sl_price = entry_price + (sl_usd / position_size)
            adjusted = True
        
        # TP çok küçükse limitele
        if tp_usd < MIN_TP_USD:
            logger.warning(f"   ⚠️ TP çok küçük (${tp_usd:.2f}), ${MIN_TP_USD}'ye ayarlanıyor")
            tp_usd = MIN_TP_USD
            if direction.upper() == 'LONG':
                tp_price = entry_price + (tp_usd / position_size)
            else:
                tp_price = entry_price - (tp_usd / position_size)
            adjusted = True
        
        # RR oranını yeniden hesapla
        if adjusted:
            tp_usd = abs(tp_price - entry_price) * position_size
            sl_usd = abs(sl_price - entry_price) * position_size
            rr_ratio = tp_usd / sl_usd if sl_usd > 0 else 0
        
        logger.info(f"📊 {symbol} - ATR Bazlı TP/SL:")
        logger.info(f"   💰 Margin: ${MARGIN_USD} | Leverage: {LEVERAGE}x")
        logger.info(f"   📈 Entry: ${entry_price:,.6f}")
        logger.info(f"   📉 ATR({ATR_PERIOD}): ${atr:.6f}")
        logger.info(f"   🎯 TP: ${tp_price:,.6f} (ATR×{TP_MULTIPLIER}) → ${tp_usd:.2f} kar")
        logger.info(f"   🛑 SL: ${sl_price:,.6f} (ATR×{SL_MULTIPLIER}) → ${sl_usd:.2f} zarar")
        logger.info(f"   ⚖️ Risk-Reward: {rr_ratio:.2f}:1")
        
        return sl_price, tp_price
        
    except Exception as e:
        logger.error(f"❌ ATR TP/SL hesaplama hatası: {e}", exc_info=True)
        logger.warning(f"   Sabit TP/SL'ye geri dönülüyor")
        return calculate_fixed_sl_tp(symbol, direction, entry_price, score)


def calculate_confluence_based_sl_tp(symbol: str, direction: str, entry_price: float, confluence_score: float) -> tuple:
    """
    🎯 v11.4 CONFLUENCE-BASED TP/SL SİSTEMİ
    
    Sinyal kalitesine göre dinamik TP/SL:
    - A-grade (8.0-10.0): Geniş targets → SL: $2.5, TP: $6.0 (R:R = 2.4)
    - B-grade (6.5-7.9): Dengeli targets → SL: $2.0, TP: $4.0 (R:R = 2.0)
    - C-grade (5.0-6.4): Muhafazakar targets → SL: $1.5, TP: $3.0 (R:R = 2.0)
    
    Avantajlar:
    - Kaliteli sinyaller daha fazla kar potansiyeli
    - Zayıf sinyaller hızlı çıkış
    - ATR karmaşasından kurtulma
    - USD bazlı net risk yönetimi
    """
    try:
        MARGIN_USD = config.FIXED_MARGIN_USD
        LEVERAGE = config.FUTURES_LEVERAGE
        
        # Confluence score'a göre grade belirle
        if confluence_score >= 8.0:
            grade = 'A'
            sl_usd = config.CONFLUENCE_A_SL_USD  # $2.5
            tp_usd = config.CONFLUENCE_A_TP_USD  # $6.0
        elif confluence_score >= 6.5:
            grade = 'B'
            sl_usd = config.CONFLUENCE_B_SL_USD  # $2.0
            tp_usd = config.CONFLUENCE_B_TP_USD  # $4.0
        else:  # 5.0-6.4
            grade = 'C'
            sl_usd = config.CONFLUENCE_C_SL_USD  # $1.5
            tp_usd = config.CONFLUENCE_C_TP_USD  # $3.0
        
        # Pozisyon büyüklüğü (coin adedi)
        position_size = (MARGIN_USD * LEVERAGE) / entry_price
        
        # USD'den fiyata çevirme
        if direction.upper() == 'LONG':
            tp_price = entry_price + (tp_usd / position_size)
            sl_price = entry_price - (sl_usd / position_size)
        else:  # SHORT
            tp_price = entry_price - (tp_usd / position_size)
            sl_price = entry_price + (sl_usd / position_size)
        
        # R:R oranı hesapla
        rr_ratio = tp_usd / sl_usd if sl_usd > 0 else 0
        
        logger.info(f"🎯 {symbol} - Confluence-Based TP/SL (Grade {grade}):")
        logger.info(f"   ⭐ Confluence Score: {confluence_score:.2f}/10.0")
        logger.info(f"   💰 Margin: ${MARGIN_USD} | Leverage: {LEVERAGE}x")
        logger.info(f"   📈 Entry: ${entry_price:,.6f}")
        logger.info(f"   🎯 TP: ${tp_price:,.6f} → ${tp_usd:.2f} kar")
        logger.info(f"   🛑 SL: ${sl_price:,.6f} → ${sl_usd:.2f} zarar")
        logger.info(f"   ⚖️ Risk-Reward: {rr_ratio:.2f}:1")
        
        return sl_price, tp_price
        
    except Exception as e:
        logger.error(f"❌ Confluence TP/SL hesaplama hatası: {e}", exc_info=True)
        logger.warning(f"   Sabit TP/SL'ye geri dönülüyor")
        return calculate_fixed_sl_tp(symbol, direction, entry_price, confluence_score)


def calculate_fixed_sl_tp(symbol: str, direction: str, entry_price: float, score: float) -> tuple:
    """
    v10.7.1 SABİT MARGIN TP/SL SİSTEMİ
    
    Margin bazlı TP/SL hesaplama:
    - Margin: 10 USD (sabit)
    - TP: Margin + %40 kar = 14 USD (+4 USD kar)
    - SL: Margin - %10 zarar = 9 USD (-1 USD zarar)
    
    Config'den sabit değerler:
    - FIXED_MARGIN_USD: 10 USD
    - FIXED_TARGET_TP_VALUE: 14 USD (10 + 4)
    - FIXED_TARGET_SL_VALUE: 9 USD (10 - 1)
    - FIXED_TP_PROFIT: +4 USD (%40 kar)
    - FIXED_SL_LOSS: +1 USD (%10 zarar)
    """
    try:
        # Config'den sabit değerleri al
        MARGIN_USD = config.FIXED_MARGIN_USD
        LEVERAGE = config.FUTURES_LEVERAGE
        TARGET_TP_VALUE = config.FIXED_TARGET_TP_VALUE
        TARGET_SL_VALUE = config.FIXED_TARGET_SL_VALUE
        TP_PROFIT = config.FIXED_TP_PROFIT
        SL_LOSS = config.FIXED_SL_LOSS
        
        # Pozisyon büyüklüğü (coin adedi)
        position_size = (MARGIN_USD * LEVERAGE) / entry_price
        
        # ✅ DOĞRU FORMÜL: Kar/Zarar USD'den fiyata çevirme
        # TP kar = (tp_price - entry_price) * position_size = TP_PROFIT
        # tp_price = entry_price + (TP_PROFIT / position_size)
        # 
        # SL zarar = (entry_price - sl_price) * position_size = SL_LOSS
        # sl_price = entry_price - (SL_LOSS / position_size)
        
        if direction.upper() == 'LONG':
            # LONG: TP üstte (+$4 kar), SL altta (-$1 zarar)
            tp_price = entry_price + (TP_PROFIT / position_size)
            sl_price = entry_price - (SL_LOSS / position_size)
        else:
            # SHORT: TP altta (+$4 kar), SL üstte (-$1 zarar)
            tp_price = entry_price - (TP_PROFIT / position_size)
            sl_price = entry_price + (SL_LOSS / position_size)
        
        logger.info(f"📊 {symbol} - Sabit Margin TP/SL:")
        logger.info(f"   💰 Margin: ${MARGIN_USD} | Leverage: {LEVERAGE}x")
        logger.info(f"   📈 Entry: ${entry_price:,.4f}")
        logger.info(f"   🎯 TP: ${tp_price:,.4f} → ${TP_PROFIT} kar")
        logger.info(f"   🛑 SL: ${sl_price:,.4f} → ${SL_LOSS} zarar")
        
        return sl_price, tp_price
        
    except Exception as e:
        logger.error(f"SL/TP hesaplama hatası: {e}")
        return None, None


def calculate_hybrid_sl_tp(symbol: str, direction: str, entry_price: float, score: float) -> tuple:
    """
    🎯 v11.4 HİBRİT TP/SL SİSTEMİ (Confluence-Based Primary)
    
    Öncelik Sırası:
    1. USE_CONFLUENCE_BASED_TP_SL = True → Confluence-based sistem (PRIMARY)
    2. USE_ATR_BASED_TP_SL = True → ATR bazlı sistem (FALLBACK)
    3. Else → Sabit TP/SL (LEGACY)
    
    A/B Test modu kapalı - %100 Confluence kullanımı
    """
    try:
        # Öncelik 1: Confluence-based sistem
        if getattr(config, 'USE_CONFLUENCE_BASED_TP_SL', True):
            logger.info(f"🎯 {symbol} → Confluence-based TP/SL kullanılıyor")
            return calculate_confluence_based_sl_tp(symbol, direction, entry_price, score)
        
        # Öncelik 2: ATR-based sistem (fallback)
        if config.USE_ATR_BASED_TP_SL:
            logger.info(f"📊 {symbol} → ATR-based TP/SL kullanılıyor (fallback)")
            return calculate_atr_based_sl_tp(symbol, direction, entry_price, score)
        
        # Öncelik 3: Sabit sistem (legacy)
        logger.info(f"🔧 {symbol} → Sabit TP/SL kullanılıyor (legacy)")
        return calculate_fixed_sl_tp(symbol, direction, entry_price, score)
        
    except Exception as e:
        logger.error(f"Hybrid TP/SL hatası: {e}", exc_info=True)
        # Final fallback: Sabit TP/SL
        return calculate_fixed_sl_tp(symbol, direction, entry_price, score)


# ═══════════════════════════════════════════════════════════════════════
# 🆕 v10.7 ADAPTIVE SCANNER THREAD
# ═══════════════════════════════════════════════════════════════════════

def run_adaptive_scanner(scanner, stop_event):
    """
    Adaptive scanner thread fonksiyonu.
    Her ADAPTIVE_SCAN_INTERVAL'de bir full market scan yapar.
    """
    global websocket_manager, ema_manager
    
    scan_interval = getattr(config, 'ADAPTIVE_SCAN_INTERVAL', 300)
    max_watchlist = getattr(config, 'ADAPTIVE_MAX_WATCHLIST_SIZE', 20)
    min_watchlist = getattr(config, 'ADAPTIVE_MIN_WATCHLIST_SIZE', 5)
    instant_trade = getattr(config, 'ADAPTIVE_INSTANT_TRADE', True)
    
    logger.info(f"🔍 Adaptive Scanner thread başlatıldı")
    logger.info(f"   Scan interval: {scan_interval}s ({scan_interval/60:.1f} min)")
    logger.info(f"   Watchlist size: {min_watchlist}-{max_watchlist}")
    logger.info(f"   Instant trade: {instant_trade}")
    
    current_watchlist = set()  # Şu anda WebSocket'te olan coinler
    websocket_started = False  # WebSocket başlatıldı mı?
    
    while not stop_event.is_set():
        try:
            logger.info("\n" + "=" * 70)
            logger.info("🔍 ADAPTIVE SCAN BAŞLIYOR")
            logger.info("=" * 70)
            
            # Full market scan
            scan_results = scanner.full_market_scan()
            
            # 🆕 İlk scan'de WebSocket'i başlat
            if not websocket_started:
                logger.info("\n📡 WebSocket Manager başlatılıyor...")
                try:
                    websocket_manager.start()
                    websocket_started = True
                    logger.info("   ✅ WebSocket bağlantısı kuruldu")
                except Exception as ws_error:
                    logger.error(f"   ❌ WebSocket başlatılamadı: {ws_error}")
                    logger.warning("   ⚠️ Subscription'lar atlanacak, bir sonraki scan'de tekrar denenecek")
            
            # 1. Instant signals varsa işlem aç
            if instant_trade and scan_results['instant_signals']:
                logger.warning(f"\n🚨 {len(scan_results['instant_signals'])} INSTANT CROSSOVER BULUNDU!")
                logger.warning("⚠️ DEPRECATED: Adaptive scanner artık kullanılmıyor (v11.0 HTF-LTF kullanıyor)")
                # DEPRECATED: v11.0'da instant crossover için HTF-LTF sistemi kullanılıyor
                #
                # for signal in scan_results['instant_signals']:
                #     try:
                #         logger.info(f"\n📍 Processing instant signal: {signal['symbol']} → {signal['direction']}")
                #         ... (handle_ema_crossover kodu kaldırıldı)
                #     except Exception as e:
                #         logger.error(f"Instant signal işleme hatası [{signal['symbol']}]: {e}")
                #         continue
            
            # 2. Watchlist güncelle
            close_coins = scan_results['close_to_crossover']
            
            # Top N coini seç (mesafeye göre sıralı)
            new_watchlist = set()
            
            # Min watchlist için en yakın coinleri ekle
            for coin in close_coins[:min_watchlist]:
                new_watchlist.add(coin['symbol'])
            
            # Kalan slotlar için (max_watchlist'e kadar)
            remaining_slots = max_watchlist - len(new_watchlist)
            for coin in close_coins[min_watchlist:min_watchlist + remaining_slots]:
                new_watchlist.add(coin['symbol'])
            
            # 3. WebSocket'ten çıkarılacaklar (artık yakın değiller)
            to_remove = current_watchlist - new_watchlist
            for symbol in to_remove:
                try:
                    logger.info(f"   ➖ Watchlist'ten çıkarılıyor: {symbol}")
                    websocket_manager.unsubscribe_symbol(symbol)
                    ema_manager.remove_symbol(symbol)
                except Exception as e:
                    logger.debug(f"Unsubscribe hatası [{symbol}]: {e}")
            
            # 4. WebSocket'e eklenecekler (yeni yakın coinler)
            to_add = new_watchlist - current_watchlist
            
            # WebSocket aktif ise subscribe et
            if websocket_started and to_add:
                for symbol in to_add:
                    try:
                        logger.info(f"   ➕ Watchlist'e ekleniyor: {symbol}")
                        
                        # EMA calculator ekle
                        ema_manager.add_symbol(
                            symbol=symbol,
                            ema_short=config.HYBRID_EMA_SHORT,
                            ema_long=config.HYBRID_EMA_LONG,
                            warmup=config.HYBRID_WARMUP_CANDLES
                        )
                        
                        # WebSocket subscribe
                        websocket_manager.subscribe_symbol(symbol)
                        
                    except Exception as e:
                        logger.error(f"Subscribe hatası [{symbol}]: {e}")
                        continue
            elif not websocket_started and to_add:
                logger.warning(f"   ⚠️ WebSocket henüz başlatılmadı, {len(to_add)} coin beklemede")
            
            # Watchlist'i güncelle
            current_watchlist = new_watchlist
            
            logger.info("\n📊 ADAPTIVE SCAN TAMAMLANDI")
            logger.info(f"   Watchlist size: {len(current_watchlist)}")
            if current_watchlist:
                logger.info(f"   Coins: {', '.join(sorted(current_watchlist))}")
            logger.info("=" * 70 + "\n")
            
            # Bir sonraki scan'e kadar bekle
            logger.info(f"⏳ Next scan in {scan_interval}s...")
            stop_event.wait(scan_interval)
            
        except Exception as e:
            logger.error(f"❌ Adaptive scanner hatası: {e}", exc_info=True)
            # Hata durumunda 60 saniye bekle
            stop_event.wait(60)
    
    logger.info("🛑 Adaptive Scanner thread sonlandırıldı")


# ═══════════════════════════════════════════════════════════════════════
# 🆕 v10.9: HYBRID WEBSOCKET CROSSOVER CALLBACK
# ═══════════════════════════════════════════════════════════════════════

def on_websocket_crossover(kline_data: dict):
    """
    WebSocket crossover callback - instant position opening
    
    Called by WebSocket manager when kline data arrives.
    Checks for crossover and opens position if detected.
    
    Args:
        kline_data: Dict with keys:
            - symbol: str
            - open: float
            - high: float
            - low: float
            - close: float
            - volume: float
            - timestamp: int
            - is_closed: bool
    """
    try:
        symbol = kline_data.get('symbol')
        close_price = kline_data.get('close')
        is_closed = kline_data.get('is_closed', False)
        
        # Only process closed candles for crossover detection
        if not is_closed:
            return
        
        logger.debug(f"📊 WebSocket kline received: {symbol} @ ${close_price:.2f}")
        
        # Get EMA cache to check for crossover
        ema_cache = websocket_manager.get_ema_cache(symbol)
        
        if not ema_cache:
            logger.debug(f"⚠️ No EMA cache for {symbol}, skipping crossover check")
            return
        
        prev_ema5 = ema_cache.get('prev_ema5')
        prev_ema20 = ema_cache.get('prev_ema20')
        current_ema5 = ema_cache.get('current_ema5')
        current_ema20 = ema_cache.get('current_ema20')
        
        if None in (prev_ema5, prev_ema20, current_ema5, current_ema20):
            logger.debug(f"⚠️ Incomplete EMA cache for {symbol}")
            return
        
        # Detect crossover
        direction = None
        
        # Bullish crossover: EMA5 crosses above EMA20
        if prev_ema5 < prev_ema20 and current_ema5 > current_ema20:
            direction = 'LONG'
        # Bearish crossover: EMA5 crosses below EMA20
        elif prev_ema5 > prev_ema20 and current_ema5 < current_ema20:
            direction = 'SHORT'
        
        if not direction:
            return  # No crossover
        
        logger.info("\n" + "="*80)
        logger.info(f"🚨 INSTANT CROSSOVER DETECTED - WebSocket")
        logger.info("="*80)
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Direction: {direction}")
        logger.info(f"Price: ${close_price:.2f}")
        logger.info(f"EMA5: {prev_ema5:.2f} → {current_ema5:.2f}")
        logger.info(f"EMA20: {prev_ema20:.2f} → {current_ema20:.2f}")
        logger.info("="*80)
        
        # Check if instant trade is enabled
        if not config.INSTANT_CROSSOVER_TRADE:
            logger.warning("⚠️ Instant crossover trade disabled in config")
            return
        
        # Validate with 30m trend
        logger.info(f"🔍 Validating with 30m timeframe...")
        
        from src.data_fetcher.binance_fetcher import get_binance_klines
        df_30m = get_binance_klines(symbol, config.SECONDARY_TIMEFRAME, limit=50)
        
        if df_30m is None or df_30m.empty:
            logger.warning(f"⚠️ Cannot validate 30m trend for {symbol}")
            return
        
        # Calculate 30m EMAs
        df_30m['ema5'] = df_30m['close'].ewm(span=config.HYBRID_EMA_SHORT, adjust=False).mean()
        df_30m['ema20'] = df_30m['close'].ewm(span=config.HYBRID_EMA_LONG, adjust=False).mean()
        
        last_30m = df_30m.iloc[-1]
        
        if pd.isna(last_30m['ema5']) or pd.isna(last_30m['ema20']):
            logger.warning(f"⚠️ Missing 30m EMA data for {symbol}")
            return
        
        # Check 30m alignment
        ema5_30m = float(last_30m['ema5'])
        ema20_30m = float(last_30m['ema20'])
        
        trend_aligned = False
        
        if direction == 'LONG' and ema5_30m > ema20_30m:
            trend_aligned = True
            logger.info(f"✅ 30m trend ALIGNED for LONG (EMA5: {ema5_30m:.2f} > EMA20: {ema20_30m:.2f})")
        elif direction == 'SHORT' and ema5_30m < ema20_30m:
            trend_aligned = True
            logger.info(f"✅ 30m trend ALIGNED for SHORT (EMA5: {ema5_30m:.2f} < EMA20: {ema20_30m:.2f})")
        else:
            logger.warning(
                f"❌ 30m trend NOT ALIGNED for {direction} "
                f"(EMA5: {ema5_30m:.2f}, EMA20: {ema20_30m:.2f})"
            )
            return
        
        # Create instant signal (simplified confidence = 0.6 for WebSocket signals)
        signal = {
            'signal': direction,
            'entry_price': close_price,
            'confidence': 0.6,  # WebSocket signals get base confidence
            'source': 'websocket',
            'timeframes': {
                '15m': {'ema5': current_ema5, 'ema20': current_ema20},
                '30m': {'ema5': ema5_30m, 'ema20': ema20_30m}
            }
        }
        
        logger.info(f"📊 Instant signal confidence: {signal['confidence']:.2f}")
        
        # Execute position
        try:
            position_opened = execute_multi_timeframe_position(symbol, signal)
            
            if position_opened:
                logger.info(f"✅ INSTANT POSITION OPENED: {symbol} {direction}")
                
                # Send Telegram alert
                try:
                    alert_msg = (
                        f"🚨 *INSTANT CROSSOVER ENTRY*\n\n"
                        f"*Symbol:* `{symbol}`\n"
                        f"*Direction:* {direction}\n"
                        f"*Entry:* ${close_price:.2f}\n"
                        f"*Source:* WebSocket (Real-time)\n"
                        f"*Confidence:* {signal['confidence']:.2f}\n\n"
                        f"_Position opened immediately on crossover detection_"
                    )
                    telegram_notifier.send_message(alert_msg)
                except Exception as tg_error:
                    logger.error(f"❌ Telegram alert error: {tg_error}")
            else:
                logger.warning(f"⚠️ Instant position could not be opened: {symbol}")
        
        except Exception as exec_error:
            logger.error(f"❌ Instant position execution error: {exec_error}", exc_info=True)
    
    except Exception as e:
        logger.error(f"❌ WebSocket crossover callback error: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════════════
# 🆕 v10.9: HYBRID WEBSOCKET MONITORING THREAD
# ═══════════════════════════════════════════════════════════════════════

def run_hybrid_websocket_monitor(stop_event):
    """
    v10.9: Hybrid WebSocket Monitoring Thread
    
    Proximity coinleri gerçek zamanlı izler:
    1. Scanner thread proximity coinleri tespit eder
    2. Bu thread onları WebSocket ile takip eder
    3. EMA crossover anında pozisyon açar
    4. Uzaklaşan coinleri unsubscribe eder
    
    Global değişken kullanır:
    - proximity_watchlist: Scanner'dan gelen yakın coinler
    """
    global proximity_watchlist, websocket_manager
    
    logger.info("🚀 Hybrid WebSocket Monitor thread başlatıldı")
    
    # WebSocket manager başlat (crossover callback ile)
    try:
        from src.data_fetcher.websocket_manager import WebSocketKlineManager
        
        # Create manager with crossover callback
        websocket_manager = WebSocketKlineManager(config, stop_event)
        
        # Set crossover callback
        websocket_manager.on_kline_callback = on_websocket_crossover
        
        # Start WebSocket manager
        websocket_manager.start()
        logger.info("✅ WebSocket manager started with crossover callback")
    except Exception as e:
        logger.error(f"❌ WebSocket manager başlatılamadı: {e}", exc_info=True)
        return
    
    subscribed_symbols = set()
    check_interval = config.WEBSOCKET_CHECK_INTERVAL  # Default: 5 saniye
    
    while not stop_event.is_set():
        try:
            # Proximity watchlist'ten yeni coinleri al
            with proximity_watchlist_lock:
                current_watchlist = proximity_watchlist.copy()
            
            new_symbols = set(current_watchlist.keys())
            
            # Eklenmesi gerekenler
            to_subscribe = new_symbols - subscribed_symbols
            
            # Çıkarılması gerekenler (artık yakın değil)
            to_unsubscribe = subscribed_symbols - new_symbols
            
            # Subscribe new coins
            for symbol in to_subscribe:
                if len(subscribed_symbols) >= config.MAX_WEBSOCKET_SUBSCRIPTIONS:
                    logger.warning(
                        f"⚠️ WebSocket limit reached ({config.MAX_WEBSOCKET_SUBSCRIPTIONS}), "
                        f"cannot subscribe {symbol}"
                    )
                    break
                
                try:
                    # Update EMA cache for crossover detection
                    coin_data = current_watchlist[symbol]
                    
                    # Get previous EMA values (from 1 candle ago)
                    df = binance_fetcher.get_binance_klines(
                        symbol, 
                        config.PRIMARY_TIMEFRAME, 
                        limit=3
                    )
                    
                    if df is not None and len(df) >= 2:
                        df['ema5'] = df['close'].ewm(span=config.HYBRID_EMA_SHORT, adjust=False).mean()
                        df['ema20'] = df['close'].ewm(span=config.HYBRID_EMA_LONG, adjust=False).mean()
                        
                        prev_ema5 = float(df.iloc[-2]['ema5'])
                        prev_ema20 = float(df.iloc[-2]['ema20'])
                        current_ema5 = coin_data['ema5']
                        current_ema20 = coin_data['ema20']
                        
                        websocket_manager.update_ema_cache(
                            symbol,
                            prev_ema5,
                            prev_ema20,
                            current_ema5,
                            current_ema20
                        )
                        
                        # Subscribe to WebSocket
                        if websocket_manager.subscribe(symbol):
                            subscribed_symbols.add(symbol)
                            logger.info(
                                f"📡 WebSocket subscribed: {symbol} "
                                f"(distance: {coin_data['distance_percent']:.4f}%, "
                                f"bias: {coin_data['direction_bias']})"
                            )
                
                except Exception as sub_error:
                    logger.error(f"❌ {symbol} WebSocket subscribe error: {sub_error}")
            
            # Unsubscribe removed coins
            for symbol in to_unsubscribe:
                try:
                    if websocket_manager.unsubscribe(symbol):
                        subscribed_symbols.remove(symbol)
                        logger.info(f"📴 WebSocket unsubscribed: {symbol} (moved away from crossover)")
                except Exception as unsub_error:
                    logger.error(f"❌ {symbol} WebSocket unsubscribe error: {unsub_error}")
            
            # Status log
            if subscribed_symbols:
                logger.debug(
                    f"📊 WebSocket monitoring: {len(subscribed_symbols)} coins "
                    f"(Watchlist: {len(current_watchlist)})"
                )
            
            # Wait before next check
            stop_event.wait(check_interval)
            
        except Exception as e:
            logger.error(f"❌ Hybrid WebSocket monitor error: {e}", exc_info=True)
            stop_event.wait(check_interval)
    
    # Cleanup on shutdown
    try:
        if websocket_manager:
            websocket_manager.stop()
            logger.info("✅ WebSocket manager stopped")
    except Exception as e:
        logger.error(f"❌ WebSocket cleanup error: {e}")
    
    logger.info("🛑 Hybrid WebSocket Monitor thread sonlandırıldı")


# ═══════════════════════════════════════════════════════════════════════
# 🆕 v10.8: MULTI-TIMEFRAME SCAN CYCLE
# ═══════════════════════════════════════════════════════════════════════

def run_multi_timeframe_scanner(stop_event):
    """
    v11.0: HTF-LTF Scanner (1H Filter + 15M Trigger)
    
    Yeni Strateji Mantığı:
    1. Layer 1 (HTF Filter): 1H grafikte trend yönünü belirle (LONG/SHORT izni)
    2. Layer 2 (LTF Trigger): 15M grafikte izin verilen yönde giriş sinyali ara
    3. Layer 3 (Risk Filters): ATR ve volume kontrolleri
    
    Her 15 dakikada (900 saniye) bir çalışır ve tüm USDT futures'ı tarar.
    
    Avantajları:
    - HTF trend filtresi sayesinde kararsız piyasalarda işlem yok
    - LTF trigger ile zamanında giriş
    - Risk filtreleri ile volatilite ve hacim kontrolü
    - Yüksek kaliteli sinyaller
    """
    scan_interval = getattr(config, 'ADAPTIVE_SCAN_INTERVAL', 900)  # 15 dakika
    
    # Coin pool - tüm USDT futures pairs
    try:
        from src.data_fetcher.binance_fetcher import binance_client
        
        logger.info("🔍 Binance Futures symbol listesi çekiliyor...")
        exchange_info = binance_client.futures_exchange_info()
        
        # Sadece USDT perpetual ve TRADING aktif olanlar
        coin_pool = [
            s['symbol'] 
            for s in exchange_info['symbols']
            if s['symbol'].endswith('USDT') 
            and s['contractType'] == 'PERPETUAL'
            and s['status'] == 'TRADING'
        ]
        
        logger.info(f"🎯 HTF-LTF Scanner başlatıldı (v11.0)")
        logger.info(f"   Scan interval: {scan_interval}s ({scan_interval/60:.1f} min)")
        logger.info(f"   HTF Filter: {config.HTF_TIMEFRAME}")
        logger.info(f"   LTF Trigger: {config.LTF_TIMEFRAME}")
        logger.info(f"   Coin pool: {len(coin_pool)} USDT pairs")
        
    except Exception as e:
        logger.error(f"❌ Coin pool alınamadı: {e}")
        # Fallback: config'den al
        coin_pool = getattr(config, 'HYBRID_SYMBOLS', ['BTCUSDT', 'ETHUSDT'])
        logger.warning(f"   ⚠️ Fallback coin pool: {coin_pool}")
    
    scan_count = 0
    
    while not stop_event.is_set():
        try:
            scan_count += 1
            logger.info("\n" + "="*80)
            logger.info(f"🔍 HTF-LTF SCAN #{scan_count} BAŞLIYOR")
            logger.info("="*80)
            logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            signals_found = 0
            positions_opened = 0
            htf_filtered = 0  # HTF filter tarafından reddedilen
            ltf_no_trigger = 0  # LTF'de sinyal bulunamayan
            risk_rejected = 0  # Risk filter tarafından reddedilen
            
            # Her coin için HTF-LTF analiz
            for idx, symbol in enumerate(coin_pool, 1):
                try:
                    # Emergency stop check
                    if is_emergency_stop_active():
                        logger.warning("🚨 Emergency stop active - Scanner durduruluyor")
                        return
                    
                    if idx % 50 == 0:  # Her 50 coinde progress log
                        logger.info(f"\n📊 Progress: {idx}/{len(coin_pool)} coins scanned...")
                    
                    logger.debug(f"[{idx}/{len(coin_pool)}] 🔍 {symbol}")
                    
                    # ═══════════════════════════════════════════════════════
                    # STEP 1: Fetch HTF (1H) Data
                    # ═══════════════════════════════════════════════════════
                    from src.data_fetcher.binance_fetcher import get_binance_klines
                    
                    df_1h = get_binance_klines(
                        symbol=symbol,
                        interval=config.HTF_TIMEFRAME,
                        limit=config.HTF_CANDLE_LIMIT
                    )
                    
                    if df_1h is None or df_1h.empty:
                        logger.debug(f"   ⚠️ {symbol}: 1H data alınamadı")
                        continue
                    
                    # Add HTF indicators
                    df_1h = add_htf_indicators(df_1h, config.HTF_TIMEFRAME)
                    
                    # ═══════════════════════════════════════════════════════
                    # STEP 2: HTF Filter Check (Layer 1)
                    # ═══════════════════════════════════════════════════════
                    from src.technical_analyzer.htf_ltf_strategy import check_htf_filter_1h
                    
                    allowed_direction = check_htf_filter_1h(df_1h, symbol)
                    
                    if allowed_direction is None:
                        # HTF kararsız - coin atla
                        htf_filtered += 1
                        logger.debug(f"   ⛔ {symbol}: HTF kararsız (atlandı)")
                        continue
                    
                    # HTF izin veriyor - LTF'ye geç
                    logger.info(f"\n[{idx}/{len(coin_pool)}] ✅ {symbol}: HTF → {allowed_direction} izni var")
                    
                    # ═══════════════════════════════════════════════════════
                    # STEP 3: Fetch LTF (15M) Data
                    # ═══════════════════════════════════════════════════════
                    df_15m = get_binance_klines(
                        symbol=symbol,
                        interval=config.LTF_TIMEFRAME,
                        limit=config.LTF_CANDLE_LIMIT
                    )
                    
                    if df_15m is None or df_15m.empty:
                        logger.debug(f"   ⚠️ {symbol}: 15M data alınamadı")
                        continue
                    
                    # Add LTF indicators
                    df_15m = add_ltf_indicators(df_15m, config.LTF_TIMEFRAME)
                    
                    # ═══════════════════════════════════════════════════════
                    # STEP 4: Full HTF-LTF Analysis
                    # ═══════════════════════════════════════════════════════
                    signal = analyze_htf_ltf_signal(
                        df_1h=df_1h,
                        df_15m=df_15m,
                        symbol=symbol,
                        max_atr_percent=config.SCALP_MAX_ATR_PERCENT,
                        volume_confirmation_required=config.VOLUME_CONFIRMATION_REQUIRED
                    )
                    
                    if signal is None:
                        # LTF trigger veya risk filter başarısız
                        logger.debug(f"   ⚠️ {symbol}: LTF trigger veya risk filter başarısız")
                        ltf_no_trigger += 1
                        continue
                    
                    # ═══════════════════════════════════════════════════════
                    # STEP 5: SIGNAL FOUND! 
                    # ═══════════════════════════════════════════════════════
                    signals_found += 1
                    
                    logger.info(f"\n{'🎯'*30}")
                    logger.info(f"✅ VALID SIGNAL: {symbol}")
                    logger.info(f"{'🎯'*30}")
                    logger.info(f"   Direction: {signal['signal']}")
                    logger.info(f"   Entry Price: ${signal['entry_price']:.4f}")
                    logger.info(f"   HTF Direction: {signal['htf_direction']}")
                    logger.info(f"   LTF EMA5: {signal['ltf_trigger']['ema5']:.4f}")
                    logger.info(f"   LTF EMA20: {signal['ltf_trigger']['ema20']:.4f}")
                    logger.info(f"   LTF RSI: {signal['ltf_trigger']['rsi']:.1f}")
                    logger.info(f"   Crossover: {signal['ltf_trigger']['crossover_candle']}")
                    
                    # ═══════════════════════════════════════════════════════
                    # STEP 6: Open Position
                    # ═══════════════════════════════════════════════════════
                    try:
                        # Convert signal to expected format for execute_multi_timeframe_position
                        formatted_signal = {
                            'signal': signal['signal'],
                            'entry_price': signal['entry_price'],
                            'confidence': 0.7,  # HTF-LTF signals have good confidence
                            'source': 'htf_ltf_v11',
                            'htf_direction': signal['htf_direction'],
                            'ltf_trigger': signal['ltf_trigger']
                        }
                        
                        position_opened = execute_multi_timeframe_position(symbol, formatted_signal)
                        
                        if position_opened:
                            positions_opened += 1
                            logger.info(f"✅ POSITION OPENED: {symbol} {signal['signal']}")
                            
                            # Telegram alert
                            try:
                                alert_msg = (
                                    f"🎯 *HTF-LTF SIGNAL (v11.0)*\n\n"
                                    f"*Symbol:* `{symbol}`\n"
                                    f"*Direction:* {signal['signal']}\n"
                                    f"*Entry:* ${signal['entry_price']:.4f}\n\n"
                                    f"*HTF Filter (1H):* {signal['htf_direction']} izni\n"
                                    f"*LTF Trigger (15M):* EMA crossover\n"
                                    f"  - RSI: {signal['ltf_trigger']['rsi']:.1f}\n"
                                    f"  - MACD Hist: {signal['ltf_trigger']['macd_hist']:.4f}\n\n"
                                    f"_Multi-layer filtering: HTF trend + LTF timing + Risk checks_"
                                )
                                telegram_notifier.send_message(alert_msg)
                            except Exception as tg_error:
                                logger.error(f"❌ Telegram alert error: {tg_error}")
                        else:
                            logger.warning(f"⚠️ Position could not be opened: {symbol}")
                    
                    except Exception as exec_error:
                        logger.error(f"❌ Position execution error [{symbol}]: {exec_error}", exc_info=True)
                    
                except Exception as coin_error:
                    logger.error(f"❌ Error analyzing {symbol}: {coin_error}")
                    continue
                
                finally:
                    # Rate limiting: coinler arası 0.2 saniye bekle (5 coin/saniye)
                    time.sleep(0.2)
            
            # Scan özeti
            logger.info("\n" + "="*80)
            logger.info(f"📊 HTF-LTF SCAN #{scan_count} TAMAMLANDI")
            logger.info("="*80)
            logger.info(f"   Scanned coins: {len(coin_pool)}")
            logger.info(f"   HTF filtered: {htf_filtered} (kararsız trend)")
            logger.info(f"   LTF checked: {len(coin_pool) - htf_filtered}")
            logger.info(f"   Signals found: {signals_found}")
            logger.info(f"   Positions opened: {positions_opened}")
            logger.info(f"   Next scan: {scan_interval}s ({scan_interval/60:.1f} min)")
            logger.info("="*80 + "\n")
            
            # Bir sonraki scan'e kadar bekle
            logger.info(f"⏳ Waiting {scan_interval}s until next scan...")
            stop_event.wait(scan_interval)
            
        except Exception as e:
            logger.error(f"❌ HTF-LTF scanner error: {e}", exc_info=True)
            # Hata durumunda 60 saniye bekle
            logger.warning("⚠️ Waiting 60s before retry...")
            stop_event.wait(60)
    
    logger.info("🛑 HTF-LTF Scanner thread sonlandırıldı")


def execute_multi_timeframe_position(symbol: str, signal: dict) -> bool:
    """
    Multi-timeframe sinyali pozisyona çevir
    
    Args:
        symbol: Trading pair
        signal: check_multi_timeframe_entry() output
            {
                'signal': 'LONG' or 'SHORT',
                'entry_price': float,
                'confidence': float,
                'timeframes': {...}
            }
    
    Returns:
        bool: Pozisyon açıldı mı?
    """
    try:
        direction = signal['signal']
        entry_price = signal['entry_price']
        confidence = signal['confidence']
        
        logger.info(f"\n{'='*60}")
        logger.info(f"💼 EXECUTING POSITION: {symbol}")
        logger.info(f"{'='*60}")
        logger.info(f"Direction: {direction}")
        logger.info(f"Entry: ${entry_price:.2f}")
        logger.info(f"Confidence: {confidence:.2f}")
        
        # 🆕 v11.3: CONFLUENCE SCORE CALCULATION
        logger.info(f"📊 Calculating confluence score...")
        confluence_data = None
        try:
            # Get confluence scorer instance
            confluence_scorer = get_confluence_scorer(config)
            
            # Fetch 1H and 15M dataframes with indicators
            from src.data_fetcher.binance_fetcher import get_binance_klines
            from src.technical_analyzer.indicators import calculate_indicators
            
            df_1h = get_binance_klines(symbol, '1h', limit=100)
            df_15m = get_binance_klines(symbol, '15m', limit=100)
            
            if df_1h is not None and not df_1h.empty:
                df_1h = calculate_indicators(df_1h)
            
            if df_15m is not None and not df_15m.empty:
                df_15m = calculate_indicators(df_15m)
            
            # Calculate HTF (1H) score
            htf_score_data = confluence_scorer.calculate_htf_score(
                df_1h=df_1h,
                signal_direction=direction
            )
            
            # Calculate LTF (15M) score
            ltf_score_data = confluence_scorer.calculate_ltf_score(
                df_15m=df_15m,
                signal_direction=direction
            )
            
            # Get quality grade from signal (default to 'B' if not present)
            quality_grade = signal.get('quality_grade', 'B')
            
            # Calculate final confluence score
            confluence_data = confluence_scorer.calculate_confluence_score(
                htf_score_data=htf_score_data,
                ltf_score_data=ltf_score_data,
                quality_grade=quality_grade
            )
            
            logger.info(f"   ✅ Confluence Score: {confluence_data['total_score']}/10")
            logger.info(f"      HTF (1H): {confluence_data['htf_score']}")
            logger.info(f"      LTF (15M): {confluence_data['ltf_score']}")
            logger.info(f"      Sentiment: {confluence_data['sentiment_bonus']}")
            logger.info(f"      Recommendation: {confluence_data['recommendation']}")
            
            # Check threshold
            if not confluence_data['passed_threshold']:
                logger.warning(
                    f"❌ SIGNAL REJECTED: Confluence score {confluence_data['total_score']} "
                    f"< minimum {confluence_data['min_threshold']}"
                )
                return False
            
            logger.info(f"   ✅ Threshold PASSED ({confluence_data['total_score']} >= {confluence_data['min_threshold']})")
            
        except Exception as conf_error:
            logger.error(f"⚠️ Confluence score calculation failed: {conf_error}", exc_info=True)
            logger.warning(f"⚠️ Continuing without confluence filtering...")
            confluence_data = None
        
        # 1. TP/SL hesapla
        sl_price, tp_price = calculate_hybrid_sl_tp(symbol, direction, entry_price, confidence)
        
        if not sl_price or not tp_price:
            logger.error(f"❌ SL/TP hesaplanamadı: {symbol}")
            return False
        
        # 2. Position size hesapla
        position_size = calculate_position_size(symbol, entry_price, sl_price, confidence)
        
        if not position_size or position_size <= 0:
            logger.error(f"❌ Position size hesaplanamadı: {symbol}")
            return False
        
        # 3. Risk check
        if not can_open_position(symbol):
            logger.warning(f"⚠️ Cannot open position (risk limits): {symbol}")
            return False
        
        # 🚨 4. GERÇEK BİNANCE EMRİNİ AÇ (ENABLE_REAL_TRADING=true ise)
        order_result = None
        if config.ENABLE_REAL_TRADING:
            logger.info(f"🔥 GERÇEK TRADING AKTİF - Binance'de emir açılıyor: {symbol}")
            order_result = place_real_order({
                'symbol': symbol,
                'direction': direction,
                'quantity': position_size,
                'entry_price': entry_price,
                'tp_price': tp_price,
                'sl_price': sl_price
            })
            
            if not order_result:
                logger.error(f"❌ Binance emir açılamadı - Pozisyon kaydedilmeyecek: {symbol}")
                return False
            
            logger.info(f"✅ Binance emirleri açıldı: Entry={order_result.get('entry_order_id')}, "
                       f"TP={order_result.get('tp_order_id')}, SL={order_result.get('sl_order_id')}")
        else:
            logger.info(f"ℹ️  Simülasyon modu - Sadece DB'ye kaydedilecek: {symbol}")
        
        # 5. Pozisyon kaydet (DB)
        position_saved = save_hybrid_position(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            position_size=position_size,
            score=confidence,  # confidence_score -> score
            execution_type='MULTI_TIMEFRAME',
            execution_result={'signal': signal},
            sentiment_data={
                'fear_greed_index': signal.get('fear_greed_index'),
                'news_sentiment': signal.get('news_sentiment'),
                'reddit_sentiment': signal.get('reddit_sentiment')
            },
            confluence_data=confluence_data  # 🆕 v11.3: Pass confluence data
        )
        
        if position_saved:
            logger.info(f"✅ Position saved to database: {symbol}")
            
            # 5. Telegram notification
            try:
                send_multi_timeframe_signal_alert(symbol, signal, sl_price, tp_price, position_size, confluence_data)
            except Exception as tg_error:
                logger.warning(f"⚠️ Telegram notification failed: {tg_error}")
            
            return True
        else:
            logger.error(f"❌ Position could not be saved: {symbol}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Execute position error [{symbol}]: {e}", exc_info=True)
        return False


def send_multi_timeframe_signal_alert(symbol: str, signal: dict, sl_price: float, tp_price: float, position_size: float, confluence_data: dict = None):
    """Telegram bildirimi gönder - v11.3 Confluence score eklendi"""
    try:
        direction = signal['signal']
        entry_price = signal['entry_price']
        confidence = signal['confidence']
        
        tf_15m = signal['timeframes']['15m']
        tf_30m = signal['timeframes']['30m']
        
        # Confluence score formatı
        conf_msg = ""
        if confluence_data:
            total = confluence_data.get('total_score', 0)
            htf = confluence_data.get('htf_score', 0)
            ltf = confluence_data.get('ltf_score', 0)
            sentiment = confluence_data.get('sentiment_bonus', 0)
            recommendation = confluence_data.get('recommendation', 'N/A')
            
            conf_msg = f"""
📊 **Confluence Score:** {total}/10 ⭐
├─ HTF (1H): {htf}/6
├─ LTF (15M): {ltf}/5
├─ Sentiment: +{sentiment}
└─ Grade: {recommendation}
"""
        
        message = f"""
🚀 **YENİ POZİSYON AÇILDI**

📊 **Coin:** `{symbol}`
📈 **Direction:** {direction}
💰 **Entry:** ${entry_price:,.4f}

**Multi-Timeframe Analysis:**
├─ 15m EMA5: ${tf_15m['ema5']:.2f}
├─ 15m EMA20: ${tf_15m['ema20']:.2f}
├─ 30m EMA5: ${tf_30m['ema5']:.2f}
└─ 30m EMA20: ${tf_30m['ema20']:.2f}
{conf_msg}
🎯 **TP:** ${tp_price:,.4f} (+$4.00)
🛑 **SL:** ${sl_price:,.4f} (-$1.00)

📊 **Position Size:** {position_size:.6f} units
🎯 **Confidence:** {confidence:.2%}

💎 **Margin:** $10.00
⚡ **Leverage:** 10x

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        telegram_notifier.send_message(message)
        logger.info("✅ Telegram notification sent")
        
    except Exception as e:
        logger.error(f"❌ Telegram notification error: {e}")


# ═══════════════════════════════════════════════════════════════════════


def calculate_position_size(symbol: str, entry_price: float, sl_price: float, score: float) -> float:
    """
    v10.7.1 SABİT MARGIN SİSTEMİ
    
    Config'den sabit margin:
    - FIXED_MARGIN_USD: 10 USD
    - FUTURES_LEVERAGE: 10x
    - Position Size = (10 × 10) / Entry Price
    """
    try:
        MARGIN_USD = config.FIXED_MARGIN_USD
        LEVERAGE = config.FUTURES_LEVERAGE
        
        # Position size hesapla (coin/token cinsinden)
        position_size = (MARGIN_USD * LEVERAGE) / entry_price
        
        logger.info(f"   💰 Sabit Margin: ${MARGIN_USD} × {LEVERAGE}x = ${MARGIN_USD * LEVERAGE} notional")
        logger.info(f"   📊 Position Size: {position_size:.6f} {symbol.replace('USDT', '')}")
        
        return position_size
        
    except Exception as e:
        logger.error(f"Position sizing hatası: {e}")
        return None


def get_portfolio_value() -> float:
    """Portfolio değerini al"""
    try:
        balance = binance_fetcher.get_futures_balance('USDT')
        if balance:
            return balance.get('availableBalance', 1000.0)
        return 1000.0
    except:
        return 1000.0


def save_hybrid_position(symbol: str, direction: str, entry_price: float,
                        sl_price: float, tp_price: float, position_size: float,
                        score: float, execution_type: str, execution_result: dict,
                        sentiment_data: dict, confluence_data: dict = None) -> int:
    """
    Pozisyonu DB'ye kaydet - v10.7.1 SABİT MARGIN + v11.3 CONFLUENCE SCORE
    
    Config'den sabit değerler:
    - FIXED_MARGIN_USD: 10 USD
    - FUTURES_LEVERAGE: 10x
    """
    with open_positions_lock:
        db = db_session()
        try:
            # Direction düzeltmesi
            if direction.lower() in ['bullish', 'long']:
                db_direction = 'LONG'
            elif direction.lower() in ['bearish', 'short']:
                db_direction = 'SHORT'
            else:
                db_direction = direction.upper()
            
            # Config'den sabit değerler
            MARGIN_USD = config.FIXED_MARGIN_USD
            leverage = config.FUTURES_LEVERAGE
            amount = position_size
            
            # 🆕 v11.3: Extract confluence scores
            confluence_score = None
            htf_score = None
            ltf_score = None
            
            if confluence_data:
                confluence_score = confluence_data.get('total_score')
                htf_score = confluence_data.get('htf_score')
                ltf_score = confluence_data.get('ltf_score')
            
            new_position = OpenPosition(
                symbol=symbol,
                strategy='v10.7.1_fixed_margin',
                direction=db_direction,
                entry_price=entry_price,
                sl_price=sl_price,
                tp_price=tp_price,
                amount=amount,
                leverage=leverage,
                position_size_units=position_size,
                final_risk_usd=MARGIN_USD,  # ✅ Sabit margin değeri
                open_time=int(time.time() * 1000),
                strategy_source='v10.7.1',
                hybrid_score=score,
                execution_type=execution_type,
                fng_index_at_signal=sentiment_data.get('fear_greed_index'),
                news_sentiment_at_signal=sentiment_data.get('news_sentiment'),
                reddit_sentiment_at_signal=sentiment_data.get('reddit_sentiment'),
                status='OPEN',
                initial_sl=sl_price,
                order_status='FILLED',
                confluence_score=confluence_score,  # 🆕 v11.3
                htf_score=htf_score,  # 🆕 v11.3
                ltf_score=ltf_score  # 🆕 v11.3
            )
            
            db.add(new_position)
            db.commit()
            position_id = new_position.id
            
            logger.info(f"   ✅ Position saved to DB: ID={position_id}, {symbol} {db_direction} @ ${entry_price:.4f}")
            logger.info(f"      💰 Margin: ${MARGIN_USD} | Leverage: {leverage}x | Amount: {amount:.4f}")
            logger.info(f"      🎯 TP: ${tp_price:.4f} (+$4) | SL: ${sl_price:.4f} (-$1)")
            if confluence_score:
                logger.info(f"      📊 Confluence: {confluence_score}/10 (HTF: {htf_score}, LTF: {ltf_score})")
            
            return position_id
        except Exception as e:
            logger.error(f"DB kayıt hatası: {e}", exc_info=True)
            db.rollback()
            return None
        finally:
            db_session.remove()


def send_hybrid_signal_alert(symbol: str, crossover_data: dict, confirmation: dict,
                             execution_result: dict, sentiment_data: dict):
    """Telegram sinyal bildirimi - ATR Bazlı TP/SL ile"""
    try:
        direction = crossover_data.get('crossover', '').upper()
        score = confirmation.get('score', 0)
        exec_type = execution_result.get('execution_type', 'unknown').upper()
        components = confirmation.get('components', {})
        
        # TP/SL bilgilerini al (execution_result içinde)
        entry_price = execution_result.get('entry_price', crossover_data.get('current_price', 0))
        sl_price = execution_result.get('sl_price', 0)
        tp_price = execution_result.get('tp_price', 0)
        
        # Position size bilgileri
        position_size = execution_result.get('position_size', 0)
        leverage = config.FUTURES_LEVERAGE
        
        # Kar/zarar hesapla
        if direction == 'LONG':
            tp_profit = (tp_price - entry_price) * position_size if position_size > 0 else 0
            sl_loss = abs((entry_price - sl_price) * position_size) if position_size > 0 else 0
        else:
            tp_profit = (entry_price - tp_price) * position_size if position_size > 0 else 0
            sl_loss = abs((sl_price - entry_price) * position_size) if position_size > 0 else 0
        
        rr_ratio = tp_profit / sl_loss if sl_loss > 0 else 0
        
        msg = f"""
🤖 v10.10 ATR System

💎 {symbol}
📊 {direction} ({leverage}x)
⚡ EMA5: {crossover_data.get('ema_short', 0):.2f}
⚡ EMA20: {crossover_data.get('ema_long', 0):.2f}

� Fiyatlar:
   Entry: ${entry_price:,.4f}
   TP: ${tp_price:,.4f} (+${tp_profit:.2f})
   SL: ${sl_price:,.4f} (-${sl_loss:.2f})
   R:R: {rr_ratio:.2f}:1

🎯 Score: {score}/100
   Trend:{components.get('trend_score',0)}/30
   Strength:{components.get('strength_score',0)}/25
   Momentum:{components.get('momentum_score',0)}/25
   RSI:{components.get('rsi_score',0)}/20

📈 Execution: {exec_type}
💭 F&G: {sentiment_data.get('fear_greed_index', 50)}

✅ Position OPENED (ATR-Based TP/SL)
"""
        telegram_notifier.send_message(msg)
    except Exception as e:
        logger.error(f"Telegram bildirimi hatası: {e}")


def log_hybrid_stats():
    """İstatistikleri logla"""
    logger.info("=" * 70)
    logger.info("📊 v10.6 HYBRID STATISTICS")
    logger.info("=" * 70)
    logger.info(f"Crossovers: {hybrid_stats['total_crossovers']}")
    logger.info(f"Signals: {hybrid_stats['total_signals']}")
    logger.info(f"Rejected: {hybrid_stats['rejected_signals']}")
    logger.info(f"Market: {hybrid_stats['market_executions']}")
    logger.info(f"Partial: {hybrid_stats['partial_executions']}")
    logger.info(f"Limit: {hybrid_stats['limit_executions']}")
    logger.info(f"Avg Score: {hybrid_stats['avg_score']:.1f}/100")
    logger.info("=" * 70)


def graceful_shutdown(signum, frame):
    """Graceful shutdown"""
    logger.info("\n" + "=" * 70)
    logger.info("🛑 Shutdown signal alındı...")
    logger.info("=" * 70)
    
    stop_event.set()
    
    if websocket_manager:
        logger.info("📡 WebSocket kapatılıyor...")
        try:
            websocket_manager.stop()
            logger.info("   ✅ WebSocket kapatıldı")
        except:
            pass
    
    # Trade manager thread'i bekle
    if trade_manager_thread and trade_manager_thread.is_alive():
        logger.info("⏳ Trade manager thread durması bekleniyor...")
        trade_manager_thread.join(timeout=5)
        logger.info("   ✅ Trade manager durduruldu")
    
    # Scanner thread'i bekle
    if scanner_thread and scanner_thread.is_alive():
        logger.info("⏳ Scanner thread durması bekleniyor...")
        scanner_thread.join(timeout=5)
        logger.info("   ✅ Scanner durduruldu")
    
    log_hybrid_stats()
    logger.info("\n✅ Shutdown tamamlandı!")
    sys.exit(0)


def main():
    """Ana program"""
    logger.info("\n" + "=" * 70)
    logger.info(f"🤖 ChimeraBot v{config.BOT_VERSION}")
    logger.info("=" * 70)
    logger.info("Architecture: Event-Driven Real-Time Strategy")
    logger.info("Strategy: 15m EMA Crossover + 1H Confirmation")
    logger.info("=" * 70 + "\n")
    
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    try:
        logger.info("🔧 Database başlatılıyor...")
        init_db()
        logger.info("   ✅ Database hazır\n")
        
        # 🆕 v11.1: Telegram Bot Başlat
        logger.info("📱 Telegram bot başlatılıyor...")
        telegram_notifier.initialize_bot(config)
        logger.info("   ✅ Telegram bot hazır\n")
        
        # 🚨 v11.2: Binance Futures Executor Başlat (REAL TRADING için gerekli!)
        if config.ENABLE_REAL_TRADING:
            logger.info("🔥 Binance Futures Executor başlatılıyor (REAL TRADING MODE)...")
            try:
                from src.trade_manager.executor import initialize_executor
                initialize_executor(config)
                logger.info("   ✅ Binance Futures client hazır")
                logger.info(f"   📊 API Key: {config.BINANCE_API_KEY[:8]}...")
                logger.info(f"   🌐 Testnet: {config.BINANCE_TESTNET}")
                logger.info("   ⚠️ GERÇEK PARA İLE İŞLEM AÇILACAK!\n")
            except Exception as executor_error:
                logger.critical(f"❌ Binance Executor başlatılamadı: {executor_error}")
                logger.critical("   REAL TRADING iptal ediliyor - Simülasyon moduna geçiş yapılıyor")
                config.ENABLE_REAL_TRADING = False
        else:
            logger.info("ℹ️  Simülasyon modu - Binance Executor başlatılmıyor\n")
        
        # 🆕 v11.0: HTF-LTF sistem - eski v10.6 sistem kaldırıldı
        # if not initialize_v10_6_system():
        #     logger.critical("❌ v10.6 sistem başlatılamadı!")
        #     return 1
        
        # Trade Manager Thread Başlat
        logger.info("🔧 Trade Manager thread başlatılıyor...")
        global trade_manager_thread
        
        # RealTimeDataManager oluştur (trade manager için gerekli)
        from src.data_fetcher.realtime_manager import RealTimeDataManager
        realtime_data_manager = RealTimeDataManager(stop_event, config)
        
        trade_manager_thread = threading.Thread(
            target=continuously_check_positions,
            args=(realtime_data_manager, open_positions_lock, stop_event, config),
            daemon=True,
            name="TradeManagerThread"
        )
        trade_manager_thread.start()
        logger.info("   ✅ Trade Manager thread aktif\n")
        
        # 🆕 v10.8: Multi-Timeframe Scanner Thread Başlat
        logger.info("🔍 Multi-Timeframe Scanner (15m + 30m) başlatılıyor...")
        global scanner_thread
        
        scanner_thread = threading.Thread(
            target=run_multi_timeframe_scanner,
            args=(stop_event,),
            daemon=True,
            name="MultiTimeframeScanner"
        )
        scanner_thread.start()
        logger.info("   ✅ Multi-Timeframe Scanner thread aktif\n")
        
        # 🆕 v10.9: Hybrid WebSocket Monitor Thread Başlat
        logger.info("📡 Hybrid WebSocket Monitor başlatılıyor...")
        global websocket_thread
        
        websocket_thread = threading.Thread(
            target=run_hybrid_websocket_monitor,
            args=(stop_event,),
            daemon=True,
            name="HybridWebSocketMonitor"
        )
        websocket_thread.start()
        logger.info("   ✅ Hybrid WebSocket Monitor thread aktif\n")
        
        logger.info("🔄 Ana döngü başlatılıyor...")
        logger.info("⏳ Hybrid sistem aktif: Scan + WebSocket monitoring...\n")
        
        stats_interval = 600
        last_stats_time = time.time()
        
        while not stop_event.is_set():
            time.sleep(1)
            
            if time.time() - last_stats_time > stats_interval:
                log_hybrid_stats()
                last_stats_time = time.time()
        
    except KeyboardInterrupt:
        logger.info("\n⌨️  Keyboard interrupt")
        graceful_shutdown(None, None)
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
