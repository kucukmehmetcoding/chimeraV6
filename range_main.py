#!/usr/bin/env python3
"""
RANGE TRADING - LEVERAGE FUTURES BOT
====================================
Random futures tarama + Range detection + Kaldıraçlı işlem

Özellikler:
- 500+ USDT futures random tarama
- Otomatik destek/direnç tespit
- Max 5 pozisyon
- $10 margin + 10x leverage per trade
- %75+ win rate hedef
"""

import sys
import os
import time
import logging
import random
from datetime import datetime
from threading import Thread, Event
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Proje yolunu ekle
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import src.config as config
from src.data_fetcher.binance_fetcher import get_binance_klines, binance_client
from src.technical_analyzer.range_strategy import analyze_range_signal
from src.database.models import OpenPosition, db_session
from src.notifications import telegram as telegram_notifier
# Trade manager için kendi monitoring fonksiyonu kullanacağız (import yok)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('logs/range_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global event
stop_event = Event()

# ========== ENVIRONMENT-BASED CONFIGURATION ==========
# Range Trading Core Parameters
MARGIN_PER_TRADE = float(os.getenv('RANGE_MARGIN_PER_TRADE', '10.0'))
LEVERAGE = int(os.getenv('RANGE_LEVERAGE', '7'))
MAX_OPEN_POSITIONS = int(os.getenv('RANGE_MAX_OPEN_POSITIONS', '3'))
SCAN_INTERVAL = int(os.getenv('RANGE_SCAN_INTERVAL', '300'))

# Range Detection Parameters
MIN_RANGE_WIDTH = float(os.getenv('RANGE_MIN_WIDTH', '0.035'))
MIN_TOUCHES = int(os.getenv('RANGE_MIN_TOUCHES', '3'))
MAX_AGE_HOURS = int(os.getenv('RANGE_MAX_AGE_HOURS', '168'))
VOLUME_WEIGHT = float(os.getenv('RANGE_VOLUME_WEIGHT', '0.3'))

# Risk Management
MIN_SL_DISTANCE = float(os.getenv('RANGE_MIN_SL_DISTANCE', '0.008'))
MIN_RR_RATIO = float(os.getenv('RANGE_MIN_RR_RATIO', '2.0'))
MAX_POSITIONS_PER_SYMBOL = int(os.getenv('RANGE_MAX_POSITIONS_PER_SYMBOL', '1'))
SL_BUFFER = float(os.getenv('RANGE_SL_BUFFER', '0.008'))
TP_BUFFER = float(os.getenv('RANGE_TP_BUFFER', '0.008'))

# Quality Filters
MIN_QUALITY = os.getenv('RANGE_MIN_QUALITY', 'B')
ALLOW_FALSE_BREAKOUTS = os.getenv('RANGE_ALLOW_FALSE_BREAKOUTS', 'False').lower() == 'true'
MAX_FALSE_BREAKOUTS = int(os.getenv('RANGE_MAX_FALSE_BREAKOUTS', '0'))

# Multi-Timeframe Confirmation
USE_HTF_CONFIRMATION = os.getenv('RANGE_USE_HTF_CONFIRMATION', 'True').lower() == 'true'
HTF_TIMEFRAME = os.getenv('RANGE_HTF_TIMEFRAME', '1h')
HTF_MIN_OVERLAP = float(os.getenv('RANGE_HTF_MIN_OVERLAP', '0.7'))

logger.info(f"📊 Range Bot Configuration Loaded:")
logger.info(f"  Leverage: {LEVERAGE}x | Margin: ${MARGIN_PER_TRADE} | Max Positions: {MAX_OPEN_POSITIONS}")
logger.info(f"  Min Range Width: {MIN_RANGE_WIDTH*100:.1f}% | Min RR: {MIN_RR_RATIO}:1")
logger.info(f"  Quality Filter: {MIN_QUALITY}+ | HTF Confirmation: {USE_HTF_CONFIRMATION}")

