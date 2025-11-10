# src/technical_analyzer/strategies.py

import pandas as pd
import logging
import numpy as np
import sys
import os
import re
import time

# --- Strategy Metrics (Instrumentation) ---
strategy_metrics = {
    'breakout_layer1_pass': 0,
    'breakout_layer2_pass': 0,
    'breakout_layer2_fail': 0,
    'breakout_relaxed_adx_used': 0,
    'breakout_relaxed_macd_used': 0,
    'breakout_extended_rsi_usage': 0,
    'breakout_layer3_fail': 0,
    'breakout_layer4_fail': 0,
    'breakout_layer5_fail': 0,
    'pullback_vwap_extended_usage': 0
}
_last_metrics_dump_ts = time.time()

def _maybe_dump_metrics(config):
    """Periyodik olarak metriği logla (varsayılan 30dk)."""
    global _last_metrics_dump_ts
    interval = getattr(config, 'METRICS_DUMP_INTERVAL_SECONDS', 1800)
    now = time.time()
    if now - _last_metrics_dump_ts >= interval:
        msg = (
            f"METRICS ROLLUP | L1_pass={strategy_metrics['breakout_layer1_pass']} "
            f"L2_pass={strategy_metrics['breakout_layer2_pass']} L2_fail={strategy_metrics['breakout_layer2_fail']} "
            f"ADX_relaxed={strategy_metrics['breakout_relaxed_adx_used']} MACD_relaxed={strategy_metrics['breakout_relaxed_macd_used']} "
            f"RSI_ext_used={strategy_metrics['breakout_extended_rsi_usage']} L3_fail={strategy_metrics['breakout_layer3_fail']} "
            f"L4_fail={strategy_metrics['breakout_layer4_fail']} L5_fail={strategy_metrics['breakout_layer5_fail']} "
            f"Pullback_VWAP_ext={strategy_metrics['pullback_vwap_extended_usage']}"
        )
        logger.info(msg)
        _last_metrics_dump_ts = now

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
    BTC 1D verisine bakarak piyasa rejimini belirler.
    ADX ve BB Width değerlerine göre strateji modu döndürür.
    
    Args:
        df_1d: BTC 1 günlük DataFrame (göstergelerle)
        df_4h: BTC 4 saatlik DataFrame (fallback için, opsiyonel)
    
    Returns:
        'PULLBACK', 'MEAN_REVERSION', 'BREAKOUT', 'ADVANCED_SCALP' veya 'STOP'
    """
    # 1D veri kontrolü
    if df_1d is None or df_1d.empty or len(df_1d) < 2:
        logger.warning("BTC 1D DataFrame boş veya yetersiz, 4H fallback deneniyor...")
        
        # Fallback: 4H verisi
        if df_4h is None or df_4h.empty or len(df_4h) < 2:
            logger.warning("BTC 4H DataFrame de yetersiz, STOP moduna geçiliyor")
            return 'STOP'
        else:
            # 4H ile devam et
            df_to_use = df_4h
            logger.info("📊 Regime belirleme 4H verisi ile yapılıyor")
    else:
        df_to_use = df_1d
    
    required_cols = ['adx14', 'bbw']
    if not all(col in df_to_use.columns for col in required_cols):
        logger.warning(f"BTC verisinde gerekli kolonlar eksik: {required_cols}, STOP moduna geçiliyor")
        return 'STOP'
    
    last = df_to_use.iloc[-1]
    
    # NaN kontrolü
    if last[required_cols].isna().any():
        logger.warning("BTC son bar'ında NaN değer var, STOP moduna geçiliyor")
        return 'STOP'
    
    adx = last['adx14']
    bbw = last['bbw']
    
    # Orijinal regime mantığı (algoritma korunuyor)
    if adx > 25 and bbw > 0.04:
        regime = 'BREAKOUT'
    elif adx < 20 and bbw < 0.02:
        regime = 'MEAN_REVERSION'
    elif adx >= 30 and bbw > 0.05:
        regime = 'ADVANCED_SCALP'
    else:
        regime = 'PULLBACK'
    
    logger.info(f"📊 BTC Regime: {regime} (ADX={adx:.2f}, BBW={bbw:.4f})")
    return regime


# --- Strateji Fonksiyonları ---

def validate_dataframe(df: pd.DataFrame, required_columns: list, min_rows: int = 2) -> bool:
    """
    DataFrame'in strateji için kullanılabilir olup olmadığını kontrol eder.
    
    Args:
        df: Kontrol edilecek DataFrame
        required_columns: Olması gereken kolon isimleri
        min_rows: Minimum satır sayısı
    
    Returns:
        True: Veri kullanılabilir, False: Veri eksik/hatalı
    """
    if df is None or df.empty:
        logger.debug("DataFrame boş")
        return False
    
    if len(df) < min_rows:
        logger.debug(f"DataFrame yetersiz veri: {len(df)} < {min_rows}")
        return False
    
    # Kolon varlık kontrolü
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        logger.debug(f"Eksik kolonlar: {missing_cols}")
        return False
    
    # Son satırda NaN kontrolü
    last_row = df.iloc[-1]
    if last_row[required_columns].isna().any():
        nan_cols = [col for col in required_columns if pd.isna(last_row[col])]
        logger.debug(f"Son satırda NaN değer var: {nan_cols}")
        return False
    
    return True

# --- v9.0 PRECISION: Trend ve Volume Validation Helper Fonksiyonları ---

def check_strong_trend(df: pd.DataFrame, direction: str) -> bool:
    """
    Güçlü trend kontrolü: EMA50 > SMA200 (LONG) veya tersi (SHORT).
    
    Args:
        df: DataFrame (1D veya 4H timeframe)
        direction: 'LONG' veya 'SHORT'
    
    Returns:
        True: Trend güçlü ve yönü doğru, False: Trend yok veya zayıf
    """
    required_cols = ['close', 'ema50', 'sma200']
    if not all(col in df.columns for col in required_cols):
        logger.debug(f"Trend kontrolü: Gerekli kolonlar eksik ({required_cols})")
        return False
    
    last = df.iloc[-1]
    if last[required_cols].isna().any():
        logger.debug("Trend kontrolü: NaN değer var")
        return False
    
    close = last['close']
    ema50 = last['ema50']
    sma200 = last['sma200']
    
    if direction == 'LONG':
        # LONG için: EMA50 > SMA200 ve fiyat her ikisinin de üstünde
        trend_ok = (ema50 > sma200) and (close > ema50)
        if not trend_ok:
            logger.debug(f"LONG trend zayıf: Close={close:.6f}, EMA50={ema50:.6f}, SMA200={sma200:.6f}")
        return trend_ok
    
    elif direction == 'SHORT':
        # SHORT için: EMA50 < SMA200 ve fiyat her ikisinin de altında
        trend_ok = (ema50 < sma200) and (close < ema50)
        if not trend_ok:
            logger.debug(f"SHORT trend zayıf: Close={close:.6f}, EMA50={ema50:.6f}, SMA200={sma200:.6f}")
        return trend_ok
    
    return False


def check_volume_confirmation(df: pd.DataFrame, min_ratio: float = 1.5) -> bool:
    """
    Volume confirmation kontrolü: Mevcut hacim ortalamanın min_ratio katından fazla mı?
    
    Args:
        df: DataFrame (genellikle 1H)
        min_ratio: Minimum hacim oranı (varsayılan: 1.5x)
    
    Returns:
        True: Volume yeterli, False: Volume düşük
    """
    required_cols = ['volume', 'volume_sma20']
    if not all(col in df.columns for col in required_cols):
        logger.debug(f"Volume kontrolü: Gerekli kolonlar eksik ({required_cols})")
        return False
    
    last = df.iloc[-1]
    if last[required_cols].isna().any():
        logger.debug("Volume kontrolü: NaN değer var")
        return False
    
    current_vol = last['volume']
    avg_vol = last['volume_sma20']
    
    if avg_vol <= 0:
        logger.debug("Volume kontrolü: volume_sma20 sıfır veya negatif")
        return False
    
    vol_ratio = current_vol / avg_vol
    volume_ok = vol_ratio >= min_ratio
    
    if not volume_ok:
        logger.debug(f"Volume yetersiz: {vol_ratio:.2f}x < {min_ratio}x gerekli")
    else:
        logger.debug(f"Volume yeterli: {vol_ratio:.2f}x >= {min_ratio}x")
    
    return volume_ok


# =============================================================================
# v9.0 PRECISION MODE: Advanced Multi-Layer Helper Functions
# =============================================================================

def check_institutional_trend_1d(df_1d: pd.DataFrame) -> tuple:
    """
    Layer 1 for BREAKOUT: 1D kurumsal trend - Sadece TEK YÖNDE breakout al.
    EMA/SMA hierarchy kontrolü ile kurumsal bias belirleme.
    
    Returns:
        (direction, message): ('LONG'|'SHORT'|None, açıklama mesajı)
    """
    required = ['close', 'ema5', 'ema20', 'ema50', 'sma200']
    if not all(col in df_1d.columns for col in required):
        return None, "1D'de gerekli EMA/SMA kolonları eksik"
    
    last = df_1d.iloc[-1]
    if last[required].isna().any():
        return None, "1D'de NaN değer var"
    
    close = last['close']
    ema5 = last['ema5']
    ema20 = last['ema20']
    ema50 = last['ema50']
    sma200 = last['sma200']
    
    # Perfect bullish hierarchy: Close > EMA5 > EMA20 > EMA50 > SMA200
    bullish_hierarchy = (close > ema5 > ema20 > ema50 > sma200)
    
    # Perfect bearish hierarchy: Close < EMA5 < EMA20 < EMA50 < SMA200
    bearish_hierarchy = (close < ema5 < ema20 < ema50 < sma200)
    
    if bullish_hierarchy:
        return 'LONG', f"1D perfect bullish hierarchy (Close>{ema5:.2f}>{ema20:.2f}>{ema50:.2f}>{sma200:.2f})"
    elif bearish_hierarchy:
        return 'SHORT', f"1D perfect bearish hierarchy (Close<{ema5:.2f}<{ema20:.2f}<{ema50:.2f}<{sma200:.2f})"
    else:
        return None, f"1D trend karışık - breakout yok (Close={close:.2f}, EMA hierarşisi bozuk)"


def check_momentum_buildup_4h(df_4h: pd.DataFrame, direction: str, config) -> tuple:
    """
    Layer 2 for BREAKOUT: 4H'de momentum birikmesi kontrolü.
    RSI momentum zone + artan MACD + artan ADX.
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['rsi14', 'macd_hist', 'adx14']
    if not all(col in df_4h.columns for col in required):
        return False, "4H'de RSI/MACD/ADX eksik"
    
    if len(df_4h) < 5:
        return False, "4H'de yetersiz veri (<5 mum)"
    
    last = df_4h.iloc[-1]
    prev = df_4h.iloc[-2]
    
    if last[required].isna().any() or prev[required].isna().any():
        return False, "4H'de NaN değer var"
    
    rsi = last['rsi14']
    adx = last['adx14']
    prev_adx = prev['adx14']
    
    # --- RSI Core / Extended Bantları (Konfigürasyondan) ---
    core_low_long = getattr(config, 'BREAKOUT_RSI_CORE_LOW', 52)
    core_high_long = getattr(config, 'BREAKOUT_RSI_CORE_HIGH', 68)
    ext_low_long = getattr(config, 'BREAKOUT_RSI_EXT_LOW', 48)
    ext_high_long = getattr(config, 'BREAKOUT_RSI_EXT_HIGH', 72)

    core_low_short = getattr(config, 'BREAKOUT_RSI_CORE_SHORT_LOW', 30)
    core_high_short = getattr(config, 'BREAKOUT_RSI_CORE_SHORT_HIGH', 50)
    ext_low_short = getattr(config, 'BREAKOUT_RSI_EXT_SHORT_LOW', 28)
    ext_high_short = getattr(config, 'BREAKOUT_RSI_EXT_SHORT_HIGH', 52)
    require_extra = getattr(config, 'BREAKOUT_REQUIRE_EXTRA_CONFIRM_OUTSIDE_CORE', True)

    extended_rsi_used = False
    if direction == 'LONG':
        if not (core_low_long <= rsi <= core_high_long):
            # Extended banda düşerse ek doğrulama gerek
            if ext_low_long <= rsi <= ext_high_long:
                # Ek doğrulama: ADX hafif yükselme + son 3 MACD diflerinden >=1 pozitif
                macd_hist_recent = df_4h['macd_hist'].iloc[-5:]
                macd_diff_positive = (macd_hist_recent.diff() > 0).sum() >= 1
                if require_extra and not macd_diff_positive:
                    return False, f"4H RSI extended bölgede ama MACD momentum zayıf (rsi={rsi:.1f})"
                extended_rsi_used = True
            else:
                return False, f"4H RSI momentum zone dışında ({rsi:.1f}, core:{core_low_long}-{core_high_long})"
    else:  # SHORT
        if not (core_low_short <= rsi <= core_high_short):
            if ext_low_short <= rsi <= ext_high_short:
                macd_hist_recent = df_4h['macd_hist'].iloc[-5:]
                macd_diff_negative = (macd_hist_recent.diff() < 0).sum() >= 1
                if require_extra and not macd_diff_negative:
                    return False, f"4H RSI extended bölgede ama MACD momentum zayıf (rsi={rsi:.1f})"
                extended_rsi_used = True
            else:
                return False, f"4H RSI momentum zone dışında ({rsi:.1f}, core:{core_low_short}-{core_high_short})"
    
    # MACD histogram trending kontrolü
    macd_hist_recent = df_4h['macd_hist'].iloc[-5:]
    macd_relaxed_used = False
    if direction == 'LONG':
        increasing = (macd_hist_recent.diff() > 0).sum()
        if increasing < 3:
            # Relaxed kuralı devrede mi?
            if (
                getattr(config, 'BREAKOUT_ENABLE_MACD_RELAXED', False)
                and increasing >= getattr(config, 'BREAKOUT_MACD_RELAXED_MIN_INCREASING', 2)
                and macd_hist_recent.iloc[-1] > macd_hist_recent.iloc[-2]
            ):
                macd_relaxed_used = True
            else:
                return False, f"4H MACD histogram artan değil ({increasing}/5)"
    elif direction == 'SHORT':
        decreasing = (macd_hist_recent.diff() < 0).sum()
        if decreasing < 3:
            if (
                getattr(config, 'BREAKOUT_ENABLE_MACD_RELAXED', False)
                and decreasing >= getattr(config, 'BREAKOUT_MACD_RELAXED_MIN_INCREASING', 2)
                and macd_hist_recent.iloc[-1] < macd_hist_recent.iloc[-2]
            ):
                macd_relaxed_used = True
            else:
                return False, f"4H MACD histogram azalan değil ({decreasing}/5)"
    
    # ADX yükseliyor mu?
    tolerance = getattr(config, 'BREAKOUT_ADX_DELTA_TOLERANCE', 0.0)
    adx_relaxed_used = False
    if adx + tolerance < prev_adx:
        return False, f"4H ADX düşüyor ({adx:.1f} < {prev_adx:.1f} - tol:{tolerance:.2f})"
    elif adx < prev_adx:
        adx_relaxed_used = True  # Tolerance sayesinde kabul

    return True, f"4H momentum building (RSI:{rsi:.1f}, ADX:{adx:.1f}↑)", extended_rsi_used, macd_relaxed_used, adx_relaxed_used



