# src/main_orchestrator.py

import logging
import time
import schedule
import sys
import os
import threading
from datetime import datetime, timezone  # YENİ: datetime import eklendi
from binance.exceptions import BinanceAPIException, BinanceRequestException
import pandas as pd

# --- Proje Kök Dizinini Ayarla ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path: sys.path.append(project_root)
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path: sys.path.append(src_path)

# --- Loglamayı Ayarla ---
try:
    from src import config
    log_level_enum = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    log_file_path = getattr(config, 'LOG_FILE', os.path.join(project_root, 'logs', 'chimerabot.log'))
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir): os.makedirs(log_dir); print(f"Log dizini oluşturuldu: {log_dir}")
    logging.basicConfig(level=log_level_enum,
                        format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s',
                        handlers=[logging.FileHandler(log_file_path, mode='a', encoding='utf-8'),
                                  logging.StreamHandler(sys.stdout)])
    logger = logging.getLogger(__name__)
    logger.info(f"--- ChimeraBot v{getattr(config, 'BOT_VERSION', '?.?')} Başlatılıyor ---")
except ImportError: print("KRİTİK HATA: src/config.py bulunamadı!"); sys.exit(1)
except Exception as e: print(f"KRİTİK HATA: Loglama ayarlanırken hata: {e}"); sys.exit(1)

# --- Modülleri ve Veritabanını İçe Aktar ---
try:
    from src.data_fetcher import binance_fetcher
    from src.technical_analyzer import indicators, strategies
    from src.alpha_engine import analyzer as alpha_analyzer
    from src.alpha_engine import sentiment_analyzer
    from src.risk_manager import calculator as risk_calculator
    from src.risk_manager.dynamic_risk import DynamicRiskCalculator
    from src.risk_manager.kelly_calculator import KellyPositionSizer
    from src.trade_manager import manager as trade_manager
    from src.notifications import telegram as telegram_notifier
    from src.database.models import db_session, init_db, OpenPosition, AlphaCache, get_db_session
    from src.data_fetcher.realtime_manager import RealTimeDataManager
    from src.utils import performance_monitor
    from src.trade_manager.executor import initialize_executor, get_executor
    from src.trade_manager.capital_manager import initialize_capital_manager
    from src.trade_manager.margin_tracker import create_margin_tracker
    from src.utils.emergency_stop import check_emergency_stop, is_emergency_stop_active
except ImportError as e:
    logger.critical(f"❌ Gerekli modül veya veritabanı import edilemedi: {e}", exc_info=True)
    logger.critical("   Dosya yapısını, __init__.py'ları ve SQLAlchemy/kütüphane bağımlılıklarını kontrol edin.")
    sys.exit(1)


# --- Global Değişkenler ---
rate_limit_status = {'binance_delay_multiplier': 1.0, 'last_binance_error_time': 0}
open_positions_lock = threading.Lock()
rate_limit_lock = threading.Lock()  # YENİ: Rate limit için thread-safe erişim
stop_event = threading.Event()

# v5.0: Executor instance (global)
executor = None
capital_manager = None

# v8.1: Rotating coin scan offset (tüm coinlerin taranması için)
# v9.1: DB'den yükle (restart'ta kaybolmasın)
def get_coin_scan_offset():
    """Rotating scan offset'ini DB'den yükle veya 0 döndür"""
    try:
        db = db_session()
        try:
            cache_record = db.query(AlphaCache).filter(AlphaCache.key == 'coin_scan_offset').first()
            if cache_record and cache_record.value:
                offset = int(cache_record.value)
                logger.info(f"🔄 Coin scan offset DB'den yüklendi: {offset}")
                return offset
        except Exception as e:
            logger.warning(f"Offset yüklenemedi: {e}")
        finally:
            db_session.remove()
    except:
        pass
    return 0

def save_coin_scan_offset(offset):
    """Rotating scan offset'ini DB'ye kaydet"""
    try:
        db = db_session()
        try:
            cache_record = db.query(AlphaCache).filter(AlphaCache.key == 'coin_scan_offset').first()
            if cache_record:
                cache_record.value = offset
                db.merge(cache_record)
            else:
                new_cache = AlphaCache(key='coin_scan_offset', value=offset)
                db.add(new_cache)
            db.commit()
            logger.debug(f"🔄 Coin scan offset DB'ye kaydedildi: {offset}")
        except Exception as e:
            logger.error(f"Offset kaydedilemedi: {e}")
            db.rollback()
        finally:
            db_session.remove()
    except:
        pass

coin_scan_offset = get_coin_scan_offset()  # İlk yüklemede DB'den al

# --- Öncelik Sıralama İskeleti (geleceğe hazır) ---
def rank_coins_by_priority(symbols: list, config) -> list:
    """
    Basit önceliklendirme iskeleti (stub):
    - Şimdilik alfabetik/varolan sıralamayı korur (deterministik davranış)
    - Gelecekte: 24h USDT hacmi, ATR/price (volatilite), son X saatte sinyal geçmişi skorlanabilir.
    - Dışarıdan veri çekme eklenene kadar minimal tutuluyor.
    """
    try:
        adaptive = getattr(config, 'ADAPTIVE_CHUNK_ENABLED', True)
        if not adaptive or not symbols:
            return symbols

        # 24h ticker verisini çek (quoteVolume ve priceChangePercent için)
        tickers = binance_fetcher.get_all_24h_ticker_data()
        if not tickers:
            return symbols

        # Map: symbol -> {quoteVolume, priceChangePercent}
        meta = {}
        for t in tickers:
            sym = t.get('symbol')
            if not sym:
                continue
            try:
                qv = float(t.get('quoteVolume', 0.0) or 0.0)
            except Exception:
                qv = 0.0
            try:
                pcp = float(t.get('priceChangePercent', 0.0) or 0.0)
            except Exception:
                pcp = 0.0
            meta[sym] = {'qv': qv, 'pcp': pcp}

        # Skor: log10(quoteVolume+1) + 0.25*abs(priceChange%)
        def score(sym: str) -> float:
            d = meta.get(sym, None)
            if not d:
                return 0.0
            from math import log10
            return log10(d['qv'] + 1.0) + 0.25 * abs(d['pcp'])

        # Sadece gelen liste içindekileri skora göre sırala
        ranked = sorted(symbols, key=lambda s: score(s), reverse=True)
        return ranked
    except Exception as e:
        logger.debug(f"Öncelik sıralaması yapılamadı: {e}")
        return symbols

# --- Rate Limit Ayarları ---
def adjust_rate_limit(increase: bool = True):
    """
    Rate limit durumunda delay'i artırır veya azaltır.
    Thread-safe implementasyon.
    """
    global rate_limit_status
    
    with rate_limit_lock:
        current_multiplier = rate_limit_status['binance_delay_multiplier']
        
        if increase:
            new_multiplier = min(current_multiplier * 1.5, 16.0)
            rate_limit_status['binance_delay_multiplier'] = new_multiplier
            rate_limit_status['last_binance_error_time'] = time.time()
            logger.warning(f"⚠️ Rate limit artırıldı: {current_multiplier:.1f}x -> {new_multiplier:.1f}x")
        else:
            # Azaltma: 5 dakika hata yoksa yarıya düş
            last_error_time = rate_limit_status.get('last_binance_error_time', 0)
            if last_error_time > 0 and (time.time() - last_error_time) > 300:
                new_multiplier = max(current_multiplier * 0.9, 1.0)
                if new_multiplier < current_multiplier:
                    rate_limit_status['binance_delay_multiplier'] = new_multiplier
                    logger.info(f"✅ Rate limit azaltıldı: {current_multiplier:.1f}x -> {new_multiplier:.1f}x")
                    if new_multiplier == 1.0:
                        rate_limit_status['last_binance_error_time'] = 0

# --- Yardımcı Fonksiyonlar ---
def get_btc_correlation(symbol: str, correlation_matrix: dict) -> float:
    """
    Verilen symbol için BTC ile korelasyon skorunu döndürür.
    
    Args:
        symbol: Kontrol edilecek sembol (örn: 'PEPEUSDT')
        correlation_matrix: AlphaCache'den yüklenen korelasyon matrisi
    
    Returns:
        float: Korelasyon skoru (-1.0 ile 1.0 arası), veri yoksa 0.0
    """
    if not correlation_matrix:
        return 0.0
    
    try:
        # DataFrame formatındaki korelasyon matrisinden BTC sütununu oku
        if 'BTCUSDT' in correlation_matrix and symbol in correlation_matrix['BTCUSDT']:
            corr_value = correlation_matrix['BTCUSDT'][symbol]
            return abs(float(corr_value))  # Mutlak değer (negatif korelasyon da önemli)
        else:
            return 0.0
    except Exception as e:
        logger.warning(f"Korelasyon skoru okunamadı ({symbol}): {e}")
        return 0.0