# Symbol precision cache
SYMBOL_PRECISION_CACHE = {}

# Position mode cache (tekrar kontrol etmemek için)
POSITION_MODE_CHECKED = False
IS_HEDGE_MODE = False


def ensure_one_way_mode():
    """
    Binance Futures position mode'unu One-Way (tek yön) moduna ayarla.
    Hedge mode varsa otomatik değiştir.
    """
    global POSITION_MODE_CHECKED, IS_HEDGE_MODE
    
    if POSITION_MODE_CHECKED:
        return IS_HEDGE_MODE
    
    try:
        # Mevcut mode'u kontrol et
        position_mode = binance_client.futures_get_position_mode()
        is_hedge = position_mode.get('dualSidePosition', False)
        
        if is_hedge:
            logger.warning("⚠️ Hedge Mode tespit edildi, One-Way Mode'a geçiliyor...")
            try:
                binance_client.futures_change_position_mode(dualSidePosition=False)
                logger.info("✅ One-Way Mode aktif edildi!")
                IS_HEDGE_MODE = False
            except Exception as change_error:
                logger.error(f"❌ Mode değiştirilemedi: {change_error}")
                logger.warning("⚠️ Hedge Mode ile devam ediliyor...")
                IS_HEDGE_MODE = True
        else:
            logger.info("✅ One-Way Mode zaten aktif")
            IS_HEDGE_MODE = False
        
        POSITION_MODE_CHECKED = True
        return IS_HEDGE_MODE
    
    except Exception as e:
        logger.error(f"❌ Position mode kontrolü başarısız: {e}")
        logger.info("ℹ️ One-Way Mode varsayılıyor")
        POSITION_MODE_CHECKED = True
        IS_HEDGE_MODE = False
        return False


def get_symbol_precision(symbol: str) -> dict:
    """
    Binance'den symbol precision bilgilerini al.
    Returns: {'quantity': 3, 'price': 2}
    """
    global SYMBOL_PRECISION_CACHE
    
    if symbol in SYMBOL_PRECISION_CACHE:
        return SYMBOL_PRECISION_CACHE[symbol]
    
    try:
        exchange_info = binance_client.futures_exchange_info()
        
        for s in exchange_info['symbols']:
            if s['symbol'] == symbol:
                # Quantity precision
                quantity_precision = s['quantityPrecision']
                
                # Price precision
                price_precision = s['pricePrecision']
                
                precision_info = {
                    'quantity': quantity_precision,
                    'price': price_precision
                }
                
                SYMBOL_PRECISION_CACHE[symbol] = precision_info
                logger.debug(f"📊 {symbol} precision: qty={quantity_precision}, price={price_precision}")
                return precision_info
        
        # Default fallback
        logger.warning(f"⚠️ {symbol} precision bulunamadı, default kullanılıyor")
        return {'quantity': 3, 'price': 2}
    
    except Exception as e:
        logger.error(f"❌ Precision alma hatası [{symbol}]: {e}")
        return {'quantity': 3, 'price': 2}


def get_current_open_positions_count():
    """Açık pozisyon sayısını getir."""
    db = db_session()
    try:
        count = db.query(OpenPosition).count()
        return count
    finally:
        db_session.remove()


