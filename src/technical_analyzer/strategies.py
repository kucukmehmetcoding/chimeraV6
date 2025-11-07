# src/technical_analyzer/strategies.py

import pandas as pd
import logging
import numpy as np
import sys
import os
import re

# Proje kök dizinini ayarla
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.append(src_path)

# Loglamayı ayarla
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')

# --- Piyasa Rejimi Belirleme Fonksiyonu ---

def determine_regime(df_1d: pd.DataFrame, df_4h: pd.DataFrame = None) -> str:
    """
    Verilen 1D DataFrame'e göre (BTC veya herhangi bir coin) piyasa rejimini belirler.
    v4.0 Enhanced: Yeni coinler için 4H fallback eklendi.
    
    Args:
        df_1d: 1 günlük timeframe DataFrame
        df_4h: 4 saatlik timeframe DataFrame (opsiyonel, fallback için)
    
    Returns:
        str: 'PULLBACK', 'MEAN_REVERSION', 'BREAKOUT', 'ADVANCED_SCALP', veya 'STOP'
    """
    if df_1d is None or df_1d.empty:
        logger.warning("⚠️ Rejim belirleme için DataFrame boş. 'STOP' varsayılıyor.")
        return 'STOP'
        
    required_cols = ['adx14', 'bbw', 'close', 'sma200']
    
    # v4.0: Yeni coin kontrolü - 1D verisi yetersizse 4H'ye fallback
    use_fallback = False
    if not all(col in df_1d.columns for col in required_cols) or \
       (not df_1d.empty and df_1d.iloc[-1][required_cols].isna().any()):
        
        if df_4h is not None and not df_4h.empty and len(df_4h) >= 50:
            # 4H verisi yeterliyse onu kullan
            if all(col in df_4h.columns for col in required_cols) and \
               not df_4h.iloc[-1][required_cols].isna().any():
                logger.info(f"ℹ️ 1D verisi yetersiz, 4H timeframe'den rejim belirleniyor (Yeni coin)")
                df_1d = df_4h  # 4H'yi 1D gibi kullan
                use_fallback = True
            else:
                logger.warning(f"⚠️ Hem 1D hem 4H verisi yetersiz. 'STOP' varsayılıyor.")
                return 'STOP'
        else:
            logger.warning(f"⚠️ Rejim belirleme için DataFrame'de gerekli göstergeler eksik/NaN.")
            return 'STOP'

    last_row = df_1d.iloc[-1]
    adx = last_row['adx14']
    bbw = last_row['bbw']

    trend_threshold = 25  # Güçlü trend (Pullback için)
    chop_threshold = 20   # Trendin bittiği yer (diğer stratejiler için)
    
    bbw_period = 60; is_squeeze = False; bbw_avg = 0.0
    if len(df_1d) > bbw_period:
        historical_bbw = df_1d['bbw'].iloc[-bbw_period-1:-1]
        if not historical_bbw.empty and not historical_bbw.isna().all():
            bbw_avg = historical_bbw.mean()
            bbw_min = historical_bbw.min()
            is_squeeze = pd.notna(bbw_min) and bbw < (bbw_min * 1.1)
        else: logger.debug("   Rejim: Sıkışma kontrolü için yeterli geçmiş BBW verisi yok (NaN).")
    else: logger.debug("   Rejim: Sıkışma kontrolü için yeterli veri yok (60 günden az).")

    strategy_mode = 'STOP'

    if adx >= trend_threshold:
        strategy_mode = 'PULLBACK'
        logger.debug(f"   Rejim Hesaplandı: PULLBACK (ADX={adx:.1f} >= {trend_threshold})")
    
    elif adx < chop_threshold:
        if is_squeeze:
            strategy_mode = 'BREAKOUT'
            logger.debug(f"   Rejim Hesaplandı: BREAKOUT (ADX={adx:.1f} < {chop_threshold}, BBW={bbw:.4f} Sıkışmada)")
        elif bbw > 0 and bbw_avg > 0 and bbw > (bbw_avg * 1.1):
             strategy_mode = 'MEAN_REVERSION'
             logger.debug(f"   Rejim Hesaplandı: MEAN_REVERSION (ADX={adx:.1f} < {chop_threshold}, BBW={bbw:.4f} Genişlemede)")
        else:
             # GÜNCELLENDİ: Burası artık 'Gelişmiş Scalping' bölgesi
             strategy_mode = 'ADVANCED_SCALP'
             logger.debug(f"   Rejim Hesaplandı: ADVANCED_SCALP (ADX={adx:.1f} < {chop_threshold}, BBW={bbw:.4f} Belirsiz/Daralma)")
    
    else: # ADX, 20 ile 25 arasında (Geçiş Bölgesi)
        strategy_mode = 'STOP'
        logger.debug(f"   Rejim Hesaplandı: STOP (ADX={adx:.1f} Geçiş Bölgesi)")

    return strategy_mode