# --- Ana Tarama Fonksiyonu ---
def main_scan_cycle():
    """
    Ana tarama döngüsü - regime detection ve sinyal üretimi.
    Thread-safe ve hata korumalı implementasyon.
    """
    logger.info("====== ANA TARAMA DÖNGÜSÜ BAŞLADI ======")
    
    # Rate limit azaltma kontrolü
    adjust_rate_limit(increase=False)
    
    # Emergency Stop kontrolü
    can_trade, stop_reason = check_emergency_stop()
    if not can_trade:
        logger.critical(f"🚨 EMERGENCY STOP AKTİF: {stop_reason}")
        logger.critical("⛔ Yeni pozisyon açılmayacak! EMERGENCY_STOP.flag dosyasını silin ve botu yeniden başlatın.")
        return
    
    try:
        # --- Adım 1: Global Rejim Belirle ---
        logger.info("--- Adım 1: Global Rejim Belirleniyor ---")
        btc_1d_raw = binance_fetcher.get_binance_klines(symbol='BTCUSDT', interval='1d', limit=300)
        btc_4h_raw = binance_fetcher.get_binance_klines(symbol='BTCUSDT', interval='4h', limit=300)
        global_btc_regime = 'STOP'
        
        if btc_1d_raw is not None and not btc_1d_raw.empty:
            btc_1d_indicators = indicators.calculate_indicators(btc_1d_raw.copy())
            btc_4h_indicators = indicators.calculate_indicators(btc_4h_raw.copy()) if btc_4h_raw is not None else None
            
            if not btc_1d_indicators.empty and 'adx14' in btc_1d_indicators.columns and not pd.isna(btc_1d_indicators['adx14'].iloc[-1]):
                try:
                    global_btc_regime = strategies.determine_regime(btc_1d_indicators, btc_4h_indicators)
                    logger.info(f"Global BTC Rejimi: '{global_btc_regime}' olarak belirlendi.")
                    # --- Rejim Yumuşatma (Smoothing) ---
                    try:
                        smoothing_window = getattr(config, 'REGIME_SMOOTHING_WINDOW', 5)
                        if smoothing_window > 1:
                            from collections import Counter
                            with get_db_session() as db_smooth:
                                regime_record = db_smooth.query(AlphaCache).filter(AlphaCache.key == 'regime_history').first()
                                history = []
                                if regime_record and regime_record.value:
                                    history = regime_record.value
                                history.append(global_btc_regime)
                                # Son N değeri tut
                                history = history[-smoothing_window:]
                                # Çoğunluk oyu
                                counts = Counter(history)
                                majority_regime, majority_count = counts.most_common(1)[0]
                                smoothed_regime = majority_regime
                                if smoothed_regime != global_btc_regime:
                                    logger.info(f"🔁 Rejim Yumuşatma: {global_btc_regime} -> {smoothed_regime} (window={history})")
                                global_btc_regime = smoothed_regime
                                # Kaydet
                                if regime_record:
                                    regime_record.value = history
                                    db_smooth.merge(regime_record)
                                else:
                                    from src.database.models import AlphaCache as AC
                                    db_smooth.add(AC(key='regime_history', value=history))
                            logger.debug(f"Rejim geçmişi güncellendi: {history}")
                    except Exception as smooth_err:
                        logger.warning(f"Rejim smoothing uygulanamadı: {smooth_err}")
                except Exception as e:
                    logger.error(f"Rejim belirlenirken hata: {e}", exc_info=True)
            else:
                logger.error("Rejim belirlenemedi: BTC 1D göstergeleri eksik/NaN.")
        else:
            logger.error("Rejim belirlenemedi: BTC 1D verisi çekilemedi.")
        
        # --- Adım 2: Coin Listesi ---
        logger.info("--- Adım 2: Dinamik Tarama Listesi ---")
        try:
            coin_list_mode = getattr(config, 'COIN_LIST_MODE', 'MANUAL')
            
            if coin_list_mode.upper() == 'AUTO_FUTURES':
                logger.info("📡 Coin Listesi Modu: AUTO_FUTURES (Binance Futures tüm USDT çiftleri)")
                
                cache_key = 'futures_symbols_list'
                update_interval = getattr(config, 'AUTO_FUTURES_UPDATE_HOURS', 24) * 3600
                
                # YENİ: Context manager kullan
                with get_db_session() as db:
                    cached_record = db.query(AlphaCache).filter(AlphaCache.key == cache_key).first()
                    need_update = True
                    
                    if cached_record and cached_record.value:
                        last_update = cached_record.last_updated
                        if last_update:
                            if last_update.tzinfo is None:
                                last_update = last_update.replace(tzinfo=timezone.utc)
                            age_seconds = (datetime.now(timezone.utc) - last_update).total_seconds()
                            if age_seconds < update_interval:
                                initial_list = cached_record.value
                                need_update = False
                                logger.info(f"✅ Futures listesi cache'den yüklendi ({len(initial_list)} coin, {age_seconds/3600:.1f} saat önce güncellendi)")
                    
                    if need_update:
                        initial_list = binance_fetcher.get_all_futures_usdt_symbols()
                        if initial_list:
                            if cached_record:
                                cached_record.value = initial_list
                                db.merge(cached_record)
                            else:
                                new_cache = AlphaCache(key=cache_key, value=initial_list)
                                db.add(new_cache)
                            logger.info(f"✅ Futures listesi güncellendi ve cache'e kaydedildi ({len(initial_list)} coin)")
                        else:
                            logger.error("❌ Futures listesi çekilemedi!")
                            if cached_record and cached_record.value:
                                initial_list = cached_record.value
                                logger.warning(f"⚠️ Eski cache verisi kullanılıyor ({len(initial_list)} coin)")
                            else:
                                logger.error("Cache'de de veri yok, CORRELATION_GROUPS'a dönülüyor")
                                initial_list = list(getattr(config, 'CORRELATION_GROUPS', {}).keys())
            
            else:  # MANUAL mode
                logger.info("📋 Coin Listesi Modu: MANUAL (CORRELATION_GROUPS)")
                correlation_groups = getattr(config, 'CORRELATION_GROUPS', {})
                if not correlation_groups:
                    logger.error("Config'de CORRELATION_GROUPS yok/boş.")
                    return
                initial_list = list(correlation_groups.keys())
            
            # v8.1: Rotating Queue - Tüm coinlerin taranması için
            global coin_scan_offset
            max_coins = getattr(config, 'MAX_COINS_TO_SCAN', 300)  # Havuzdan aynı anda seçilebilecek üst sınır
            chunk_size = getattr(config, 'SCAN_CHUNK_SIZE', max_coins)  # Her cycle taranacak gerçek alt küme
            enable_rotating = getattr(config, 'ENABLE_ROTATING_SCAN', True)
            
            full_pool_size = len(initial_list)
            if enable_rotating and full_pool_size > chunk_size:
                # Önceliklendirme opsiyonel: yüksek hacim / volatilite / yakın zamanda sinyal alanlar
                adaptive_enabled = getattr(config, 'ADAPTIVE_CHUNK_ENABLED', True)
                if adaptive_enabled:
                    try:
                        initial_list = rank_coins_by_priority(initial_list, config)
                        # Placeholder: Burada gerçek zamanlı hacim/ATR çekilip skorlanabilir.
                        pass
                    except Exception as prio_err:
                        logger.debug(f"Öncelik hesaplanamadı: {prio_err}")

                start_idx = coin_scan_offset % full_pool_size
                end_idx = (start_idx + chunk_size) % full_pool_size
                if end_idx > start_idx:
                    cycle_coins = initial_list[start_idx:end_idx]
                else:
                    cycle_coins = initial_list[start_idx:] + initial_list[:end_idx]

                coverage_pct = (chunk_size / full_pool_size) * 100.0
                logger.info(
                    f"� Rotating Chunk Scan: {chunk_size} coin (offset={coin_scan_offset}, kapsam={coverage_pct:.1f}% / toplam {full_pool_size})"
                )
                initial_list = cycle_coins
                coin_scan_offset += chunk_size
                save_coin_scan_offset(coin_scan_offset)
                logger.debug(f"🔄 Yeni offset kaydedildi: {coin_scan_offset}")
            elif full_pool_size > chunk_size:
                logger.warning(f"⚠️ Liste büyük ({full_pool_size}), chunk_size={chunk_size}, Rotating KAPALI → ilk {chunk_size} coin")
                initial_list = initial_list[:chunk_size]
            
            if not initial_list:
                logger.error("Başlangıç coin listesi boş!")
                return
            
            logger.info(f"📊 Bu cycle taranacak coin sayısı: {len(initial_list)} (Pool={full_pool_size}, Chunk={chunk_size})")
            
            # Pre-Screening Filtresi
            min_volume = getattr(config, 'PRE_SCREEN_MIN_VOLUME_USD', 5_000_000)
            min_price_change = getattr(config, 'PRE_SCREEN_MIN_PRICE_CHANGE_PERCENT', 1.5)
            filter_mode = getattr(config, 'PRE_SCREEN_FILTER_MODE', 'OR')
            
            logger.info(f"Pre-screening başlıyor: {len(initial_list)} coin → Minimum Hacim: ${min_volume:,.0f}, Minimum Değişim: %{min_price_change}, Mod: {filter_mode}")
            
            all_tickers = binance_fetcher.get_all_24h_ticker_data()
            scan_list = []
            
            if all_tickers:
                ticker_dict = {t['symbol']: t for t in all_tickers}
                
                for symbol in initial_list:
                    ticker = ticker_dict.get(symbol)
                    if not ticker:
                        logger.debug(f"   {symbol}: 24h ticker verisi yok, atlıyor.")
                        continue
                    
                    try:
                        volume_usd = float(ticker.get('quoteVolume', 0))
                        price_change_pct = abs(float(ticker.get('priceChangePercent', 0)))
                        
                        volume_ok = volume_usd >= min_volume
                        price_change_ok = price_change_pct >= min_price_change
                        
                        if filter_mode.upper() == 'OR':
                            passed = volume_ok or price_change_ok
                        else:
                            passed = volume_ok and price_change_ok
                        
                        if passed:
                            scan_list.append(symbol)
                            reason = []
                            if volume_ok: reason.append(f"${volume_usd:,.0f} hacim")
                            if price_change_ok: reason.append(f"%{price_change_pct:.2f} değişim")
                            logger.debug(f"   ✅ {symbol}: {' + '.join(reason)} → Geçti")
                        else:
                            logger.debug(f"   ❌ {symbol}: ${volume_usd:,.0f} hacim, %{price_change_pct:.2f} değişim → Filtrelendi")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"   {symbol}: Ticker verisi parse edilemedi: {e}")
                        continue
                
                logger.info(f"✅ Pre-screening tamamlandı: {len(initial_list)} → {len(scan_list)} aktif coin taranacak")
            else:
                logger.warning("⚠️ 24h ticker verisi alınamadı, filtreleme atlanıyor, tüm liste kullanılacak.")
                scan_list = initial_list
            
            if not scan_list:
                logger.warning("Pre-screening sonrası hiç coin kalmadı! Tarama yapılmayacak.")
                return

            # --- Two-Stage Pipeline: Stage-1 (hafif) aday kısıtlaması ---
            if getattr(config, 'ENABLE_TWO_STAGE_PIPELINE', False) and all_tickers:
                try:
                    stage1_min_vol_ratio = getattr(config, 'STAGE1_MIN_VOL_RATIO', 1.05)
                    stage1_min_momentum = getattr(config, 'STAGE1_MIN_MOMENTUM_SCORE', 0.4)
                    stage1_max = getattr(config, 'STAGE1_MAX_CANDIDATES', 25)

                    # Basit momentum skoru: normalize edilmiş fiyat değişimi + hacim oranı katkısı
                    # Hacim oranı ~ (24h quoteVolume / min_volume)
                    stage1_scores = []
                    for sym in scan_list:
                        t = ticker_dict.get(sym)
                        if not t:
                            continue
                        try:
                            price_change_pct = abs(float(t.get('priceChangePercent', 0.0)))
                            volume_usd = float(t.get('quoteVolume', 0.0))
                            vol_ratio = volume_usd / max(min_volume, 1.0)
                            momentum_score = (price_change_pct / 10.0) * 0.6 + min(vol_ratio, 3.0) * 0.4
                            if vol_ratio >= stage1_min_vol_ratio and momentum_score >= stage1_min_momentum:
                                stage1_scores.append((sym, momentum_score, vol_ratio, price_change_pct))
                        except Exception:
                            continue

                    # Skora göre sırala ve limitle
                    stage1_scores.sort(key=lambda x: (-x[1], -x[3]))
                    limited = stage1_scores[:stage1_max]
                    new_scan_list = [s[0] for s in limited]

                    logger.info(f"🪄 Stage-1 Pipeline: {len(scan_list)} → {len(new_scan_list)} adaya indirildi (max={stage1_max})")
                    logger.debug(f"Stage-1 Top Adaylar: {limited[:5]}")
                    scan_list = new_scan_list if new_scan_list else scan_list
                except Exception as stage1_err:
                    logger.warning(f"Stage-1 pipeline uygulanamadı: {stage1_err}")
                
        except Exception as e:
            logger.error(f"Coin listesi/pre-screening hatası: {e}", exc_info=True)
            return

        # --- Adım 3: Alfa Verilerini Güncelle ---
        logger.info("--- Adım 3: Alfa Verileri (Duygu ve Korelasyon) Güncelleme ---")
        try:
            cache_updated = sentiment_analyzer.update_sentiment_cache(config)
            if cache_updated:
                logger.info("Alfa cache (duygu/korelasyon) güncellendi ve DB'ye kaydedildi.")
            else:
                logger.info("Alfa/Duygu verileri güncel, güncelleme atlandı.")
        except Exception as e:
            logger.error(f"Alfa/Duygu verileri güncellenirken hata: {e}", exc_info=True)

        # --- YENİ: Korelasyon Matrisini Yükle (Adım 4'ten önce) ---
        correlation_record = None
        try:
            with get_db_session() as db_corr:
                corr_key = getattr(sentiment_analyzer, 'CORRELATION_MATRIX_KEY', 'correlation_matrix')
                corr_cache = db_corr.query(AlphaCache).filter(AlphaCache.key == corr_key).first()
                if corr_cache and corr_cache.value:
                    correlation_record = corr_cache.value
                    logger.info("✅ Korelasyon Matrisi yüklendi (rejim seçimi için)")
                else:
                    logger.warning("⚠️ Korelasyon Matrisi bulunamadı, tüm coinler kendi rejimini kullanacak")
        except Exception as e:
            logger.error(f"Korelasyon matrisi yüklenemedi: {e}", exc_info=True)
        
    # --- Adım 4: Coin Analizi ve Aday Sinyal Toplama ---
        logger.info(f"--- Adım 4: {len(scan_list)} Coin Analiz Ediliyor (Dinamik Rejim) ---")

        # 🆕 v10.5: 1H EMA Mode Check (15m devre dışı)
        ema_mode_enabled = getattr(config, 'ENABLE_1H_EMA_MODE', False)
        fast_mode_enabled = getattr(config, 'ENABLE_15M_FAST_MODE', False) and not ema_mode_enabled  # 1H aktifse 15m devre dışı
        
        if ema_mode_enabled:
            logger.info("🎯 1H EMA CROSSOVER MODE AKTIF - EMA5 x EMA20 kesişim stratejisi")
            logger.info(f"   Parametreler: TF=1h, Leverage={getattr(config, 'EMA_MODE_LEVERAGE', 10)}x, Margin=${getattr(config, 'EMA_MODE_BASE_SIZE_USD', 10)}")
            logger.info(f"   TP/SL: Margin ${getattr(config, 'EMA_MODE_BASE_SIZE_USD', 10)} → TP=${getattr(config, 'EMA_MODE_TP_MARGIN', 14)} / SL=${getattr(config, 'EMA_MODE_SL_MARGIN', 9)}")
        elif fast_mode_enabled:
            logger.info("🚀 15M FAST MODE AKTIF - Mehmet Küçük Stratejisi kullanılıyor")
            logger.info(f"   Parametreler: TF=15m, TP=+{getattr(config, 'FAST_MODE_TP_PERCENT', 25)}%, SL=-{getattr(config, 'FAST_MODE_SL_PERCENT', 5)}%, Leverage={getattr(config, 'FAST_MODE_LEVERAGE', 10)}x")

        # --- Adım 4: Coin Analizi ve Aday Sinyal Toplama ---
        logger.info(f"--- Adım 4: {len(scan_list)} Coin Analiz Ediliyor (Dinamik Rejim) ---")
        candidate_signals = []
        scan_delay = getattr(config, 'SCAN_DELAY_SECONDS', 0.5)
        scalp_tf = getattr(config, 'SCALP_TIMEFRAME', '15m')

        for i, symbol in enumerate(scan_list):
            if stop_event.is_set():
                logger.info("Kapanış sinyali alındı, tarama durduruluyor...")
                break
            
            logger.info(f"--- [{i+1}/{len(scan_list)}] {symbol} Analiz Başladı ---")
            current_delay = scan_delay * rate_limit_status['binance_delay_multiplier']
            time.sleep(current_delay)

            try:
                # 🆕 v10.5: 1H EMA Mode - Sadece 1H veri çek
                if ema_mode_enabled:
                    ema_tf = getattr(config, 'EMA_MODE_TIMEFRAME', '1h')
                    df_1h = binance_fetcher.get_binance_klines(symbol=symbol, interval=ema_tf, limit=100)
                    
                    if df_1h is None or df_1h.empty:
                        logger.warning(f"{symbol}: 1H veri çekilemedi, atlanıyor.")
                        continue
                    
                    # Göstergeleri hesapla (EMA5, EMA20)
                    df_1h = indicators.calculate_indicators(df_1h.copy())
                    
                    # EMA Crossover Stratejisini uygula
                    technical_signal = None
                    try:
                        technical_signal = strategies.find_ema_crossover_1h_signal(df_1h, config)
                    except Exception as e:
                        logger.error(f"{symbol} EMA crossover stratejisi hatası: {e}", exc_info=True)
                    
                    if technical_signal:
                        signal_direction = technical_signal['direction']
                        entry_price = technical_signal['entry_price']
                        sl_price = technical_signal['sl_price']
                        tp_price = technical_signal['tp_price']
                        rr_ratio = technical_signal['rr_ratio']
                        crossover_type = technical_signal['crossover_type']
                        
                        logger.info(f"✅ {symbol}: {crossover_type} EMA CROSSOVER → {signal_direction}")
                        logger.info(f"   Entry={entry_price:.4f}, SL={sl_price:.4f}, TP={tp_price:.4f}, R:R={rr_ratio:.2f}")
                        
                        # Minimum R:R kontrolü
                        min_rr = getattr(config, 'MIN_RR_RATIO', 1.0)
                        if rr_ratio >= min_rr:
                            # Kalite notu (1H EMA için varsayılan B grade)
                            quality_grade = 'B'
                            
                            candidate_signals.append({
                                'symbol': symbol,
                                'strategy': 'EMA_CROSSOVER_1H',
                                'direction': signal_direction,
                                'entry_price': entry_price,
                                'sl_price': sl_price,
                                'tp_price': tp_price,
                                'partial_tp_1_price': None,  # 1H EMA mode: tek TP
                                'rr_ratio': rr_ratio,
                                'quality_grade': quality_grade,
                                'signal_strength': 85.0,  # EMA crossover güçlü sinyal
                                'atr': technical_signal.get('atr'),
                                'fng_index_at_signal': None,
                                'news_sentiment_at_signal': None,
                                'reddit_sentiment_at_signal': None,
                                'google_trends_score_at_signal': None,
                                'rr_tier': 'PRIMARY',
                                'nan_penalty_count': 0,
                                'crossover_type': crossover_type
                            })
                        else:
                            logger.info(f"   REJECTED: R:R çok düşük ({rr_ratio:.2f} < {min_rr})")
                    
                    continue  # 1H EMA mode: multi-timeframe analizi atlayalım
                
                # 🆕 v10.0: 15m Fast Mode - Sadece 15m veri çek
                elif fast_mode_enabled:
                    fast_tf = getattr(config, 'FAST_MODE_TIMEFRAME', '15m')
                    df_15m = binance_fetcher.get_binance_klines(symbol=symbol, interval=fast_tf, limit=100)
                    
                    if df_15m is None or df_15m.empty:
                        logger.warning(f"{symbol}: 15m veri çekilemedi, atlanıyor.")
                        continue
                    
                    # Göstergeleri hesapla
                    df_15m = indicators.calculate_indicators(df_15m.copy())
                    
                    # Mehmet Küçük Stratejisini uygula
                    technical_signal = None
                    try:
                        technical_signal = strategies.find_mehmet_kucuk_signal(df_15m, config)
                    except Exception as e:
                        logger.error(f"{symbol} Mehmet Küçük stratejisi hatası: {e}", exc_info=True)
                    
                    if technical_signal:
                        signal_strength = technical_signal.get('signal_strength', 80.0)
                        signal_direction = technical_signal['direction']
                        current_price = df_15m.iloc[-1]['close']
                        
                        logger.info(f"✅ {symbol}: MEHMET KÜÇÜK {signal_direction} sinyali (Güç: {signal_strength:.1f}/100)")
                        
                        # Fast Mode: Sabit SL/TP
                        tp_percent = getattr(config, 'FAST_MODE_TP_PERCENT', 25.0) / 100.0
                        sl_percent = getattr(config, 'FAST_MODE_SL_PERCENT', 5.0) / 100.0
                        
                        if signal_direction == 'LONG':
                            tp_price = current_price * (1 + tp_percent)
                            sl_price = current_price * (1 - sl_percent)
                        else:  # SHORT
                            tp_price = current_price * (1 - tp_percent)
                            sl_price = current_price * (1 + sl_percent)
                        
                        # RR hesapla
                        rr = risk_calculator.calculate_rr(current_price, sl_price, tp_price, signal_direction)
                        
                        if rr and rr >= 0.5:  # Fast mode için düşük RR yeterli (TP/SL=25/5=5.0 RR teorik)
                            logger.info(f"   R:R = {rr:.2f} (TP={tp_price:.6f}, SL={sl_price:.6f})")
                            
                            # Kalite notu (basitleştirilmiş, fast mode için her zaman B grade)
                            quality_grade = 'B'
                            
                            candidate_signals.append({
                                'symbol': symbol,
                                'strategy': 'MEHMET_KUCUK',
                                'direction': signal_direction,
                                'entry_price': current_price,
                                'sl_price': sl_price,
                                'tp_price': tp_price,
                                'partial_tp_1_price': None,  # Fast mode: tek TP
                                'rr_ratio': rr,
                                'quality_grade': quality_grade,
                                'signal_strength': signal_strength,
                                'atr': None,  # Fast mode ATR kullanmıyor
                                'fng_index_at_signal': None,
                                'news_sentiment_at_signal': None,
                                'reddit_sentiment_at_signal': None,
                                'google_trends_score_at_signal': None,
                                'rr_tier': 'PRIMARY',
                                'nan_penalty_count': 0
                            })
                        else:
                            logger.info(f"   REJECTED: R:R çok düşük ({rr:.2f if rr else 'None'})")
                    
                    continue  # Fast mode: multi-timeframe analizi atlayalım
                
                # ESKİ SİSTEM (fast_mode_enabled=False): Multi-timeframe analiz
                # Gerekli tüm zaman dilimi verilerini çek
                df_1d = binance_fetcher.get_binance_klines(symbol=symbol, interval='1d', limit=300)
                df_4h = binance_fetcher.get_binance_klines(symbol=symbol, interval='4h', limit=300)
                df_1h = binance_fetcher.get_binance_klines(symbol=symbol, interval='1h', limit=300)
                
                df_scalp = None
                if scalp_tf not in ['1h', '4h', '1d']:
                    df_scalp = binance_fetcher.get_binance_klines(symbol=symbol, interval=scalp_tf, limit=100)

                if df_1d is None or df_4h is None or df_1h is None:
                    logger.warning(f"{symbol}: Gerekli TFs çekilemedi, atlanıyor.")
                    continue
                
                # Göstergeleri hesapla
                df_1d = indicators.calculate_indicators(df_1d.copy())
                df_4h = indicators.calculate_indicators(df_4h.copy())
                df_1h = indicators.calculate_indicators(df_1h.copy())
                
                # Scalp DataFrame referansını güncelle
                if scalp_tf == '1h':
                    df_scalp = df_1h
                elif scalp_tf == '4h':
                    df_scalp = df_4h
                elif scalp_tf == '1d':
                    df_scalp = df_1d
                else:
                    df_scalp = indicators.calculate_indicators(df_scalp.copy())

                # Dinamik Strateji Seçimi (v7.0: KORELASYON BAZLI)
                coin_specific_strategy = 'STOP'
                try:
                    # Korelasyon matrisini kontrol et (dış scope'dan gelen correlation_record)
                    btc_corr = get_btc_correlation(symbol, correlation_record)
                    correlation_threshold = getattr(config, 'BTC_CORRELATION_THRESHOLD', 0.7)
                    
                    if btc_corr >= correlation_threshold:
                        # YÜKSEK KORELASYON: BTC'nin rejimini kullan
                        coin_specific_strategy = global_btc_regime
                        logger.info(f"   {symbol} → BTC rejimi kullanılıyor (Korelasyon: {btc_corr:.2f})")
                    else:
                        # DÜŞÜK KORELASYON: Kendi verisiyle rejim belirle
                        if not df_1d.empty and 'adx14' in df_1d.columns and not pd.isna(df_1d['adx14'].iloc[-1]):
                            coin_specific_strategy = strategies.determine_regime(df_1d, df_4h)
                            logger.info(f"   {symbol} → Kendi rejimi: {coin_specific_strategy} (Korelasyon: {btc_corr:.2f})")
                        else:
                            # 1D veri yoksa 4H'den dene
                            logger.warning(f"{symbol} için 1D verisi yetersiz, 4H'den rejim belirleniyor...")
                            coin_specific_strategy = strategies.determine_regime(df_4h, None)
                    
                except Exception as e:
                    logger.error(f"{symbol} için rejim belirlenirken hata: {e}")
                    continue

                # NaN Kontrolü + Tolerans
                data_valid = True
                nan_reason = []
                nan_penalty_count = 0
                tol_enabled = getattr(config, 'NAN_TOLERANCE_ENABLED', False)
                max_nan_allowed = getattr(config, 'MAX_NAN_INDICATORS_ALLOWED', 0)
                required_cols = getattr(config, 'STRATEGY_REQUIRED_INDICATORS', {}).get(coin_specific_strategy, {})
                dfs = {'1d': df_1d, '4h': df_4h, '1h': df_1h, scalp_tf: df_scalp}
                
                for tf_name, df in dfs.items():
                    if tf_name not in required_cols:
                        continue
                    if df is None or df.empty or len(df) < 2:
                        data_valid = False
                        nan_reason.append(f"{tf_name} yetersiz veri")
                        continue
                    
                    last_row = df.iloc[-1]
                    cols_to_check = required_cols.get(tf_name, [])
                    missing = [c for c in cols_to_check if c not in df.columns]
                    nans = [c for c in cols_to_check if c in last_row and pd.isna(last_row[c])]
                    
                    if missing or nans:
                        issue_count = len(missing) + len(nans)
                        if tol_enabled and issue_count > 0:
                            nan_penalty_count += issue_count
                            nan_reason.append(f"{tf_name} tolerans: eksik={len(missing)}, NaN={len(nans)}")
                        else:
                            data_valid = False
                            if missing:
                                nan_reason.append(f"{tf_name} eksik: {','.join(missing)}")
                            if nans:
                                nan_reason.append(f"{tf_name} NaN: {','.join(nans)}")
                
                if tol_enabled and data_valid:
                    if nan_penalty_count > max_nan_allowed:
                        data_valid = False
                        nan_reason.append(f"Toplam eksik/NaN {nan_penalty_count} > izin verilen {max_nan_allowed}")

                if not data_valid:
                    logger.warning(f"{symbol}: Veri kontrolü başarısız ({coin_specific_strategy}): {'; '.join(nan_reason)}")
                    continue

                # Stratejiyi Uygula
                technical_signal = None
                try:
                    if coin_specific_strategy == 'PULLBACK':
                        technical_signal = strategies.find_pullback_signal(df_1d, df_4h, df_1h, config)
                    elif coin_specific_strategy == 'MEAN_REVERSION':
                        # v9.0: 1D eklendi
                        technical_signal = strategies.find_mean_reversion_signal(df_1d, df_4h, df_1h, config)
                    elif coin_specific_strategy == 'BREAKOUT':
                        # v9.0: 1D ve 4H eklendi
                        technical_signal = strategies.find_breakout_signal(df_1d, df_4h, df_1h, config)
                    elif coin_specific_strategy == 'ADVANCED_SCALP':
                        # v9.0: 1D, 4H, 1H eklendi
                        technical_signal = strategies.find_advanced_scalp_signal(df_1d, df_4h, df_1h, df_scalp, config)
                except Exception as e:
                    logger.error(f"{symbol} strateji hatası: {e}", exc_info=True)

                if technical_signal:
                    signal_strength = technical_signal.get('signal_strength', 50.0)  # Default: 50
                    logger.info(f"✅ {symbol}: Teknik {coin_specific_strategy} {technical_signal['direction']} sinyali bulundu (Güç: {signal_strength:.1f}/100).")
                    
                    # SL/TP hesaplama için doğru DataFrame seç
                    df_levels = None
                    current_price = 0.0
                    current_atr = 0.0
                    
                    if coin_specific_strategy in ['ADVANCED_SCALP', 'BREAKOUT']:
                        df_levels = df_1h
                        current_price = df_1h.iloc[-1]['close']
                        current_atr = df_1h.iloc[-1]['atr14']
                    elif coin_specific_strategy == 'MEAN_REVERSION':
                        df_levels = df_4h
                        current_price = df_4h.iloc[-1]['close']
                        current_atr = df_4h.iloc[-1]['atr14']
                    elif coin_specific_strategy == 'PULLBACK':
                        df_levels = df_1h
                        current_price = df_1h.iloc[-1]['close']
                        current_atr = df_1h.iloc[-1]['atr14']
                    
                    if df_levels is None or pd.isna(current_price) or current_price <= 0 or pd.isna(current_atr) or current_atr <= 0:
                        logger.warning(f"   {symbol}: Geçersiz fiyat/ATR (Fiyat: {current_price}, ATR: {current_atr}), SL/TP hesaplanamıyor.")
                        continue

                    signal_direction = technical_signal['direction']
                    
                    # v9.2 SMART SL/TP hesaplama
                    sl_tp_method = getattr(config, 'SL_TP_METHOD', 'SMART')
                    partial_tp_1_price = None
                    
                    if sl_tp_method == 'SMART':
                        # YENİ: Hibrit sistem (ATR + Fibonacci + Swing Levels)
                        from src.risk_manager.smart_sl_tp import calculate_smart_sl_tp
                        sl_tp = calculate_smart_sl_tp(current_price, signal_direction, df_levels, config, current_atr)
                        
                        # Fallback: SMART başarısız olursa ATR kullan
                        if sl_tp is None:
                            logger.warning(f"   {symbol}: SMART sistem başarısız, ATR'ye düşülüyor")
                            sl_tp = risk_calculator.calculate_dynamic_sl_tp(current_price, current_atr, signal_direction, config, strategy=coin_specific_strategy)
                    
                    elif sl_tp_method == 'PERCENTAGE':
                        # Yüzde bazlı (volatilite uyumlu - v9.3)
                        sl_tp = risk_calculator.calculate_percentage_sl_tp(current_price, signal_direction, config, current_atr)
                    
                    elif sl_tp_method == 'ATR':
                        # ATR bazlı (volatilite uyumlu)
                        sl_tp = risk_calculator.calculate_dynamic_sl_tp(current_price, current_atr, signal_direction, config, strategy=coin_specific_strategy)
                    
                    else:
                        # Varsayılan: SMART
                        logger.warning(f"   Bilinmeyen SL_TP_METHOD: {sl_tp_method}, SMART kullanılıyor")
                        from src.risk_manager.smart_sl_tp import calculate_smart_sl_tp
                        sl_tp = calculate_smart_sl_tp(current_price, signal_direction, df_levels, config, current_atr)
                    
                    if sl_tp:
                        sl_price = sl_tp['sl_price']
                        tp_price = sl_tp['tp_price']
                        partial_tp_1_price = sl_tp.get('partial_tp_1_price')
                        
                        min_rr_base = getattr(config, 'MIN_RR_RATIO', 2.0)
                        rr = risk_calculator.calculate_rr(current_price, sl_price, tp_price, signal_direction)

                        # Rejim adaptif R:R eşiği
                        effective_min_rr = min_rr_base
                        try:
                            if getattr(config, 'ADAPTIVE_THRESHOLDS_ENABLED', False):
                                rr_by_regime = getattr(config, 'RR_THRESHOLDS_BY_REGIME', {})
                                regime_rr = rr_by_regime.get(coin_specific_strategy, min_rr_base)
                                effective_min_rr = max(min_rr_base, regime_rr)
                        except Exception:
                            effective_min_rr = min_rr_base
                        
                        if rr is not None and rr >= effective_min_rr:
                            logger.info(f"   PASSED R:R Check! ({rr:.2f} >= {effective_min_rr})")
                            
                            # Kalite notu hesaplama
                            quality_grade = 'C'
                            fng_score = 'N/A'
                            news_score = 'N/A'
                            news_score_val = None
                            sentiment_scores = None
                            
                            try:
                                quality_grade = alpha_analyzer.calculate_quality_grade(symbol, config, signal_direction)
                                sentiment_scores = sentiment_analyzer.get_sentiment_scores(symbol, config)
                                fng_score = sentiment_scores.get('fng_index', 'N/A')
                                news_score_val = sentiment_scores.get('news_sentiment')
                                news_score = f"{news_score_val:.3f}" if news_score_val is not None else 'N/A'
                                logger.info(f"   Hesaplanan Kalite Notu: {quality_grade}")
                            except Exception as e:
                                logger.error(f"   Kalite notu hatası: {e}", exc_info=True)
                                quality_grade = 'C'
                                fng_score = 'HATA'
                                news_score = 'HATA'
                            
                            logger.info(f"   Alfa Detayları: F&G={fng_score}, Haber={news_score} -> Kalite={quality_grade}")
                            
                            # ATR değerini signal'a ekle
                            atr_value = None
                            if 'atr14' in df_1h.columns and not pd.isna(df_1h.iloc[-1]['atr14']):
                                atr_value = df_1h.iloc[-1]['atr14']

                            candidate_signals.append({
                                'symbol': symbol,
                                'strategy': coin_specific_strategy,
                                'direction': signal_direction,
                                'entry_price': current_price,
                                'sl_price': sl_price,
                                'tp_price': tp_price,
                                'partial_tp_1_price': partial_tp_1_price,  # YENİ: Partial TP fiyatı
                                'rr_ratio': rr,
                                'quality_grade': quality_grade,
                                'signal_strength': signal_strength,  # 🆕 v9.3: Sinyal gücü
                                'atr': atr_value,
                                'fng_index_at_signal': fng_score if isinstance(fng_score, int) else None,
                                'news_sentiment_at_signal': news_score_val,
                                'reddit_sentiment_at_signal': sentiment_scores.get('reddit_sentiment') if sentiment_scores else None,
                                'google_trends_score_at_signal': sentiment_scores.get('google_trends_score') if sentiment_scores else None,
                                'rr_tier': 'PRIMARY',
                                'nan_penalty_count': nan_penalty_count
                            })
                        elif rr is None:
                            logger.warning(f"   {symbol}: R:R hesaplanamadı (Dinamik SL/TP ile).")
                        else:
                            # Secondary tier kontrolü
                            min_rr_secondary = getattr(config, 'MIN_RR_SECONDARY', None)
                            if min_rr_secondary is not None and rr >= float(min_rr_secondary):
                                logger.info(f"   Secondary Tier: R:R {rr:.2f} ikincil eşik {min_rr_secondary} üzerinde")
                                # Kalite ve sentiment yine hesaplanır
                                quality_grade = 'C'
                                fng_score = 'N/A'
                                news_score = 'N/A'
                                news_score_val = None
                                sentiment_scores = None
                                try:
                                    quality_grade = alpha_analyzer.calculate_quality_grade(symbol, config, signal_direction)
                                    sentiment_scores = sentiment_analyzer.get_sentiment_scores(symbol, config)
                                    fng_score = sentiment_scores.get('fng_index', 'N/A')
                                    news_score_val = sentiment_scores.get('news_sentiment')
                                    news_score = f"{news_score_val:.3f}" if news_score_val is not None else 'N/A'
                                except Exception:
                                    pass

                                candidate_signals.append({
                                    'symbol': symbol,
                                    'strategy': coin_specific_strategy,
                                    'direction': signal_direction,
                                    'entry_price': current_price,
                                    'sl_price': sl_price,
                                    'tp_price': tp_price,
                                    'partial_tp_1_price': partial_tp_1_price,
                                    'rr_ratio': rr,
                                    'quality_grade': quality_grade,
                                    'signal_strength': signal_strength,
                                    'atr': atr_value,
                                    'fng_index_at_signal': fng_score if isinstance(fng_score, int) else None,
                                    'news_sentiment_at_signal': news_score_val,
                                    'reddit_sentiment_at_signal': sentiment_scores.get('reddit_sentiment') if sentiment_scores else None,
                                    'google_trends_score_at_signal': sentiment_scores.get('google_trends_score') if sentiment_scores else None,
                                    'rr_tier': 'SECONDARY',
                                    'nan_penalty_count': nan_penalty_count
                                })
                            else:
                                logger.info(f"   REJECTED: R:R düşük ({rr:.2f} < {effective_min_rr}).")
                    else:
                        logger.warning(f"   {symbol}: Dinamik SL/TP hesaplanamadı.")

            except BinanceAPIException as e:
                if e.code == -1003 or e.status_code == 429 or e.status_code == 418:
                    adjust_rate_limit(increase=True)
                else:
                    logger.error(f"❌ Binance API hatası ({symbol}): {e.code} - {e.message}")
            except Exception as e:
                logger.error(f"❌ Analiz hatası ({symbol}): {e}", exc_info=True)

        # --- Adım 5: Aday Sinyalleri İşle ---
        logger.info(f"--- Adım 5: {len(candidate_signals)} Aday Sinyal İşleniyor ---")
        final_signals_to_open = []
        
        if candidate_signals:
            # 🆕 v9.3: Signal strength'e göre sıralama (önce kalite, sonra signal_strength, sonra RR)
            quality_map = {'A': 1, 'B': 2, 'C': 3, 'D': 4}
            candidate_signals.sort(key=lambda s: (
                quality_map.get(s.get('quality_grade', 'D'), 5),  # Önce kalite
                -s.get('signal_strength', 0),  # Sonra sinyal gücü (yüksek = iyi)
                -s.get('rr_ratio', 0)  # Son olarak RR
            ))
            
            top_signal = candidate_signals[0]
            logger.info(f"🏆 EN İYİ SİNYAL: {top_signal['symbol']} {top_signal['strategy']} "
                       f"Grade:{top_signal['quality_grade']} Strength:{top_signal.get('signal_strength', 0):.1f} "
                       f"RR:{top_signal['rr_ratio']:.2f}")
            
            max_open = getattr(config, 'MAX_OPEN_POSITIONS', 10)
            base_risk = getattr(config, 'BASE_RISK_PERCENT', 1.0)
            q_multipliers = getattr(config, 'QUALITY_MULTIPLIERS', {'A': 1.25, 'B': 1.0, 'C': 0.6, 'D': 0.1})
            secondary_multiplier = getattr(config, 'SECONDARY_RISK_MULTIPLIER', 0.55)
            enable_micro_low = getattr(config, 'ENABLE_MICRO_RISK_LOW_GRADES', True)
            
            # Gerçek bakiyeyi kullan
            use_real_balance = getattr(config, 'USE_REAL_BALANCE', True)
            if use_real_balance and executor:
                portfolio_usd = executor.get_futures_account_balance()
                if portfolio_usd <= 0:
                    logger.warning("⚠️ Gerçek bakiye alınamadı, sanal portföy kullanılıyor")
                    portfolio_usd = getattr(config, 'VIRTUAL_PORTFOLIO_USD', 1000)
                else:
                    logger.info(f"💰 Gerçek Bakiye: ${portfolio_usd:.2f} USDT")
            else:
                portfolio_usd = getattr(config, 'VIRTUAL_PORTFOLIO_USD', 1000)
                logger.info(f"💰 Sanal Portföy: ${portfolio_usd:.2f} USDT")
            
            corr_groups_map = getattr(config, 'CORRELATION_GROUPS', {})
            max_pos_per_symbol = getattr(config, 'MAX_POSITIONS_PER_SYMBOL', 1)
            max_correlation_allowed = getattr(config, 'MAX_CORRELATION_ALLOWED', 0.7)
            
            # Context manager ile DB işlemleri
            with get_db_session() as db:
                # Korelasyon matrisini yükle
                correlation_matrix = None
                corr_key = getattr(sentiment_analyzer, 'CORRELATION_MATRIX_KEY', 'correlation_matrix')
                corr_record = db.query(AlphaCache.value).filter(AlphaCache.key == corr_key).first()
                if corr_record and corr_record[0]:
                    correlation_matrix = corr_record[0]
                    logger.info("Korelasyon Matrisi başarıyla DB'den yüklendi.")
                else:
                    logger.warning("Korelasyon Matrisi DB'de bulunamadı. Korelasyon filtresi atlanacak.")
                
                # 🆕 v7.1: Margin Tracker başlat
                margin_tracker = create_margin_tracker(config)
                margin_status = margin_tracker.calculate_total_margin_usage(db)
                
                # Margin durumunu logla
                logger.info("=" * 60)
                logger.info(f"💰 Margin Durumu: {margin_status['health_status']}")
                logger.info(f"   Kullanılan: ${margin_status['total_margin_used']:.2f}/{portfolio_usd:.2f} ({margin_status['usage_percent']:.1%})")
                logger.info(f"   Serbest: ${margin_status['available_margin']:.2f}")
                logger.info(f"   Açık Pozisyon: {margin_status['position_count']} adet")
                logger.info("=" * 60)
                
                # Kritik margin durumunda uyarı
                if margin_status['health_status'] in ['CRITICAL', 'DANGER']:
                    logger.warning(f"⚠️ UYARI: Margin {margin_status['health_status']} seviyede! Yeni pozisyon sınırlandırılabilir.")

                with open_positions_lock:
                    logger.debug("Pozisyon kilidi alındı (Adım 5). DB sorgulanıyor...")
                    current_open_positions_db = db.query(OpenPosition).all()
                    current_open_count = len(current_open_positions_db)
                    
                    # Mevcut pozisyon bilgilerini topla
                    group_risks = {}
                    symbol_counts = {}
                    open_symbols_set = set()
                    
                    for pos in current_open_positions_db:
                        group = pos.correlation_group or 'OTHER'
                        risk_perc = pos.planned_risk_percent or (base_risk * q_multipliers.get(pos.quality_grade, 0.5))
                        group_risks[group] = group_risks.get(group, 0.0) + risk_perc
                        symbol_counts[pos.symbol] = symbol_counts.get(pos.symbol, 0) + 1
                        open_symbols_set.add(pos.symbol)
                    
                    logger.debug(f"Filtreleme öncesi (DB): Açık={current_open_count}, Grup Risk={group_risks}, Sembol Sayıları={symbol_counts}")

                    # Sinyal işleme döngüsü
                    for signal in candidate_signals:
                        symbol = signal['symbol']
                        quality_grade = signal['quality_grade']
                        rr_tier = signal.get('rr_tier', 'PRIMARY')
                        
                        # Grup ataması
                        if symbol in corr_groups_map:
                            signal_group = corr_groups_map[symbol]
                        else:
                            signal_group = config.auto_assign_correlation_group(symbol)
                            logger.debug(f"   {symbol}: Otomatik grup atandı → {signal_group}")
                        
                        risk_multiplier = q_multipliers.get(quality_grade, 0.0)
                        if rr_tier == 'SECONDARY':
                            risk_multiplier *= secondary_multiplier
                        # Mikro risk kapalıysa C ve D azalt
                        if not enable_micro_low and quality_grade in ['C', 'D']:
                            logger.debug(f"   SKIP {symbol}: Mikro risk kapalı ve kalite {quality_grade}")
                            continue
                        
                        if risk_multiplier <= 0:
                            logger.debug(f"   SKIP {symbol}: Kalite yetersiz ({quality_grade}).")
                            continue
                        if current_open_count >= max_open:
                            logger.warning(f"Maksimum açık pozisyon limitine ({max_open}) ulaşıldı.")
                            break
                        if symbol_counts.get(symbol, 0) >= max_pos_per_symbol:
                            logger.info(f"   SKIP {symbol}: Sembol başına max pozisyon ({max_pos_per_symbol}) limitine ulaşıldı.")
                            continue
                        
                        planned_risk_percent = base_risk * risk_multiplier

                        # Probabilistic sizing (sinyal gücü + kalite etkisi)
                        if getattr(config, 'ENABLE_PROBABILISTIC_SIZING', False):
                            try:
                                strength = signal.get('signal_strength', 50.0) / 100.0  # 0-1
                                quality_factor = {'A': 1.0, 'B': 0.8, 'C': 0.55, 'D': 0.3}.get(quality_grade, 0.5)
                                probability_score = min(1.0, max(0.0, (strength * 0.6 + quality_factor * 0.4)))
                                prob_min = getattr(config, 'PROB_SIZING_MIN', 0.45)
                                prob_max = getattr(config, 'PROB_SIZING_MAX', 1.1)
                                prob_scale = prob_min + (prob_max - prob_min) * probability_score
                                planned_risk_percent *= prob_scale
                                signal['probability_score'] = probability_score
                                signal['prob_scaled'] = prob_scale
                                logger.debug(f"   ProbSizing {symbol}: score={probability_score:.2f} scale={prob_scale:.2f} risk%={planned_risk_percent:.2f}")
                            except Exception as ps_err:
                                logger.warning(f"   Prob sizing hata: {ps_err}")
                        
                        # 🆕 GRUP RİSK KONTROLÜ
                        max_group_risk = getattr(config, 'MAX_RISK_PER_GROUP', 5.0)
                        current_group_risk = group_risks.get(signal_group, 0.0)
                        
                        if current_group_risk + planned_risk_percent > max_group_risk:
                            logger.warning(f"   SKIP {symbol}: Grup '{signal_group}' risk limiti aşılacak! "
                                          f"(Mevcut: {current_group_risk:.2f}% + Yeni: {planned_risk_percent:.2f}% > Max: {max_group_risk:.2f}%)")
                            continue
                        
                        # Korelasyon kontrolü
                        is_highly_correlated = False
                        if correlation_matrix and open_symbols_set:
                            for open_symbol in open_symbols_set:
                                if open_symbol == symbol:
                                    continue
                                try:
                                    corr_value = correlation_matrix.get(symbol, {}).get(open_symbol, 0.0)
                                    if abs(corr_value) > max_correlation_allowed:
                                        is_highly_correlated = True
                                        logger.warning(f"   SKIP {symbol}: {open_symbol} ile Yüksek Korelasyon ({corr_value:.2f} > {max_correlation_allowed}).")
                                        break
                                except Exception as e_corr:
                                    logger.error(f"   Korelasyon değeri okunurken hata ({symbol} vs {open_symbol}): {e_corr}")
                        
                        if is_highly_correlated:
                            continue

                        # Frequency throttle (ikincil tier ve düşük kaliteyi sınırlama)
                        if getattr(config, 'ENABLE_FREQUENCY_THROTTLE', False):
                            try:
                                window_minutes = getattr(config, 'THROTTLE_WINDOW_MINUTES', 90)
                                max_new = getattr(config, 'MAX_NEW_POSITIONS_PER_WINDOW', 4)
                                now_ts = int(time.time())
                                window_start = now_ts - window_minutes * 60

                                # ✅ FIX: DB'den detached object'leri kullanırken session hatası olmaması için
                                # open_time attribute'unu doğrudan dict'e çevir
                                recent_count = 0
                                for p in current_open_positions_db:
                                    try:
                                        if p.open_time and p.open_time >= window_start:
                                            recent_count += 1
                                    except Exception:
                                        # Session detached ise, skip
                                        pass
                                
                                if recent_count >= max_new and rr_tier == 'SECONDARY':
                                    logger.info(f"   THROTTLE SKIP {symbol}: İkincil tier ve pencere dolu ({recent_count}/{max_new})")
                                    continue
                            except Exception as throttle_err:
                                # Session hatası artık warning değil debug
                                logger.debug(f"   Throttle kontrol hatası (ignored): {throttle_err}")
                        
                        
                        # 🆕 v10.5: 1H EMA MODE - Sabit Pozisyon Boyutu (Fast mode ile aynı mantık)
                        if ema_mode_enabled:
                            base_size_usd = getattr(config, 'EMA_MODE_BASE_SIZE_USD', 10.0)
                            ema_leverage = getattr(config, 'EMA_MODE_LEVERAGE', 10)
                            
                            # Margin = base_size × leverage
                            margin_usd = base_size_usd
                            position_value_usd = base_size_usd * ema_leverage
                            position_size_units = position_value_usd / signal['entry_price']
                            
                            risk_per_unit = abs(signal['entry_price'] - signal['sl_price'])
                            final_risk_usd = risk_per_unit * position_size_units
                            
                            # v10.5: Margin-based TP/SL thresholds (1H EMA için)
                            tp_margin = getattr(config, 'EMA_MODE_TP_MARGIN', 14.0)
                            sl_margin = getattr(config, 'EMA_MODE_SL_MARGIN', 9.0)
                            
                            sizing_result = {
                                'position_size_units': position_size_units,
                                'final_risk_usd': final_risk_usd,
                                'leverage': ema_leverage,
                                'volatility_multiplier': 1.0,
                                'volatility_score': 0.5,
                                'margin_usd': margin_usd,
                                'position_value_usd': position_value_usd,
                                'initial_margin': margin_usd,  # Başlangıç margin ($10)
                                'tp_margin': tp_margin,         # TP threshold ($14)
                                'sl_margin': sl_margin          # SL threshold ($9)
                            }
                            
                            logger.info(f"   🎯 1H EMA MODE Sizing: Margin=${margin_usd:.2f}, Leverage={ema_leverage}x, Value=${position_value_usd:.2f}, Units={position_size_units:.6f}, Risk=${final_risk_usd:.2f}")
                            logger.info(f"   🎯 Margin Thresholds: TP=${tp_margin:.2f}, SL=${sl_margin:.2f} (R:R={(tp_margin-margin_usd)/(margin_usd-sl_margin):.1f})")
                        
                        # 🆕 v10.0: FAST MODE - Sabit Pozisyon Boyutu
                        elif fast_mode_enabled:
                            base_size_usd = getattr(config, 'FAST_MODE_BASE_SIZE_USD', 10.0)
                            fast_leverage = getattr(config, 'FAST_MODE_LEVERAGE', 10)
                            
                            # Margin = base_size × leverage
                            margin_usd = base_size_usd
                            position_value_usd = base_size_usd * fast_leverage
                            position_size_units = position_value_usd / signal['entry_price']
                            
                            risk_per_unit = abs(signal['entry_price'] - signal['sl_price'])
                            final_risk_usd = risk_per_unit * position_size_units
                            
                            # 🆕 v10.4: Margin-based TP/SL thresholds
                            tp_margin = getattr(config, 'FAST_MODE_TP_MARGIN', 14.0)
                            sl_margin = getattr(config, 'FAST_MODE_SL_MARGIN', 9.0)
                            
                            sizing_result = {
                                'position_size_units': position_size_units,
                                'final_risk_usd': final_risk_usd,
                                'leverage': fast_leverage,
                                'volatility_multiplier': 1.0,
                                'volatility_score': 0.5,
                                'margin_usd': margin_usd,
                                'position_value_usd': position_value_usd,
                                'initial_margin': margin_usd,  # Başlangıç margin ($10)
                                'tp_margin': tp_margin,         # TP threshold ($14)
                                'sl_margin': sl_margin          # SL threshold ($9)
                            }
                            
                            logger.info(f"   🚀 FAST MODE Sizing: Margin=${margin_usd:.2f}, Leverage={fast_leverage}x, Value=${position_value_usd:.2f}, Units={position_size_units:.6f}, Risk=${final_risk_usd:.2f}")
                            logger.info(f"   🎯 Margin Thresholds: TP=${tp_margin:.2f}, SL=${sl_margin:.2f} (R:R={(tp_margin-margin_usd)/(margin_usd-sl_margin):.1f})")
                        else:
                            # ESKİ SİSTEM: Position Sizing (her zaman risk_calculator'ı kullan → min margin enforcement aktif)
                            try:
                                atr_value = float(signal.get('atr', 0.0) or 0.0)
                                sizing_result = risk_calculator.calculate_position_size_with_volatility(
                                    entry_price=signal['entry_price'],
                                    sl_price=signal['sl_price'],
                                    portfolio_usd=portfolio_usd,
                                    planned_risk_percent=planned_risk_percent,
                                    atr=atr_value,
                                    config=config
                                )
                                if not sizing_result:
                                    raise ValueError("Volatilite bazlı sizing başarısız")

                                # 🆕 VOLATILITE MULTIPLIER UYGULA (atr yoksa skor ~0.5 gelir, değişim olmaz)
                                volatility_multiplier = sizing_result.get('volatility_multiplier', 1.0)
                                volatility_score = sizing_result.get('volatility_score', 0.5)
                                if volatility_score > 0.7:
                                    adjusted_risk_percent = planned_risk_percent * volatility_multiplier
                                    logger.warning(f"   ⚠️ {symbol} Yüksek Volatilite! Risk %{planned_risk_percent:.2f} → %{adjusted_risk_percent:.2f} (Skor: {volatility_score:.2f}, Çarpan: {volatility_multiplier:.2f})")

                                    # Risk'i yeniden hesapla ve pozisyonu güncelle
                                    final_risk_usd = portfolio_usd * (adjusted_risk_percent / 100.0)
                                    risk_per_unit = abs(signal['entry_price'] - signal['sl_price'])
                                    adjusted_pos_size = final_risk_usd / risk_per_unit if risk_per_unit > 0 else 0
                                    sizing_result['final_risk_usd'] = final_risk_usd
                                    sizing_result['position_size_units'] = adjusted_pos_size
                                    sizing_result['adjusted_risk_percent'] = adjusted_risk_percent
                                    logger.info(f"      Pozisyon boyutu: {sizing_result['position_size_units']:.6f} {symbol} (~${final_risk_usd / (adjusted_risk_percent/100.0) * (adjusted_risk_percent/100.0):.2f})")
                                else:
                                    logger.info(f"   ✅ {symbol} Normal Volatilite (Skor: {volatility_score:.2f}), risk ayarlaması yok")
                            
                            except Exception as e:
                                logger.error(f"   SKIP {symbol}: Boyut hesaplama hatası: {e}")
                                continue
                        
                        # Partial TP ayarları
                        partial_tp_1_percent = None
                        partial_tp_1_price = signal.get('partial_tp_1_price')
                        
                        if getattr(config, 'PARTIAL_TP_ENABLED', False):
                            partial_tp_1_percent = getattr(config, 'PARTIAL_TP_1_PERCENT', 50.0)
                            
                            if partial_tp_1_price is None:
                                partial_tp_1_rr = getattr(config, 'PARTIAL_TP_1_RR_RATIO', 1.5)
                                entry = signal['entry_price']
                                sl = signal['sl_price']
                                risk_distance = abs(entry - sl)
                                reward_distance_partial = risk_distance * partial_tp_1_rr
                                
                                if signal['direction'] == 'LONG':
                                    partial_tp_1_price = entry + reward_distance_partial
                                else:
                                    partial_tp_1_price = entry - reward_distance_partial
                            
                            logger.info(f"   📊 Partial TP-1: {partial_tp_1_percent:.0f}% pozisyon @ {partial_tp_1_price:.6f}")
                        
                        # Trailing Stop ayarları
                        is_trailing_active = False
                        trailing_distance = None
                        high_water_mark = signal['entry_price']

                        if signal['strategy'] in ['ADVANCED_SCALP', 'BREAKOUT']:
                            is_trailing_active = True
                            trailing_distance = abs(signal['entry_price'] - signal['sl_price'])
                            logger.info(f"   TRAILING STOP AKTİF! Strateji: {signal['strategy']}, Mesafe: {trailing_distance:.4f}")
                        
                        # 🆕 KELLY CRITERION KONTROLÜ
                        kelly_size = None
                        kelly_percent = None
                        kelly_confidence = None
                        kelly_reasoning = ''
                        
                        try:
                            from src.risk_manager.kelly_calculator import KellyPositionSizer
                            
                            kelly_sizer = KellyPositionSizer(config, db)  # 🔧 db parametresi eklendi
                            
                            # Strateji bazlı win rate (gerçek performanstan alınmalı, şimdilik varsayılan)
                            estimated_win_rate = 0.60  # %60 başarı oranı varsayımı
                            
                            kelly_result = kelly_sizer.calculate_kelly_size(
                                win_rate=estimated_win_rate,
                                avg_win_loss_ratio=signal['rr_ratio'],  # 🔧 Düzeltildi
                                rr_ratio=signal['rr_ratio'],
                                max_position_value=portfolio_usd  # 🔧 Düzeltildi
                            )
                            
                            if kelly_result and kelly_result.get('recommended_size', 0) > 0:
                                kelly_size = kelly_result['recommended_size']
                                kelly_percent = kelly_result.get('kelly_percent', 0.0)
                                kelly_confidence = kelly_result.get('confidence')
                                kelly_reasoning = kelly_result.get('risk_reasoning', '')
                                
                                current_position_value = sizing_result['position_size_units'] * signal['entry_price']
                                
                                # Kelly ile karşılaştır
                                if current_position_value > kelly_size * 1.5:  # %50 fazla
                                    logger.warning(f"   ⚠️ Kelly Uyarısı: Pozisyon Kelly önerisinden büyük! "
                                                  f"${current_position_value:.2f} > ${kelly_size:.2f} (Kelly)")
                                    
                                    # Opsiyonel: Kelly'e göre ayarla
                                    if getattr(config, 'USE_KELLY_ADJUSTMENT', False):
                                        adjusted_units = kelly_size / signal['entry_price']
                                        logger.info(f"      🔧 Boyut Kelly'e göre azaltıldı: {sizing_result['position_size_units']:.6f} → {adjusted_units:.6f}")
                                        sizing_result['position_size_units'] = adjusted_units
                                        sizing_result['final_risk_usd'] = abs(signal['entry_price'] - signal['sl_price']) * adjusted_units
                                else:
                                    logger.info(f"   ✅ Kelly Kontrolü OK: ${current_position_value:.2f} <= ${kelly_size:.2f}")
                                # ✅ Post-Kelly minimum margin enforcement (downstream shrinking koruması)
                                try:
                                    leverage_after_kelly = sizing_result.get('leverage', getattr(config, 'FUTURES_LEVERAGE', 5))
                                    min_static = getattr(config, 'MIN_MARGIN_USD', 10.0)
                                    # Sabit alt sınır: 10$
                                    effective_min_margin = min_static
                                    post_kelly_position_value = sizing_result['position_size_units'] * signal['entry_price']
                                    post_kelly_margin = post_kelly_position_value / leverage_after_kelly
                                    if post_kelly_margin < effective_min_margin:
                                        needed_position_value = effective_min_margin * leverage_after_kelly
                                        needed_units = needed_position_value / signal['entry_price']
                                        logger.warning(
                                            f"      🛡️ Post-Kelly MinMargin Enforce: Margin ${post_kelly_margin:.2f} < ${effective_min_margin:.2f} → Units {sizing_result['position_size_units']:.6f} → {needed_units:.6f}" 
                                        )
                                        sizing_result['position_size_units'] = needed_units
                                        sizing_result['final_risk_usd'] = abs(signal['entry_price'] - signal['sl_price']) * needed_units
                                    else:
                                        logger.debug(f"      🛡️ Post-Kelly MinMargin OK: ${post_kelly_margin:.2f} >= ${effective_min_margin:.2f}")
                                except Exception as mm_kelly_err:
                                    logger.error(f"      ❌ Post-Kelly min margin enforcement hatası: {mm_kelly_err}")
                        
                        except ImportError as ie:
                            logger.warning(f"   ⚠️ Kelly calculator modülü yüklenemedi: {ie}")
                            logger.warning(f"   💡 Kelly kontrolü atlandı - risk_manager/kelly_calculator.py dosyasını kontrol edin")
                        except Exception as kelly_err:
                            logger.error(f"   ❌ Kelly hesaplama hatası: {kelly_err}", exc_info=True)
                            logger.warning(f"   Kelly kontrolü atlandı, pozisyon boyutu değiştirilmedi")
                        
                        # 🆕 v7.1: MARGIN KONTROLÜ
                        # Pozisyon için gerekli margin'i hesapla
                        position_value = sizing_result['position_size_units'] * signal['entry_price']
                        required_leverage = sizing_result.get('leverage', config.FUTURES_LEVERAGE)
                        required_margin = position_value / required_leverage
                        # 📌 DIAGNOSTIC: Pre-open sizing trace
                        try:
                            logger.info(
                                f"   🧪 SizingTrace Pre-Open | Units={sizing_result['position_size_units']:.6f} Value=${position_value:.2f} Leverage={required_leverage}x Margin=${required_margin:.2f} RiskUSD=${sizing_result['final_risk_usd']:.2f}" 
                            )
                        except Exception:
                            pass
                        
                        # Margin yeterli mi kontrol et
                        can_open_position, margin_reason = margin_tracker.can_open_new_position(required_margin, db)
                        
                        if not can_open_position:
                            logger.warning(f"   ⛔ SKIP {symbol}: {margin_reason}")
                            continue
                        else:
                            logger.info(f"   ✅ Margin OK: ${required_margin:.2f} gereken, pozisyon açılabilir")
                        
                        # Portföy guard: günlük risk/drawdown limitleri
                        try:
                            # Portföy bakiyesi al (mevcut akıştan)
                            if executor:
                                portfolio_usd = executor.get_futures_account_balance()
                                if portfolio_usd <= 0:
                                    portfolio_usd = getattr(config, 'VIRTUAL_PORTFOLIO_USD', 1000)
                            else:
                                portfolio_usd = getattr(config, 'VIRTUAL_PORTFOLIO_USD', 1000)

                            from src.risk_manager.portfolio_guard import check_daily_limits
                            allow_open, reason, guard_status = check_daily_limits(config, portfolio_usd)
                            if not allow_open:
                                logger.warning(f"   ⛔ Portföy Guard engelledi: {reason} | Status: {guard_status}")
                                continue
                            else:
                                logger.info(f"   ✅ Portföy Guard OK: Risk%={guard_status.get('open_risk_today_pct',0):.2f}, DD%={guard_status.get('dd_today_pct',0):.2f}")
                        except Exception as guard_err:
                            logger.warning(f"   Portföy guard kontrolü başarısız: {guard_err}")

                        # Signal verilerini güncelle
                        signal.update({
                            'final_risk_usd': sizing_result['final_risk_usd'],
                            'reward_usd': sizing_result['final_risk_usd'] * signal['rr_ratio'],
                            'position_size_units': sizing_result['position_size_units'],
                            'correlation_group': signal_group,
                            'open_time': int(time.time()),
                            'planned_risk_percent': planned_risk_percent,
                            'volatility_multiplier': sizing_result.get('volatility_multiplier', 1.0),
                            'volatility_score': sizing_result.get('volatility_score', 0.5),
                            'leverage': sizing_result.get('leverage', config.FUTURES_LEVERAGE),
                            'position_size_usd': signal['entry_price'] * sizing_result['position_size_units'],
                            'kelly_size': kelly_size,                # Kelly önerilen pozisyon değeri (USD)
                            'kelly_percent': kelly_percent,          # Gerçek Kelly yüzdesi (cap sonrası)
                            'kelly_confidence': kelly_confidence,
                            'risk_reasoning': kelly_reasoning,
                            # v10.4: Margin-based TP/SL fields (fast mode için)
                            'initial_margin': sizing_result.get('initial_margin'),
                            'tp_margin': sizing_result.get('tp_margin'),
                            'sl_margin': sizing_result.get('sl_margin')
                        })
                        
                        # DB'ye kaydet (PENDING durumunda)
                        new_db_position = OpenPosition(
                            symbol=signal['symbol'],
                            strategy=signal['strategy'],
                            direction=signal['direction'],
                            quality_grade=signal['quality_grade'],
                            entry_price=signal['entry_price'],
                            sl_price=signal['sl_price'],
                            tp_price=signal['tp_price'],
                            rr_ratio=signal['rr_ratio'],
                            position_size_units=signal['position_size_units'],
                            final_risk_usd=signal['final_risk_usd'],
                            planned_risk_percent=signal['planned_risk_percent'],
                            correlation_group=signal['correlation_group'],
                            open_time=signal['open_time'],
                            fng_index_at_signal=signal.get('fng_index_at_signal'),
                            news_sentiment_at_signal=signal.get('news_sentiment_at_signal'),
                            reddit_sentiment_at_signal=signal.get('reddit_sentiment_at_signal'),
                            google_trends_score_at_signal=signal.get('google_trends_score_at_signal'),
                            leverage=sizing_result.get('leverage', 2),
                            trailing_stop_active=is_trailing_active,
                            trailing_stop_distance=trailing_distance,
                            high_water_mark=high_water_mark,
                            partial_tp_1_price=partial_tp_1_price,
                            partial_tp_1_percent=partial_tp_1_percent,
                            partial_tp_1_taken=False,
                            remaining_position_size=signal['position_size_units'],
                            volatility_score=signal.get('volatility_score', 0.5),  # 🆕 EKLENDİ
                            kelly_percent=(signal.get('kelly_percent') or 0.0),
                            kelly_confidence=signal.get('kelly_confidence'),
                            risk_reasoning=signal.get('risk_reasoning', ''),
                            initial_margin=sizing_result.get('initial_margin'),  # 🆕 v10.4: Margin tracking
                            tp_margin=sizing_result.get('tp_margin'),              # 🆕 v10.4: TP threshold
                            sl_margin=sizing_result.get('sl_margin'),              # 🆕 v10.4: SL threshold
                            status='PENDING'
                        )
                        
                        db.add(new_db_position)
                        db.flush()
                        
                        # ⚠️ KRİTİK: SİMÜLASYON MODU KONTROLÜ
                        position_opened_successfully = False
                        
                        if not config.ENABLE_REAL_TRADING:
                            # SİMÜLASYON MODU - Binance'e emir gönderme
                            logger.warning(f"   ⚠️ SİMÜLASYON MODU - {symbol} için Binance'e emir GÖNDERİLMEDİ")
                            logger.info(f"      📝 Sadece DB'ye kaydedildi: {symbol} {signal['direction']}")
                            logger.info(f"      💰 Miktar: {signal['position_size_units']:.4f} ({signal['final_risk_usd']:.2f} USD risk)")
                            logger.info(f"      📊 Entry: {signal['entry_price']:.4f} | SL: {signal['sl_price']:.4f} | TP: {signal['tp_price']:.4f}")
                            
                            # Simülasyon için sahte order ID
                            new_db_position.status = 'SIMULATED'
                            new_db_position.market_order_id = f"SIM_{int(time.time())}_{symbol}"
                            position_opened_successfully = True
                            
                            # Simülasyon bildirimi gönder
                            try:
                                telegram_notifier.send_new_signal_alert([signal])
                            except Exception as tel_e:
                                logger.error(f"Telegram bildirimi hatası: {tel_e}")
                            
                            if realtime_manager_instance:
                                realtime_manager_instance.add_symbol(symbol)
                        
                        else:
                            # GERÇEK İŞLEM MODU - Binance'e emir gönder
                            try:
                                logger.info(f"   🚀 GERÇEK EMİR GÖNDERİLİYOR: {symbol} {signal['direction']}")
                                
                                leverage_to_use = sizing_result.get('leverage', config.FUTURES_LEVERAGE)
                                if executor and executor.set_leverage(symbol, leverage_to_use):
                                    logger.info(f"      ✅ Kaldıraç ayarlandı: {leverage_to_use}x")
                                
                                if executor and executor.set_margin_type(symbol, config.FUTURES_MARGIN_TYPE):
                                    logger.info(f"      ✅ Margin tipi: {config.FUTURES_MARGIN_TYPE}")
                                
                                if executor:
                                    market_order = executor.open_market_order(
                                        symbol=symbol,
                                        direction=signal['direction'],
                                        quantity_units=signal['position_size_units'],
                                        entry_price=signal['entry_price'],
                                        leverage=leverage_to_use
                                    )
                                    
                                    if market_order:
                                        logger.info(f"      ✅ Pozisyon açıldı! Order ID: {market_order['orderId']}")
                                        # 🔍 Post-rounding actual executed qty ve min margin doğrulama
                                        try:
                                            executed_qty = float(market_order.get('executedQty', signal['position_size_units']))
                                            avg_price = float(market_order.get('avgPrice', signal['entry_price']))
                                            executed_position_value = executed_qty * avg_price
                                            executed_margin = executed_position_value / leverage_to_use if leverage_to_use else executed_position_value
                                            min_static = getattr(config, 'MIN_MARGIN_USD', 10.0)
                                            # Sabit alt sınır: 10$
                                            effective_min_margin = min_static
                                            logger.info(
                                                f"      🧪 SizingTrace Post-Order | ExecQty={executed_qty:.6f} AvgPrice={avg_price:.6f} Value=${executed_position_value:.2f} Margin=${executed_margin:.2f} MinMargin=${effective_min_margin:.2f}" 
                                            )
                                            if executed_margin + 1e-8 < effective_min_margin:
                                                # Eğer yuvarlama sonrası margin altına düştüyse, yeniden büyütmeye çalış (bilgi amaçlı log - manuel müdahale gerekebilir)
                                                logger.warning(
                                                    f"      🚨 Post-Order Margin DÜŞÜK: ${executed_margin:.2f} < ${effective_min_margin:.2f}. Yuvarlama step_size küçültmüş olabilir." 
                                                )
                                                logger.warning("      ÖNERİ: Bu sembol için step_size / min_notional değerlerini incele veya min_per_leverage ayarını artır.")
                                        except Exception as post_ord_err:
                                            logger.error(f"      ❌ Post-order sizing trace hatası: {post_ord_err}")
                                        new_db_position.market_order_id = market_order['orderId']
                                        
                                        # Gerçekleşen miktarı kullan (SL/TP için kritik)
                                        used_qty = float(market_order.get('executedQty', signal['position_size_units']))
                                        # DB ve sinyal objesini güncelle
                                        try:
                                            new_db_position.position_size_units = used_qty
                                            new_db_position.remaining_position_size = used_qty
                                            signal['position_size_units'] = used_qty
                                            signal['position_size_usd'] = used_qty * signal['entry_price']
                                        except Exception:
                                            pass

                                        sl_tp_orders = executor.place_sl_tp_orders(
                                            symbol=symbol,
                                            direction=signal['direction'],
                                            quantity_units=used_qty,
                                            sl_price=signal['sl_price'],
                                            tp_price=signal['tp_price'],
                                            entry_price=signal['entry_price']
                                        )
                                        
                                        if sl_tp_orders:
                                            logger.info(f"      ✅ SL/TP emirleri yerleştirildi!")
                                            new_db_position.sl_order_id = sl_tp_orders['sl_order_id']
                                            new_db_position.tp_order_id = sl_tp_orders['tp_order_id']
                                            new_db_position.status = 'ACTIVE'
                                            position_opened_successfully = True
                                            
                                            logger.info(f"   ✅ {symbol} POZİSYON AKTİF!")
                                            
                                            try:
                                                telegram_notifier.send_new_signal_alert([signal])
                                            except Exception as tel_e:
                                                logger.error(f"Telegram bildirimi hatası: {tel_e}")
                                            
                                            if realtime_manager_instance:
                                                realtime_manager_instance.add_symbol(symbol)
                                        else:
                                            raise Exception("SL/TP emirleri yerleştirilemedi!")
                                    else:
                                        raise Exception("Market emri gönderilemedi!")
                                else:
                                    raise Exception("Executor başlatılmamış!")
                            
                            except Exception as order_error:
                                logger.error(f"   ❌ {symbol} POZİSYON AÇILAMADI: {order_error}", exc_info=True)
                                
                                try:
                                    error_msg = f"*❌ POZİSYON AÇILAMADI*\n\n"
                                    error_msg += f"*{telegram_notifier.escape_markdown_v2('-')} Sembol:* {telegram_notifier.escape_markdown_v2(symbol)}\n"
                                    error_msg += f"*{telegram_notifier.escape_markdown_v2('-')} Yön:* {telegram_notifier.escape_markdown_v2(signal['direction'])}\n"
                                    error_msg += f"*{telegram_notifier.escape_markdown_v2('-')} Hata:* {telegram_notifier.escape_markdown_v2(str(order_error)[:200])}"
                                    telegram_notifier.send_message(error_msg)
                                except Exception as tel_e:
                                    logger.error(f"Hata bildirimi gönderilemedi: {tel_e}")
                                
                                db.delete(new_db_position)
                                position_opened_successfully = False
                        
                        if position_opened_successfully:
                            final_signals_to_open.append(signal)
                            current_open_count += 1
                            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
                            open_symbols_set.add(symbol)
                            
                            # 🆕 GRUP RİSK GÜNCELLE
                            group_risks[signal_group] = group_risks.get(signal_group, 0.0) + planned_risk_percent
                            
                            logger.info(f"   ✅ SELECTED {symbol} {signal['direction']} (Strateji:{signal['strategy']}, Kalite:{quality_grade}, Risk:{signal['final_risk_usd']:.2f}$)")
                            logger.debug(f"      Grup '{signal_group}' toplam risk: {group_risks[signal_group]:.2f}%")

                if final_signals_to_open:
                    logger.info(f"{len(final_signals_to_open)} yeni pozisyon AÇILDI ve DB'ye kaydedildi.")
                else:
                    logger.info("Sıralama/filtreleme sonrası açılacak yeni pozisyon bulunamadı.")
        
        else:
            logger.info("Bu tarama döngüsünde R:R filtresini geçen aday sinyal bulunamadı.")
            try:
                if getattr(config, 'NOTIFY_ON_NO_SIGNAL', True):
                    telegram_notifier.send_message(telegram_notifier.escape_markdown_v2("Tarama tamamlandı. Uygun sinyal bulunamadı."))
            except Exception as e:
                logger.error(f"Sinyal yok bildirimi hatası: {e}", exc_info=True)
        
        # Rate Limit Azaltma
        if rate_limit_status['binance_delay_multiplier'] > 1.0:
            time_since_err = time.time() - rate_limit_status.get('last_binance_error_time', 0)
            if time_since_err > 300:
                old_mult = rate_limit_status['binance_delay_multiplier']
                rate_limit_status['binance_delay_multiplier'] = max(1.0, old_mult * 0.9)
                logger.info(f"Rate limit çarpanı azaltıldı: {old_mult:.1f}x -> {rate_limit_status['binance_delay_multiplier']:.1f}x")
                rate_limit_status['last_binance_error_time'] = 0

    except Exception as e:
        logger.critical(f"====== ANA TARAMA DÖNGÜSÜ ÇÖKTÜ: {e} ======", exc_info=True)
        try:
            if telegram_notifier.bot_instance:
                err_msg = f"🚨 KRİTİK HATA: Ana tarama döngüsü çöktü!\n{type(e).__name__}: {str(e)[:500]}"
                telegram_notifier.send_message(telegram_notifier.escape_markdown_v2(err_msg))
        except Exception as telegram_e:
            logger.error(f"Telegram çökme bildirimi hatası: {telegram_e}")

    logger.info("====== ANA TARAMA DÖNGÜSÜ TAMAMLANDI ======")
    
    try:
        performance_monitor.print_performance_summary()
    except Exception as perf_err:
        logger.warning(f"⚠️  Performans özeti gösterilemedi: {perf_err}")