def open_range_position(symbol: str, signal: dict):
    """
    Range sinyali için kaldıraçlı pozisyon aç.
    Binance otomatik SL/TP emirleri ile.
    """
    try:
        # Pozisyon limiti kontrolü
        current_positions = get_current_open_positions_count()
        if current_positions >= MAX_OPEN_POSITIONS:
            logger.warning(f"⚠️ Pozisyon limiti doldu ({current_positions}/{MAX_OPEN_POSITIONS})")
            return False
        
        entry_price = signal['entry_price']
        tp_price = signal['tp_price']
        sl_price = signal['sl_price']
        direction = signal['signal']
        
        # Pozisyon büyüklüğü hesapla
        position_size = (MARGIN_PER_TRADE * LEVERAGE) / entry_price
        
        # Kar/zarar hesapla
        if direction == 'LONG':
            profit_usd = (tp_price - entry_price) * position_size
            loss_usd = (entry_price - sl_price) * position_size
        else:  # SHORT
            profit_usd = (entry_price - tp_price) * position_size
            loss_usd = (sl_price - entry_price) * position_size
        
        rr_ratio = profit_usd / loss_usd if loss_usd > 0 else 0
        
        logger.info(f"\n{'💰' * 40}")
        logger.info(f"📊 RANGE POZİSYON AÇILIYOR:")
        logger.info(f"{'💰' * 40}")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Direction: {direction}")
        logger.info(f"   Entry: ${entry_price:.6f}")
        logger.info(f"   TP: ${tp_price:.6f} (${profit_usd:.2f} kar)")
        logger.info(f"   SL: ${sl_price:.6f} (${loss_usd:.2f} zarar)")
        logger.info(f"   RR: {rr_ratio:.2f}:1")
        logger.info(f"   Margin: ${MARGIN_PER_TRADE}")
        logger.info(f"   Leverage: {LEVERAGE}x")
        logger.info(f"   Position Size: {position_size:.6f} {symbol[:-4]}")
        logger.info(f"   Support: ${signal['support']:.6f}")
        logger.info(f"   Resistance: ${signal['resistance']:.6f}")
        
        # ADIM 1: Kaldıraç ayarla
        try:
            binance_client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
            logger.info(f"✅ Kaldıraç ayarlandı: {LEVERAGE}x")
        except Exception as lev_error:
            logger.warning(f"⚠️ Kaldıraç ayarlama hatası: {lev_error}")
        
        # Precision bilgilerini al
        precision = get_symbol_precision(symbol)
        qty_precision = precision['quantity']
        price_precision = precision['price']
        
        # Quantity'yi precision'a göre round et
        position_size_rounded = round(position_size, qty_precision)
        
        logger.info(f"📊 Precision: qty={qty_precision}, price={price_precision}")
        logger.info(f"📊 Position size: {position_size:.6f} → {position_size_rounded}")
        
        # Position mode'u kontrol et ve One-Way yap
        is_hedge_mode = ensure_one_way_mode()
        
        # ADIM 2: Market emri ile pozisyon aç
        side_market = 'BUY' if direction == 'LONG' else 'SELL'
        
        try:
            order_params = {
                'symbol': symbol,
                'side': side_market,
                'type': 'MARKET',
                'quantity': position_size_rounded
            }
            
            # Hedge mode ise positionSide ekle
            if is_hedge_mode:
                order_params['positionSide'] = 'LONG' if direction == 'LONG' else 'SHORT'
            
            market_order = binance_client.futures_create_order(**order_params)
            logger.info(f"✅ Market emri çalıştı: {market_order['orderId']}")
            
            # Market emrinden sonra güncel fiyatı al
            time.sleep(0.5)  # Emrin işlemesi için kısa bekle
            from src.data_fetcher.binance_fetcher import get_current_price
            current_market_price = get_current_price(symbol)
            if current_market_price is None:
                current_market_price = entry_price
            
            logger.info(f"📊 Current market price: ${current_market_price:.{price_precision}f}")
            
        except Exception as market_error:
            logger.error(f"❌ Market emri hatası: {market_error}")
            return False
        
        # ADIM 3: Take Profit emri (otomatik)
        side_tp = 'SELL' if direction == 'LONG' else 'BUY'
        
        # TP mesafesini kontrol et (minimum %0.3)
        if direction == 'LONG':
            tp_distance_percent = ((tp_price - current_market_price) / current_market_price) * 100
            if tp_distance_percent < 0.3:
                logger.warning(f"⚠️ TP çok yakın ({tp_distance_percent:.2f}%), emri atlanıyor")
                skip_tp = True
            else:
                skip_tp = False
        else:  # SHORT
            tp_distance_percent = ((current_market_price - tp_price) / current_market_price) * 100
            if tp_distance_percent < 0.3:
                logger.warning(f"⚠️ TP çok yakın ({tp_distance_percent:.2f}%), emri atlanıyor")
                skip_tp = True
            else:
                skip_tp = False
        
        if not skip_tp:
            try:
                tp_params = {
                    'symbol': symbol,
                    'side': side_tp,
                    'type': 'TAKE_PROFIT_MARKET',
                    'quantity': position_size_rounded,
                    'stopPrice': round(tp_price, price_precision),
                    'closePosition': True
                }
                
                # Hedge mode ise positionSide ekle
                if is_hedge_mode:
                    tp_params['positionSide'] = 'LONG' if direction == 'LONG' else 'SHORT'
                
                tp_order = binance_client.futures_create_order(**tp_params)
                logger.info(f"✅ TP emri yerleştirildi: ${tp_price:.{price_precision}f} (+{tp_distance_percent:.2f}%) (ID: {tp_order['orderId']})")
            except Exception as tp_error:
                logger.error(f"❌ TP emri hatası: {tp_error}")
        else:
            logger.info(f"ℹ️ TP emri atlandı (mesafe yetersiz)")
        
        # ADIM 4: Stop Loss emri (otomatik)
        # SL mesafesini kontrol et (minimum %0.2)
        if direction == 'LONG':
            sl_distance_percent = ((current_market_price - sl_price) / current_market_price) * 100
            if sl_distance_percent < 0.2:
                logger.warning(f"⚠️ SL çok yakın ({sl_distance_percent:.2f}%), emri atlanıyor")
                skip_sl = True
            else:
                skip_sl = False
        else:  # SHORT
            sl_distance_percent = ((sl_price - current_market_price) / current_market_price) * 100
            if sl_distance_percent < 0.2:
                logger.warning(f"⚠️ SL çok yakın ({sl_distance_percent:.2f}%), emri atlanıyor")
                skip_sl = True
            else:
                skip_sl = False
        
        if not skip_sl:
            try:
                sl_params = {
                    'symbol': symbol,
                    'side': side_tp,
                    'type': 'STOP_MARKET',
                    'quantity': position_size_rounded,
                    'stopPrice': round(sl_price, price_precision),
                    'closePosition': True
                }
                
                # Hedge mode ise positionSide ekle
                if is_hedge_mode:
                    sl_params['positionSide'] = 'LONG' if direction == 'LONG' else 'SHORT'
                
                sl_order = binance_client.futures_create_order(**sl_params)
                logger.info(f"✅ SL emri yerleştirildi: ${sl_price:.{price_precision}f} (-{sl_distance_percent:.2f}%) (ID: {sl_order['orderId']})")
            except Exception as sl_error:
                logger.error(f"❌ SL emri hatası: {sl_error}")
        else:
            logger.info(f"ℹ️ SL emri atlandı (mesafe yetersiz)")
        
        # ADIM 5: Database'e kaydet
        db = db_session()
        try:
            position = OpenPosition(
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                tp_price=tp_price,
                sl_price=sl_price,
                margin=MARGIN_PER_TRADE,
                leverage=LEVERAGE,
                position_size=position_size,
                strategy='range_trading',
                support_level=signal.get('support'),
                resistance_level=signal.get('resistance'),
                range_width=signal.get('range_width', 0)
            )
            db.add(position)
            db.commit()
            
            logger.info(f"✅ Pozisyon database'e kaydedildi (ID: {position.id})")
            logger.info(f"🎯 Binance otomatik SL/TP aktif - manuel kontrol gerekmez!")
            
            # Telegram bildirim
            send_position_opened_alert(symbol, signal, profit_usd, loss_usd, rr_ratio)
            
            return True
        
        except Exception as db_error:
            db.rollback()
            logger.error(f"❌ Database kayıt hatası: {db_error}")
            return False
        finally:
            db_session.remove()
    
    except Exception as e:
        logger.error(f"❌ Pozisyon açma hatası [{symbol}]: {e}", exc_info=True)
        return False