def check_squeeze_quality_1h(df_1h: pd.DataFrame, config=None) -> tuple:
    """
    Layer 3 for BREAKOUT: Squeeze kalitesi - sadece EN İYİ sıkışmalarda breakout al.
    Sıkışma süresi (5-20 mum) + BBW alt %15'te.
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    if 'bbw' not in df_1h.columns:
        return False, "1H'de BBW eksik"
    
    if len(df_1h) < 100:
        return False, "1H'de BBW percentile hesabı için yetersiz veri (<100)"
    
    # BBW threshold (alt %25)
    historical_bbw = df_1h['bbw'].iloc[-100:-3]
    bbw_threshold = historical_bbw.quantile(0.25)
    
    # Sıkışma süresi hesapla
    squeeze_duration = 0
    for i in range(len(df_1h) - 1, -1, -1):
        if df_1h.iloc[i]['bbw'] < bbw_threshold:
            squeeze_duration += 1
        else:
            break
    
    # Çok kısa sıkışma = zayıf
    min_bars = getattr(config, 'BREAKOUT_MIN_SQUEEZE_BARS', 5) if config is not None else 5
    max_bars = getattr(config, 'BREAKOUT_MAX_SQUEEZE_BARS', 20) if config is not None else 20
    if squeeze_duration < min_bars:
        return False, f"Sıkışma çok kısa ({squeeze_duration} mum < {min_bars})"
    
    # Çok uzun sıkışma = enerji tükendi
    if squeeze_duration > max_bars:
        return False, f"Sıkışma çok uzun ({squeeze_duration} mum > {max_bars}) - enerji tükendi"
    
    # BBW percentile kontrolü (alt %15'te mi?)
    recent_bbw = df_1h['bbw'].iloc[-100:]
    current_bbw = df_1h.iloc[-1]['bbw']
    percentile = (recent_bbw < current_bbw).sum() / len(recent_bbw) * 100
    
    bbw_percentile_max = getattr(config, 'BREAKOUT_BBW_PERCENTILE_MAX', 15.0) if config is not None else 15.0
    if percentile > bbw_percentile_max:
        return False, f"BBW yeterince düşük değil ({percentile:.0f}. percentile, gerekli: <{bbw_percentile_max:.0f})"
    
    return True, f"Squeeze PERFECT (Süre:{squeeze_duration} mum, BBW:{percentile:.0f}. %)"


def check_volume_expansion(df_1h: pd.DataFrame, config=None) -> tuple:
    """
    Layer 4 for BREAKOUT: Kurumsal hacim patlaması kontrolü.
    2.5x ortalama hacim + son muma göre %30+ artış + progressive artış.
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['volume', 'volume_sma20']
    if not all(col in df_1h.columns for col in required):
        return False, "1H'de volume kolonları eksik"
    
    if len(df_1h) < 3:
        return False, "1H'de progressive volume için yetersiz veri"
    
    last = df_1h.iloc[-1]
    prev = df_1h.iloc[-2]
    
    vol = last['volume']
    avg_vol = last['volume_sma20']
    prev_vol = prev['volume']
    
    if avg_vol <= 0:
        return False, "volume_sma20 sıfır veya negatif"
    
    # Hacim eşiği (varsayılan 2.5x, gevşeme fazında düşürülebilir)
    vol_ratio = vol / avg_vol
    if config is not None and getattr(config, 'ENABLE_BREAKOUT_RELAX_PHASE', False):
        vol_min = getattr(config, 'BREAKOUT_VOLUME_RATIO_MIN_RELAXED', 2.25)
    else:
        vol_min = 2.5
    if vol_ratio < vol_min:
        return False, f"Volume yetersiz ({vol_ratio:.1f}x < {vol_min:.2f}x)"
    
    # Son muma göre artış (%30 varsayılan, gevşeme fazında %27)
    if prev_vol > 0:
        vol_increase = ((vol / prev_vol) - 1) * 100
        if config is not None and getattr(config, 'ENABLE_BREAKOUT_RELAX_PHASE', False):
            inc_min = getattr(config, 'BREAKOUT_VOLUME_INCREASE_MIN_RELAXED', 27.0)
        else:
            inc_min = 30.0
        if vol_increase < inc_min:
            return False, f"Volume artışı düşük ({vol_increase:.0f}% < {inc_min:.0f}%)"
    else:
        return False, "Önceki volume sıfır"
    
    # Progressive volume artışı (son 3 mum)
    recent_vols = df_1h['volume'].iloc[-3:]
    progressive = all(recent_vols.iloc[i] < recent_vols.iloc[i+1] for i in range(len(recent_vols)-1))
    if not progressive:
        return False, "Volume artışı progressive değil"
    
    return True, f"Volume EXPLOSION ({vol_ratio:.1f}x, +{vol_increase:.0f}%, progressive)"