# --- Strateji Fonksiyonları ---

def find_pullback_signal(df_1d: pd.DataFrame, df_4h: pd.DataFrame, df_1h: pd.DataFrame, config: object) -> dict | None:
    """
    v5.0 ULTRA-OPTIMIZED: Pullback stratejisi sıkılaştırıldı
    
    YAPILAN OPTİMİZASYONLAR:
    1. RSI aralığı genişletildi: 30-50 → 25-55 (LONG), 50-70 → 45-75 (SHORT)
    2. VWAP toleransı artırıldı: ±0.5% → ±1.0%
    3. Ana trend konfirmasyonu güçlendirildi
    
    HEDEF: %60-70 win rate
    """
    logger.debug("ℹ️ v5.0 Pullback stratejisi çalıştırılıyor...")
    signal = None
    required_cols_1d_4h = ['close', 'ema50', 'sma200', 'supertrend_direction']
    required_cols_1h = ['close', 'ema50', 'sma200', 'rsi14', 'macd_hist', 'atr14', 'volume', 'volume_sma20', 'vwap', 'supertrend_direction']
    
    if not all(col in df_1d.columns for col in required_cols_1d_4h) or \
       not all(col in df_4h.columns for col in required_cols_1d_4h) or \
       not all(col in df_1h.columns for col in required_cols_1h):
        logger.warning("   Pullback: Gerekli gösterge sütunları eksik."); return None
    try:
        last_1d = df_1d.iloc[-1]; last_4h = df_4h.iloc[-1]; last_1h = df_1h.iloc[-1]
        if last_1d[required_cols_1d_4h].isna().any() or \
           last_4h[required_cols_1d_4h].isna().any() or \
           last_1h[required_cols_1h].isna().any():
            logger.warning("   Pullback: Son mum verilerinde NaN var."); return None

        # 1. Ana Trend (Enhanced: Supertrend confirmation on higher TFs)
        trend_1d_bullish = last_1d['close'] > last_1d['ema50'] and last_1d['ema50'] > last_1d['sma200'] and last_1d['supertrend_direction'] == 1
        trend_1d_bearish = last_1d['close'] < last_1d['ema50'] and last_1d['ema50'] < last_1d['sma200'] and last_1d['supertrend_direction'] == -1
        trend_4h_bullish = last_4h['close'] > last_4h['ema50'] and last_4h['ema50'] > last_4h['sma200'] and last_4h['supertrend_direction'] == 1
        trend_4h_bearish = last_4h['close'] < last_4h['ema50'] and last_4h['ema50'] < last_4h['sma200'] and last_4h['supertrend_direction'] == -1
        main_direction = None
        if trend_1d_bullish and trend_4h_bullish: 
            main_direction = 'LONG'
            logger.debug("   Pullback: Ana Trend = LONG (EMA+SMA+Supertrend)")
        elif trend_1d_bearish and trend_4h_bearish: 
            main_direction = 'SHORT'
            logger.debug("   Pullback: Ana Trend = SHORT (EMA+SMA+Supertrend)")
        else: 
            logger.debug("   Pullback: Ana Trend uyumsuz veya Supertrend çelişkili."); return None

        # 2. v5.0: Geri Çekilme Onayı (RSI genişletildi, VWAP toleransı artırıldı)
        rsi_1h = last_1h['rsi14']; macd_hist_1h = last_1h['macd_hist']
        vwap_1h = last_1h['vwap']; close_1h = last_1h['close']
        pullback_confirmed = False
        if main_direction == 'LONG':
            # v5.0: RSI 30-50 → 25-55 (daha esnek)
            if (25 <= rsi_1h <= 55) and (macd_hist_1h <= 0):
                # v5.0: VWAP toleransı 0.5% → 1.0%
                if close_1h >= vwap_1h * 0.99:  # ±1% tolerance
                    pullback_confirmed = True
                    logger.debug(f"   ✅ LONG Pullback: RSI={rsi_1h:.1f}, MACD<0, Price near VWAP")
                else:
                    logger.debug(f"   Pullback: Price too far below VWAP ({close_1h:.6f} vs {vwap_1h:.6f})")
        elif main_direction == 'SHORT':
            # v5.0: RSI 50-70 → 45-75 (daha esnek)
            if (45 <= rsi_1h <= 75) and (macd_hist_1h >= 0):
                # v5.0: VWAP toleransı 0.5% → 1.0%
                if close_1h <= vwap_1h * 1.01:  # ±1% tolerance
                    pullback_confirmed = True
                    logger.debug(f"   ✅ SHORT Pullback: RSI={rsi_1h:.1f}, MACD>0, Price near VWAP")
                else:
                    logger.debug(f"   Pullback: Price too far above VWAP ({close_1h:.6f} vs {vwap_1h:.6f})")
        if not pullback_confirmed: logger.debug(f"   Pullback: Geri çekilme onaylanmadı."); return None

        # 3. 1H Supertrend Direction Check (must align with main trend)
        st_1h = last_1h['supertrend_direction']
        if main_direction == 'LONG' and st_1h != 1:
            logger.debug(f"   Pullback REJECTED: 1H Supertrend bearish during LONG setup")
            return None
        elif main_direction == 'SHORT' and st_1h != -1:
            logger.debug(f"   Pullback REJECTED: 1H Supertrend bullish during SHORT setup")
            return None

        # 4. Hacim ve Volatilite Filtreleri
        current_volume = last_1h['volume']; avg_volume = last_1h['volume_sma20']
        pullback_vol_limit = getattr(config, 'PULLBACK_VOL_RATIO_LIMIT', 2.0)
        if avg_volume and avg_volume > 0 and (current_volume / avg_volume > pullback_vol_limit):
            logger.info(f"   Pullback REJECTED: Yüksek Hacim (Oran > {pullback_vol_limit})."); return None

        max_atr_percent = getattr(config, 'MAX_ATR_PERCENT', 5.0)
        current_atr = last_1h['atr14']; current_price = last_1h['close']
        atr_percent = (current_atr / current_price) * 100 if current_price > 0 else 0
        if atr_percent > max_atr_percent:
            logger.info(f"   Pullback REJECTED: Aşırı Volatilite (ATR={atr_percent:.2f}% > {max_atr_percent}%)")
            return None
        
        logger.info(f"   ✅ Pullback {main_direction} sinyali bulundu! (v5.0 OPTIMIZED: Daha esnek RSI+VWAP)")
        signal = {'direction': main_direction}
    except IndexError: logger.warning("   Pullback: Yetersiz veri."); return None
    except Exception as e: logger.error(f"   Pullback: Hata: {e}", exc_info=True); return None
    return signal