def send_position_opened_alert(symbol: str, signal: dict, profit_usd: float, loss_usd: float, rr_ratio: float):
    """Pozisyon açıldı Telegram bildirimi."""
    try:
        direction_emoji = "🟢" if signal['signal'] == 'LONG' else "🔴"
        
        message = (
            f"{direction_emoji} *RANGE {signal['signal']} POZİSYON AÇILDI*\n\n"
            f"*Symbol:* `{symbol}`\n"
            f"*Entry:* ${signal['entry_price']:.6f}\n\n"
            f"*Range:*\n"
            f"  🔵 Destek: ${signal['support']:.6f}\n"
            f"  🔴 Direnç: ${signal['resistance']:.6f}\n"
            f"  �� Genişlik: {signal['range_width']:.2%}\n\n"
            f"*Hedefler:*\n"
            f"  🎯 TP: ${signal['tp_price']:.6f} (+${profit_usd:.2f})\n"
            f"  🛡️ SL: ${signal['sl_price']:.6f} (-${loss_usd:.2f})\n"
            f"  ⚖️ RR: {rr_ratio:.2f}:1\n\n"
            f"*Detay:*\n"
            f"  💰 Margin: ${MARGIN_PER_TRADE}\n"
            f"  📊 Leverage: {LEVERAGE}x\n\n"
            f"_Range Trading - Destek/Direnç Stratejisi_"
        )
        
        telegram_notifier.send_message(message)
        logger.info("✅ Telegram bildirimi gönderildi")
    
    except Exception as e:
        logger.error(f"❌ Telegram bildirim hatası: {e}")


