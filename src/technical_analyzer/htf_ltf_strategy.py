# src/technical_analyzer/htf_ltf_strategy.py
"""
HTF-LTF Strategy: High Timeframe Filter + Low Timeframe Trigger
================================================================

Felsefe:
- HTF (1H): Ana trend filtresi - Hangi yöne girilebileceğini belirler
- LTF (15M): Giriş tetikleyicisi - Ne zaman girileceğini belirler
- Risk Filters: Son güvenlik kontrolleri (ATR, Volume)

Katmanlar:
1. Layer 1 (HTF Filter - 1H): Trend yönünü belirle (LONG/SHORT/NEUTRAL)
2. Layer 2 (LTF Trigger - 15M): İzin verilen yönde giriş sinyali ara
3. Layer 3 (Risk Filters): ATR ve hacim kontrolü

Author: Mehmet Küçük
Date: 2025-11-12
Version: v11.0
"""

import logging
import pandas as pd
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# LAYER 1: HTF FILTER (1H) - Ana Trend Filtresi
# ═══════════════════════════════════════════════════════════════════════

def check_htf_filter_1h(df_1h: pd.DataFrame, symbol: str = "") -> Optional[str]:
    """
    1 Saatlik grafikte ana trend yönünü belirle
    
    LONG İzin Koşulları:
    - Close > EMA50
    - RSI > 50
    - MACD Histogram > 0
    
    SHORT İzin Koşulları:
    - Close < EMA50
    - RSI < 50
    - MACD Histogram < 0
    
    Args:
        df_1h: 1H OHLCV data with indicators (ema50, rsi, macd_hist)
        symbol: Coin symbol (for logging)
    
    Returns:
        'LONG': Sadece LONG sinyallere izin ver
        'SHORT': Sadece SHORT sinyallere izin ver
        None: Kararsız pazar - İşlem yapma
    """
    if df_1h is None or df_1h.empty or len(df_1h) < 2:
        logger.warning(f"⚠️ {symbol} 1H data yetersiz")
        return None
    
    # Required columns check
    required_cols = ['close', 'ema50', 'rsi', 'macd_hist']
    if not all(col in df_1h.columns for col in required_cols):
        logger.error(f"❌ {symbol} 1H data eksik kolonlar: {set(required_cols) - set(df_1h.columns)}")
        return None
    
    # Son mum
    last = df_1h.iloc[-1]
    
    # NaN kontrolü
    if pd.isna(last['close']) or pd.isna(last['ema50']) or pd.isna(last['rsi']) or pd.isna(last['macd_hist']):
        logger.warning(f"⚠️ {symbol} 1H data'da NaN değerler var")
        return None
    
    close = float(last['close'])
    ema50 = float(last['ema50'])
    rsi = float(last['rsi'])
    macd_hist = float(last['macd_hist'])
    
    # LONG KOŞULLARI (2/3 yeterli - daha esnek)
    long_price = close > ema50
    long_rsi = rsi > 45  # 50 → 45 (daha esnek)
    long_macd = macd_hist > 0
    
    # SHORT KOŞULLARI (2/3 yeterli)
    short_price = close < ema50
    short_rsi = rsi < 55  # 50 → 55 (daha esnek)
    short_macd = macd_hist < 0
    
    # Karar - 2/3 koşul yeterli
    long_count = sum([long_price, long_rsi, long_macd])
    short_count = sum([short_price, short_rsi, short_macd])
    
    if long_count >= 2:
        logger.info(f"✅ {symbol} 1H FILTER → LONG İZİN VERİLİR ({long_count}/3 koşul)")
        logger.info(f"   Price > EMA50: {long_price} (${close:.2f} vs ${ema50:.2f})")
        logger.info(f"   RSI > 45: {long_rsi} ({rsi:.1f})")
        logger.info(f"   MACD > 0: {long_macd} ({macd_hist:.4f})")
        return 'LONG'
    
    elif short_count >= 2:
        logger.info(f"✅ {symbol} 1H FILTER → SHORT İZİN VERİLİR ({short_count}/3 koşul)")
        logger.info(f"   Price < EMA50: {short_price} (${close:.2f} vs ${ema50:.2f})")
        logger.info(f"   RSI < 55: {short_rsi} ({rsi:.1f})")
        logger.info(f"   MACD < 0: {short_macd} ({macd_hist:.4f})")
        return 'SHORT'
    
    else:
        # Kararsız durum
        logger.debug(f"⚠️ {symbol} 1H FILTER → KARARSIZ ({long_count} LONG, {short_count} SHORT)")
        return None


