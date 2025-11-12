#!/usr/bin/env python3
"""
EMA Proximity Alert System
==========================

Manuel trading için EMA yakınlaşma bildirimleri gönderir.
Ana bot sistemine dokunmaz, bağımsız çalışır.

Filtreler:
1. EMA5-EMA20 mesafe < %0.5 (15m timeframe)
2. 30m timeframe'de trend aligned
3. RSI extreme değil (>30 ve <70)

Kullanım:
    python ema_proximity_alert.py
"""

import logging
import time
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
import pandas as pd

# Proje root'u path'e ekle
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

# Config ve modülleri import et
try:
    from src import config
    from src.data_fetcher import binance_fetcher
    from src.notifications import telegram as telegram_notifier
    
    # Logging ayarla
    log_file = os.path.join(project_root, 'logs', 'ema_proximity_alert.log')
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)
    
except ImportError as e:
    print(f"❌ Import hatası: {e}")
    print("   src/config.py ve diğer modüller bulunamadı!")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Alert parametreleri
PROXIMITY_THRESHOLD_15M = 0.5  # %0.5 mesafe (15m)
PROXIMITY_THRESHOLD_30M = 0.5  # %0.5 mesafe (30m)
REQUIRE_BOTH_TIMEFRAMES = True  # HER İKİSİ DE yakın olmalı
RSI_MIN = 40  # Nötr bölge (40-60)
RSI_MAX = 60  # Nötr bölge (40-60)
MIN_VOLUME_24H = 5_000_000  # $5M minimum 24h volume (çok sıkı değil)
SCAN_INTERVAL = 120  # 2 dakika (saniye)
ALERT_COOLDOWN = 1800  # 30 dakika (saniye) - aynı coin için tekrar bildirim
DISTANCE_RESET_THRESHOLD = 2.0  # %2'nin üstüne çıkarsa alert reset

# Timeframe ayarları
PRIMARY_TF = '15m'
SECONDARY_TF = '30m'
EMA_SHORT = 5
EMA_LONG = 20

# Alert state tracking
alerted_coins: Dict[str, datetime] = {}  # {symbol: last_alert_time}
last_distances: Dict[str, float] = {}  # {symbol: last_distance_percent}


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def calculate_ema(df: pd.DataFrame, column: str, span: int) -> pd.Series:
    """EMA hesapla"""
    return df[column].ewm(span=span, adjust=False).mean()


def calculate_rsi(df: pd.DataFrame, column: str = 'close', period: int = 14) -> pd.Series:
    """RSI hesapla"""
    delta = df[column].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def get_coin_pool() -> list:
    """Tüm USDT futures çiftlerini al"""
    try:
        exchange_info = binance_fetcher.binance_client.futures_exchange_info()
        
        coins = [
            s['symbol'] 
            for s in exchange_info['symbols']
            if s['symbol'].endswith('USDT') 
            and s['contractType'] == 'PERPETUAL'
            and s['status'] == 'TRADING'
        ]
        
        logger.info(f"✅ {len(coins)} USDT perpetual futures coin yüklendi")
        return coins
        
    except Exception as e:
        logger.error(f"❌ Coin pool hatası: {e}")
        return []


def should_alert(symbol: str, distance_percent: float) -> bool:
    """
    Alert gönderilmeli mi kontrol et
    
    Returns:
        True: Alert gönder
        False: Skip
    """
    now = datetime.now()
    
    # 1. Cooldown kontrolü (30 dakika)
    if symbol in alerted_coins:
        last_alert = alerted_coins[symbol]
        time_since_alert = (now - last_alert).total_seconds()
        
        if time_since_alert < ALERT_COOLDOWN:
            return False  # Henüz cooldown süresi dolmadı
    
        # 2. Distance reset kontrolü
        if symbol in last_distances:
            last_distance = last_distances[symbol]
            
            # Mesafe %2'nin üstüne çıktıysa reset (crossover gerçekleşti veya uzaklaştı)
            if last_distance > DISTANCE_RESET_THRESHOLD and distance_percent < PROXIMITY_THRESHOLD_15M:
                logger.info(f"   🔄 {symbol}: Distance reset ({last_distance:.2f}% → {distance_percent:.2f}%)")
                # Alert state'i temizle, yeniden bildirim gönderebilir
                if symbol in alerted_coins:
                    del alerted_coins[symbol]    # 3. Distance güncelle
    last_distances[symbol] = distance_percent
    
    # 4. Alert gönder
    return True