# --- Ana Çalıştırma Bloğu ---
if __name__ == "__main__":
    logger.info("Ana orchestrator başlatılıyor...")
    
    # Güvenlik kontrolü
    if not config.BINANCE_TESTNET:
        print("=" * 70)
        print("⚠️  UYARI: LIVE TRADING MODE AKTİF - GERÇEK PARA KULLANILACAK! ⚠️")
        print("=" * 70)
        print(f"📊 Maksimum Pozisyon: {config.MAX_OPEN_POSITIONS}")
        print(f"💰 Sabit Risk per Trade: ${config.FIXED_RISK_USD}")
        print(f"🎯 Max Pozisyon Değeri: ${config.MAX_POSITION_VALUE_USD}")
        print(f"🎯 Grup Riski Limiti: %{config.MAX_RISK_PER_GROUP}")
        print(f"⚡ Kaldıraç: Dinamik (2x - 10x, SL mesafesine göre)")
        print(f"💵 Gerçek Bakiye Kullanımı: {config.USE_REAL_BALANCE}")
        print("=" * 70)
        print("\n⏰ 10 saniye içinde başlayacak...")
        print("   (Ctrl+C ile iptal edebilirsiniz)\n")
        
        try:
            for i in range(10, 0, -1):
                print(f"   Başlama: {i} saniye...", end='\r')
                time.sleep(1)
            print("\n")
            logger.warning("🚀 LIVE TRADING BAŞLATILDI - GERÇEK PARA KULLANILIYOR!")
        except KeyboardInterrupt:
            print("\n\n❌ Kullanıcı tarafından iptal edildi. Güvenli çıkış yapılıyor...")
            sys.exit(0)
    else:
        logger.info("✅ TESTNET MODE - Güvenli test ortamı kullanılıyor")
    
    can_trade, reason = check_emergency_stop()
    if not can_trade:
        logger.critical(f"🚨 EMERGENCY STOP AKTİF: {reason}")
        logger.critical("Trading başlatılamıyor! EMERGENCY_STOP.flag dosyasını silin ve yeniden başlatın.")
        sys.exit(1)
    
    try:
        init_db()
    except Exception as e_db:
        logger.critical(f"❌ Veritabanı başlatma hatası! Bot çalıştırılamıyor. Hata: {e_db}")
        sys.exit(1)

    logger.info("🔧 Binance Futures Executor başlatılıyor...")
    try:
        executor = initialize_executor(config)
        logger.info("✅ Executor başarıyla başlatıldı!")
    except Exception as e_exec:
        logger.critical(f"❌ Executor başlatılamadı! Hata: {e_exec}", exc_info=True)
        allow_fallback = getattr(config, 'ALLOW_SIMULATION_FALLBACK', False)
        if allow_fallback:
            try:
                import time as _t
                logger.warning("⚠️ Executor yok - Simülasyon moduna düşülüyor (ALLOW_SIMULATION_FALLBACK=True)")
                setattr(config, 'ENABLE_REAL_TRADING', False)
                executor = None
                _t.sleep(0.2)
            except Exception as _fallback_err:
                logger.error(f"Simülasyon moduna geçiş başarısız: {_fallback_err}")
                sys.exit(1)
        else:
            logger.critical("❌ Fallback devre dışı (ALLOW_SIMULATION_FALLBACK=False) - Bot durduruluyor.")
            sys.exit(1)
    
    # 🆕 STARTUP RECONCILIATION: DB ile Binance senkronizasyonu
    logger.info("🔍 Startup Reconciliation: DB pozisyonları Binance ile karşılaştırılıyor...")
    try:
        from src.trade_manager.reconciliation import reconcile_positions_on_startup
        recon_result = reconcile_positions_on_startup(config)
        if recon_result['orphaned_count'] > 0:
            logger.warning(f"⚠️ {recon_result['orphaned_count']} orphan pozisyon temizlendi: {recon_result['closed_symbols']}")
        else:
            logger.info(f"✅ Reconciliation OK: DB ({recon_result['db_count']}) ve Binance ({recon_result['binance_count']}) senkron")
    except Exception as e_recon:
        logger.error(f"❌ Reconciliation başarısız (devam edilecek): {e_recon}", exc_info=True)
    
    logger.info("🏦 Capital Manager başlatılıyor...")
    try:
        capital_manager = initialize_capital_manager(config, executor, stop_event)
        logger.info("✅ Capital Manager başarıyla başlatıldı!")
    except Exception as e_cap:
        logger.error(f"❌ Capital Manager başlatılamadı: {e_cap}", exc_info=True)
        capital_manager = None

    realtime_manager_instance = None
    realtime_manager_thread = None
    logger.info("RealTime Fiyat Yöneticisi (WebSocket) thread'i başlatılıyor...")
    try:
        realtime_manager_instance = RealTimeDataManager(stop_event, config)
        realtime_manager_thread = realtime_manager_instance.start()
        if realtime_manager_thread and realtime_manager_thread.is_alive():
            logger.info("✅ RealTime Fiyat Yöneticisi thread'i başarıyla başlatıldı.")
        else:
            logger.error("❌ RealTime Fiyat Yöneticisi thread'i BAŞLATILAMADI!")
    except Exception as e:
        logger.error(f"❌ RealTime Fiyat Yöneticisi başlatılırken hata: {e}", exc_info=True)

    telegram_initialized = False
    try:
        if telegram_notifier.initialize_bot(config):
            telegram_initialized = True
            try:
                start_msg = f"ChimeraBot v{getattr(config, 'BOT_VERSION', '?.?')} başlatıldı."
                telegram_notifier.send_message(telegram_notifier.escape_markdown_v2(start_msg))
            except Exception as e:
                logger.error(f"Başlangıç mesajı gönderilemedi: {e}")
        else:
            logger.warning("Telegram botu başlatılamadı.")
    except Exception as e:
        logger.error(f"Telegram başlatma hatası: {e}", exc_info=True)

    trade_manager_thread = None
    logger.info("Trade Manager thread'i başlatılıyor...")
    try:
        if not hasattr(trade_manager, 'continuously_check_positions'):
            raise AttributeError("TM fonksiyonu yok")
        
        if realtime_manager_instance is None:
            logger.critical("❌ RealTime Manager başlatılamadığı için Trade Manager başlatılamıyor!")
            raise RuntimeError("RealTimeManager başlatılamadı.")
        
        trade_manager_thread = threading.Thread(
            target=trade_manager.continuously_check_positions,
            args=(realtime_manager_instance, open_positions_lock, stop_event, config),
            name="TradeManagerThread",
            daemon=True
        )
        trade_manager_thread.start()
        logger.info("✅ Trade Manager thread'i başarıyla başlatıldı (WebSocket modunda).")
    except Exception as e:
        logger.error(f"❌ Trade Manager başlatma hatası: {e}", exc_info=True)

    scan_interval = getattr(config, 'SCAN_INTERVAL_MINUTES', 5)
    logger.info(f"Ana tarama döngüsü her {scan_interval} dakikada bir çalışacak.")
    schedule.every(scan_interval).minutes.do(main_scan_cycle)
    
    if capital_manager:
        logger.info("Capital Manager saatlik kontrol için zamanlandı.")
        schedule.every(1).hour.do(capital_manager.check_capital)
    else:
        logger.warning("⚠️ Capital Manager başlatılamadı, sermaye kontrolü yapılmayacak!")

    logger.info("İlk tarama döngüsü manuel olarak başlatılıyor...")
    main_scan_cycle()

    logger.info("Zamanlanmış görev döngüsü başlatıldı. Çıkmak için Ctrl+C.")
    
    # YENİ: Düzeltilmiş ana döngü
    try:
        while not stop_event.is_set():
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Ctrl+C algılandı. Kapanış...")
        stop_event.set()
    except Exception as e:
        logger.error(f"Ana schedule döngüsü hatası: {e}", exc_info=True)
        stop_event.set()
    
    # Graceful Shutdown
    logger.info("Kapanış işlemleri yürütülüyor...")
    
    if trade_manager_thread and trade_manager_thread.is_alive():
        logger.info("Trade Manager thread'inin bitmesi bekleniyor (max 10sn)...")
        trade_manager_thread.join(timeout=10)
        if trade_manager_thread.is_alive():
            logger.warning("Trade Manager thread'i zamanında durmadı.")
        else:
            logger.info("Trade Manager thread'i durduruldu.")

    if realtime_manager_thread and realtime_manager_thread.is_alive():
        logger.info("RealTime Fiyat Yöneticisi thread'inin bitmesi bekleniyor (max 10sn)...")
        realtime_manager_thread.join(timeout=10)
        if realtime_manager_thread.is_alive():
            logger.warning("RealTime Fiyat Yöneticisi thread'i zamanında durmadı.")
        else:
            logger.info("RealTime Fiyat Yöneticisi thread'i durduruldu.")

    logger.info("Veritabanı bağlantısı kapatılıyor...")
    try:
        db_session.remove()
        logger.info("✅ Veritabanı bağlantısı kapatıldı.")
    except Exception as e:
        logger.error(f"❌ Veritabanı kapatma hatası: {e}", exc_info=True)
    
    if telegram_initialized:
        try:
            stop_msg = f"ChimeraBot v{getattr(config, 'BOT_VERSION', '?.?')} durduruldu."
            telegram_notifier.send_message(telegram_notifier.escape_markdown_v2(stop_msg))
        except RuntimeError:
            logger.warning("Kapanış mesajı gönderilemedi (event loop kapalı?).")
        except Exception as e:
            logger.error(f"Kapanış mesajı hatası: {e}")

    logger.info(f"--- ChimeraBot Durduruldu ---")