def find_mean_reversion_signal(df_4h: pd.DataFrame, df_1h: pd.DataFrame, config: object) -> dict | None:
    """
    v5.0 ULTRA-OPTIMIZED: Mean reversion stratejisi iyileştirildi
    
    YAPILAN OPTİMİZASYONLAR:
    1. RSI eşikleri gevşetildi: 30/70 → 35/65 (daha erken giriş)
    2. Trend filtresi eklendi: ADX > 30 ise mean reversion yapma
    3. VWAP distance kontrolü optimize edildi
    
    HEDEF: %50-60 win rate (riskli strateji ama düzeltildi)
    """
    logger.debug("ℹ️ v5.0 Mean Reversion stratejisi çalıştırılıyor...")
    signal = None
    required_cols_4h = ['close', 'bb_upper', 'bb_lower', 'rsi14', 'atr14', 'vwap', 'adx14']  # v5.0: ADX eklendi
    required_cols_1h = ['close', 'vwap', 'rsi14']
    
    if not all(col in df_4h.columns for col in required_cols_4h):
        logger.warning("   Mean Reversion: 4H'de gerekli göstergeler eksik."); return None
    if not all(col in df_1h.columns for col in required_cols_1h):
        logger.warning("   Mean Reversion: 1H'de gerekli göstergeler eksik."); return None
    
    try:
        last_row_4h = df_4h.iloc[-1]
        last_row_1h = df_1h.iloc[-1]
        if last_row_4h[required_cols_4h].isna().any(): 
            logger.debug(f"   Mean Reversion: Son 4H mumunda NaN var."); return None
        if last_row_1h[required_cols_1h].isna().any():
            logger.debug(f"   Mean Reversion: Son 1H mumunda NaN var."); return None
            
        close_4h = last_row_4h['close']
        bb_upper = last_row_4h['bb_upper']
        bb_lower = last_row_4h['bb_lower']
        rsi_4h = last_row_4h['rsi14']
        vwap_4h = last_row_4h['vwap']
        adx_4h = last_row_4h['adx14']  # v5.0: Trend gücü kontrolü
        
        close_1h = last_row_1h['close']
        vwap_1h = last_row_1h['vwap']
        rsi_1h = last_row_1h['rsi14']
        
        # v5.0: Güçlü trendde mean reversion yapma!
        if adx_4h > 30:
            logger.debug(f"   Mean Reversion REJECTED: Güçlü trend (ADX={adx_4h:.1f} > 30)")
            return None
        
        # ATR Volatility Filter
        max_atr_percent = getattr(config, 'MAX_ATR_PERCENT', 5.0) * 1.5
        current_atr = last_row_4h['atr14']
        atr_percent = (current_atr / close_4h) * 100 if close_4h > 0 else 0
        if atr_percent > max_atr_percent:
            logger.info(f"   Mean Reversion REJECTED: Aşırı Volatilite (ATR={atr_percent:.2f}% > {max_atr_percent}%)")
            return None
        
        # v5.0: RSI eşikleri gevşetildi 30/70 → 35/65
        # LONG: Price oversold below BB lower, but VWAP suggests reversion upward
        if close_4h < bb_lower and rsi_4h < 35:  # 30 → 35
            # Check if price is returning toward VWAP on 1H
            vwap_distance_1h = ((close_1h - vwap_1h) / vwap_1h) * 100
            if vwap_distance_1h > -5.0:  # Price within 5% below VWAP (reversion in progress)
                signal = {'direction': 'LONG'}
                logger.info(f"   ✅ Mean Reversion LONG! (4H BB+RSI oversold, 1H reverting to VWAP: {vwap_distance_1h:.2f}%)")
            else:
                logger.debug(f"   Mean Reversion: LONG setup, but price too far from VWAP ({vwap_distance_1h:.2f}%)")
        
        # SHORT: Price overbought above BB upper, but VWAP suggests reversion downward
        elif close_4h > bb_upper and rsi_4h > 65:  # 70 → 65
            # Check if price is returning toward VWAP on 1H
            vwap_distance_1h = ((close_1h - vwap_1h) / vwap_1h) * 100
            if vwap_distance_1h < 5.0:  # Price within 5% above VWAP (reversion in progress)
                signal = {'direction': 'SHORT'}
                logger.info(f"   ✅ Mean Reversion SHORT! (4H BB+RSI overbought, 1H reverting to VWAP: {vwap_distance_1h:.2f}%)")
            else:
                logger.debug(f"   Mean Reversion: SHORT setup, but price too far from VWAP ({vwap_distance_1h:.2f}%)")
        
        else:
            logger.debug(f"   Mean Reversion: 4H koşul sağlanmadı (close={close_4h:.6f}, BB=[{bb_lower:.6f}, {bb_upper:.6f}], RSI={rsi_4h:.1f}, ADX={adx_4h:.1f})")
    
    except Exception as e: 
        logger.error(f"   Mean Reversion: Hata: {e}", exc_info=True)
        return None
    return signal