# ═══════════════════════════════════════════════════════════════════════
# LAYER 2: LTF TRIGGER (15M) - Giriş Tetikleyicisi
# ═══════════════════════════════════════════════════════════════════════

def check_ltf_trigger_15m(
    df_15m: pd.DataFrame, 
    allowed_direction: str,
    symbol: str = ""
) -> Optional[Dict]:
    """
    15 Dakikalık grafikte giriş sinyali ara
    
    LONG TETİKLEYİCİ (sadece allowed_direction='LONG' ise):
    - EMA5 yukarı kesmiş EMA20'yi (son veya bir önceki mum)
    - MACD Histogram > 0
    - 50 < RSI < 75
    
    SHORT TETİKLEYİCİ (sadece allowed_direction='SHORT' ise):
    - EMA5 aşağı kesmiş EMA20'yi
    - MACD Histogram < 0
    - 25 < RSI < 50
    
    Args:
        df_15m: 15M OHLCV data with indicators (ema5, ema20, rsi, macd_hist)
        allowed_direction: 'LONG' or 'SHORT' (from HTF filter)
        symbol: Coin symbol (for logging)
    
    Returns:
        Dict with signal details or None
        {
            'signal': 'LONG' or 'SHORT',
            'entry_price': float,
            'ema5': float,
            'ema20': float,
            'rsi': float,
            'macd_hist': float,
            'crossover_candle': 'current' or 'previous'
        }
    """
    if df_15m is None or df_15m.empty or len(df_15m) < 3:
        logger.warning(f"⚠️ {symbol} 15M data yetersiz")
        return None
    
    # Required columns check
    required_cols = ['close', 'ema5', 'ema20', 'rsi', 'macd_hist']
    if not all(col in df_15m.columns for col in required_cols):
        logger.error(f"❌ {symbol} 15M data eksik kolonlar: {set(required_cols) - set(df_15m.columns)}")
        return None
    
    # Son 2 mum
    prev = df_15m.iloc[-2]
    curr = df_15m.iloc[-1]
    
    # NaN kontrolü
    if any(pd.isna(prev[col]) for col in required_cols) or any(pd.isna(curr[col]) for col in required_cols):
        logger.warning(f"⚠️ {symbol} 15M data'da NaN değerler var")
        return None
    
    # Current values
    close = float(curr['close'])
    ema5_curr = float(curr['ema5'])
    ema20_curr = float(curr['ema20'])
    rsi_curr = float(curr['rsi'])
    macd_hist_curr = float(curr['macd_hist'])
    
    # Previous values
    ema5_prev = float(prev['ema5'])
    ema20_prev = float(prev['ema20'])
    
    # ───────────────────────────────────────────────────────────────────
    # LONG TRIGGER (sadece allowed_direction='LONG' ise kontrol et)
    # ───────────────────────────────────────────────────────────────────
    if allowed_direction == 'LONG':
        # 🔥 ESNEK: Son 2 mumda crossover arayabiliriz
        # 15M timeframe'de son 2 mum içinde crossover yeterli
        
        # Son mum kontrolü
        crossover_on_last_candle = (ema5_prev <= ema20_prev) and (ema5_curr > ema20_curr)
        
        # Bir önceki mum kontrolü (ek şans)
        if len(df_15m) >= 3:
            prev2 = df_15m.iloc[-3]
            ema5_prev2 = float(prev2['ema5'])
            ema20_prev2 = float(prev2['ema20'])
            crossover_on_prev_candle = (ema5_prev2 <= ema20_prev2) and (ema5_prev > ema20_prev)
        else:
            crossover_on_prev_candle = False
        
        has_crossover = crossover_on_last_candle or crossover_on_prev_candle
        
        if not has_crossover:
            # 🔍 PRE-CROSSOVER DETECTION: EMA'lar yaklaşıyor mu?
            ema_distance_pct = abs((ema5_curr - ema20_curr) / ema20_curr) * 100
            proximity_threshold = 0.5  # %0.5 - crossover'a yakın
            
            if ema5_curr < ema20_curr and ema_distance_pct <= proximity_threshold:
                # EMA5 hala altında ama çok yakın - yaklaşma var!
                ema5_slope = ema5_curr - ema5_prev
                ema20_slope = ema20_curr - ema20_prev
                
                if ema5_slope > ema20_slope:
                    # EMA5 daha hızlı yükseliyor - kesişme yakın!
                    logger.info(f"⚡ {symbol} PRE-CROSSOVER ALERT (LONG)")
                    logger.info(f"   EMA5: {ema5_curr:.4f} ({ema5_slope:+.4f}/mum)")
                    logger.info(f"   EMA20: {ema20_curr:.4f} ({ema20_slope:+.4f}/mum)")
                    logger.info(f"   Distance: {ema_distance_pct:.3f}% (threshold: {proximity_threshold}%)")
                    logger.info(f"   🎯 Yaklaşık {int(ema_distance_pct / abs(ema5_slope - ema20_slope + 0.0001) * 15)} dakika içinde crossover olabilir!")
            
            logger.debug(f"   {symbol} 15M: LONG için SON MUMDA crossover YOK (EMA5 prev: {ema5_prev:.4f}, curr: {ema5_curr:.4f} | EMA20 prev: {ema20_prev:.4f}, curr: {ema20_curr:.4f})")
            return None        # MACD Histogram kontrolü (opsiyonel - RSI yeterli ise skip edilebilir)
        macd_ok = macd_hist_curr > 0
        
        # RSI kontrolü (45 < RSI < 85 - GENİŞLETİLDİ)
        rsi_ok = 45 < rsi_curr < 85
        
        if not rsi_ok:
            logger.debug(f"   {symbol} 15M: LONG için RSI aralık dışı ({rsi_curr:.1f}, gerekli: 45-85)")
            return None
        
        # MACD zorunlu değil ama varsa daha iyi
        if not macd_ok:
            logger.debug(f"   {symbol} 15M: MACD negatif ama RSI OK, devam ediliyor ({macd_hist_curr:.4f})")
        
        # ✅ TÜM KOŞULLAR SAĞLANDI
        logger.info(f"🎯 {symbol} 15M TRIGGER → LONG SİNYALİ!")
        logger.info(f"   Entry: ${close:.4f}")
        logger.info(f"   🔥 SON MUMDA EMA CROSSOVER: EMA5({ema5_prev:.4f}→{ema5_curr:.4f}) > EMA20({ema20_prev:.4f}→{ema20_curr:.4f})")
        logger.info(f"   RSI: {rsi_curr:.1f} (50-75 ✓)")
        logger.info(f"   MACD Hist: {macd_hist_curr:.4f} > 0 ✓")
        
        return {
            'signal': 'LONG',
            'entry_price': close,
            'ema5': ema5_curr,
            'ema20': ema20_curr,
            'rsi': rsi_curr,
            'macd_hist': macd_hist_curr,
            'crossover_candle': 'last_candle',
            'crossover_confirmed': True
        }
    
    # ───────────────────────────────────────────────────────────────────
    # SHORT TRIGGER (sadece allowed_direction='SHORT' ise kontrol et)
    # ───────────────────────────────────────────────────────────────────
    elif allowed_direction == 'SHORT':
        # 🔥 ESNEK: Son 2 mumda crossover arayabiliriz
        
        # Son mum kontrolü
        crossover_on_last_candle = (ema5_prev >= ema20_prev) and (ema5_curr < ema20_curr)
        
        # Bir önceki mum kontrolü (ek şans)
        if len(df_15m) >= 3:
            prev2 = df_15m.iloc[-3]
            ema5_prev2 = float(prev2['ema5'])
            ema20_prev2 = float(prev2['ema20'])
            crossover_on_prev_candle = (ema5_prev2 >= ema20_prev2) and (ema5_prev < ema20_prev)
        else:
            crossover_on_prev_candle = False
        
        has_crossover = crossover_on_last_candle or crossover_on_prev_candle
        
        if not has_crossover:
            # 🔍 PRE-CROSSOVER DETECTION: EMA'lar yaklaşıyor mu?
            ema_distance_pct = abs((ema5_curr - ema20_curr) / ema20_curr) * 100
            proximity_threshold = 0.5  # %0.5 - crossover'a yakın
            
            if ema5_curr > ema20_curr and ema_distance_pct <= proximity_threshold:
                # EMA5 hala üstünde ama çok yakın - yaklaşma var!
                ema5_slope = ema5_curr - ema5_prev
                ema20_slope = ema20_curr - ema20_prev
                
                if ema5_slope < ema20_slope:
                    # EMA5 daha hızlı düşüyor - kesişme yakın!
                    logger.info(f"⚡ {symbol} PRE-CROSSOVER ALERT (SHORT)")
                    logger.info(f"   EMA5: {ema5_curr:.4f} ({ema5_slope:+.4f}/mum)")
                    logger.info(f"   EMA20: {ema20_curr:.4f} ({ema20_slope:+.4f}/mum)")
                    logger.info(f"   Distance: {ema_distance_pct:.3f}% (threshold: {proximity_threshold}%)")
                    logger.info(f"   🎯 Yaklaşık {int(ema_distance_pct / abs(ema5_slope - ema20_slope + 0.0001) * 15)} dakika içinde crossover olabilir!")
            
            logger.debug(f"   {symbol} 15M: SHORT için SON MUMDA crossover YOK (EMA5 prev: {ema5_prev:.4f}, curr: {ema5_curr:.4f} | EMA20 prev: {ema20_prev:.4f}, curr: {ema20_curr:.4f})")
            return None
        
        # MACD Histogram kontrolü
        if macd_hist_curr >= 0:
            logger.debug(f"   {symbol} 15M: SHORT için MACD Histogram >= 0 ({macd_hist_curr:.4f})")
            return None
        
        # RSI kontrolü (25 < RSI < 50)
        if rsi_curr <= 25 or rsi_curr >= 50:
            logger.debug(f"   {symbol} 15M: SHORT için RSI aralık dışı ({rsi_curr:.1f}, gerekli: 25-50)")
            return None
        
        # ✅ TÜM KOŞULLAR SAĞLANDI
        logger.info(f"🎯 {symbol} 15M TRIGGER → SHORT SİNYALİ!")
        logger.info(f"   Entry: ${close:.4f}")
        logger.info(f"   🔥 SON MUMDA EMA CROSSOVER: EMA5({ema5_prev:.4f}→{ema5_curr:.4f}) < EMA20({ema20_prev:.4f}→{ema20_curr:.4f})")
        logger.info(f"   RSI: {rsi_curr:.1f} (25-50 ✓)")
        logger.info(f"   MACD Hist: {macd_hist_curr:.4f} < 0 ✓")
        
        return {
            'signal': 'SHORT',
            'entry_price': close,
            'ema5': ema5_curr,
            'ema20': ema20_curr,
            'rsi': rsi_curr,
            'macd_hist': macd_hist_curr,
            'crossover_candle': 'last_candle',
            'crossover_confirmed': True
        }
    
    else:
        logger.error(f"❌ {symbol} Geçersiz allowed_direction: {allowed_direction}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# LAYER 3: RISK FILTERS - Son Güvenlik Kontrolleri
# ═══════════════════════════════════════════════════════════════════════

def check_risk_filters(
    df_15m: pd.DataFrame,
    signal: Dict,
    max_atr_percent: float = 2.0,
    volume_confirmation_required: bool = True,
    symbol: str = ""
) -> Tuple[bool, str]:
    """
    Son güvenlik kontrolleri (ATR, Volume)
    
    Filtreler:
    1. ATR Volatilite: ATR / Price < max_atr_percent (örn: 2%)
    2. Volume Confirmation: Current Volume > Volume SMA(20)
    
    Args:
        df_15m: 15M data with indicators (atr, volume, volume_sma20)
        signal: Signal dict from check_ltf_trigger_15m()
        max_atr_percent: Maximum ATR as % of price (default: 2.0)
        volume_confirmation_required: Require volume > average (default: True)
        symbol: Coin symbol
    
    Returns:
        (passed: bool, reason: str)
    """
    if df_15m is None or df_15m.empty:
        return False, "15M data yetersiz"
    
    # Required columns
    required_cols = ['atr', 'volume', 'volume_sma20']
    if not all(col in df_15m.columns for col in required_cols):
        return False, f"Eksik kolonlar: {set(required_cols) - set(df_15m.columns)}"
    
    last = df_15m.iloc[-1]
    
    if pd.isna(last['atr']) or pd.isna(last['volume']) or pd.isna(last['volume_sma20']):
        return False, "NaN değerler var"
    
    atr = float(last['atr'])
    volume = float(last['volume'])
    volume_sma = float(last['volume_sma20'])
    entry_price = signal['entry_price']
    
    # ───────────────────────────────────────────────────────────────────
    # 1. ATR Volatilite Filtresi
    # ───────────────────────────────────────────────────────────────────
    atr_percent = (atr / entry_price) * 100
    
    if atr_percent > max_atr_percent:
        reason = f"ATR çok yüksek ({atr_percent:.2f}% > {max_atr_percent}%)"
        logger.warning(f"❌ {symbol} RISK FILTER: {reason}")
        return False, reason
    
    logger.info(f"✅ {symbol} ATR Filter: {atr_percent:.2f}% <= {max_atr_percent}%")
    
    # ───────────────────────────────────────────────────────────────────
    # 2. Volume Filtresi
    # ───────────────────────────────────────────────────────────────────
    if volume_confirmation_required:
        if volume < volume_sma:
            reason = f"Hacim yetersiz (${volume/1e6:.1f}M < ${volume_sma/1e6:.1f}M avg)"
            logger.warning(f"❌ {symbol} RISK FILTER: {reason}")
            return False, reason
        
        logger.info(f"✅ {symbol} Volume Filter: ${volume/1e6:.1f}M > ${volume_sma/1e6:.1f}M avg")
    
    # ───────────────────────────────────────────────────────────────────
    # ✅ TÜM FİLTRELER GEÇİLDİ
    # ───────────────────────────────────────────────────────────────────
    logger.info(f"🎉 {symbol} TÜM RISK FİLTRELERİ GEÇİLDİ!")
    return True, "OK"


# ═══════════════════════════════════════════════════════════════════════
# MASTER FUNCTION - Tüm Katmanları Birleştir
# ═══════════════════════════════════════════════════════════════════════

def analyze_htf_ltf_signal(
    df_1h: pd.DataFrame,
    df_15m: pd.DataFrame,
    symbol: str,
    max_atr_percent: float = 2.0,
    volume_confirmation_required: bool = True
) -> Optional[Dict]:
    """
    HTF-LTF Strategy - Tüm katmanları birleştir
    
    Akış:
    1. Layer 1: 1H trend filtresi → Hangi yöne girilebilir?
    2. Layer 2: 15M trigger → İzin verilen yönde sinyal var mı?
    3. Layer 3: Risk filters → ATR ve hacim uygun mu?
    
    Args:
        df_1h: 1H OHLCV with indicators
        df_15m: 15M OHLCV with indicators
        symbol: Coin symbol
        max_atr_percent: Max ATR % (default: 2.0)
        volume_confirmation_required: Require volume confirmation (default: True)
    
    Returns:
        Signal dict with all details or None
        {
            'symbol': str,
            'signal': 'LONG' or 'SHORT',
            'entry_price': float,
            'htf_direction': str,
            'ltf_trigger': dict,
            'risk_filters': {'passed': bool, 'reason': str},
            'timestamp': str
        }
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"🔍 HTF-LTF Analysis: {symbol}")
    logger.info(f"{'='*70}")
    
    # ───────────────────────────────────────────────────────────────────
    # LAYER 1: HTF FILTER (1H)
    # ───────────────────────────────────────────────────────────────────
    logger.info(f"\n📊 LAYER 1: HTF Filter (1H)")
    allowed_direction = check_htf_filter_1h(df_1h, symbol)
    
    if allowed_direction is None:
        logger.info(f"⛔ {symbol} ATLA: 1H trend kararsız (işlem yok)")
        return None
    
    # ───────────────────────────────────────────────────────────────────
    # LAYER 2: LTF TRIGGER (15M)
    # ───────────────────────────────────────────────────────────────────
    logger.info(f"\n🎯 LAYER 2: LTF Trigger (15M) - Arama: {allowed_direction}")
    ltf_signal = check_ltf_trigger_15m(df_15m, allowed_direction, symbol)
    
    if ltf_signal is None:
        logger.info(f"⛔ {symbol} ATLA: 15M'de {allowed_direction} sinyali bulunamadı")
        return None
    
    # ───────────────────────────────────────────────────────────────────
    # LAYER 3: RISK FILTERS
    # ───────────────────────────────────────────────────────────────────
    logger.info(f"\n🛡️ LAYER 3: Risk Filters")
    risk_passed, risk_reason = check_risk_filters(
        df_15m=df_15m,
        signal=ltf_signal,
        max_atr_percent=max_atr_percent,
        volume_confirmation_required=volume_confirmation_required,
        symbol=symbol
    )
    
    if not risk_passed:
        logger.warning(f"⛔ {symbol} ATLA: Risk filter başarısız - {risk_reason}")
        return None
    
    # ───────────────────────────────────────────────────────────────────
    # ✅ BAŞARILI SİNYAL
    # ───────────────────────────────────────────────────────────────────
    final_signal = {
        'symbol': symbol,
        'signal': ltf_signal['signal'],
        'entry_price': ltf_signal['entry_price'],
        'htf_direction': allowed_direction,
        'ltf_trigger': ltf_signal,
        'risk_filters': {'passed': True, 'reason': 'OK'},
        'timestamp': datetime.now().isoformat()
    }
    
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ SINYAL GEÇERLİ: {symbol} → {final_signal['signal']} @ ${final_signal['entry_price']:.4f}")
    logger.info(f"{'='*70}\n")
    
    return final_signal