def analyze_coin(symbol: str) -> Optional[dict]:
    """
    Tek bir coin'i analiz et
    
    Returns:
        dict: Alert verisi (varsa)
        None: Alert yok
    """
    try:
        # 1. 24h volume kontrolü (ilk filtre - hızlı)
        try:
            ticker_24h = binance_fetcher.binance_client.futures_ticker(symbol=symbol)
            volume_usd = float(ticker_24h.get('quoteVolume', 0))
            
            if volume_usd < MIN_VOLUME_24H:
                return None  # Düşük hacimli coin, skip
                
        except Exception as vol_error:
            logger.debug(f"   ⚠️ {symbol}: Volume alınamadı, skip")
            return None
        
        # 2. 15m data çek
        df_15m = binance_fetcher.get_binance_klines(symbol, PRIMARY_TF, limit=50)
        
        if df_15m is None or df_15m.empty or len(df_15m) < 20:
            return None
        
        # 3. EMA hesapla
        df_15m['ema5'] = calculate_ema(df_15m, 'close', EMA_SHORT)
        df_15m['ema20'] = calculate_ema(df_15m, 'close', EMA_LONG)
        
        last_candle = df_15m.iloc[-1]
        ema5 = float(last_candle['ema5'])
        ema20 = float(last_candle['ema20'])
        current_price = float(last_candle['close'])
        
        if pd.isna(ema5) or pd.isna(ema20):
            return None
        
        # 4. Mesafe hesapla (15m)
        distance_percent_15m = abs((ema5 - ema20) / ema20) * 100
        
        # Filtre 1: 15m EMA mesafe kontrolü
        if distance_percent_15m >= PROXIMITY_THRESHOLD_15M:
            return None
        
        # 5. RSI hesapla (15m)
        df_15m['rsi'] = calculate_rsi(df_15m)
        rsi_15m = float(df_15m.iloc[-1]['rsi'])
        
        if pd.isna(rsi_15m):
            return None
        
        # Filtre 2: RSI nötr bölge kontrolü (40-60)
        if rsi_15m <= RSI_MIN or rsi_15m >= RSI_MAX:
            logger.debug(f"   ❌ {symbol}: RSI nötr bölge dışında ({rsi_15m:.1f})")
            return None
        
        # 6. 30m data çek
        df_30m = binance_fetcher.get_binance_klines(symbol, SECONDARY_TF, limit=50)
        
        if df_30m is None or df_30m.empty or len(df_30m) < 20:
            return None
        
        # 7. 30m EMA hesapla
        df_30m['ema5'] = calculate_ema(df_30m, 'close', EMA_SHORT)
        df_30m['ema20'] = calculate_ema(df_30m, 'close', EMA_LONG)
        
        ema5_30m = float(df_30m.iloc[-1]['ema5'])
        ema20_30m = float(df_30m.iloc[-1]['ema20'])
        
        if pd.isna(ema5_30m) or pd.isna(ema20_30m):
            return None
        
        # Mesafe hesapla (30m)
        distance_percent_30m = abs((ema5_30m - ema20_30m) / ema20_30m) * 100
        
        # Filtre 3a: 30m EMA mesafe kontrolü
        if REQUIRE_BOTH_TIMEFRAMES and distance_percent_30m >= PROXIMITY_THRESHOLD_30M:
            logger.debug(f"   ❌ {symbol}: 30m mesafe çok büyük ({distance_percent_30m:.3f}%)")
            return None
        
        # Filtre 3b: 30m trend alignment
        # 15m'de EMA5 > EMA20 ise (bullish bias) → 30m'de de EMA5 > EMA20 olmalı
        # 15m'de EMA5 < EMA20 ise (bearish bias) → 30m'de de EMA5 < EMA20 olmalı
        
        bullish_15m = ema5 > ema20
        bullish_30m = ema5_30m > ema20_30m
        
        if bullish_15m != bullish_30m:
            logger.debug(f"   ❌ {symbol}: 30m trend aligned değil")
            return None
        
        # 8. Cooldown ve reset kontrolü (15m distance kullan)
        if not should_alert(symbol, distance_percent_15m):
            return None
        
        # ✅ Tüm filtrelerden geçti!
        bias = "🔵 BULLISH" if bullish_15m else "🔴 BEARISH"
        
        # Her iki timeframe'de de yakın mı kontrol et
        both_close = distance_percent_15m < PROXIMITY_THRESHOLD_15M and distance_percent_30m < PROXIMITY_THRESHOLD_30M
        proximity_status = "🔥 HER İKİSİ DE YAKIN!" if both_close else "📊 15m Yakın"
        
        return {
            'symbol': symbol,
            'price': current_price,
            'volume_24h': volume_usd,
            'ema5_15m': ema5,
            'ema20_15m': ema20,
            'distance_15m': distance_percent_15m,
            'ema5_30m': ema5_30m,
            'ema20_30m': ema20_30m,
            'distance_30m': distance_percent_30m,
            'rsi_15m': rsi_15m,
            'bias': bias,
            'proximity_status': proximity_status,
            'both_close': both_close,
            'timestamp': datetime.now()
        }
        
    except Exception as e:
        logger.error(f"❌ {symbol} analiz hatası: {e}")
        return None


