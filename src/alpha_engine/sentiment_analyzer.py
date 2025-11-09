# src/alpha_engine/sentiment_analyzer.py

import logging
import sys
import feedparser
import requests
from bs4 import BeautifulSoup
import praw
import re
import time
from typing import Dict, Any, List, Optional
import math
from datetime import datetime, timedelta, timezone 
try:
    from pytrends.request import TrendReq
    import pandas as pd
except ImportError:
    print("UYARI: 'pytrends' veya 'pandas' kütüphanesi bulunamadı...")
    TrendReq = None
    pd = None

# --- Loglama (En başta tanımla) ---
logger = logging.getLogger(__name__)

# --- Veritabanı Modellerini Import Etme ---
try:
    from src.database.models import db_session, AlphaCache, init_db, get_db_session
except ImportError as e:
    print(f"KRİTİK HATA: src/database/models.py import edilemedi! Hata: {e}")
    raise

# --- GÜNCELLENDİ: Correlation Manager'ı import et ---
try:
    from src.risk_manager import correlation_manager
except ImportError:
    logger.error("correlation_manager modülü import edilemedi!")
    correlation_manager = None

# --- VADER Başlatma (Opsiyonel) ---
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    analyzer = SentimentIntensityAnalyzer()
    logger.info("✅ VADER sentiment analyzer yüklendi")
except ImportError:
    logger.warning("⚠️ vaderSentiment paketi bulunamadı - Reddit sentiment analizi devre dışı")
    analyzer = None
except Exception as e:
    logger.warning(f"⚠️ VADER başlatılamadı: {e}")
    analyzer = None

# --- Reddit İstemcisini Başlatma (Global) ---
reddit_client: Optional[praw.Reddit] = None

def initialize_reddit_client(config: object) -> bool:
    # ... (Bu fonksiyonun içeriği aynı, değişiklik yok) ...
    global reddit_client
    if reddit_client: return True
    client_id = getattr(config, 'REDDIT_CLIENT_ID', None)
    client_secret = getattr(config, 'REDDIT_CLIENT_SECRET', None)
    username = getattr(config, 'REDDIT_USERNAME', None)
    password = getattr(config, 'REDDIT_PASSWORD', None)
    user_agent = getattr(config, 'REDDIT_USER_AGENT', None)
    if not all([client_id, client_secret, username, password, user_agent]):
        logger.warning("⚠️ Reddit API bilgileri eksik. Reddit entegrasyonu çalışmayacak.")
        return False
    try:
        logger.info("⏳ Reddit API istemcisi (PRAW) başlatılıyor...")
        reddit_client = praw.Reddit(
            client_id=client_id, client_secret=client_secret,
            username=username, password=password, user_agent=user_agent,
            check_for_async=False
        )
        user_info = reddit_client.user.me()
        logger.info(f"✅ Reddit API istemcisi başarıyla başlatıldı ve '{user_info.name}' olarak bağlandı.")
        return True
    except praw.exceptions.PrawcoreException as e:
        logger.error(f"❌ Reddit API kimlik doğrulaması başarısız! Hata: {e}")
        reddit_client = None; return False
    except Exception as e:
        logger.error(f"❌ Reddit API istemcisi başlatılırken beklenmedik hata: {e}", exc_info=True)
        reddit_client = None; return False

# --- Cache Anahtarları (DB'deki 'key' sütunu için) ---
FNG_INDEX_KEY = "fng_index"
RSS_HEADLINES_KEY = "rss_headlines"
REDDIT_POSTS_KEY = "reddit_posts"
GOOGLE_TRENDS_DATA_KEY = "google_trends_data"
CORRELATION_MATRIX_KEY = "correlation_matrix"  # GÜNCELLENDİ: Yeni eklenen
# Not: _LAST_UPDATE anahtarlarına artık gerek yok, DB'deki 'last_updated' sütununu kullanacağız

# --- Veri Çekme Fonksiyonları (İçerikleri Aynı, Değişiklik Yok) ---