def find_breakout_signal(df_1h: pd.DataFrame, config: object) -> dict | None:
    """
    v5.0 ULTRA-OPTIMIZED: Breakout stratejisi iyileştirildi
    
    YAPILAN OPTİMİZASYONLAR:
    1. Squeeze period 50 → 30 (daha sık sinyal)
    2. Volume threshold 2.0x → 1.5x (daha gerçekçi)
    3. Min ATR threshold 0.5% → 0.3% (düşük volatilitede de sinyal)
    4. BBW quantile 0.10 → 0.15 (daha esnek squeeze tanımı)
    
    HEDEF: %60-70 win rate (yüksek momentum yakalama)
    """
    logger.debug("ℹ️ v5.0 Breakout stratejisi çalıştırılıyor...")
    signal = None
    required_cols = ['close', 'bb_upper', 'bb_lower', 'bbw', 'volume', 'atr14', 'volume_sma20']
    if not all(col in df_1h.columns for col in required_cols):
        logger.warning("   Breakout: Gerekli sütunlar eksik."); return None
    try:
        volume_ratio_col = 'volumeRatio' # Bu, indicators.py'de hesaplanmıyor, burada hesaplanıyor
        volume_avg_period = 20
        if volume_ratio_col not in df_1h.columns:
            if len(df_1h) > volume_avg_period:
                 avg_volume = df_1h['volume'].iloc[-(volume_avg_period+1):-1].mean(skipna=True)
                 if avg_volume and avg_volume > 0: df_1h[volume_ratio_col] = df_1h['volume'] / avg_volume
                 else: df_1h[volume_ratio_col] = 0.0
            else: logger.warning(f"   Breakout: Hacim oranı için yetersiz veri."); df_1h[volume_ratio_col] = 0.0

        squeeze_period = 30  # v5.0: 50 → 30
        check_period = 3
        if len(df_1h) < squeeze_period + check_period: logger.debug("   Breakout: Sıkışma kontrolü için yetersiz veri."); return None
        historical_bbw = df_1h['bbw'].iloc[-squeeze_period-check_period:-check_period]
        if historical_bbw.empty or historical_bbw.isna().all(): logger.warning("   Breakout: Geçmiş BBW verisi yok/NaN."); return None
        bbw_threshold = historical_bbw.quantile(0.15)  # v5.0: 0.10 → 0.15 (daha esnek)
        recent_bbw = df_1h['bbw'].iloc[-check_period:]
        is_squeeze = pd.notna(recent_bbw).all() and (recent_bbw < bbw_threshold).all()

        if not is_squeeze: logger.debug(f"   Breakout: Sıkışma yok."); return None
        logger.debug(f"   Breakout: Sıkışma tespit edildi!")
        
        last_row = df_1h.iloc[-1]
        required_last = ['close', 'bb_upper', 'bb_lower', volume_ratio_col, 'atr14', 'supertrend_direction']
        if last_row[required_last].isna().any(): logger.debug(f"   Breakout: Son mumda NaN var."); return None
        
        close = last_row['close']; bb_upper = last_row['bb_upper']; bb_lower = last_row['bb_lower']
        volume_ratio = last_row[volume_ratio_col]
        supertrend_direction = last_row['supertrend_direction']
        volume_threshold = 1.5  # v5.0: getattr(config, 'BREAKOUT_VOL_RATIO_MIN', 2.0) → 1.5
        
        if not (volume_ratio > volume_threshold): logger.debug(f"   Breakout: Hacim yetersiz ({volume_ratio:.2f}x < {volume_threshold}x)."); return None
        
        min_atr_percent = 0.3  # v5.0: getattr(config, 'MIN_ATR_PERCENT_BREAKOUT', 0.5) → 0.3
        current_atr = last_row['atr14']
        atr_percent = (current_atr / close) * 100 if close > 0 else 0
        if atr_percent < min_atr_percent:
            logger.info(f"   Breakout REJECTED: Aşırı Düşük Volatilite (ATR={atr_percent:.2f}% < {min_atr_percent}%)")
            return None
        
        # v4.0 Enhanced: Supertrend trend confirmation (maintained in v5.0)
        if close > bb_upper:
            if supertrend_direction != 1:
                logger.info(f"   Breakout REJECTED: LONG breakout in downtrend (Supertrend=-1)")
                return None
            signal = {'direction': 'LONG'}
            logger.info(f"   ✅ Breakout LONG! (v5.0: Vol={volume_ratio:.2f}x, ATR={atr_percent:.2f}%, Supertrend Onaylı)")
        elif close < bb_lower:
            if supertrend_direction != -1:
                logger.info(f"   Breakout REJECTED: SHORT breakout in uptrend (Supertrend=1)")
                return None
            signal = {'direction': 'SHORT'}
            logger.info(f"   ✅ Breakout SHORT! (v5.0: Vol={volume_ratio:.2f}x, ATR={atr_percent:.2f}%, Supertrend Onaylı)")
        else: logger.debug(f"   Breakout: Kırılım koşulu sağlanmadı.")
    except Exception as e: logger.error(f"   Breakout: Hata: {e}", exc_info=True); return None
    return signal