def range_scanner_thread():
    """
    Range trading scanner - Random futures tarama.
    """
    scan_count = 0
    
    # Coin pool al
    try:
        logger.info("🔍 Binance Futures symbol listesi çekiliyor...")
        exchange_info = binance_client.futures_exchange_info()
        
        coin_pool = [
            s['symbol'] 
            for s in exchange_info['symbols']
            if s['symbol'].endswith('USDT') 
            and s['contractType'] == 'PERPETUAL'
            and s['status'] == 'TRADING'
        ]
        
        logger.info("\n" + "="*80)
        logger.info("�� RANGE TRADING LEVERAGE BOT BAŞLATILDI")
        logger.info("="*80)
        logger.info(f"   Total coins: {len(coin_pool)}")
        logger.info(f"   Scan interval: {SCAN_INTERVAL}s ({SCAN_INTERVAL/60:.1f} min)")
        logger.info(f"   Timeframe: 15M")
        logger.info(f"   Max positions: {MAX_OPEN_POSITIONS}")
        logger.info(f"   Margin per trade: ${MARGIN_PER_TRADE}")
        logger.info(f"   Leverage: {LEVERAGE}x")
        logger.info(f"   Strateji: Destek/Direnç Range Trading")
        logger.info("="*80 + "\n")
    
    except Exception as e:
        logger.error(f"❌ Coin pool alınamadı: {e}")
        coin_pool = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    
    while not stop_event.is_set():
        try:
            scan_count += 1
            logger.info("\n" + "="*80)
            logger.info(f"🔍 RANGE SCAN #{scan_count} BAŞLIYOR")
            logger.info("="*80)
            logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            signals_found = 0
            positions_opened = 0
            
            # Random shuffle
            shuffled_pool = list(coin_pool)
            random.shuffle(shuffled_pool)
            
            for idx, symbol in enumerate(shuffled_pool, 1):
                try:
                    # Pozisyon limiti kontrolü
                    current_positions = get_current_open_positions_count()
                    if current_positions >= MAX_OPEN_POSITIONS:
                        logger.info(f"⚠️ Pozisyon limiti doldu ({current_positions}/{MAX_OPEN_POSITIONS}), scan durduruluyor")
                        break
                    
                    if idx % 50 == 0:
                        logger.info(f"\n📊 Progress: {idx}/{len(coin_pool)} coins scanned...")
                    
                    logger.debug(f"[{idx}/{len(coin_pool)}] 🔍 {symbol}")
                    
                    # ════════════════════════════════════════════════
                    # 15M Data Çek
                    # ════════════════════════════════════════════════
                    df_15m = get_binance_klines(symbol, '15m', limit=100)
                    
                    if df_15m is None or df_15m.empty:
                        continue
                    
                    # ════════════════════════════════════════════════
                    # ✅ YENİ: 1H Data Çek (Confirmation için)
                    # ════════════════════════════════════════════════
                    df_1h = None
                    try:
                        df_1h = get_binance_klines(symbol, '1h', limit=100)
                        if df_1h is not None and len(df_1h) >= 50:
                            logger.debug(f"   ✅ {symbol} 1H data loaded ({len(df_1h)} bars)")
                    except Exception as htf_error:
                        logger.debug(f"   ⚠️ {symbol} 1H data yüklenemedi: {htf_error}")
                    
                    # ════════════════════════════════════════════════
                    # Range Analiz (Multi-timeframe)
                    # ════════════════════════════════════════════════
                    signal = analyze_range_signal(df_15m, df_1h, symbol)  # ✅ df_1h eklendi
                    
                    if signal:
                        signals_found += 1
                        
                        # ════════════════════════════════════════════════
                        # ✅ YENİ: RANGE QUALITY FİLTRESİ
                        # ════════════════════════════════════════════════
                        range_quality = signal.get('range_quality', 'D')
                        if range_quality in ['C', 'D']:
                            logger.warning(f"   ❌ {symbol} range kalitesi düşük ({range_quality}), skip")
                            continue
                        
                        # ════════════════════════════════════════════════
                        # ✅ YENİ: FALSE BREAKOUT FİLTRESİ
                        # ════════════════════════════════════════════════
                        false_breakouts = signal.get('false_breakouts', [])
                        if len(false_breakouts) > 2:
                            logger.warning(f"   ❌ {symbol} çok fazla false breakout ({len(false_breakouts)}), skip")
                            continue
                        
                        # ════════════════════════════════════════════════
                        # ✅ YENİ: RISK-REWARD FİLTRESİ
                        # ════════════════════════════════════════════════
                        entry_price = signal['entry_price']
                        tp_price = signal['tp_price']
                        sl_price = signal['sl_price']
                        
                        risk = abs(entry_price - sl_price)
                        reward = abs(tp_price - entry_price)
                        rr_ratio = reward / risk if risk > 0 else 0
                        
                        if rr_ratio < MIN_RR_RATIO:
                            logger.warning(f"   ❌ {symbol} RR çok düşük ({rr_ratio:.2f} < {MIN_RR_RATIO}), skip")
                            continue
                        
                        # ════════════════════════════════════════════════
                        # ✅ YENİ: SL MESAFE FİLTRESİ
                        # ════════════════════════════════════════════════
                        sl_distance_pct = risk / entry_price
                        if sl_distance_pct < MIN_SL_DISTANCE:
                            logger.warning(f"   ❌ {symbol} SL çok dar ({sl_distance_pct*100:.2f}% < {MIN_SL_DISTANCE*100:.1f}%), skip")
                            continue
                        
                        # ════════════════════════════════════════════════
                        # ✅ YENİ: RANGE WIDTH FİLTRESİ
                        # ════════════════════════════════════════════════
                        range_width = signal.get('range_width', 0)
                        if range_width < MIN_RANGE_WIDTH:
                            logger.warning(f"   ❌ {symbol} range çok dar ({range_width*100:.2f}% < {MIN_RANGE_WIDTH*100:.1f}%), skip")
                            continue
                        
                        # ════════════════════════════════════════════════
                        # ✅ YENİ: DUPLICATE SYMBOL FİLTRESİ
                        # ════════════════════════════════════════════════
                        db = db_session()
                        try:
                            existing = db.query(OpenPosition).filter_by(symbol=symbol).count()
                            if existing >= MAX_POSITIONS_PER_SYMBOL:
                                logger.warning(f"   ❌ {symbol} zaten açık pozisyon var, skip")
                                continue
                        finally:
                            db_session.remove()
                        
                        # ════════════════════════════════════════════════
                        # TÜM FİLTRELER BAŞARILI - POZİSYON AÇ
                        # ════════════════════════════════════════════════
                        logger.info(f"   ✅ {symbol} tüm filtreleri geçti (Quality: {range_quality}, RR: {rr_ratio:.2f}, SL: {sl_distance_pct*100:.1f}%)")
                        
                        signal['symbol'] = symbol
                        
                        # Pozisyon aç
                        if open_range_position(symbol, signal):
                            positions_opened += 1
                    
                    # Rate limiting
                    time.sleep(0.2)
                
                except Exception as coin_error:
                    logger.error(f"❌ {symbol} tarama hatası: {coin_error}")
                    continue
            
            # Scan özeti
            logger.info("\n" + "="*80)
            logger.info(f"📊 RANGE SCAN #{scan_count} TAMAMLANDI")
            logger.info("="*80)
            logger.info(f"   Taranan coin: {min(idx, len(coin_pool))}")
            logger.info(f"   Range tespit: {signals_found}")
            logger.info(f"   Pozisyon açılan: {positions_opened}")
            logger.info(f"   Açık pozisyon: {get_current_open_positions_count()}/{MAX_OPEN_POSITIONS}")
            logger.info(f"   Sonraki scan: {SCAN_INTERVAL}s")
            logger.info("="*80 + "\n")
            
            # Bekleme
            logger.info(f"⏳ {SCAN_INTERVAL}s bekleniyor...")
            stop_event.wait(SCAN_INTERVAL)
        
        except Exception as e:
            logger.error(f"❌ Scanner hatası: {e}", exc_info=True)
            stop_event.wait(60)