def send_alert(alert_data: dict):
    """Telegram bildirimi gönder"""
    try:
        symbol = alert_data['symbol']
        price = alert_data['price']
        volume_24h = alert_data['volume_24h']
        ema5_15m = alert_data['ema5_15m']
        ema20_15m = alert_data['ema20_15m']
        distance_15m = alert_data['distance_15m']
        ema5_30m = alert_data['ema5_30m']
        ema20_30m = alert_data['ema20_30m']
        distance_30m = alert_data['distance_30m']
        rsi = alert_data['rsi_15m']
        bias = alert_data['bias']
        proximity_status = alert_data['proximity_status']
        both_close = alert_data['both_close']
        
        # Telegram mesajı
        message = f"""
⚠️ **EMA YAKINLAŞMA UYARISI** {proximity_status}

📊 **Coin:** `{symbol}`
💹 **Price:** ${price:,.4f}
💰 **24h Volume:** ${volume_24h/1_000_000:.1f}M

**15m Timeframe:**
📉 EMA5: {ema5_15m:.4f}
📉 EMA20: {ema20_15m:.4f}
📏 Mesafe: **{distance_15m:.3f}%** ⬇️

**30m Timeframe:**
📉 EMA5: {ema5_30m:.4f}
📉 EMA20: {ema20_30m:.4f}
📏 Mesafe: **{distance_30m:.3f}%** {'⬇️ YAKIN!' if distance_30m < PROXIMITY_THRESHOLD_30M else ''}

📊 RSI(14): {rsi:.1f} (Nötr)
{bias}

{'🔥 HER İKİ TIMEFRAME DE CROSSOVERA YAKIN!' if both_close else '✅ 15m yakın, 30m trend aligned'}
✅ Volume > $5M

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        # Telegram'a gönder
        telegram_notifier.send_message(message)
        
        # Alert state güncelle
        alerted_coins[symbol] = datetime.now()
        
        status_text = "BOTH" if both_close else "15M"
        logger.info(f"✅ ALERT [{status_text}]: {symbol} (15m:{distance_15m:.3f}%, 30m:{distance_30m:.3f}%, Vol:${volume_24h/1_000_000:.1f}M)")
        
    except Exception as e:
        logger.error(f"❌ Telegram alert hatası: {e}")


# ═══════════════════════════════════════════════════════════════
# MAIN SCANNER
# ═══════════════════════════════════════════════════════════════

def run_scanner():
    """Ana tarama döngüsü"""
    logger.info("="*70)
    logger.info("🚀 EMA Proximity Alert System Başlatılıyor...")
    logger.info("="*70)
    logger.info(f"📊 Parametreler:")
    logger.info(f"   Proximity Threshold 15m: {PROXIMITY_THRESHOLD_15M}%")
    logger.info(f"   Proximity Threshold 30m: {PROXIMITY_THRESHOLD_30M}%")
    logger.info(f"   Require Both Timeframes: {REQUIRE_BOTH_TIMEFRAMES}")
    logger.info(f"   RSI Range: {RSI_MIN}-{RSI_MAX} (Nötr bölge)")
    logger.info(f"   Min Volume 24h: ${MIN_VOLUME_24H/1_000_000:.1f}M")
    logger.info(f"   Scan Interval: {SCAN_INTERVAL}s ({SCAN_INTERVAL/60:.1f} min)")
    logger.info(f"   Alert Cooldown: {ALERT_COOLDOWN}s ({ALERT_COOLDOWN/60:.1f} min)")
    logger.info(f"   Primary TF: {PRIMARY_TF}, Secondary TF: {SECONDARY_TF}")
    logger.info("="*70)
    
    # Telegram bot başlat
    logger.info("\n📱 Telegram bot başlatılıyor...")
    if telegram_notifier.initialize_bot(config):
        logger.info("   ✅ Telegram bot hazır")
        
        # Test mesajı
        try:
            test_msg = f"""