# --- YENİ EKLENDİ: Gelişmiş Scalp Stratejisi (Aşama 4) ---

def find_advanced_scalp_signal(df_to_scan: pd.DataFrame, config: object) -> dict | None:
    """
    v5.0 ULTRA-OPTIMIZED: Gelişmiş scalping stratejisi
    
    YAPILAN OPTİMİZASYONLAR:
    1. RSI ranges gevşetildi: LONG 45-75 → 40-80, SHORT 25-55 → 20-60
    2. Volume threshold 1.8x → 1.3x (daha sık sinyal)
    3. Required conditions 6/8 → 5/8 (%75 → %62.5)
    4. Max ATR 2.0% → 3.0% (daha volatil coinde de çalışır)
    
    NOT: Config'de SCALP_TIMEFRAME'i '15m' → '1h' değiştirin (funding maliyeti için)
    
    HEDEF: %55-65 win rate (hızlı giriş-çıkış)
    """
    logger.debug("ℹ️ v5.0 Gelişmiş Scalp stratejisi çalıştırılıyor...")
    signal = None
    
    # Gerekli göstergeler (v4.0 güncellemesi)
    required_cols = ['close', 'ema8', 'ema21', 'rsi14', 'macd', 'macd_signal', 'macd_hist', 
                     'volume', 'volume_sma20', 'atr14']
    optional_cols = ['vwap', 'supertrend_direction', 'stoch_rsi_signal']  # Yeni göstergeler
    
    if not all(col in df_to_scan.columns for col in required_cols):
        logger.warning(f"   Advanced Scalp: Gerekli gösterge sütunları eksik. İhtiyaç: {required_cols}")
        return None
        
    if len(df_to_scan) < 2:
        logger.warning("   Advanced Scalp: Kesişim kontrolü için yetersiz veri (< 2 mum)."); return None

    try:
        last_row = df_to_scan.iloc[-1]
        prev_row = df_to_scan.iloc[-2]

        # Son mumdaki değerlerde NaN kontrolü
        if last_row[required_cols].isna().any() or prev_row[required_cols].isna().any():
            logger.debug("   Advanced Scalp: Son 2 mumda NaN değerler var."); return None

        # --- Strateji Koşullarını Oluştur (9 Koşul - 3 Yeni) ---
        conditions = {}
        
        # 1. EMA Kesişimi
        conditions['ema_cross_long'] = (prev_row['ema8'] <= prev_row['ema21']) and (last_row['ema8'] > last_row['ema21'])
        conditions['ema_cross_short'] = (prev_row['ema8'] >= prev_row['ema21']) and (last_row['ema8'] < last_row['ema21'])

        # 2. MACD Onayı
        conditions['macd_bullish'] = (last_row['macd'] > last_row['macd_signal']) and (last_row['macd_hist'] > 0)
        conditions['macd_bearish'] = (last_row['macd'] < last_row['macd_signal']) and (last_row['macd_hist'] < 0)

        # 3. RSI Filtresi - v5.0: Gevşetildi
        rsi = last_row['rsi14']
        rsi_upper_filter = 80.0  # v5.0: getattr(config, 'SCALP_RSI_LONG_ENTRY_MAX', 75.0) → 80
        rsi_lower_filter = 40.0  # v5.0: getattr(config, 'SCALP_RSI_LONG_ENTRY_MIN', 45.0) → 40
        conditions['rsi_optimal_long'] = (rsi > rsi_lower_filter) and (rsi < rsi_upper_filter)

        rsi_upper_filter_short = 60.0  # v5.0: getattr(config, 'SCALP_RSI_SHORT_ENTRY_MAX', 55.0) → 60
        rsi_lower_filter_short = 20.0  # v5.0: getattr(config, 'SCALP_RSI_SHORT_ENTRY_MIN', 25.0) → 20
        conditions['rsi_optimal_short'] = (rsi > rsi_lower_filter_short) and (rsi < rsi_upper_filter_short)

        # 4. Hacim Artışı - v5.0: 1.8x → 1.3x
        volume_ratio_min = 1.3  # v5.0: getattr(config, 'SCALP_VOL_RATIO_MIN', 1.8) → 1.3
        current_volume = last_row['volume']; avg_volume = last_row['volume_sma20']
        conditions['volume_spike'] = (avg_volume > 0) and (current_volume / avg_volume > volume_ratio_min)
        
        # 5. Volatilite Filtresi - v5.0: 2.0% → 3.0%
        max_atr_percent = 3.0  # v5.0: getattr(config, 'SCALP_MAX_ATR_PERCENT', 2.0) → 3.0
        current_atr = last_row['atr14']; current_price = last_row['close']
        atr_percent = (current_atr / current_price) * 100 if current_price > 0 else 0
        conditions['volatility_ok'] = (atr_percent > 0) and (atr_percent < max_atr_percent)
        
        # --- YENİ v4.0 KOŞULLAR (v5.0'da korundu) ---
        
        # 6. VWAP Filtresi (Büyük oyuncular hangi tarafta?)
        if 'vwap' in df_to_scan.columns and pd.notna(last_row.get('vwap')):
            conditions['price_above_vwap'] = last_row['close'] > last_row['vwap']
            conditions['price_below_vwap'] = last_row['close'] < last_row['vwap']
        else:
            conditions['price_above_vwap'] = True  # VWAP yoksa nötr
            conditions['price_below_vwap'] = True
        
        # 7. Supertrend Onayı (Trend yönü doğru mu?)
        if 'supertrend_direction' in df_to_scan.columns and pd.notna(last_row.get('supertrend_direction')):
            conditions['supertrend_bullish'] = last_row['supertrend_direction'] == 1
            conditions['supertrend_bearish'] = last_row['supertrend_direction'] == -1
        else:
            conditions['supertrend_bullish'] = True  # Supertrend yoksa nötr
            conditions['supertrend_bearish'] = True
        
        # 8. Stochastic RSI Momentum Onayı
        if 'stoch_rsi_signal' in df_to_scan.columns and pd.notna(last_row.get('stoch_rsi_signal')):
            conditions['stoch_rsi_bullish'] = last_row['stoch_rsi_signal'] == 'BUY'
            conditions['stoch_rsi_bearish'] = last_row['stoch_rsi_signal'] == 'SELL'
        else:
            conditions['stoch_rsi_bullish'] = True  # Stoch RSI yoksa nötr
            conditions['stoch_rsi_bearish'] = True
        
        # --- Koşulları Değerlendir ---
        
        # v5.0: 8 koşuldan en az 5'i (%62.5) sağlanmalı (6 yerine)
        required_count = 5  # v5.0: getattr(config, 'SCALP_CONDITIONS_REQUIRED_COUNT', 6) → 5
        
        # LONG Değerlendirmesi
        long_conditions_met = sum([
            conditions['ema_cross_long'],
            conditions['macd_bullish'],
            conditions['rsi_optimal_long'],
            conditions['volume_spike'],
            conditions['volatility_ok'],
            conditions['price_above_vwap'],      # YENİ
            conditions['supertrend_bullish'],    # YENİ
            conditions['stoch_rsi_bullish']      # YENİ
        ])
        
        if long_conditions_met >= required_count:
            signal = {'direction': 'LONG'}
            logger.info(f"   ✅ Advanced Scalp LONG! (v5.0: {long_conditions_met}/8 Koşul, Vol={current_volume/avg_volume:.2f}x, ATR={atr_percent:.2f}%)")
            logger.debug(f"      VWAP: {'✓' if conditions['price_above_vwap'] else '✗'} | "
                        f"Supertrend: {'✓' if conditions['supertrend_bullish'] else '✗'} | "
                        f"Stoch RSI: {'✓' if conditions['stoch_rsi_bullish'] else '✗'}")

        # SHORT Değerlendirmesi
        short_conditions_met = sum([
            conditions['ema_cross_short'],
            conditions['macd_bearish'],
            conditions['rsi_optimal_short'],
            conditions['volume_spike'],
            conditions['volatility_ok'],
            conditions['price_below_vwap'],      # YENİ
            conditions['supertrend_bearish'],    # YENİ
            conditions['stoch_rsi_bearish']      # YENİ
        ])
        
        if short_conditions_met >= required_count:
            signal = {'direction': 'SHORT'}
            logger.info(f"   ✅ Advanced Scalp SHORT! (v5.0: {short_conditions_met}/8 Koşul, Vol={current_volume/avg_volume:.2f}x, ATR={atr_percent:.2f}%)")
            logger.debug(f"      VWAP: {'✓' if conditions['price_below_vwap'] else '✗'} | "
                        f"Supertrend: {'✓' if conditions['supertrend_bearish'] else '✗'} | "
                        f"Stoch RSI: {'✓' if conditions['stoch_rsi_bearish'] else '✗'}")

        if not signal:
             logger.debug(f"   Advanced Scalp: Koşullar sağlanmadı (LONG: {long_conditions_met}/8, SHORT: {short_conditions_met}/8)")
             
    except IndexError: logger.warning("   Advanced Scalp: Yetersiz veri."); return None
    except Exception as e: logger.error(f"   Advanced Scalp: Hata: {e}", exc_info=True); return None

    return signal