def fetch_fear_and_greed_index() -> Optional[int]:
    # ... (Kod aynı, değişiklik yok) ...
    logger.info("Fear & Greed Index çekiliyor...")
    url = "https://alternative.me/crypto/fear-and-greed-index/"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15); response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        index_circle = soup.find('div', class_=lambda x: x and x.startswith('fng-circle'))
        if index_circle: index_text = index_circle.text.strip()
        else: logger.error("F&G Index değeri sayfada bulunamadı."); return None
        if index_text.isdigit(): index_value = int(index_text); logger.info(f"✅ F&G Index: {index_value}"); return index_value
        else: logger.error(f"F&G Index değeri sayısal değil: '{index_text}'"); return None
    except Exception as e: logger.error(f"F&G Index çekme hatası: {e}", exc_info=True); return None

def fetch_rss_feeds(rss_urls: list) -> List[Dict[str, Any]]:
    # ... (Kod aynı, değişiklik yok) ...
    if not rss_urls: logger.warning("Config'de RSS feed URL'si yok."); return []
    logger.info(f"{len(rss_urls)} RSS feed'den haberler çekiliyor...")
    all_headlines = []; processed_links = set()
    for url in rss_urls:
        try:
            feed_data = feedparser.parse(url, agent='Mozilla/5.0')
            if feed_data.bozo: logger.warning(f"RSS ({url}) parse sorunu: {getattr(feed_data, 'bozo_exception', 'Bilinmeyen')}")
            source_name = getattr(feed_data.feed, 'title', url)
            for entry in feed_data.entries:
                link = getattr(entry, 'link', None); title = getattr(entry, 'title', None)
                if not link or link in processed_links or not title: continue
                processed_links.add(link)
                published_time_struct = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
                published_timestamp = time.mktime(published_time_struct) if published_time_struct else None
                all_headlines.append({'title': title, 'link': link, 'published_timestamp': published_timestamp, 'source': source_name})
        except Exception as e: logger.error(f"RSS feed ({url}) işlenirken hata: {e}", exc_info=True)
    all_headlines.sort(key=lambda x: x.get('published_timestamp') or float('-inf'), reverse=True)
    logger.info(f"✅ {len(all_headlines)} benzersiz haber başlığı çekildi.")
    return all_headlines

def fetch_reddit_data(config: object) -> List[Dict[str, Any]]:
    # ... (Kod aynı, değişiklik yok) ...
    global reddit_client
    if not reddit_client and not initialize_reddit_client(config): return []
    subreddits = getattr(config, 'SENTIMENT_REDDIT_SUBREDDITS', [])
    limit = getattr(config, 'REDDIT_POST_LIMIT_PER_SUB', 25)
    if not subreddits: logger.warning("Config'de Reddit subredditi yok."); return []
    logger.info(f"{len(subreddits)} subredditten gönderi çekiliyor (max {limit} adet)...")
    all_posts = []; processed_ids = set()
    try:
        for name in subreddits:
            try:
                subreddit = reddit_client.subreddit(name)
                for sub in subreddit.new(limit=limit):
                    if sub.stickied or sub.id in processed_ids: continue
                    processed_ids.add(sub.id)
                    all_posts.append({'id': sub.id, 'title': sub.title, 'text': sub.selftext, 'score': sub.score,
                                     'created_utc': sub.created_utc, 'subreddit': name, 'url': sub.permalink})
            except Exception as e_sub: logger.error(f"'{name}' işlenirken hata: {e_sub}", exc_info=True)
        all_posts.sort(key=lambda x: x.get('created_utc', 0), reverse=True)
        logger.info(f"✅ Toplam {len(all_posts)} Reddit gönderisi çekildi.")
        return all_posts
    except Exception as e: logger.error(f"Reddit verisi çekilirken hata: {e}", exc_info=True); return []