🤖 **EMA Proximity Alert System BAŞLATILDI**

📊 **Parametreler:**
• Proximity 15m: < {PROXIMITY_THRESHOLD_15M}%
• Proximity 30m: < {PROXIMITY_THRESHOLD_30M}%
• Dual Timeframe: {REQUIRE_BOTH_TIMEFRAMES}
• RSI: {RSI_MIN}-{RSI_MAX} (Nötr bölge)
• Min Volume: ${MIN_VOLUME_24H/1_000_000:.1f}M
• Scan: Her {SCAN_INTERVAL/60:.1f} dakika
• Cooldown: {ALERT_COOLDOWN/60:.1f} dakika

✅ Manuel trading için hazır!
"""
            telegram_notifier.send_message(test_msg)
        except Exception as e:
            logger.warning(f"   ⚠️ Test mesajı gönderilemedi: {e}")
    else:
        logger.error("   ❌ Telegram bot başlatılamadı!")
        logger.error("   Alertler gönderilemeyecek!")
        return
    
    # Coin pool yükle
    logger.info("\n🔍 Coin pool yükleniyor...")
    coin_pool = get_coin_pool()
    
    if not coin_pool:
        logger.error("❌ Coin pool yüklenemedi!")
        return
    
    logger.info(f"✅ {len(coin_pool)} coin taranacak\n")
    
    scan_count = 0
    
    # Ana döngü
    while True:
        try:
            scan_count += 1
            logger.info("\n" + "="*70)
            logger.info(f"🔍 SCAN #{scan_count} BAŞLIYOR")
            logger.info("="*70)
            logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"📊 Taranacak coin: {len(coin_pool)}")
            
            alerts_sent = 0
            
            # Her coin'i tara
            for idx, symbol in enumerate(coin_pool, 1):
                try:
                    # Progress her 50 coin'de bir
                    if idx % 50 == 0:
                        logger.info(f"   Progress: {idx}/{len(coin_pool)} ({idx/len(coin_pool)*100:.1f}%)")
                    
                    # Analiz et
                    alert_data = analyze_coin(symbol)
                    
                    if alert_data:
                        # Alert gönder
                        send_alert(alert_data)
                        alerts_sent += 1
                    
                    # Rate limiting: 0.2 saniye bekle
                    time.sleep(0.2)
                    
                except Exception as coin_error:
                    logger.error(f"❌ {symbol} hatası: {coin_error}")
                    continue
            
            # Scan özeti
            logger.info("\n" + "="*70)
            logger.info(f"📊 SCAN #{scan_count} TAMAMLANDI")
            logger.info("="*70)
            logger.info(f"   Tarandı: {len(coin_pool)} coin")
            logger.info(f"   Alert: {alerts_sent} bildirim gönderildi")
            logger.info(f"   Aktif alerts: {len(alerted_coins)} coin cooldown'da")
            logger.info(f"   Sonraki scan: {SCAN_INTERVAL}s ({SCAN_INTERVAL/60:.1f} min)")
            logger.info("="*70 + "\n")
            
            # Bir sonraki scan'e kadar bekle
            logger.info(f"⏳ {SCAN_INTERVAL}s bekleniyor...")
            time.sleep(SCAN_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("\n\n⌨️  Keyboard interrupt - Kapatılıyor...")
            break
            
        except Exception as e:
            logger.error(f"❌ Scanner hatası: {e}", exc_info=True)
            logger.warning("⚠️ 60s bekleyip tekrar denenecek...")
            time.sleep(60)
    
    logger.info("\n✅ EMA Proximity Alert System kapatıldı.")


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    try:
        run_scanner()
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