def check_breakout_strength(df_1h: pd.DataFrame, direction: str, config=None) -> tuple:
    """
    Layer 5 for BREAKOUT: Breakout gücü kontrolü.
    BB kırılma mesafesi (%0.3+) + mum body gücü (%60+) + önceki mum momentum.
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['close', 'open', 'high', 'low', 'bb_upper', 'bb_lower']
    if not all(col in df_1h.columns for col in required):
        return False, "1H'de OHLC/BB kolonları eksik"
    
    if len(df_1h) < 2:
        return False, "Breakout strength için yetersiz veri"
    
    last = df_1h.iloc[-1]
    prev = df_1h.iloc[-2]
    
    if last[required].isna().any():
        return False, "Son mumda NaN değer var"
    
    close = last['close']
    open_price = last['open']
    high = last['high']
    low = last['low']
    bb_upper = last['bb_upper']
    bb_lower = last['bb_lower']
    
    if direction == 'LONG':
        # BB upper kırılma gücü
        if bb_upper <= 0:
            return False, "bb_upper sıfır veya negatif"
        
        breakout_distance = ((close - bb_upper) / bb_upper) * 100
        if config is not None and getattr(config, 'ENABLE_BREAKOUT_RELAX_PHASE', False):
            dist_min = getattr(config, 'BREAKOUT_DISTANCE_MIN_RELAXED', 0.27)
        else:
            dist_min = 0.30
        if breakout_distance < dist_min:
            return False, f"Breakout zayıf ({breakout_distance:.2f}% < {dist_min:.2f}%)"
        
        # Mum body strength
        body = close - open_price
        total_range = high - low
        body_pct = (body / total_range) * 100 if total_range > 0 else 0
        
        if config is not None and getattr(config, 'ENABLE_BREAKOUT_RELAX_PHASE', False):
            body_min = getattr(config, 'BREAKOUT_BODY_STRENGTH_MIN_RELAXED', 54.0)
        else:
            body_min = 60.0
        if body_pct < body_min:
            return False, f"Mum body zayıf ({body_pct:.0f}% < {body_min:.0f}%)"
        
        # Önceki mum pozitif mi?
        prev_close = prev['close']
        prev_open = prev['open']
        if prev_close <= prev_open:
            return False, "Önceki mum negatif - momentum yok"
        
        return True, f"Breakout STRONG (Distance:{breakout_distance:.2f}%, Body:{body_pct:.0f}%)"
    
    elif direction == 'SHORT':
        # BB lower kırılma gücü
        if bb_lower <= 0:
            return False, "bb_lower sıfır veya negatif"
        
        breakout_distance = ((bb_lower - close) / bb_lower) * 100
        if config is not None and getattr(config, 'ENABLE_BREAKOUT_RELAX_PHASE', False):
            dist_min = getattr(config, 'BREAKOUT_DISTANCE_MIN_RELAXED', 0.27)
        else:
            dist_min = 0.30
        if breakout_distance < dist_min:
            return False, f"Breakout zayıf ({breakout_distance:.2f}% < {dist_min:.2f}%)"
        
        # Mum body strength
        body = open_price - close
        total_range = high - low
        body_pct = (body / total_range) * 100 if total_range > 0 else 0
        
        if config is not None and getattr(config, 'ENABLE_BREAKOUT_RELAX_PHASE', False):
            body_min = getattr(config, 'BREAKOUT_BODY_STRENGTH_MIN_RELAXED', 54.0)
        else:
            body_min = 60.0
        if body_pct < body_min:
            return False, f"Mum body zayıf ({body_pct:.0f}% < {body_min:.0f}%)"
        
        # Önceki mum negatif mi?
        prev_close = prev['close']
        prev_open = prev['open']
        if prev_close >= prev_open:
            return False, "Önceki mum pozitif - momentum yok"
        
        return True, f"Breakout STRONG (Distance:{breakout_distance:.2f}%, Body:{body_pct:.0f}%)"
    
    return False, "Geçersiz direction"


# =============================================================================
# MEAN REVERSION Helper Functions
# =============================================================================

def check_trend_strength_1d(df_1d: pd.DataFrame, direction: str) -> tuple:
    """
    Layer 1 for MEAN REVERSION: 1D trend gücü kontrolü.
    Sadece güçlü trendlerde mean reversion - zayıf trendde alma.
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['ema50', 'sma200', 'adx14']
    if not all(col in df_1d.columns for col in required):
        return False, "1D'de EMA50/SMA200/ADX eksik"
    
    last = df_1d.iloc[-1]
    if last[required].isna().any():
        return False, "1D'de NaN değer var"
    
    ema50 = last['ema50']
    sma200 = last['sma200']
    adx = last['adx14']
    
    # EMA-SMA mesafesi (trend gücü)
    if sma200 <= 0:
        return False, "SMA200 sıfır veya negatif"
    
    spread_pct = abs((ema50 - sma200) / sma200) * 100
    
    if direction == 'LONG':
        # LONG için: EMA > SMA (uptrend)
        if ema50 <= sma200:
            return False, f"1D downtrend (EMA50={ema50:.2f} <= SMA200={sma200:.2f})"
        
        # Trend çok zayıf
        if spread_pct < 2.0:
            return False, f"Trend çok zayıf (spread={spread_pct:.1f}% < 2%)"
        
        # ADX çok düşük
        if adx < 20:
            return False, f"ADX düşük ({adx:.1f} < 20)"
        
        return True, f"1D trend OK (Spread:{spread_pct:.1f}%, ADX:{adx:.1f})"
    
    elif direction == 'SHORT':
        # SHORT için: EMA < SMA (downtrend)
        if ema50 >= sma200:
            return False, f"1D uptrend (EMA50={ema50:.2f} >= SMA200={sma200:.2f})"
        
        if spread_pct < 2.0:
            return False, f"Trend çok zayıf (spread={spread_pct:.1f}% < 2%)"
        
        if adx < 20:
            return False, f"ADX düşük ({adx:.1f} < 20)"
        
        return True, f"1D trend OK (Spread:{spread_pct:.1f}%, ADX:{adx:.1f})"
    
    return False, "Geçersiz direction"