def fetch_google_trends(keywords: list, timeframe: str = 'now 7-d') -> Optional[pd.DataFrame]:
    # ... (Kod aynı, değişiklik yok) ...
    if TrendReq is None or pd is None: logger.error("Google Trends için 'pytrends'/'pandas' eksik."); return None
    if not keywords: logger.warning("Google Trends için anahtar kelime yok."); return None
    keywords_to_fetch = keywords[:5]
    logger.info(f"Google Trends verisi çekiliyor (Kelimeler: {keywords_to_fetch}, Zaman: {timeframe})...")
    try:
        pytrends = TrendReq(hl='en-US', tz=360, timeout=20)
        pytrends.build_payload(kw_list=keywords_to_fetch, cat=0, timeframe=timeframe, geo='', gprop='')
        df = pytrends.interest_over_time()
        if df.empty: logger.warning(f"Google Trends'ten '{keywords_to_fetch}' için veri bulunamadı."); return None
        if 'isPartial' in df.columns:
            try:
                if df['isPartial'].astype(bool).iloc[-1]: logger.warning("   Google Trends verisi 'isPartial=True'.")
            except Exception: pass
            df = df.drop(columns=['isPartial'])
        logger.info(f"✅ Google Trends verisi ({len(df)} satır) çekildi.")
        return df
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str: logger.warning("   Google Trends rate limit hatası.")
        elif "400" in error_str: logger.warning(f"   Google Trends geçersiz istek (400): {keywords_to_fetch}")
        else: logger.error(f"Google Trends hatası: {e}", exc_info=False)
        return None

# --- Analiz Fonksiyonları (İçerikleri Aynı, Değişiklik Yok) ---

def analyze_sentiment_vader(text: str) -> float:
    # ... (Kod aynı, değişiklik yok) ...
    if not analyzer: logger.error("VADER başlatılmadı."); return 0.0
    if not isinstance(text, str) or not text.strip(): return 0.0
    try: return analyzer.polarity_scores(text)['compound']
    except Exception: return 0.0 # Hata durumunda 0 dön

def _get_search_terms(symbol: str, config: object) -> set:
    # ... (Kod aynı, değişiklik yok) ...
    symbol_keywords_map = getattr(config, 'SENTIMENT_SYMBOL_KEYWORDS', {})
    base_symbol = symbol.replace('USDT', '').lower()
    return set(symbol_keywords_map.get(base_symbol, [base_symbol]))

def calculate_news_sentiment_for_symbol(symbol: str, headlines: list, config: object) -> Optional[float]:
    # ... (Kod aynı, değişiklik yok) ...
    relevant_scores = []
    current_time = time.time(); lookback_hours = getattr(config, 'SENTIMENT_NEWS_LOOKBACK_HOURS', 24)
    lookback_seconds = lookback_hours * 3600; search_terms = _get_search_terms(symbol, config)
    if not headlines: return None
    for h in headlines:
        ts = h.get('published_timestamp'); title = h.get('title')
        if ts is None or (current_time - ts > lookback_seconds) or not title: continue
        title_lower = title.lower()
        try:
             if any(re.search(r'\b' + re.escape(term) + r'\b', title_lower) for term in search_terms):
                 relevant_scores.append(analyze_sentiment_vader(title))
        except Exception: # Regex hatası olursa
             if any(term in title_lower for term in search_terms):
                  relevant_scores.append(analyze_sentiment_vader(title))
    if not relevant_scores: logger.info(f"'{symbol}' için son {lookback_hours}s ilgili haber yok."); return None
    avg_score = sum(relevant_scores) / len(relevant_scores)
    logger.info(f"'{symbol}' için {len(relevant_scores)} haberin ort. duygu skoru: {avg_score:.3f}")
    return avg_score