def monitor_positions_websocket(stop_event: Event):
    """
    Binance Websocket ile pozisyon güncellemelerini dinle.
    SL/TP Binance tarafından otomatik kapatılıyor, biz sadece bildirimleri yakalıyoruz.
    """
    logger.info("✅ Websocket Position Monitor başlatıldı")
    logger.info("🎯 Binance otomatik SL/TP aktif - manuel kontrol YOK")
    
    while not stop_event.is_set():
        try:
            # Mevcut açık pozisyonları kontrol et
            db = db_session()
            try:
                db_positions = db.query(OpenPosition).filter(
                    OpenPosition.strategy == 'range_trading'
                ).all()
                
                db_symbols = {p.symbol for p in db_positions}
                
                # Binance'den gerçek pozisyonları al
                try:
                    binance_positions = binance_client.futures_position_information()
                    active_binance_symbols = {
                        p['symbol'] for p in binance_positions 
                        if float(p.get('positionAmt', 0)) != 0
                    }
                except Exception as api_error:
                    logger.error(f"❌ Binance API hatası: {api_error}")
                    active_binance_symbols = set()
                
                # Database'de var ama Binance'de kapanmış pozisyonlar
                closed_symbols = db_symbols - active_binance_symbols
                
                for symbol in closed_symbols:
                    pos = db.query(OpenPosition).filter(
                        OpenPosition.symbol == symbol,
                        OpenPosition.strategy == 'range_trading'
                    ).first()
                    
                    if pos:
                        # Pozisyon Binance tarafından kapatılmış
                        logger.info(f"\n{'='*80}")
                        logger.info(f"🎯 POZİSYON KAPANDI (Binance Otomatik)")
                        logger.info(f"{'='*80}")
                        logger.info(f"   Symbol: {pos.symbol}")
                        logger.info(f"   Direction: {pos.direction}")
                        logger.info(f"   Entry: ${pos.entry_price:.6f}")
                        logger.info(f"   TP: ${pos.tp_price:.6f}")
                        logger.info(f"   SL: ${pos.sl_price:.6f}")
                        logger.info(f"{'='*80}\n")
                        
                        # PnL'yi Binance'den al (daha doğru)
                        try:
                            trades = binance_client.futures_account_trades(
                                symbol=symbol,
                                limit=5
                            )
                            if trades:
                                # Son trade'den PnL hesapla
                                last_trade = trades[-1]
                                realized_pnl = float(last_trade.get('realizedPnl', 0))
                                
                                logger.info(f"💰 Realized PnL: ${realized_pnl:.2f}")
                                
                                # Telegram bildirim
                                send_binance_close_telegram(pos, realized_pnl)
                        except Exception as trade_error:
                            logger.warning(f"⚠️ Trade history alınamadı: {trade_error}")
                            send_binance_close_telegram(pos, 0.0)
                        
                        # Database'den sil
                        db.delete(pos)
                        db.commit()
            
            finally:
                db_session.remove()
            
            # 30 saniye bekle (Binance otomatik kapatıyor, sık kontrol gerekmez)
            stop_event.wait(30)
        
        except Exception as e:
            logger.error(f"❌ Websocket monitor hatası: {e}", exc_info=True)
            stop_event.wait(60)