def check_mean_reversion_setup_4h(df_4h: pd.DataFrame, direction: str) -> tuple:
    """
    Layer 2 for MEAN REVERSION: 4H'de gerçek mean reversion setup kontrolü.
    BB extreme + oversold/overbought + reversion başlamış mı?
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['close', 'bb_upper', 'bb_lower', 'bb_middle', 'rsi14', 'macd_hist']
    if not all(col in df_4h.columns for col in required):
        return False, "4H'de BB/RSI/MACD eksik"
    
    if len(df_4h) < 3:
        return False, "4H'de yetersiz veri (<3 mum)"
    
    last = df_4h.iloc[-1]
    prev = df_4h.iloc[-2]
    
    if last[required].isna().any() or prev[required].isna().any():
        return False, "4H'de NaN değer var"
    
    close = last['close']
    bb_upper = last['bb_upper']
    bb_lower = last['bb_lower']
    bb_middle = last['bb_middle']
    rsi = last['rsi14']
    macd_hist = last['macd_hist']
    prev_macd_hist = prev['macd_hist']
    
    if direction == 'LONG':
        # 1. BB lower'a dokunmuş mu? (%0.5 margin)
        if close >= bb_lower * 1.005:
            return False, f"BB lower'a yeterince yakın değil (close={close:.6f} >= bb_lower*1.005={bb_lower*1.005:.6f})"
        
        # 2. RSI oversold mu? (Daha sıkı: 30)
        if rsi >= 30:
            return False, f"RSI oversold değil ({rsi:.1f} >= 30)"
        
        # 3. Son 3 mum BB lower altında mı? (Gerçek oversold)
        recent_closes = df_4h['close'].iloc[-3:]
        below_lower_count = (recent_closes < bb_lower).sum()
        if below_lower_count < 2:
            return False, f"Yeterince oversold değil ({below_lower_count}/3 mum BB lower altında)"
        
        # 4. Reversion başlamış mı? (Kapanış BB lower üstünde)
        if close <= bb_lower:
            return False, "Reversion henüz başlamadı (kapanış BB lower altında)"
        
        # 5. MACD histogram pozitife dönüş
        if not (prev_macd_hist < 0 and macd_hist >= 0):
            return False, f"MACD histogram pozitife dönmedi (prev={prev_macd_hist:.6f}, current={macd_hist:.6f})"
        
        return True, f"4H mean reversion setup PERFECT (RSI:{rsi:.1f}, {below_lower_count}/3 mum oversold, MACD dönüş)"
    
    elif direction == 'SHORT':
        # SHORT için benzer mantık
        if close <= bb_upper * 0.995:
            return False, f"BB upper'a yeterince yakın değil (close={close:.6f} <= bb_upper*0.995={bb_upper*0.995:.6f})"
        
        if rsi <= 70:
            return False, f"RSI overbought değil ({rsi:.1f} <= 70)"
        
        recent_closes = df_4h['close'].iloc[-3:]
        above_upper_count = (recent_closes > bb_upper).sum()
        if above_upper_count < 2:
            return False, f"Yeterince overbought değil ({above_upper_count}/3 mum BB upper üstünde)"
        
        if close >= bb_upper:
            return False, "Reversion henüz başlamadı (kapanış BB upper üstünde)"
        
        if not (prev_macd_hist > 0 and macd_hist <= 0):
            return False, f"MACD histogram negatife dönmedi (prev={prev_macd_hist:.6f}, current={macd_hist:.6f})"
        
        return True, f"4H mean reversion setup PERFECT (RSI:{rsi:.1f}, {above_upper_count}/3 mum overbought, MACD dönüş)"
    
    return False, "Geçersiz direction"


def check_reversion_confirmation_1h(df_1h: pd.DataFrame, direction: str) -> tuple:
    """
    Layer 3 for MEAN REVERSION: 1H'de reversion confirmation - 5 indikatör sync.
    VWAP + RSI + MACD + Supertrend + Price Action.
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['close', 'vwap', 'rsi14', 'macd_hist', 'supertrend_direction']
    if not all(col in df_1h.columns for col in required):
        return False, "1H'de VWAP/RSI/MACD/Supertrend eksik"
    
    if len(df_1h) < 2:
        return False, "1H'de yetersiz veri (<2 mum)"
    
    last = df_1h.iloc[-1]
    prev = df_1h.iloc[-2]
    
    if last[required].isna().any() or prev[required].isna().any():
        return False, "1H'de NaN değer var"
    
    close = last['close']
    vwap = last['vwap']
    rsi = last['rsi14']
    prev_rsi = prev['rsi14']
    macd_hist = last['macd_hist']
    st = last['supertrend_direction']
    prev_close = prev['close']
    
    confirmations = []
    
    if direction == 'LONG':
        # 1. VWAP'a yaklaşıyor mu? (VWAP'ın %3 altında)
        if vwap <= 0:
            return False, "VWAP sıfır veya negatif"
        
        vwap_dist = ((close - vwap) / vwap) * 100
        if not (-3.0 <= vwap_dist <= 0):
            return False, f"VWAP uzak (distance={vwap_dist:.1f}%, gerekli: -3% ile 0% arası)"
        confirmations.append(f"VWAP OK({vwap_dist:.1f}%)")
        
        # 2. RSI dönüyor mu? (Yükseliyor ama aşırı değil: 25-45)
        if not (rsi > prev_rsi and 25 <= rsi <= 45):
            return False, f"RSI uygun değil (rsi={rsi:.1f}, prev_rsi={prev_rsi:.1f}, gerekli: dönüş + 25-45)"
        confirmations.append(f"RSI dönüyor({rsi:.1f})")
        
        # 3. MACD histogram pozitif mi?
        if macd_hist <= 0:
            return False, f"MACD negatif ({macd_hist:.6f})"
        confirmations.append("MACD pozitif")
        
        # 4. Supertrend alignment
        if st != 1:
            return False, f"Supertrend bearish ({st})"
        confirmations.append("Supertrend LONG")
        
        # 5. Price action bullish (son 2 mumda yükseliş)
        if close <= prev_close:
            return False, f"Price action bearish (close={close:.6f} <= prev_close={prev_close:.6f})"
        confirmations.append("Price action bullish")
        
        return True, f"1H confirmation: {', '.join(confirmations)}"
    
    elif direction == 'SHORT':
        # SHORT için benzer mantık
        if vwap <= 0:
            return False, "VWAP sıfır veya negatif"
        
        vwap_dist = ((close - vwap) / vwap) * 100
        if not (0 <= vwap_dist <= 3.0):
            return False, f"VWAP uzak (distance={vwap_dist:.1f}%, gerekli: 0% ile 3% arası)"
        confirmations.append(f"VWAP OK({vwap_dist:.1f}%)")
        
        if not (rsi < prev_rsi and 55 <= rsi <= 75):
            return False, f"RSI uygun değil (rsi={rsi:.1f}, prev_rsi={prev_rsi:.1f}, gerekli: dönüş + 55-75)"
        confirmations.append(f"RSI dönüyor({rsi:.1f})")
        
        if macd_hist >= 0:
            return False, f"MACD pozitif ({macd_hist:.6f})"
        confirmations.append("MACD negatif")
        
        if st != -1:
            return False, f"Supertrend bullish ({st})"
        confirmations.append("Supertrend SHORT")
        
        if close >= prev_close:
            return False, f"Price action bullish (close={close:.6f} >= prev_close={prev_close:.6f})"
        confirmations.append("Price action bearish")
        
        return True, f"1H confirmation: {', '.join(confirmations)}"
    
    return False, "Geçersiz direction"