def calculate_reddit_sentiment_for_symbol(symbol: str, reddit_posts: list, config: object) -> Optional[float]:
    # ... (Kod aynı, değişiklik yok) ...
    relevant = []
    current_time = time.time(); lookback_hours = getattr(config, 'SENTIMENT_NEWS_LOOKBACK_HOURS', 24)
    lookback_seconds = lookback_hours * 3600; search_terms = _get_search_terms(symbol, config)
    if not reddit_posts: return None
    min_score = getattr(config, 'REDDIT_MIN_POST_SCORE', 1)
    for post in reddit_posts:
        ts = post.get('created_utc'); score = post.get('score', 0)
        if ts is None or (current_time - ts > lookback_seconds) or score < min_score: continue
        title = post.get('title', ''); text = post.get('text', '')
        combined = (title + " " + text).lower()
        if not combined.strip(): continue
        try:
            if any(re.search(r'\b' + re.escape(term) + r'\b', combined) for term in search_terms):
                sentiment = analyze_sentiment_vader(title + " " + text)
                weight = math.log(max(1, score)) + 1
                relevant.append((sentiment, weight))
        except Exception: # Regex hatası
             if any(term in combined for term in search_terms):
                 sentiment = analyze_sentiment_vader(title + " " + text)
                 weight = math.log(max(1, score)) + 1
                 relevant.append((sentiment, weight))
    if not relevant: logger.info(f"'{symbol}' için son {lookback_hours}s ilgili Reddit gönderisi yok."); return None
    total_w_score = sum(s * w for s, w in relevant); total_weight = sum(w for _, w in relevant)
    if total_weight == 0: return 0.0
    avg_score = total_w_score / total_weight
    logger.info(f"'{symbol}' için {len(relevant)} Reddit gönderisinin ağ.ort. duygu skoru: {avg_score:.3f}")
    return avg_score

def calculate_trends_score(symbol: str, trends_data: Optional[pd.DataFrame], config: object) -> Optional[float]:
    # ... (Kod aynı, değişiklik yok) ...
    if pd is None: return None
    if trends_data is None or trends_data.empty: return None
    search_terms = _get_search_terms(symbol, config); keyword_col = None
    possible_keywords = [term.capitalize() for term in search_terms] + list(search_terms)
    available_cols = trends_data.columns
    for kw in possible_keywords:
        if kw in available_cols: keyword_col = kw; break
    if not keyword_col: logger.warning(f"'{symbol}' ({possible_keywords}) Trends verisinde bulunamadı. Sütunlar: {list(available_cols)}"); return None
    try:
        if not isinstance(trends_data.index, pd.DatetimeIndex): trends_data.index = pd.to_datetime(trends_data.index)
        series = trends_data[keyword_col]; recent_data = series.last('3D')
        if len(recent_data) < 2 or len(series) < 5 or recent_data.isna().any() or series.isna().any(): return None
        recent_mean = recent_data.mean(); overall_mean = series.mean()
        if pd.isna(recent_mean) or pd.isna(overall_mean) or overall_mean == 0: return 0.0
        relative_change = (recent_mean - overall_mean) / overall_mean
        trend_score = max(-1.0, min(1.0, relative_change * 2.0))
        logger.info(f"'{symbol}' ({keyword_col}) için Google Trends skoru: {trend_score:.3f} (Son 3gOrt:{recent_mean:.1f}, TümOrt:{overall_mean:.1f})")
        return trend_score
    except Exception as e: logger.error(f"'{symbol}' ({keyword_col}) için Trends skoru hesaplanırken hata: {e}", exc_info=True); return None


# --- GÜNCELLENMİŞ: Veritabanı Kullanan Cache Fonksiyonları ---

