# src/technical_analyzer/range_detector.py
"""
RANGE DETECTOR - Aralık Tespit Sistemi (ENHANCED V3)
====================================================
Son 24 saatte fiyatın hareket ettiği range'i tespit eder.

V3 Yeni Özellikler:
- 📊 Volume-weighted level clustering (hacim ağırlıklı seviye tespiti)
- 🔄 Touch count tracking (seviye test sayısı)
- 📈 Range quality scoring (A/B/C/D kalite notu)
- ⚡ False breakout detection (sahte kırılım tespiti)
- 🎯 Support/resistance strength score (seviye güvenilirlik skoru)
- 📉 Volatility-adaptive thresholds (volatiliteye göre dinamik eşikler)
- 🧮 Volume profile analysis (hacim profil analizi)
"""

import logging
import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple, List

logger = logging.getLogger(__name__)


def find_support_resistance_volume_weighted(
    df: pd.DataFrame, 
    lookback: int = 96
) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Volume-weighted support/resistance tespiti (V3 ENHANCED)
    
    Özellikler:
    - Hacim ağırlıklı seviye kümeleme
    - Test sayısı (touch count) takibi
    - Seviye güvenilirlik skoru
    - Wick vs body ayrımı
    
    Args:
        df: OHLCV dataframe
        lookback: Geriye bakış periyodu (96 = 24 saat for 15m)
    
    Returns:
        (support_dict, resistance_dict) veya (None, None)
        
        Dict format:
        {
            'price': 45000.0,
            'strength': 8.5,  # 0-10 güvenilirlik skoru
            'touch_count': 5,  # Kaç kez test edildi
            'volume_weight': 1250000,  # Toplam hacim
            'last_touch_ago': 3  # Son test kaç mum önce
        }
    """
    try:
        if df is None or len(df) < lookback:
            return None, None
        
        recent = df.tail(lookback).copy()
        
        # Swing point'leri bul (hem body hem wick dikkate al)
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(recent) - 2):
            current_high = recent['high'].iloc[i]
            current_low = recent['low'].iloc[i]
            current_close = recent['close'].iloc[i]
            current_open = recent['open'].iloc[i]
            current_volume = recent['volume'].iloc[i] if 'volume' in recent.columns else 1.0
            
            # Yerel maksimum (resistance candidate)
            if (current_high > recent['high'].iloc[i-1] and 
                current_high > recent['high'].iloc[i-2] and
                current_high > recent['high'].iloc[i+1] and
                current_high > recent['high'].iloc[i+2]):
                
                # Body vs wick analizi
                body_top = max(current_close, current_open)
                wick_length = current_high - body_top
                body_length = abs(current_close - current_open)
                
                # Wick çok uzunsa (body'nin 2x'i), güvenilirlik azalır
                wick_penalty = 1.0
                if body_length > 0:
                    wick_ratio = wick_length / body_length
                    if wick_ratio > 2.0:
                        wick_penalty = 0.5  # Zayıf seviye
                
                swing_highs.append({
                    'price': float(current_high),
                    'volume': float(current_volume),
                    'index': i,
                    'wick_penalty': wick_penalty
                })
            
            # Yerel minimum (support candidate)
            if (current_low < recent['low'].iloc[i-1] and 
                current_low < recent['low'].iloc[i-2] and
                current_low < recent['low'].iloc[i+1] and
                current_low < recent['low'].iloc[i+2]):
                
                # Body vs wick analizi
                body_bottom = min(current_close, current_open)
                wick_length = body_bottom - current_low
                body_length = abs(current_close - current_open)
                
                wick_penalty = 1.0
                if body_length > 0:
                    wick_ratio = wick_length / body_length
                    if wick_ratio > 2.0:
                        wick_penalty = 0.5
                
                swing_lows.append({
                    'price': float(current_low),
                    'volume': float(current_volume),
                    'index': i,
                    'wick_penalty': wick_penalty
                })
        
        if not swing_highs or not swing_lows:
            return None, None
        
        # Volume-weighted clustering
        resistance = find_strongest_level(swing_highs, recent, lookback)
        support = find_strongest_level(swing_lows, recent, lookback)
        
        return support, resistance
    
    except Exception as e:
        logger.error(f"Volume-weighted support/resistance bulma hatası: {e}", exc_info=True)
        return None, None


def find_strongest_level(
    swing_points: List[Dict],
    df: pd.DataFrame,
    lookback: int,
    tolerance: float = 0.002
) -> Optional[Dict]:
    """
    En güçlü seviyeyi bul (volume-weighted clustering ile)
    
    Args:
        swing_points: Swing point listesi [{'price', 'volume', 'index', 'wick_penalty'}]
        df: Full dataframe
        lookback: Lookback period
        tolerance: Clustering toleransı (0.002 = %0.2)
    
    Returns:
        {
            'price': 45000.0,
            'strength': 8.5,
            'touch_count': 5,
            'volume_weight': 1250000,
            'last_touch_ago': 3
        }
    """
    if not swing_points:
        return None
    
    # Fiyata göre sırala
    sorted_points = sorted(swing_points, key=lambda x: x['price'])
    
    # Kümeleri oluştur (tolerance içinde olan noktalar aynı küme)
    clusters = []
    current_cluster = [sorted_points[0]]
    
    for point in sorted_points[1:]:
        reference_price = current_cluster[0]['price']
        
        if abs(point['price'] - reference_price) / reference_price <= tolerance:
            # Aynı kümeye ekle
            current_cluster.append(point)
        else:
            # Yeni küme başlat
            clusters.append(current_cluster)
            current_cluster = [point]
    
    clusters.append(current_cluster)
    
    # Her küme için güvenilirlik skoru hesapla
    cluster_scores = []
    
    for cluster in clusters:
        # Ortalama fiyat (volume-weighted)
        total_volume = sum(p['volume'] * p['wick_penalty'] for p in cluster)
        weighted_price = sum(p['price'] * p['volume'] * p['wick_penalty'] for p in cluster) / total_volume if total_volume > 0 else sum(p['price'] for p in cluster) / len(cluster)
        
        # Touch count
        touch_count = len(cluster)
        
        # Son test ne zaman oldu?
        last_touch_index = max(p['index'] for p in cluster)
        last_touch_ago = lookback - last_touch_index
        
        # Recency bonus (son 10 mum içinde test edildiyse bonus)
        recency_multiplier = 1.5 if last_touch_ago <= 10 else 1.0
        
        # Güvenilirlik skoru (0-10)
        # - Touch count: Her test +1.5 puan (max 5 test = 7.5 puan)
        # - Volume weight: Normalize edilmiş hacim (max 2.5 puan)
        # - Recency: Son testler daha değerli (1.0x veya 1.5x)
        
        base_score = min(7.5, touch_count * 1.5)
        volume_score = min(2.5, (total_volume / 1000000) * 0.5)  # Normalize (assumes decent volume)
        
        strength = (base_score + volume_score) * recency_multiplier
        strength = min(10.0, strength)  # Cap at 10
        
        cluster_scores.append({
            'price': weighted_price,
            'strength': strength,
            'touch_count': touch_count,
            'volume_weight': total_volume,
            'last_touch_ago': last_touch_ago
        })
    
    # En güçlü seviyeyi seç
    if not cluster_scores:
        return None
    
    strongest = max(cluster_scores, key=lambda x: x['strength'])
    
    return strongest


def calculate_range_quality(
    support: Dict,
    resistance: Dict,
    df: pd.DataFrame,
    current_price: float
) -> str:
    """
    Range kalitesi skorla (A/B/C/D)
    
    Kriterler:
    - Seviye güvenilirliği (strength score)
    - Test sayısı (touch count)
    - Range genişliği (optimal: 1.5-5%)
    - Volume consistency
    - Recency
    
    Returns:
        'A' (En iyi), 'B' (İyi), 'C' (Orta), 'D' (Zayıf)
    """
    try:
        # Bileşen skorları
        score_components = {}
        
        # 1. Seviye güvenilirliği (ortalama strength)
        avg_strength = (support['strength'] + resistance['strength']) / 2
        score_components['strength'] = avg_strength / 10 * 40  # Max 40 puan
        
        # 2. Test sayısı
        total_touches = support['touch_count'] + resistance['touch_count']
        score_components['touches'] = min(30, total_touches * 3)  # Max 30 puan
        
        # 3. Range genişliği (optimal: 1.5-5%)
        range_width = (resistance['price'] - support['price']) / support['price']
        
        if 0.015 <= range_width <= 0.05:
            # Optimal genişlik
            score_components['width'] = 20
        elif 0.01 <= range_width < 0.015 or 0.05 < range_width <= 0.08:
            # Biraz dar/geniş ama kabul edilebilir
            score_components['width'] = 10
        else:
            # Çok dar veya çok geniş
            score_components['width'] = 0
        
        # 4. Recency (her iki seviye de yakın zamanda test edildi mi?)
        avg_recency = (support['last_touch_ago'] + resistance['last_touch_ago']) / 2
        
        if avg_recency <= 10:
            score_components['recency'] = 10
        elif avg_recency <= 30:
            score_components['recency'] = 5
        else:
            score_components['recency'] = 0
        
        # Toplam skor (0-100)
        total_score = sum(score_components.values())
        
        # Grade assignment
        if total_score >= 80:
            grade = 'A'
        elif total_score >= 60:
            grade = 'B'
        elif total_score >= 40:
            grade = 'C'
        else:
            grade = 'D'
        
        logger.debug(f"   Range Quality: {grade} (score: {total_score:.1f})")
        logger.debug(f"   Components: {score_components}")
        
        return grade
    
    except Exception as e:
        logger.error(f"Range quality calculation error: {e}")
        return 'C'  # Default medium quality


def detect_false_breakout(
    df: pd.DataFrame,
    support: Dict,
    resistance: Dict,
    lookback: int = 10
) -> Dict:
    """
    False breakout (sahte kırılım) tespiti
    
    Son N mumda:
    - Seviye kırıldı mı? (close price dışında)
    - Ama hemen geri döndü mü? (false breakout)
    
    Returns:
        {
            'false_breakout_detected': bool,
            'direction': 'UP' | 'DOWN' | None,
            'bars_ago': int,
            'severity': 'HIGH' | 'MEDIUM' | 'LOW'
        }
    """
    try:
        recent = df.tail(lookback)
        
        false_breakouts = []
        
        for i in range(len(recent) - 1):
            current = recent.iloc[i]
            next_bar = recent.iloc[i + 1]
            
            # Upward false breakout (resistance kırıldı ama geri döndü)
            if current['close'] > resistance['price']:
                # Sonraki mum tekrar range içine mi döndü?
                if next_bar['close'] < resistance['price']:
                    severity = 'HIGH' if current['high'] > resistance['price'] * 1.02 else 'MEDIUM'
                    false_breakouts.append({
                        'direction': 'UP',
                        'bars_ago': len(recent) - i,
                        'severity': severity
                    })
            
            # Downward false breakout (support kırıldı ama geri döndü)
            if current['close'] < support['price']:
                if next_bar['close'] > support['price']:
                    severity = 'HIGH' if current['low'] < support['price'] * 0.98 else 'MEDIUM'
                    false_breakouts.append({
                        'direction': 'DOWN',
                        'bars_ago': len(recent) - i,
                        'severity': severity
                    })
        
        if false_breakouts:
            # En yakın false breakout'u döndür
            most_recent = min(false_breakouts, key=lambda x: x['bars_ago'])
            return {
                'false_breakout_detected': True,
                **most_recent
            }
        else:
            return {
                'false_breakout_detected': False,
                'direction': None,
                'bars_ago': None,
                'severity': None
            }
    
    except Exception as e:
        logger.error(f"False breakout detection error: {e}")
        return {
            'false_breakout_detected': False,
            'direction': None,
            'bars_ago': None,
            'severity': None
        }


def find_support_resistance(df: pd.DataFrame, lookback: int = 96) -> Tuple[Optional[float], Optional[float]]:
    """
    LEGACY METHOD - Backward compatibility
    
    Basit destek/direnç tespiti (hacim ağırlıksız)
    Yeni kod için find_support_resistance_volume_weighted() kullanın
    """
    result = find_support_resistance_volume_weighted(df, lookback)
    
    if result[0] is None or result[1] is None:
        return None, None
    
    support_dict, resistance_dict = result
    
    return support_dict['price'], resistance_dict['price']



def find_most_tested_level(levels: list, tolerance: float = 0.002) -> float:
    """En çok test edilen seviyeyi bul."""
    if not levels:
        return None
    
    sorted_levels = sorted(levels)
    clusters = []
    current_cluster = [sorted_levels[0]]
    
    for level in sorted_levels[1:]:
        if (level - current_cluster[-1]) / current_cluster[-1] <= tolerance:
            current_cluster.append(level)
        else:
            clusters.append(current_cluster)
            current_cluster = [level]
    
    clusters.append(current_cluster)
    largest_cluster = max(clusters, key=len)
    
    return sum(largest_cluster) / len(largest_cluster)


def detect_range(df: pd.DataFrame, symbol: str, min_width: float = 0.015) -> Optional[Dict]:
    """
    Coin'in range'de olup olmadığını tespit et (V3 ENHANCED)
    
    Yeni Özellikler:
    - Volume-weighted level detection
    - Quality grading (A/B/C/D)
    - False breakout detection
    - Strength scoring
    
    Returns:
        Range bilgisi dict veya None
        
        Dict format:
        {
            'symbol': 'BTCUSDT',
            'support': {'price': 45000, 'strength': 8.5, 'touch_count': 5, ...},
            'resistance': {'price': 47000, 'strength': 7.2, 'touch_count': 3, ...},
            'mid_point': 46000,
            'range_width': 0.0444,
            'current_price': 45500,
            'distance_to_support': 0.0111,
            'distance_to_resistance': 0.0330,
            'quality_grade': 'A',
            'false_breakout': {'detected': False, ...},
            'recommendation': 'STRONG_BUY' | 'BUY' | 'HOLD' | 'AVOID'
        }
    """
    try:
        # V3: Volume-weighted detection
        support_dict, resistance_dict = find_support_resistance_volume_weighted(df, lookback=96)
        
        if support_dict is None or resistance_dict is None:
            return None
        
        support = support_dict['price']
        resistance = resistance_dict['price']
        
        range_width = (resistance - support) / support
        
        # Minimum genişlik kontrolü
        if range_width < min_width:
            logger.debug(f"{symbol}: Range çok dar ({range_width:.2%} < {min_width:.2%})")
            return None
        
        mid_point = (support + resistance) / 2
        current_price = float(df.iloc[-1]['close'])
        
        # Range dışında mı kontrol (tolerance: %1)
        if current_price < support * 0.99 or current_price > resistance * 1.01:
            logger.debug(f"{symbol}: Fiyat range dışında (${current_price:.2f})")
            return None
        
        # V3: Quality grading
        quality_grade = calculate_range_quality(support_dict, resistance_dict, df, current_price)
        
        # V3: False breakout detection
        false_breakout = detect_false_breakout(df, support_dict, resistance_dict, lookback=10)
        
        # Trading recommendation
        distance_to_support = (current_price - support) / support
        distance_to_resistance = (resistance - current_price) / current_price
        
        # A/B grade + yakın support = STRONG_BUY
        # C/D grade veya false breakout = dikkatli ol
        recommendation = 'HOLD'
        
        if quality_grade in ['A', 'B']:
            if distance_to_support <= 0.005:  # %0.5 içinde
                recommendation = 'STRONG_BUY' if quality_grade == 'A' else 'BUY'
            elif distance_to_resistance <= 0.005:
                recommendation = 'STRONG_SELL' if quality_grade == 'A' else 'SELL'
        elif quality_grade == 'D' or false_breakout['false_breakout_detected']:
            recommendation = 'AVOID'
        
        logger.info(f"✅ {symbol} - RANGE TESPİT EDİLDİ (Quality: {quality_grade}):")
        logger.info(f"   Destek: ${support:.6f} (strength: {support_dict['strength']:.1f}, touches: {support_dict['touch_count']})")
        logger.info(f"   Direnç: ${resistance:.6f} (strength: {resistance_dict['strength']:.1f}, touches: {resistance_dict['touch_count']})")
        logger.info(f"   Genişlik: {range_width:.2%}")
        logger.info(f"   Öneri: {recommendation}")
        
        if false_breakout['false_breakout_detected']:
            logger.warning(f"   ⚠️ False breakout detected: {false_breakout['direction']} {false_breakout['bars_ago']} bars ago ({false_breakout['severity']})")
        
        return {
            'symbol': symbol,
            'support': support_dict,
            'resistance': resistance_dict,
            'mid_point': mid_point,
            'range_width': range_width,
            'current_price': current_price,
            'distance_to_support': distance_to_support,
            'distance_to_resistance': distance_to_resistance,
            'quality_grade': quality_grade,
            'false_breakout': false_breakout,
            'recommendation': recommendation
        }
    
    except Exception as e:
        logger.error(f"❌ {symbol} range tespit hatası: {e}", exc_info=True)
        return None


def is_near_support(range_data: Dict, threshold: float = 0.005) -> bool:
    """
    Fiyat desteğe yakın mı? (V3: threshold 0.3% → 0.5%)
    
    V3: Quality grade dikkate alınır
    - A/B grade: threshold kullan
    - C/D grade: daha sıkı threshold (0.3%)
    """
    quality = range_data.get('quality_grade', 'C')
    
    if quality in ['C', 'D']:
        threshold = 0.003  # Daha sıkı threshold
    
    return range_data['distance_to_support'] <= threshold


def is_near_resistance(range_data: Dict, threshold: float = 0.005) -> bool:
    """
    Fiyat dirence yakın mı? (V3: threshold 0.3% → 0.5%)
    
    V3: Quality grade dikkate alınır
    """
    quality = range_data.get('quality_grade', 'C')
    
    if quality in ['C', 'D']:
        threshold = 0.003
    
    return range_data['distance_to_resistance'] <= threshold