def send_binance_close_telegram(pos, realized_pnl: float):
    """Binance otomatik kapanış Telegram bildirimi."""
    try:
        emoji = "✅" if realized_pnl >= 0 else "❌"
        pnl_percent = (realized_pnl / (pos.margin * pos.leverage)) * 100 if pos.margin > 0 else 0
        
        message = (
            f"{emoji} *POZİSYON KAPANDI (Binance Otomatik)*\n\n"
            f"*Symbol:* `{pos.symbol}`\n"
            f"*Direction:* {pos.direction}\n\n"
            f"*Fiyatlar:*\n"
            f"  📍 Entry: ${pos.entry_price:.6f}\n"
            f"  🎯 TP: ${pos.tp_price:.6f}\n"
            f"  🛡️ SL: ${pos.sl_price:.6f}\n\n"
            f"*Kar/Zarar:*\n"
            f"  💰 ${realized_pnl:+.2f}\n"
            f"  📊 {pnl_percent:+.2f}%\n\n"
            f"_Range Trading - Binance Otomatik SL/TP_"
        )
        
        telegram_notifier.send_message(message)
    except Exception as e:
        logger.error(f"❌ Telegram bildirim hatası: {e}")


if __name__ == "__main__":
    try:
        logger.info("🚀 Range Trading Leverage Bot başlatılıyor...")
        logger.info("🎯 Binance Otomatik SL/TP Modu - Anında tetikleme aktif!")
        
        # Position mode'u One-Way yap
        logger.info("\n⚙️ Binance ayarları kontrol ediliyor...")
        ensure_one_way_mode()
        
        # Websocket position monitor başlat
        monitor_thread = Thread(target=monitor_positions_websocket, args=(stop_event,), daemon=True)
        monitor_thread.start()
        logger.info("✅ Websocket position monitor başlatıldı")
        
        # Scanner başlat
        range_scanner_thread()
    
    except KeyboardInterrupt:
        logger.info("\n⛔ Bot kullanıcı tarafından durduruldu.")
        stop_event.set()
    except Exception as e:
        logger.error(f"❌ Kritik hata: {e}", exc_info=True)