def update_sentiment_cache(config: object) -> bool:
    """
    Gerekliyse F&G, RSS, Reddit, Google Trends VE KORELASYON verilerini
    çekip veritabanındaki AlphaCache tablosunu günceller.
    """
    now_utc = datetime.now(timezone.utc)
    cache_updated = False
    db = db_session()
    
    try:
        # --- 1. Fear & Greed Index Güncelleme ---
        fng_interval = timedelta(seconds=getattr(config, 'SENTIMENT_FNG_UPDATE_INTERVAL_SECONDS', 3600))
        fng_record = db.query(AlphaCache).filter_by(key=FNG_INDEX_KEY).first()
        
        # Zaman karşılaştırması için timezone uyumluluğu sağla
        if fng_record and fng_record.last_updated:
            # SQLite'tan gelen datetime timezone-naive olabilir, UTC olarak işaretle
            last_updated = fng_record.last_updated if fng_record.last_updated.tzinfo else fng_record.last_updated.replace(tzinfo=timezone.utc)
        else:
            last_updated = None
        
        if not fng_record or not last_updated or (now_utc - last_updated) > fng_interval:
            logger.info("F&G güncelleniyor...")
            fng_value = fetch_fear_and_greed_index()
            if fng_value is not None:
                if not fng_record: fng_record = AlphaCache(key=FNG_INDEX_KEY)
                fng_record.value = fng_value # JSON tipine int atamak sorunsuz olmalı
                fng_record.last_updated = now_utc
                db.merge(fng_record) # Insert or Update
                cache_updated = True
                logger.info(f"✅ F&G Index cache'e kaydedildi: {fng_value}")
            else:
                logger.error("F&G Index güncellenemedi.")
                # Hata durumunda da zaman damgasını güncelleyebiliriz (sürekli denememek için)
                if fng_record: fng_record.last_updated = now_utc; db.merge(fng_record)

        # --- 2. RSS Haberlerini Güncelleme ---
        rss_interval = timedelta(seconds=getattr(config, 'SENTIMENT_RSS_UPDATE_INTERVAL_SECONDS', 600)) # 10dk
        rss_record = db.query(AlphaCache).filter_by(key=RSS_HEADLINES_KEY).first()
        rss_urls = getattr(config, 'SENTIMENT_RSS_FEEDS', [])
        
        # Timezone uyumluluğunu sağla
        if rss_record and rss_record.last_updated:
            rss_last_updated = rss_record.last_updated if rss_record.last_updated.tzinfo else rss_record.last_updated.replace(tzinfo=timezone.utc)
        else:
            rss_last_updated = None
        
        if rss_urls and (not rss_record or not rss_last_updated or (now_utc - rss_last_updated) > rss_interval):
            logger.info("RSS güncelleniyor..."); new_headlines = fetch_rss_feeds(rss_urls)
            if new_headlines:
                max_headlines = getattr(config, 'MAX_HEADLINES_IN_CACHE', 1000)
                if not rss_record: rss_record = AlphaCache(key=RSS_HEADLINES_KEY)
                rss_record.value = new_headlines[:max_headlines]
                rss_record.last_updated = now_utc
                db.merge(rss_record); cache_updated = True
            else:
                logger.warning("Yeni RSS haberi yok."); 
                if rss_record: rss_record.last_updated = now_utc; db.merge(rss_record)

        # --- 3. Reddit Verilerini Güncelleme ---
        reddit_interval = timedelta(seconds=getattr(config, 'SENTIMENT_REDDIT_UPDATE_INTERVAL_SECONDS', 600)) # 10dk
        reddit_record = db.query(AlphaCache).filter_by(key=REDDIT_POSTS_KEY).first()
        
        # Timezone uyumluluğunu sağla
        if reddit_record and reddit_record.last_updated:
            reddit_last_updated = reddit_record.last_updated if reddit_record.last_updated.tzinfo else reddit_record.last_updated.replace(tzinfo=timezone.utc)
        else:
            reddit_last_updated = None
        
        if (reddit_client or initialize_reddit_client(config)) and (not reddit_record or not reddit_last_updated or (now_utc - reddit_last_updated) > reddit_interval):
            logger.info("Reddit güncelleniyor..."); new_posts = fetch_reddit_data(config)
            if new_posts:
                max_posts = getattr(config, 'MAX_REDDIT_POSTS_IN_CACHE', 500)
                if not reddit_record: reddit_record = AlphaCache(key=REDDIT_POSTS_KEY)
                reddit_record.value = new_posts[:max_posts]
                reddit_record.last_updated = now_utc
                db.merge(reddit_record); cache_updated = True
            else:
                logger.warning("Yeni Reddit gönderisi yok."); 
                if reddit_record: reddit_record.last_updated = now_utc; db.merge(reddit_record)

        # --- 4. Google Trends Güncelleme ---
        trends_interval = timedelta(seconds=getattr(config, 'SENTIMENT_TRENDS_UPDATE_INTERVAL_SECONDS', 3600*4))
        trends_record = db.query(AlphaCache).filter_by(key=GOOGLE_TRENDS_DATA_KEY).first()
        keywords = getattr(config, 'SENTIMENT_GOOGLE_TRENDS_KEYWORDS', [])
        
        # Timezone uyumluluğunu sağla
        if trends_record and trends_record.last_updated:
            trends_last_updated = trends_record.last_updated if trends_record.last_updated.tzinfo else trends_record.last_updated.replace(tzinfo=timezone.utc)
        else:
            trends_last_updated = None
        
        if TrendReq is not None and keywords and (not trends_record or not trends_last_updated or (now_utc - trends_last_updated) > trends_interval):
             logger.info("Google Trends güncelleniyor..."); df_trends = fetch_google_trends(keywords[:5], timeframe='now 7-d')
             if df_trends is not None:
                 try:
                      trends_dict = df_trends.reset_index()
                      trends_dict['date'] = trends_dict['date'].dt.strftime('%Y-%m-%d %H:%M:%S') # String'e çevir
                      trends_dict = trends_dict.to_dict(orient='list')
                      if not trends_record: trends_record = AlphaCache(key=GOOGLE_TRENDS_DATA_KEY)
                      trends_record.value = trends_dict
                      trends_record.last_updated = now_utc
                      db.merge(trends_record)
                      cache_updated = True
                      logger.info("✅ Google Trends verisi cache'e yazıldı.")
                 except Exception as e_cache:
                      logger.error(f"Trends verisi cache'e yazılırken hata: {e_cache}");
                      if trends_record: trends_record.last_updated = now_utc; db.merge(trends_record)
             else:
                 logger.warning("Yeni Google Trends verisi çekilemedi."); 
                 if trends_record: trends_record.last_updated = now_utc; db.merge(trends_record)

        # --- 5. KORELASYON MATRİSİ GÜNCELLEME (YENİ) ---
        corr_interval = timedelta(seconds=getattr(config, 'CORRELATION_UPDATE_INTERVAL_SECONDS', 3600*24))
        corr_record = db.query(AlphaCache).filter_by(key=CORRELATION_MATRIX_KEY).first()
        
        if correlation_manager and (not corr_record or (corr_record.last_updated is None) or \
           (now_utc - corr_record.last_updated.replace(tzinfo=timezone.utc)) > corr_interval):
            logger.info("Korelasyon Matrisi güncelleniyor (Bu işlem zaman alabilir)...")
            # Taranacak tüm coinlerin listesini al
            all_symbols = list(getattr(config, 'CORRELATION_GROUPS', {}).keys())
            if all_symbols:
                matrix_df = correlation_manager.calculate_correlation_matrix(
                    all_symbols,
                    days=getattr(config, 'CORRELATION_CALCULATION_DAYS', 30)
                )
                if matrix_df is not None:
                    try:
                        # DataFrame'i JSON'a çevir (dict formatında)
                        matrix_dict = matrix_df.to_dict()
                        if not corr_record: corr_record = AlphaCache(key=CORRELATION_MATRIX_KEY)
                        corr_record.value = matrix_dict
                        corr_record.last_updated = now_utc
                        db.merge(corr_record); cache_updated = True
                        logger.info("✅ Korelasyon Matrisi başarıyla hesaplandı ve cache'e yazıldı.")
                    except Exception as e_cache_corr:
                        logger.error(f"Korelasyon Matrisi cache'e yazılırken hata: {e_cache_corr}")
                        if corr_record: corr_record.last_updated = now_utc; db.merge(corr_record)
                else:
                    logger.error("Korelasyon Matrisi hesaplanamadı.")
                    if corr_record: corr_record.last_updated = now_utc; db.merge(corr_record)
            else:
                 logger.warning("Korelasyon hesaplaması için 'CORRELATION_GROUPS' config'de boş.")

        # --- Güncellemeleri Kaydet ---
        if cache_updated:
            db.commit()
            logger.info("Alfa Cache (ve Korelasyon Matrisi) veritabanına kaydedildi.")
        else:
            db.rollback() 
            logger.info("Duygu/Korelasyon verileri güncel, veritabanı güncellemesi atlandı.")

    except Exception as e:
        logger.error(f"Cache güncelleme sırasında veritabanı hatası: {e}", exc_info=True)
        db.rollback()
        return False
    finally:
        db_session.remove()
        
    return cache_updated

