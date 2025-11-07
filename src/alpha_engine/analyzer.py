# src/alpha_engine/analyzer.py

import logging
import sys  # Test kodu için gerekli
import time # Test kodu için gerekli
from typing import Dict, Optional

# sentiment_analyzer importu
try:
    from . import sentiment_analyzer
except ImportError:
    try:
        import sentiment_analyzer
    except ImportError:
         logger = logging.getLogger(__name__)
         logger.warning("sentiment_analyzer modülü import edilemedi. Kalite hesaplama çalışmayabilir.", exc_info=False)
         sentiment_analyzer = None

logger = logging.getLogger(__name__)

# GÜNCELLENDİ: v5.0 ULTRA-OPTIMIZED - Veto sistemi kaldırıldı, scoring optimize edildi
def calculate_quality_grade(symbol: str, config: object, direction: str) -> str:
    """
    v5.0: Veto kuralları kaldırıldı. Sentiment şimdi sadece grade düşürücü, iptal edici değil.
    Eksik veri cezası azaltıldı. Grade eşikleri optimize edildi.
    
    Teknik sinyalin kalitesini (A-D) belirlemek için alfa faktörlerini (duygu, trend) analiz eder.
    """
    logger.debug(f"'{symbol}' ({direction}) için kalite notu hesaplanıyor...")

    if not sentiment_analyzer:
        logger.error("sentiment_analyzer modülü yüklenemediği için kalite hesaplanamıyor.")
        return 'C'  # Hata durumunda varsayılan

    # --- 1. Skorları Al (Doğrudan Veritabanından) ---
    try:
        sentiment_scores = sentiment_analyzer.get_sentiment_scores(symbol, config)
        fng_index = sentiment_scores.get('fng_index')
        news_sentiment = sentiment_scores.get('news_sentiment')
        reddit_sentiment = sentiment_scores.get('reddit_sentiment')
        trends_score = sentiment_scores.get('google_trends_score')
    except Exception as e:
         logger.error(f"'{symbol}' için duygu/trend skorları alınırken hata: {e}", exc_info=True)
         return 'C' # Hata durumunda 'C' dön (D değil - daha toleranslı)

    # --- 2. v5.0: VETO SİSTEMİ KALDIRILDI ---
    # Artık hiçbir sentiment değeri sinyali iptal etmez
    # Sadece grade'i düşürür veya yükseltir

    # --- 3. Ağırlıklı Skor Hesaplama ---
    # v5.0: Ağırlıklar optimize edildi
    fng_weight = 0.6        # 0.75 → 0.6 (daha az ağırlık)
    news_weight = 1.0       # 1.25 → 1.0 (daha az ağırlık)
    reddit_weight = 0.8     # 1.0 → 0.8 (daha az ağırlık)
    trends_weight = 0.4     # 0.5 → 0.4 (daha az ağırlık)
    no_info_penalty = -0.15 # v5.0: -0.5 → -0.15 (çok hafif ceza!)
    grade_score = 0.0

    # 3a. F&G Index Katkısı
    fng_contribution = 0
    if fng_index is not None:
        if direction == 'LONG':
            if fng_index < 25: fng_contribution = 1.5   # Aşırı Korku (Contrarian)
            elif fng_index < 45: fng_contribution = 0.5   # Korku
            elif fng_index > 75: fng_contribution = -1.5  # Aşırı Hırs (Riskli)
            elif fng_index > 55: fng_contribution = -0.5  # Hırs
        elif direction == 'SHORT':
            if fng_index < 25: fng_contribution = -1.5  # Aşırı Korku (Riskli)
            elif fng_index < 45: fng_contribution = -0.5  # Korku
            elif fng_index > 75: fng_contribution = 1.5   # Aşırı Hırs (Contrarian)
            elif fng_index > 55: fng_contribution = 0.5   # Hırs
        grade_score += fng_contribution * fng_weight
        logger.debug(f"F&G Index: {fng_index}, Yön: {direction}, Katkı: {fng_contribution * fng_weight:.2f}")
    else:
        logger.warning(f"'{symbol}' için F&G Index bulunamadı (DB'de yok?).")
        grade_score += no_info_penalty * fng_weight # F&G yoksa ceza

    # 3b. Haber Duygu Skoru Katkısı
    news_score_contribution = 0
    if news_sentiment is not None:
        sentiment_threshold_pos = 0.15; sentiment_strong_pos = 0.5 # Veto 0.5'te
        sentiment_threshold_neg = -0.15; sentiment_strong_neg = -0.5 # Veto -0.5'te
        if direction == 'LONG':
            # Veto zaten > 0.5'i (veya < -0.5'i) yakaladı, bu yüzden buradaki kurallar veto edilmeyenler için
            if news_sentiment > sentiment_threshold_pos: news_score_contribution = 0.75 # Pozitif
            elif news_sentiment < sentiment_threshold_neg: news_score_contribution = -1.0 # Negatif
        elif direction == 'SHORT':
            if news_sentiment > sentiment_threshold_pos: news_score_contribution = -1.0 # Pozitif
            elif news_sentiment < sentiment_threshold_neg: news_score_contribution = 0.75 # Negatif
        grade_score += news_score_contribution * news_weight
        logger.debug(f"Haber Duygusu: {news_sentiment:.3f}, Yön: {direction}, Katkı: {news_score_contribution * news_weight:.2f}")
    else:
         logger.warning(f"'{symbol}' için haber duygu skoru bulunamadı (None).")
         grade_score += no_info_penalty * news_weight
         logger.debug(f"Haber skoru yok, Ceza: {no_info_penalty * news_weight:.2f}")

    # 3c. Reddit Duygu Skoru Katkısı
    reddit_score_contribution = 0
    if reddit_sentiment is not None:
        sentiment_threshold_pos = 0.10; sentiment_strong_pos = 0.4
        sentiment_threshold_neg = -0.10; sentiment_strong_neg = -0.4
        if direction == 'LONG':
            if reddit_sentiment > sentiment_strong_pos: reddit_score_contribution = 1.0
            elif reddit_sentiment > sentiment_threshold_pos: reddit_score_contribution = 0.5
            elif reddit_sentiment < sentiment_strong_neg: reddit_score_contribution = -1.5
            elif reddit_sentiment < sentiment_threshold_neg: reddit_score_contribution = -0.75
        elif direction == 'SHORT':
            if reddit_sentiment > sentiment_strong_pos: reddit_score_contribution = -1.5
            elif reddit_sentiment > sentiment_threshold_pos: reddit_score_contribution = -0.75
            elif reddit_sentiment < sentiment_strong_neg: reddit_score_contribution = 1.0
            elif reddit_sentiment < sentiment_threshold_neg: reddit_score_contribution = 0.5
        grade_score += reddit_score_contribution * reddit_weight
        logger.debug(f"Reddit Duygusu: {reddit_sentiment:.3f}, Yön: {direction}, Katkı: {reddit_score_contribution * reddit_weight:.2f}")
    else:
        logger.warning(f"'{symbol}' için Reddit duygu skoru bulunamadı (None).")
        grade_score += no_info_penalty * reddit_weight * 0.5 # Yarım ceza
        logger.debug(f"Reddit skoru yok, Ceza: {no_info_penalty * reddit_weight * 0.5:.2f}")

    # 3d. Google Trends Skoru Katkısı
    trends_contribution = 0
    if trends_score is not None:
        if direction == 'LONG': trends_contribution = trends_score
        elif direction == 'SHORT': trends_contribution = -trends_score
        grade_score += trends_contribution * trends_weight
        logger.debug(f"Google Trends: {trends_score:.3f}, Yön: {direction}, Katkı: {trends_contribution * trends_weight:.2f}")
    else:
        logger.warning(f"'{symbol}' için Google Trends skoru bulunamadı (None).")
        grade_score += no_info_penalty * trends_weight * 0.5 # Yarım ceza
        logger.debug(f"Google Trends skoru yok, Ceza: {no_info_penalty * trends_weight * 0.5:.2f}")


    # 4. Toplam Skora Göre Harf Notu Belirleme
    # v5.0 ULTRA-OPTIMIZED: Eşikler yeniden kalibre edildi
    if grade_score >= 1.2:        # 2.0 → 1.2 (erişilebilir)
        final_grade = 'A'
    elif grade_score >= 0.0:      # 0.5 → 0.0 (daha kolay B)
        final_grade = 'B'
    elif grade_score >= -1.5:     # -1.0 → -1.5 (C daha geniş)
        final_grade = 'C'
    else:                          # < -1.5
        final_grade = 'D'
    
    logger.info(f"   '{symbol}' ({direction}) için Toplam Sentiment Skoru: {grade_score:.2f} → Kalite Notu: {final_grade}")
    logger.debug(f"   Detay: F&G={fng_index}, Haber={news_sentiment}, Reddit={reddit_sentiment}, Trends={trends_score}")
    return final_grade
    final_grade = 'C'
    if grade_score >= 3.0: final_grade = 'A'
    elif grade_score >= 1.5: final_grade = 'B'
    elif grade_score <= -2.5: final_grade = 'D'
    
    logger.info(f"'{symbol}' ({direction}) için hesaplanan kalite notu: {final_grade} (Toplam Skor: {grade_score:.2f})")
    return final_grade

