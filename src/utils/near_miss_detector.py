"""
Near-Miss Signal Detection Utility (v12.1)
==========================================

Bu modül, reddedilen sinyallerin neden reddedildiğini analiz eder ve
%90 threshold içindeki "neredeyse geçen" sinyalleri tespit eder.
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def calculate_near_miss_score(
    signal: Dict,
    range_width: float,
    min_range_width: float,
    rr_ratio: float,
    min_rr_ratio: float,
    sl_distance_pct: float,
    min_sl_distance: float,
    range_quality: str,
    min_quality: str,
    quality_score: float,
    threshold_percent: float = 0.90
) -> Optional[Dict]:
    """
    Reddedilen bir sinyalin near-miss olup olmadığını belirler.
    Yüzde bazlı threshold kullanır (%90 = gereksinimin %90'ı dahilinde).
    
    Args:
        signal: Sinyal detayları (entry, sl, tp, support, resistance, etc.)
        range_width: Gerçek range genişliği
        min_range_width: Minimum gereksinim
        rr_ratio: Risk-reward oranı
        min_rr_ratio: Minimum gereksinim
        sl_distance_pct: SL mesafesi (yüzde)
        min_sl_distance: Minimum gereksinim
        range_quality: Kalite grade (A/B/C/D)
        min_quality: Minimum kalite (B gibi)
        quality_score: Numeric kalite puanı
        threshold_percent: Near-miss threshold (0.90 = %90)
        
    Returns:
        Dict with near-miss details if qualified, None otherwise
    """
    
    # Rejection reasons ve missing criteria
    rejections = []
    criteria_scores = []
    
    # Kalite grade mapping (30-95 scale - consistent with range_main.py)
    quality_map = {'A': 95, 'B': 75, 'C': 55, 'D': 30}
    current_quality_num = quality_map.get(range_quality, 30)
    min_quality_num = quality_map.get(min_quality, 75)
    
    # ════════════════════════════════════════════════════════════
    # 1. RANGE WIDTH CHECK
    # ════════════════════════════════════════════════════════════
    if range_width < min_range_width:
        width_score = range_width / min_range_width
        criteria_scores.append(width_score)
        
        if width_score >= threshold_percent:
            rejections.append({
                'reason': 'range_width',
                'required': min_range_width,
                'actual': range_width,
                'score': width_score,
                'message': f"Range {range_width*100:.2f}% (req: {min_range_width*100:.1f}%)"
            })
    
    # ════════════════════════════════════════════════════════════
    # 2. RISK-REWARD CHECK
    # ════════════════════════════════════════════════════════════
    if rr_ratio < min_rr_ratio:
        rr_score = rr_ratio / min_rr_ratio
        criteria_scores.append(rr_score)
        
        if rr_score >= threshold_percent:
            rejections.append({
                'reason': 'rr_ratio',
                'required': min_rr_ratio,
                'actual': rr_ratio,
                'score': rr_score,
                'message': f"RR {rr_ratio:.2f}:1 (req: {min_rr_ratio}:1)"
            })
    
    # ════════════════════════════════════════════════════════════
    # 3. SL DISTANCE CHECK
    # ════════════════════════════════════════════════════════════
    if sl_distance_pct < min_sl_distance:
        sl_score = sl_distance_pct / min_sl_distance
        criteria_scores.append(sl_score)
        
        if sl_score >= threshold_percent:
            rejections.append({
                'reason': 'sl_distance',
                'required': min_sl_distance,
                'actual': sl_distance_pct,
                'score': sl_score,
                'message': f"SL {sl_distance_pct*100:.2f}% (req: {min_sl_distance*100:.1f}%)"
            })
    
    # ════════════════════════════════════════════════════════════
    # 4. QUALITY GRADE CHECK (DİNAMİK KALİTE YÜKSELTMESİ)
    # ════════════════════════════════════════════════════════════
    # Kalite düşükse izlemeye al - fiyat hareketi ile yükselebilir
    # C → B → A dönüşümü gerçek zamanlı takip edilir
    if current_quality_num < min_quality_num:
        quality_score_normalized = current_quality_num / min_quality_num
        criteria_scores.append(quality_score_normalized)
        
        # C kalite bile kabul et (%67.5+ threshold)
        # Çünkü fiyat hareketi ile B veya A'ya yükselebilir
        relaxed_quality_threshold = threshold_percent * 0.75  # %90 * 0.75 = %67.5
        if quality_score_normalized >= relaxed_quality_threshold:
            rejections.append({
                'reason': 'quality',
                'required': min_quality,
                'actual': range_quality,
                'score': quality_score_normalized,
                'message': f"Quality {range_quality} (req: {min_quality}+) - izleniyor, yükselebilir"
            })
    
    # ════════════════════════════════════════════════════════════
    # 5. FALSE BREAKOUTS CHECK
    # ════════════════════════════════════════════════════════════
    false_breakouts = signal.get('false_breakouts', [])
    max_false_breakouts = 2  # Hardcoded for now
    
    if len(false_breakouts) > max_false_breakouts:
        fb_score = max_false_breakouts / max(len(false_breakouts), 1)
        criteria_scores.append(fb_score)
        
        if fb_score >= threshold_percent:
            rejections.append({
                'reason': 'false_breakouts',
                'required': max_false_breakouts,
                'actual': len(false_breakouts),
                'score': fb_score,
                'message': f"False breakouts: {len(false_breakouts)} (max: {max_false_breakouts})"
            })
    
    # ════════════════════════════════════════════════════════════
    # NEAR-MISS QUALIFICATION (GENİŞLETİLMİŞ)
    # ════════════════════════════════════════════════════════════
    
    # Eğer hiç rejection yoksa, normal reject (near-miss değil)
    if not rejections:
        return None
    
    # ESNEKLEŞME: Herhangi bir kriterin %67.5+ threshold'u geçmesi yeterli
    # (Örnek: C kalite %67, range width %95, RR %88 → İzlemeye alınır)
    # Gerçek zamanlı takipte TÜM kriterler kontrol edilecek
    relaxed_threshold = threshold_percent * 0.75  # %90 * 0.75 = %67.5
    if not any(r['score'] >= relaxed_threshold for r in rejections):
        return None
    
    # Average missing criteria score
    avg_score = sum(criteria_scores) / len(criteria_scores) if criteria_scores else 0
    
    # Priority score: quality_score * avg_criteria_score
    # Yüksek kaliteli + kriterlere yakın sinyaller öncelikli
    priority_score = quality_score * avg_score
    
    # Near-miss detayları
    near_miss = {
        'rejections': rejections,
        'missing_criteria_percent': avg_score,
        'priority_score': priority_score,
        'quality_score': quality_score,
        'range_quality': range_quality,
        'rejection_reasons': ', '.join([r['reason'] for r in rejections]),
        'rejection_details': ' | '.join([r['message'] for r in rejections])
    }
    
    return near_miss


def create_near_miss_record(
    symbol: str,
    signal: Dict,
    near_miss_info: Dict,
    ttl_minutes: int = 10
) -> Dict:
    """
    NearMissSignal tablosu için record oluştur.
    
    Args:
        symbol: Trading pair
        signal: Sinyal detayları
        near_miss_info: calculate_near_miss_score() çıktısı
        ttl_minutes: Signal expiration time
        
    Returns:
        Dict ready for database insertion
    """
    now = datetime.now()
    expires_at = now + timedelta(minutes=ttl_minutes)
    
    record = {
        'symbol': symbol,
        'direction': signal.get('signal', 'HOLD'),  # signal field contains LONG/SHORT/HOLD
        'support': signal.get('support', 0),
        'resistance': signal.get('resistance', 0),
        'current_price': signal['entry_price'],
        'range_width_percent': signal.get('range_width', 0) * 100,  # Convert to percentage
        'quality_grade': near_miss_info['range_quality'],
        'quality_score': near_miss_info['quality_score'],
        'rejection_reason': near_miss_info.get('rejection_reasons', ''),  # Already a string
        'missing_criteria_percent': near_miss_info['missing_criteria_percent'],
        'htf_confirmed': signal.get('htf_confirmation', False),
        'htf_overlap_percent': signal.get('htf_overlap', 0.0),
        'expires_at': expires_at,
        'is_active': True,
        'is_consumed': False,
        'priority_score': near_miss_info['priority_score']
    }
    
    return record


def log_near_miss_detection(symbol: str, near_miss_info: Dict):
    """Near-miss detection loglama"""
    logger.info(f"   🎯 NEAR-MISS: {symbol}")
    logger.info(f"      Quality: {near_miss_info['range_quality']} "
               f"(score: {near_miss_info['quality_score']:.2f})")
    rejection_reasons = near_miss_info.get('rejection_reasons', [])
    if rejection_reasons:
        logger.info(f"      Rejected: {', '.join(rejection_reasons)}")
    logger.info(f"      Criteria: {near_miss_info['missing_criteria_percent']*100:.0f}% met")
    logger.info(f"      Priority: {near_miss_info['priority_score']:.2f}")