def get_sentiment_scores(symbol: str, config: object) -> Dict[str, Optional[float]]:
    """
    Verilen sembol için tüm duygu/trend skorlarını veritabanından alır/hesaplar.
    Artık 'alpha_cache' sözlüğünü parametre olarak almaz.
    """
    db = db_session()
    scores = {'fng_index': None, 'news_sentiment': None, 'reddit_sentiment': None, 'google_trends_score': None}
    
    try:
        # F&G Index Al
        fng_record = db.query(AlphaCache.value).filter(AlphaCache.key == FNG_INDEX_KEY).first()
        if fng_record: scores['fng_index'] = fng_record[0] # .value

        # Haberleri Al ve Hesapla
        headlines_record = db.query(AlphaCache.value).filter(AlphaCache.key == RSS_HEADLINES_KEY).first()
        headlines = headlines_record[0] if headlines_record else []
        scores['news_sentiment'] = calculate_news_sentiment_for_symbol(symbol, headlines, config)

        # Reddit Gönderilerini Al ve Hesapla
        reddit_record = db.query(AlphaCache.value).filter(AlphaCache.key == REDDIT_POSTS_KEY).first()
        reddit_posts = reddit_record[0] if reddit_record else []
        scores['reddit_sentiment'] = calculate_reddit_sentiment_for_symbol(symbol, reddit_posts, config)

        # Google Trends Verisini Al ve Hesapla
        trends_df = None
        trends_data_dict = db.query(AlphaCache.value).filter(AlphaCache.key == GOOGLE_TRENDS_DATA_KEY).first()
        if pd is not None and trends_data_dict:
             try:
                 trends_data_dict = trends_data_dict[0] # Kaydın kendisi (.value)
                 trends_df = pd.DataFrame(trends_data_dict)
                 if 'date' in trends_df.columns:
                     trends_df['date'] = pd.to_datetime(trends_df['date'])
                     trends_df = trends_df.set_index('date')
             except Exception as e_df:
                 logger.error(f"Cache'deki Trends verisi DataFrame'e çevrilemedi: {e_df}")
        scores['google_trends_score'] = calculate_trends_score(symbol, trends_df, config)

    except Exception as e:
         logger.error(f"Duygu skorları DB'den alınırken hata: {e}", exc_info=True)
    finally:
        db_session.remove() # Session'ı kapat
        
    return scores