# --- Test Kodu ---
if __name__ == '__main__':
     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')
     logger.info("--- alpha_analyzer.py Test Modu (DB Bağımlı) ---")

     if not sentiment_analyzer:
          logger.error("Testler çalıştırılamıyor: sentiment_analyzer modülü yüklenemedi.")
     else:
        try:
            from src import config as test_config
            from src.database.models import init_db
            logger.info("Test için src.config import edildi.")
            init_db() 
        except ImportError:
             logger.error("Test için src.config veya init_db import edilemedi! Testler çalıştırılamaz."); sys.exit(1)

        logger.info("Test: Cache güncellemesi deneniyor...")
        sentiment_analyzer.update_sentiment_cache(test_config)
        
        print("\n--- VETO TESTİ (LONG Sinyal, Aşırı Negatif Haber) ---")
        # Cache'i manuel manipüle edelim (test için)
        db = sentiment_analyzer.db_session()
        veto_cache = sentiment_analyzer.AlphaCache(key='rss_headlines', value=[{'title': 'BITCOIN IS DEAD, CRASH IMMINENT', 'published_timestamp': time.time()}])
        db.merge(veto_cache)
        db.commit()
        sentiment_analyzer.db_session.remove()
        
        grade_veto_long = calculate_quality_grade('BTCUSDT', test_config, 'LONG')
        print(f"BTC LONG (Negatif Haber Veto) için Final Kalite Notu: {grade_veto_long}") # 'D' beklenir

        print("\n--- VETO TESTİ (SHORT Sinyal, Aşırı Pozitif Reddit) ---")
        db = sentiment_analyzer.db_session()
        veto_cache_2 = sentiment_analyzer.AlphaCache(key='reddit_posts', value=[{'title': 'ETH TO $100K', 'text': 'moon moon moon', 'score': 500, 'created_utc': time.time()}])
        db.merge(veto_cache_2)
        db.commit()
        sentiment_analyzer.db_session.remove()

        grade_veto_short = calculate_quality_grade('ETHUSDT', test_config, 'SHORT')
        print(f"ETH SHORT (Pozitif Reddit Veto) için Final Kalite Notu: {grade_veto_short}") # 'D' beklenir
        
        print("\n--- Normal Skorlama Testi (BTC LONG) ---")
        grade_long_btc = calculate_quality_grade('BTCUSDT', test_config, 'LONG')
        print(f"BTC LONG (Normal) için Final Kalite Notu: {grade_long_btc}")