def check_volume_multi_tf(df_4h: pd.DataFrame, df_1h: pd.DataFrame, direction: str) -> tuple:
    """
    Layer 4 for MEAN REVERSION: Multi-timeframe volume confirmation.
    4H düşük hacim (panik bitti) + 1H artan hacim (talep artıyor).
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['volume', 'volume_sma20']
    if not all(col in df_4h.columns for col in required):
        return False, "4H'de volume kolonları eksik"
    if not all(col in df_1h.columns for col in required):
        return False, "1H'de volume kolonları eksik"
    
    last_4h = df_4h.iloc[-1]
    last_1h = df_1h.iloc[-1]
    
    vol_4h = last_4h['volume']
    avg_vol_4h = last_4h['volume_sma20']
    vol_1h = last_1h['volume']
    avg_vol_1h = last_1h['volume_sma20']
    
    if avg_vol_4h <= 0 or avg_vol_1h <= 0:
        return False, "volume_sma20 sıfır veya negatif"
    
    ratio_4h = vol_4h / avg_vol_4h
    ratio_1h = vol_1h / avg_vol_1h
    
    # 4H volume çok yüksek olmamalı (panik devam ediyor)
    if ratio_4h > 2.0:
        return False, f"4H hacim çok yüksek ({ratio_4h:.1f}x > 2.0x) - panik devam ediyor"
    
    # 1H volume yeterli olmalı (talep artıyor)
    if ratio_1h < 1.3:
        return False, f"1H hacim yetersiz ({ratio_1h:.1f}x < 1.3x)"
    
    return True, f"Volume OK (4H:{ratio_4h:.1f}x, 1H:{ratio_1h:.1f}x)"


def check_market_structure(df_4h: pd.DataFrame, direction: str) -> tuple:
    """
    Layer 5 for MEAN REVERSION: Market structure - yakında destek/direnç var mı?
    Reversion hedefe (BB middle) ulaşabilir mi?
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['close', 'bb_middle', 'high', 'low']
    if not all(col in df_4h.columns for col in required):
        return False, "4H'de close/BB middle/high/low eksik"
    
    lookback = 50
    if len(df_4h) < lookback:
        return True, "Yeterli veri yok, market structure geçiliyor"
    
    last = df_4h.iloc[-1]
    close = last['close']
    bb_middle = last['bb_middle']
    
    recent = df_4h.iloc[-lookback:]
    
    if direction == 'LONG':
        # BB middle'a kadar direnç var mı?
        resistance_levels = []
        for i in range(len(recent) - 10):
            high = recent.iloc[i]['high']
            # Local high mı?
            if i > 0 and i < len(recent) - 1:
                if (high > recent.iloc[i-1]['high'] and 
                    high > recent.iloc[i+1]['high'] and
                    close < high < bb_middle):
                    resistance_levels.append(high)
        
        if len(resistance_levels) > 2:
            return False, f"{len(resistance_levels)} direnç seviyesi var - reversion engellenebilir"
        
        return True, "BB middle'a kadar yol açık"
    
    elif direction == 'SHORT':
        # BB middle'a kadar destek var mı?
        support_levels = []
        for i in range(len(recent) - 10):
            low = recent.iloc[i]['low']
            # Local low mu?
            if i > 0 and i < len(recent) - 1:
                if (low < recent.iloc[i-1]['low'] and 
                    low < recent.iloc[i+1]['low'] and
                    close > low > bb_middle):
                    support_levels.append(low)
        
        if len(support_levels) > 2:
            return False, f"{len(support_levels)} destek seviyesi var - reversion engellenebilir"
        
        return True, "BB middle'a kadar yol açık"
    
    return False, "Geçersiz direction"


# =============================================================================
# ADVANCED SCALP Helper Functions
# =============================================================================

def check_scalp_trend_filter_1d(df_1d: pd.DataFrame) -> tuple:
    """
    Layer 1 for SCALP: 1D trend filter - sadece ana trend yönünde scalp al.
    
    Returns:
        (direction, message): ('LONG'|'SHORT'|'BOTH', açıklama mesajı)
    """
    required = ['close', 'ema50', 'sma200', 'adx14']
    if not all(col in df_1d.columns for col in required):
        return 'BOTH', "1D trend kontrolü yapılamadı - her iki yön izinli"
    
    last = df_1d.iloc[-1]
    if last[required].isna().any():
        return 'BOTH', "1D'de NaN var - her iki yön izinli"
    
    ema50 = last['ema50']
    sma200 = last['sma200']
    close = last['close']
    adx = last['adx14']
    
    # Güçlü uptrend - SADECE LONG scalp
    if ema50 > sma200 and close > ema50 and adx > 25:
        return 'LONG', f"1D strong uptrend (ADX:{adx:.1f}) - LONG only"
    
    # Güçlü downtrend - SADECE SHORT scalp
    if ema50 < sma200 and close < ema50 and adx > 25:
        return 'SHORT', f"1D strong downtrend (ADX:{adx:.1f}) - SHORT only"
    
    # Sideways - Her iki yön OK
    return 'BOTH', f"1D sideways (ADX:{adx:.1f}) - Dikkatli scalp"


def check_scalp_momentum_wave_4h(df_4h: pd.DataFrame, scalp_direction: str, trend_filter: str) -> tuple:
    """
    Layer 2 for SCALP: 4H momentum wave - dalganın doğru yerinde mi?
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['rsi14', 'macd_hist']
    if not all(col in df_4h.columns for col in required):
        return False, "4H'de RSI/MACD eksik"
    
    if len(df_4h) < 5:
        return False, "4H'de yetersiz veri (<5 mum)"
    
    last = df_4h.iloc[-1]
    if last[required].isna().any():
        return False, "4H'de NaN değer var"
    
    rsi = last['rsi14']
    macd_hist = last['macd_hist']
    
    # Trend filter LONG ise, 4H pullback arıyoruz
    if trend_filter == 'LONG' and scalp_direction == 'LONG':
        # RSI 40-60 arası (pullback bitmiş, yükseliş başlıyor)
        if not (40 <= rsi <= 60):
            return False, f"4H RSI uygun değil ({rsi:.1f}, gerekli: 40-60)"
        
        # MACD histogram çok negatif olmamalı
        if macd_hist < -0.0005:
            return False, f"4H MACD çok negatif ({macd_hist:.6f})"
        
        return True, f"4H momentum wave OK (RSI:{rsi:.1f})"
    
    elif trend_filter == 'SHORT' and scalp_direction == 'SHORT':
        # RSI 40-60 arası
        if not (40 <= rsi <= 60):
            return False, f"4H RSI uygun değil ({rsi:.1f}, gerekli: 40-60)"
        
        # MACD histogram çok pozitif olmamalı
        if macd_hist > 0.0005:
            return False, f"4H MACD çok pozitif ({macd_hist:.6f})"
        
        return True, f"4H momentum wave OK (RSI:{rsi:.1f})"
    
    elif trend_filter == 'BOTH':
        # Sideways market - her iki yön için RSI 35-65 arası
        if not (35 <= rsi <= 65):
            return False, f"4H RSI extreme ({rsi:.1f})"
        return True, f"4H sideways OK (RSI:{rsi:.1f})"
    
    return False, "Direction/trend filter uyumsuz"


def check_scalp_entry_zone_1h(df_1h: pd.DataFrame, direction: str) -> tuple:
    """
    Layer 3 for SCALP: 1H entry zone - optimal giriş bölgesi.
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['close', 'ema8', 'ema21', 'vwap', 'supertrend_direction']
    if not all(col in df_1h.columns for col in required):
        return False, "1H'de EMA8/EMA21/VWAP/Supertrend eksik"
    
    last = df_1h.iloc[-1]
    if last[required].isna().any():
        return False, "1H'de NaN değer var"
    
    close = last['close']
    ema8 = last['ema8']
    ema21 = last['ema21']
    vwap = last['vwap']
    st = last['supertrend_direction']
    
    if direction == 'LONG':
        # Fiyat EMA8-EMA21 arasında (pullback zone)
        if not (ema21 <= close <= ema8 * 1.002):
            return False, f"1H entry zone dışında (close={close:.6f}, EMA21={ema21:.6f}, EMA8={ema8:.6f})"
        
        # VWAP üstünde
        if vwap <= 0:
            return False, "VWAP sıfır veya negatif"
        
        if close < vwap * 0.998:
            return False, f"1H VWAP altında ({close:.6f} < {vwap*0.998:.6f})"
        
        # Supertrend alignment
        if st != 1:
            return False, f"1H Supertrend bearish ({st})"
        
        return True, "1H entry zone PERFECT"
    
    elif direction == 'SHORT':
        # Fiyat EMA8-EMA21 arasında
        if not (ema8 * 0.998 <= close <= ema21):
            return False, f"1H entry zone dışında (close={close:.6f}, EMA8={ema8:.6f}, EMA21={ema21:.6f})"
        
        # VWAP altında
        if vwap <= 0:
            return False, "VWAP sıfır veya negatif"
        
        if close > vwap * 1.002:
            return False, f"1H VWAP üstünde ({close:.6f} > {vwap*1.002:.6f})"
        
        # Supertrend alignment
        if st != -1:
            return False, f"1H Supertrend bullish ({st})"
        
        return True, "1H entry zone PERFECT"
    
    return False, "Geçersiz direction"