# --- Test Kodu (Güncellendi) ---
if __name__ == '__main__':
    # Test için loglamayı aç
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')
    logger.info("--- sentiment_analyzer.py Test Modu (Veritabanı ile) ---")

    try:
        from src import config as test_config
        logger.info("Test için src.config import edildi.")
        # Test çalıştırmadan önce veritabanı tablolarının var olduğundan emin ol
        print("Veritabanı tabloları kontrol ediliyor...")
        init_db() 
    except ImportError:
        logger.error("Test için src.config import edilemedi! Testler çalıştırılamaz."); sys.exit(1)

    print("\n--- Cache Güncelleme Testi (DB) ---")
    # Cache'i güncellemeye zorlamak için DB'deki zaman damgalarını sıfırlamamız gerekebilir,
    # şimdilik sadece update fonksiyonunu çağırıyoruz.
    updated = update_sentiment_cache(test_config)
    print(f"Cache güncellendi mi? {updated}")

    print("\n--- Skor Alma Testi (DB) ---")
    btc_scores = get_sentiment_scores('BTCUSDT', test_config)
    print(f"BTC Genel Skorları: {btc_scores}")
    
    eth_scores = get_sentiment_scores('ETHUSDT', test_config)
    print(f"ETH Genel Skorları: {eth_scores}")

    print("\n--- Test Tamamlandı ---")