# --- Test Kodu ---
if __name__ == "__main__":
    # ... (Test kodu aynı kalmalı, sadece yeni strateji testi eklendi) ...
    logger.info("--- strategies.py fonksiyon testi ---")
    try:
        from src.data_fetcher.binance_fetcher import get_binance_klines
        from src.technical_analyzer.indicators import calculate_indicators
        from src import config as test_config
    except ImportError as e:
        logger.error(f"❌ Gerekli modüller import edilemedi: {e}"); sys.exit(1)

    # ... (Rejim, Pullback, MR, Breakout testleri aynı) ...
    
    # GÜNCELLENDİ: Test bloğu
    logger.info("\n--- Rejim Belirleme Testi ---")
    btc_1d_raw = get_binance_klines(symbol='BTCUSDT', interval='1d', limit=300)
    current_regime = 'STOP'
    btc_1d_indicators = None
    if btc_1d_raw is not None and not btc_1d_raw.empty:
        btc_1d_indicators = calculate_indicators(btc_1d_raw.copy())
        if btc_1d_indicators is not None and 'adx14' in btc_1d_indicators.columns:
            current_regime = determine_regime(btc_1d_indicators)
            print(f"\n>>> Mevcut Piyasa Rejimi (Test): {current_regime} <<<")
        else: print("BTC 1D göstergeleri hesaplanamadı.")
    else: print("BTC 1D verisi çekilemedi.")

    btc_4h_raw = get_binance_klines(symbol='BTCUSDT', interval='4h', limit=300)
    btc_1h_raw = get_binance_klines(symbol='BTCUSDT', interval='1h', limit=300)
    btc_4h_indicators = None; btc_1h_indicators = None
    if btc_4h_raw is not None and not btc_4h_raw.empty: btc_4h_indicators = calculate_indicators(btc_4h_raw.copy())
    if btc_1h_raw is not None and not btc_1h_raw.empty: btc_1h_indicators = calculate_indicators(btc_1h_raw.copy())

    logger.info("--- Pullback Strateji Testi ---")
    if all(df is not None for df in [btc_1d_indicators, btc_4h_indicators, btc_1h_indicators]):
        pullback_result = find_pullback_signal(btc_1d_indicators, btc_4h_indicators, btc_1h_indicators, test_config)
        print(f"Pullback Sinyal Sonucu: {pullback_result}")
    else: print("Pullback testi için veri/gösterge eksik.")

    logger.info("\n--- Mean Reversion Strateji Testi ---")
    if btc_4h_indicators is not None:
        mean_reversion_result = find_mean_reversion_signal(btc_4h_indicators, btc_1h_indicators, test_config)
        print(f"Mean Reversion Sinyal Sonucu: {mean_reversion_result}")
    else: print("Mean Reversion testi için 4H verisi/gösterge eksik.")

    logger.info("\n--- Breakout Strateji Testi ---")
    if btc_1h_indicators is not None:
        breakout_result = find_breakout_signal(btc_1h_indicators, test_config)
        print(f"Breakout Sinyal Sonucu: {breakout_result}")
    else: print("Breakout testi için 1H verisi/gösterge eksik.")

    # YENİ: Advanced Scalp Strateji Testi
    logger.info(f"\n--- Advanced Scalp ({test_config.SCALP_TIMEFRAME}) Strateji Testi ---")
    scalp_tf_data_raw = get_binance_klines(symbol='BTCUSDT', interval=test_config.SCALP_TIMEFRAME, limit=100)
    scalp_tf_indicators = None
    if scalp_tf_data_raw is not None and not scalp_tf_data_raw.empty:
         scalp_tf_indicators = calculate_indicators(scalp_tf_data_raw.copy())
         
    if scalp_tf_indicators is not None and 'ema8' in scalp_tf_indicators.columns:
        scalp_result = find_advanced_scalp_signal(scalp_tf_indicators, test_config)
        print(f"Advanced Scalp Sinyal Sonucu: {scalp_result}")
    else:
        print("Advanced Scalp testi için veri/gösterge eksik.")

    print("\n--- Test tamamlandı ---")