def check_scalp_tf_precision(df_scalp: pd.DataFrame, direction: str) -> tuple:
    """
    Layer 4 for SCALP: Scalp TF'de hassas sinyal - 3 indikatör sync.
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['ema8', 'ema21', 'rsi14', 'volume', 'volume_sma20']
    if not all(col in df_scalp.columns for col in required):
        return False, "Scalp TF'de EMA/RSI/Volume eksik"
    
    if len(df_scalp) < 2:
        return False, "Scalp TF'de yetersiz veri (<2 mum)"
    
    last = df_scalp.iloc[-1]
    prev = df_scalp.iloc[-2]
    
    if last[required].isna().any() or prev[required].isna().any():
        return False, "Scalp TF'de NaN değer var"
    
    ema8 = last['ema8']
    ema21 = last['ema21']
    prev_ema8 = prev['ema8']
    prev_ema21 = prev['ema21']
    rsi = last['rsi14']
    vol = last['volume']
    avg_vol = last['volume_sma20']
    
    if direction == 'LONG':
        # 1. EMA8 > EMA21 crossover YENİ mi?
        crossover = (ema8 > ema21) and (prev_ema8 <= prev_ema21)
        if not crossover:
            return False, "EMA crossover yok - eski sinyal"
        
        # 2. RSI momentum zone (45-65)
        if not (45 <= rsi <= 65):
            return False, f"RSI uygun değil ({rsi:.1f}, gerekli: 45-65)"
        
        # 3. Volume spike
        if avg_vol <= 0:
            return False, "volume_sma20 sıfır veya negatif"
        
        vol_ratio = vol / avg_vol
        if vol_ratio < 1.3:
            return False, f"Volume yetersiz ({vol_ratio:.1f}x < 1.3x)"
        
        return True, f"Scalp TF PERFECT (Fresh crossover, RSI:{rsi:.1f}, Vol:{vol_ratio:.1f}x)"
    
    elif direction == 'SHORT':
        # EMA8 < EMA21 crossover YENİ mi?
        crossover = (ema8 < ema21) and (prev_ema8 >= prev_ema21)
        if not crossover:
            return False, "EMA crossover yok - eski sinyal"
        
        # RSI momentum zone (35-55)
        if not (35 <= rsi <= 55):
            return False, f"RSI uygun değil ({rsi:.1f}, gerekli: 35-55)"
        
        # Volume spike
        if avg_vol <= 0:
            return False, "volume_sma20 sıfır veya negatif"
        
        vol_ratio = vol / avg_vol
        if vol_ratio < 1.3:
            return False, f"Volume yetersiz ({vol_ratio:.1f}x < 1.3x)"
        
        return True, f"Scalp TF PERFECT (Fresh crossover, RSI:{rsi:.1f}, Vol:{vol_ratio:.1f}x)"
    
    return False, "Geçersiz direction"


def check_scalp_rr(current_price: float, direction: str, df_scalp: pd.DataFrame) -> tuple:
    """
    Layer 5 for SCALP: RR kontrolü - minimum 2:1.
    
    Returns:
        (success, message): (True/False, açıklama mesajı)
    """
    required = ['ema21', 'atr14', 'high', 'low']
    if not all(col in df_scalp.columns for col in required):
        return False, "Scalp TF'de EMA21/ATR/High/Low eksik"
    
    if len(df_scalp) < 20:
        return True, "RR hesabı için yeterli veri yok, geçiliyor"
    
    last = df_scalp.iloc[-1]
    if last[required].isna().any():
        return False, "Scalp TF'de NaN değer var"
    
    ema21 = last['ema21']
    atr = last['atr14']
    
    if direction == 'LONG':
        # SL: EMA21 altı (%0.5 buffer)
        sl_price = ema21 * 0.995
        
        # TP: Son 20 mumdaki swing high veya 2x ATR
        recent_highs = df_scalp['high'].iloc[-20:]
        swing_high = recent_highs.max()
        tp_atr = current_price + (2 * atr)
        tp_price = min(swing_high, tp_atr)
        
        # RR hesapla
        risk = current_price - sl_price
        reward = tp_price - current_price
        
        if risk <= 0:
            return False, f"Risk hesaplanamadı (current={current_price:.6f}, sl={sl_price:.6f})"
        
        rr = reward / risk
        
        if rr < 2.0:
            return False, f"Scalp RR düşük ({rr:.1f} < 2.0)"
        
        return True, f"Scalp RR OK ({rr:.1f})"
    
    elif direction == 'SHORT':
        # SL: EMA21 üstü (%0.5 buffer)
        sl_price = ema21 * 1.005
        
        # TP: Son 20 mumdaki swing low veya 2x ATR
        recent_lows = df_scalp['low'].iloc[-20:]
        swing_low = recent_lows.min()
        tp_atr = current_price - (2 * atr)
        tp_price = max(swing_low, tp_atr)
        
        # RR hesapla
        risk = sl_price - current_price
        reward = current_price - tp_price
        
        if risk <= 0:
            return False, f"Risk hesaplanamadı (current={current_price:.6f}, sl={sl_price:.6f})"
        
        rr = reward / risk
        
        if rr < 2.0:
            return False, f"Scalp RR düşük ({rr:.1f} < 2.0)"
        
        return True, f"Scalp RR OK ({rr:.1f})"
    
    return False, "Geçersiz direction"


# =============================================================================
# Strateji Fonksiyonları
# =============================================================================

def find_pullback_signal(df_1d: pd.DataFrame, df_4h: pd.DataFrame, df_1h: pd.DataFrame, config) -> dict:
    """
    Pullback stratejisi - trend takibi ile geri çekilme alımı/satışı.
    """
    logger.info(f"   🔍 PULLBACK stratejisi kontrol ediliyor...")
    
    # Validasyon
    required_1d = ['ema50', 'sma200']
    required_4h = ['ema50', 'sma200']
    required_1h = ['rsi14', 'macd_hist', 'sma200', 'close']
    
    if not validate_dataframe(df_1d, required_1d):
        logger.warning(f"   PULLBACK REJECTED: 1D DataFrame validasyon başarısız")
        return None
    if not validate_dataframe(df_4h, required_4h):
        logger.warning(f"   PULLBACK REJECTED: 4H DataFrame validasyon başarısız")
        return None
    if not validate_dataframe(df_1h, required_1h, min_rows=3):
        logger.warning(f"   PULLBACK REJECTED: 1H DataFrame validasyon başarısız")
        return None
    
    try:
        last_1d = df_1d.iloc[-1]; last_4h = df_4h.iloc[-1]; last_1h = df_1h.iloc[-1]
        if last_1d[required_1d].isna().any() or \
           last_4h[required_4h].isna().any() or \
           last_1h[required_1h].isna().any():
            logger.warning("   Pullback: Son mum verilerinde NaN var."); return None

        # 1. Ana Trend (Enhanced: Supertrend confirmation on higher TFs)
        trend_1d_bullish = last_1d['close'] > last_1d['ema50'] and last_1d['ema50'] > last_1d['sma200'] and last_1d['supertrend_direction'] == 1
        trend_1d_bearish = last_1d['close'] < last_1d['ema50'] and last_1d['ema50'] < last_1d['sma200'] and last_1d['supertrend_direction'] == -1
        trend_4h_bullish = last_4h['close'] > last_4h['ema50'] and last_4h['ema50'] > last_4h['sma200'] and last_4h['supertrend_direction'] == 1
        trend_4h_bearish = last_4h['close'] < last_4h['ema50'] and last_4h['ema50'] < last_4h['sma200'] and last_4h['supertrend_direction'] == -1
        main_direction = None
        if trend_1d_bullish and trend_4h_bullish: 
            main_direction = 'LONG'
            logger.info("   ✅ Pullback: Ana Trend = LONG (EMA+SMA+Supertrend)")
        elif trend_1d_bearish and trend_4h_bearish: 
            main_direction = 'SHORT'
            logger.info("   ✅ Pullback: Ana Trend = SHORT (EMA+SMA+Supertrend)")
        else: 
            logger.info("   Pullback REJECTED: Ana Trend uyumsuz veya Supertrend çelişkili."); return None

        # 2. v5.0: Geri Çekilme Onayı (RSI genişletildi, VWAP toleransı artırıldı)
        rsi_1h = last_1h['rsi14']; macd_hist_1h = last_1h['macd_hist']
        vwap_1h = last_1h['vwap']; close_1h = last_1h['close']
        pullback_confirmed = False
        if main_direction == 'LONG':
            # v5.0: RSI 30-50 → 25-55 (daha esnek)
            if (25 <= rsi_1h <= 55) and (macd_hist_1h <= 0):
                # Dinamik VWAP toleransı (config + ATR guard)
                base_tol = 0.01  # 1%
                cfg_tol = getattr(config, 'PULLBACK_VWAP_TOLERANCE_LONG', 0.0115)
                tol = min(cfg_tol, base_tol) if ((last_1h['atr14']/close_1h)*100) > getattr(config, 'PULLBACK_VWAP_MAX_ATR_PERCENT_FOR_EXTENSION', 4.0) else max(cfg_tol, base_tol)
                if close_1h >= vwap_1h * (1 - tol):
                    pullback_confirmed = True
                    logger.info(f"   ✅ LONG Pullback onaylandı: RSI={rsi_1h:.1f}, MACD<0, Price near VWAP (tol={tol*100:.2f}%)")
                    if tol > base_tol:
                        strategy_metrics['pullback_vwap_extended_usage'] += 1
                else:
                    logger.info(f"   Pullback REJECTED: Price too far below VWAP ({close_1h:.6f} vs {vwap_1h:.6f})")
            else:
                logger.info(f"   Pullback REJECTED: RSI ({rsi_1h:.1f}) veya MACD ({macd_hist_1h:.4f}) uygun değil")
        elif main_direction == 'SHORT':
            # v5.0: RSI 50-70 → 45-75 (daha esnek)
            if (45 <= rsi_1h <= 75) and (macd_hist_1h >= 0):
                base_tol = 0.01
                cfg_tol = getattr(config, 'PULLBACK_VWAP_TOLERANCE_SHORT', 0.0115)
                tol = min(cfg_tol, base_tol) if ((last_1h['atr14']/close_1h)*100) > getattr(config, 'PULLBACK_VWAP_MAX_ATR_PERCENT_FOR_EXTENSION', 4.0) else max(cfg_tol, base_tol)
                if close_1h <= vwap_1h * (1 + tol):
                    pullback_confirmed = True
                    logger.info(f"   ✅ SHORT Pullback onaylandı: RSI={rsi_1h:.1f}, MACD>0, Price near VWAP (tol={tol*100:.2f}%)")
                    if tol > base_tol:
                        strategy_metrics['pullback_vwap_extended_usage'] += 1
                else:
                    logger.info(f"   Pullback REJECTED: Price too far above VWAP ({close_1h:.6f} vs {vwap_1h:.6f})")
            else:
                logger.info(f"   Pullback REJECTED: RSI ({rsi_1h:.1f}) veya MACD ({macd_hist_1h:.4f}) uygun değil")
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
        
        # 🆕 v9.3: Signal Strength hesaplama (0-100 arası)
        signal_strength = 50.0  # Base score
        
        # RSI optimal zone bonus (LONG: 35-45, SHORT: 55-65)
        if main_direction == 'LONG':
            if 35 <= rsi_1h <= 45:
                signal_strength += 15
            elif 25 <= rsi_1h < 35 or 45 < rsi_1h <= 55:
                signal_strength += 7
        else:  # SHORT
            if 55 <= rsi_1h <= 65:
                signal_strength += 15
            elif 45 <= rsi_1h < 55 or 65 < rsi_1h <= 75:
                signal_strength += 7
        
        # VWAP proximity bonus (±0.5% = +10, ±1% = +5)
        vwap_distance_percent = abs((close_1h / vwap_1h - 1) * 100) if vwap_1h > 0 else 999
        if vwap_distance_percent <= 0.5:
            signal_strength += 10
        elif vwap_distance_percent <= 1.0:
            signal_strength += 5
        
        # Volume moderation bonus (düşük hacim = daha iyi pullback)
        vol_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        if vol_ratio < 1.2:
            signal_strength += 10
        elif vol_ratio < 1.5:
            signal_strength += 5
        
        # Low volatility bonus
        if atr_percent < 2.0:
            signal_strength += 10
        elif atr_percent < 3.0:
            signal_strength += 5
        
        signal_strength = min(signal_strength, 100.0)  # Cap at 100
        logger.info(f"   💯 Pullback Signal Strength: {signal_strength:.1f}/100")
        
        logger.info(f"   ✅ Pullback {main_direction} sinyali bulundu! (v9.3: Signal Strength = {signal_strength:.1f})")
        signal = {'direction': main_direction, 'signal_strength': signal_strength}
    except IndexError: logger.warning("   Pullback: Yetersiz veri."); return None
    except Exception as e: logger.error(f"   Pullback: Hata: {e}", exc_info=True); return None
    return signal

def find_mean_reversion_signal(df_1d: pd.DataFrame, df_4h: pd.DataFrame, df_1h: pd.DataFrame, config) -> dict:
    """
    v9.0 ULTRA PRECISION MEAN REVERSION - 5-layer filtreleme.
    Win rate hedefi: %50 → %85+
    
    Layers:
    1. 1D Trend Strength (EMA-SMA spread %2+, ADX>20)
    2. 4H Mean Reversion Setup (BB extreme, RSI<30, 3 mum oversold, MACD dönüş)
    3. 1H Reversion Confirmation (VWAP + RSI + MACD + Supertrend + Price Action)
    4. Volume Multi-TF (4H<2x panik bitti, 1H>1.3x talep arttı)
    5. Market Structure (BB middle'a kadar yol açık)
    """
    logger.info(f"   🔍 MEAN REVERSION v9.0 (5-LAYER) kontrol ediliyor...")
    
    # İlk olarak her iki direction için de deneyelim
    for direction in ['LONG', 'SHORT']:
        
        # ========== Layer 1: 1D Trend Strength ==========
        trend_ok, trend_msg = check_trend_strength_1d(df_1d, direction)
        if not trend_ok:
            logger.debug(f"   [{direction}] Layer 1 FAILED: {trend_msg}")
            continue
        logger.info(f"   ✅ [{direction}] Layer 1: {trend_msg}")
        
        # ========== Layer 2: 4H Mean Reversion Setup ==========
        setup_ok, setup_msg = check_mean_reversion_setup_4h(df_4h, direction)
        if not setup_ok:
            logger.debug(f"   [{direction}] Layer 2 FAILED: {setup_msg}")
            continue
        logger.info(f"   ✅ [{direction}] Layer 2: {setup_msg}")
        
        # ========== Layer 3: 1H Reversion Confirmation ==========
        conf_ok, conf_msg = check_reversion_confirmation_1h(df_1h, direction)
        if not conf_ok:
            logger.debug(f"   [{direction}] Layer 3 FAILED: {conf_msg}")
            continue
        logger.info(f"   ✅ [{direction}] Layer 3: {conf_msg}")
        
        # ========== Layer 4: Volume Multi-TF ==========
        vol_ok, vol_msg = check_volume_multi_tf(df_4h, df_1h, direction)
        if not vol_ok:
            logger.debug(f"   [{direction}] Layer 4 FAILED: {vol_msg}")
            continue
        logger.info(f"   ✅ [{direction}] Layer 4: {vol_msg}")
        
        # ========== Layer 5: Market Structure ==========
        struct_ok, struct_msg = check_market_structure(df_4h, direction)
        if not struct_ok:
            logger.debug(f"   [{direction}] Layer 5 FAILED: {struct_msg}")
            continue
        logger.info(f"   ✅ [{direction}] Layer 5: {struct_msg}")
        
        # ========== ALL LAYERS PASSED ==========
        # 🆕 v9.3: Signal Strength hesaplama (5 layer geçti = 100 puan)
        signal_strength = 100.0  # Mean Reversion tüm layer'ları geçerse ultra güçlü
        logger.info(f"   💯 Mean Reversion Signal Strength: {signal_strength:.1f}/100 (5/5 layers)")
        logger.info(f"   🎯🎯🎯 MEAN REVERSION {direction} SIGNAL VALIDATED - ULTRA PRECISION! 🎯🎯🎯")
        return {'direction': direction, 'signal_strength': signal_strength}
    
    # Her iki direction da başarısız
    logger.debug("   Mean Reversion: Her iki direction da layer'ları geçemedi")
    return None

def find_breakout_signal(df_1d: pd.DataFrame, df_4h: pd.DataFrame, df_1h: pd.DataFrame, config) -> dict:
    """
    v9.0 INSTITUTIONAL GRADE BREAKOUT - 6-layer filtreleme.
    Win rate hedefi: %40 → %85+
    
    Layers:
    1. 1D Institutional Trend (EMA hierarchy)
    2. 4H Momentum Buildup (RSI zone + MACD + ADX)
    3. 1H Squeeze Quality (5-20 mum, alt %15 BBW)
    4. Volume Expansion (2.5x + %30 artış + progressive)
    5. Breakout Strength (%0.3+ BB kırılma, %60+ body)
    6. Direction Confirmation (BB + Supertrend)
    """
    logger.info(f"   🔍 BREAKOUT v9.0 (6-LAYER) kontrol ediliyor...")
    
    # ========== Layer 1: 1D Institutional Trend ==========
    direction, trend_msg = check_institutional_trend_1d(df_1d)
    if direction is None:
        logger.info(f"   ❌ Layer 1 FAILED: {trend_msg}")
        return None
    logger.info(f"   ✅ Layer 1: {trend_msg} → ONLY {direction} breakouts")
    
    # ========== Layer 2: 4H Momentum Buildup ==========
    momentum_result = check_momentum_buildup_4h(df_4h, direction, config)
    if isinstance(momentum_result, tuple) and len(momentum_result) == 5:
        momentum_ok, momentum_msg, extended_rsi_used, macd_relaxed_used, adx_relaxed_used = momentum_result
    else:
        momentum_ok, momentum_msg = momentum_result[0], momentum_result[1]
        extended_rsi_used = macd_relaxed_used = adx_relaxed_used = False
    if not momentum_ok:
        logger.info(f"   ❌ Layer 2 FAILED: {momentum_msg}")
        strategy_metrics['breakout_layer2_fail'] += 1
        _maybe_dump_metrics(config)
        return None
    logger.info(f"   ✅ Layer 2: {momentum_msg}")
    strategy_metrics['breakout_layer2_pass'] += 1
    if extended_rsi_used:
        strategy_metrics['breakout_extended_rsi_usage'] += 1
    if macd_relaxed_used:
        strategy_metrics['breakout_relaxed_macd_used'] += 1
    if adx_relaxed_used:
        strategy_metrics['breakout_relaxed_adx_used'] += 1
    
    # ========== Layer 3: 1H Squeeze Quality ==========
    squeeze_ok, squeeze_msg = check_squeeze_quality_1h(df_1h)
    if not squeeze_ok:
        logger.info(f"   ❌ Layer 3 FAILED: {squeeze_msg}")
        strategy_metrics['breakout_layer3_fail'] += 1
        _maybe_dump_metrics(config)
        return None
    logger.info(f"   ✅ Layer 3: {squeeze_msg}")
    
    # ========== Layer 4: Volume Expansion ==========
    vol_ok, vol_msg = check_volume_expansion(df_1h, config)
    if not vol_ok:
        logger.info(f"   ❌ Layer 4 FAILED: {vol_msg}")
        strategy_metrics['breakout_layer4_fail'] += 1
        _maybe_dump_metrics(config)
        return None
    logger.info(f"   ✅ Layer 4: {vol_msg}")
    
    # ========== Layer 5: Breakout Strength ==========
    strength_ok, strength_msg = check_breakout_strength(df_1h, direction, config)
    if not strength_ok:
        logger.info(f"   ❌ Layer 5 FAILED: {strength_msg}")
        strategy_metrics['breakout_layer5_fail'] += 1
        _maybe_dump_metrics(config)
        return None
    logger.info(f"   ✅ Layer 5: {strength_msg}")
    
    # ========== Layer 6: Direction Confirmation ==========
    required = ['close', 'bb_upper', 'bb_lower', 'supertrend_direction']
    if not all(col in df_1h.columns for col in required):
        logger.warning(f"   ❌ Layer 6 FAILED: BB/Supertrend kolonları eksik")
        strategy_metrics['breakout_layer1_pass'] += 1
    
    last = df_1h.iloc[-1]
    if last[required].isna().any():
        logger.warning(f"   ❌ Layer 6 FAILED: Son mumda NaN var")
        return None
    
    close = last['close']
    bb_upper = last['bb_upper']
    bb_lower = last['bb_lower']
    supertrend_direction = last['supertrend_direction']
    
    # Direction ile BB breakout uyumlu mu?
    if direction == 'LONG':
        if close <= bb_upper:
            logger.info(f"   ❌ Layer 6 FAILED: LONG breakout ama close BB upper'ın altında ({close:.6f} <= {bb_upper:.6f})")
            return None
        if supertrend_direction != 1:
            logger.info(f"   ❌ Layer 6 FAILED: LONG breakout ama Supertrend bearish ({supertrend_direction})")
            return None
    elif direction == 'SHORT':
        if close >= bb_lower:
            logger.info(f"   ❌ Layer 6 FAILED: SHORT breakout ama close BB lower'ın üstünde ({close:.6f} >= {bb_lower:.6f})")
            return None
        if supertrend_direction != -1:
            logger.info(f"   ❌ Layer 6 FAILED: SHORT breakout ama Supertrend bullish ({supertrend_direction})")
            return None
    
    logger.info(f"   ✅ Layer 6: Direction confirmation OK (Close vs BB + Supertrend)")
    
    # ========== ALL LAYERS PASSED ==========
    # 🆕 v9.3: Signal Strength hesaplama (6 layer geçti = 100 puan)
    signal_strength = 100.0  # Breakout tüm layer'ları geçerse ultra güçlü
    logger.info(f"   � Breakout Signal Strength: {signal_strength:.1f}/100 (6/6 layers)")
    logger.info(f"   �🚀🚀🚀 BREAKOUT {direction} SIGNAL VALIDATED - INSTITUTIONAL GRADE! 🚀🚀🚀")
    return {'direction': direction, 'signal_strength': signal_strength}

# --- YENİ EKLENDİ: Gelişmiş Scalp Stratejisi (Aşama 4) ---

def find_advanced_scalp_signal(df_1d: pd.DataFrame, df_4h: pd.DataFrame, df_1h: pd.DataFrame, df_scalp: pd.DataFrame, config) -> dict:
    """
    v9.0 SMART SCALPING - 5-layer filtreleme.
    Win rate hedefi: %35 → %75+
    
    Layers:
    1. 1D Trend Filter (Sadece ana trend yönünde scalp)
    2. 4H Momentum Wave (Dalganın doğru yerinde)
    3. 1H Entry Zone (EMA8-21 arası + VWAP + Supertrend)
    4. Scalp TF Precision (Fresh EMA crossover + RSI + Volume spike)
    5. Scalp RR Check (Minimum 2:1)
    """
    logger.info(f"   🔍 ADVANCED SCALP v9.0 (5-LAYER) kontrol ediliyor...")
    
    # İlk olarak scalp sinyali var mı kontrol et (basit EMA crossover)
    required = ['ema8', 'ema21', 'close']
    if not all(col in df_scalp.columns for col in required):
        logger.debug("   Scalp REJECTED: EMA8/EMA21/Close eksik")
        return None
    
    if len(df_scalp) < 2:
        logger.debug("   Scalp REJECTED: Yetersiz veri (<2 mum)")
        return None
    
    last = df_scalp.iloc[-1]
    prev = df_scalp.iloc[-2]
    
    # Basit crossover kontrolü
    ema8 = last['ema8']
    ema21 = last['ema21']
    prev_ema8 = prev['ema8']
    prev_ema21 = prev['ema21']
    
    scalp_direction = None
    if (ema8 > ema21) and (prev_ema8 <= prev_ema21):
        scalp_direction = 'LONG'
    elif (ema8 < ema21) and (prev_ema8 >= prev_ema21):
        scalp_direction = 'SHORT'
    
    if scalp_direction is None:
        logger.debug("   Scalp REJECTED: EMA crossover yok")
        return None
    
    logger.info(f"   📊 Scalp TF'de {scalp_direction} crossover tespit edildi, layer'lar kontrol ediliyor...")
    
    # ========== Layer 1: 1D Trend Filter ==========
    trend_filter, filter_msg = check_scalp_trend_filter_1d(df_1d)
    logger.info(f"   ✅ Layer 1: {filter_msg}")
    
    # Trend filter ile uyumlu mu?
    if trend_filter in ['LONG', 'SHORT'] and scalp_direction != trend_filter:
        logger.info(f"   ❌ SCALP REJECTED: {scalp_direction} scalp ama 1D {trend_filter} trend")
        return None
    
    # ========== Layer 2: 4H Momentum Wave ==========
    wave_ok, wave_msg = check_scalp_momentum_wave_4h(df_4h, scalp_direction, trend_filter)
    if not wave_ok:
        logger.info(f"   ❌ Layer 2 FAILED: {wave_msg}")
        return None
    logger.info(f"   ✅ Layer 2: {wave_msg}")
    
    # ========== Layer 3: 1H Entry Zone ==========
    zone_ok, zone_msg = check_scalp_entry_zone_1h(df_1h, scalp_direction)
    if not zone_ok:
        logger.info(f"   ❌ Layer 3 FAILED: {zone_msg}")
        return None
    logger.info(f"   ✅ Layer 3: {zone_msg}")
    
    # ========== Layer 4: Scalp TF Precision ==========
    precision_ok, precision_msg = check_scalp_tf_precision(df_scalp, scalp_direction)
    if not precision_ok:
        logger.info(f"   ❌ Layer 4 FAILED: {precision_msg}")
        return None
    logger.info(f"   ✅ Layer 4: {precision_msg}")
    
    # ========== Layer 5: Scalp RR ==========
    current_price = df_scalp.iloc[-1]['close']
    rr_ok, rr_msg = check_scalp_rr(current_price, scalp_direction, df_scalp)
    if not rr_ok:
        logger.info(f"   ❌ Layer 5 FAILED: {rr_msg}")
        return None
    logger.info(f"   ✅ Layer 5: {rr_msg}")
    
    # ========== ALL LAYERS PASSED ==========
    # 🆕 v9.3: Signal Strength hesaplama (5 layer geçti = 95 puan, scalp daha riskli)
    signal_strength = 95.0  # Scalp layer'ları geçti ama inherently riskli
    logger.info(f"   💯 Scalp Signal Strength: {signal_strength:.1f}/100 (5/5 layers)")
    logger.info(f"   ⚡⚡⚡ SCALP {scalp_direction} SIGNAL VALIDATED - SMART SCALPING! ⚡⚡⚡")
    return {'direction': scalp_direction, 'signal_strength': signal_strength}


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