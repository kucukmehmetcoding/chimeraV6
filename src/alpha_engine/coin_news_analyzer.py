"""
🔍 AUTOMATED NEWS ANALYZER
Bot başlatıldığında otomatik olarak:
1. RSS feeds'den tüm haberleri topla
2. DeepSeek ile GENEL piyasa sentiment analizi yap
3. Telegram'a piyasa durumu raporu gönder
4. Belirli aralıklarla tekrarla

Author: ChimeraBot Team
Version: 2.0.0 (AUTOMATED)
"""

import logging
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import threading

# DeepSeek API
from openai import OpenAI

# Telegram
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from notifications.telegram import send_message

logger = logging.getLogger(__name__)


class AutomatedNewsAnalyzer:
    """
    OTOMATIK haber analiz sistemi.
    
    Flow:
    1. RSS feeds'den TÜM haberleri topla (coin filtresiz)
    2. DeepSeek ile GENEL piyasa sentiment analizi yap
    3. Fear & Greed Index ekle
    4. Telegram'a kapsamlı rapor gönder
    5. Belirlenen aralıklarla tekrarla (örn: her 4 saatte)
    """
    
    def __init__(self, check_interval_hours=4):
        """
        Initialize automated news analyzer
        
        Args:
            check_interval_hours: Kaç saatte bir haber analizi yapılacak (default: 4)
        """
        self.deepseek_client = self._init_deepseek()
        self.check_interval = check_interval_hours * 3600  # Saniyeye çevir
        self.running = False
        self.thread = None
        
        # RSS News Feeds
        self.rss_feeds = [
            "https://cointelegraph.com/rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://bitcoinmagazine.com/.rss/full/",
            "https://cryptoslate.com/feed/",
            "https://decrypt.co/feed",
            "https://cryptopotato.com/feed/",
            "https://u.today/rss",
            "https://ambcrypto.com/feed/",
        ]
        
        # Fear & Greed API
        self.fg_api = "https://api.alternative.me/fng/"
        
        logger.info(f"✅ AutomatedNewsAnalyzer initialized (interval: {check_interval_hours}h)")
    
    def _init_deepseek(self) -> Optional[OpenAI]:
        """Initialize DeepSeek API client"""
        try:
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                logger.error("❌ DEEPSEEK_API_KEY bulunamadı!")
                return None
            
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
            logger.info("✅ DeepSeek client initialized")
            return client
            
        except Exception as e:
            logger.error(f"❌ DeepSeek init hatası: {e}")
            return None
    
    def fetch_all_news(self, max_news: int = 30) -> List[Dict]:
        """
        TÜM kripto haberlerini topla (filtresiz)
        
        Args:
            max_news: Maksimum haber sayısı (default: 30)
        
        Returns:
            List of news dictionaries
        """
        import feedparser
        
        all_news = []
        
        logger.info(f"🔍 Kripto piyasası haberleri toplanıyor...")
        
        for feed_url in self.rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:10]:  # Her feed'den max 10 haber
                    title = entry.get('title', '')
                    description = entry.get('description', '') or entry.get('summary', '')
                    link = entry.get('link', '')
                    published = entry.get('published', 'N/A')
                    
                    all_news.append({
                        'title': title,
                        'description': description[:300],  # İlk 300 karakter
                        'link': link,
                        'published': published,
                        'source': feed_url.split('/')[2]  # Domain name
                    })
                    
                    if len(all_news) >= max_news:
                        break
                
                if len(all_news) >= max_news:
                    break
                    
                time.sleep(0.3)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"⚠️ Feed error ({feed_url}): {e}")
                continue
        
        logger.info(f"✅ Toplam {len(all_news)} haber bulundu")
        return all_news[:max_news]
    
    def fetch_fear_greed_index(self) -> Dict:
        """
        Fear & Greed Index'i çek
        
        Returns:
            Dict with value, classification, and timestamp
        """
        try:
            response = requests.get(self.fg_api, timeout=10)
            data = response.json()
            
            if data and 'data' in data and len(data['data']) > 0:
                fg_data = data['data'][0]
                return {
                    'value': int(fg_data.get('value', 50)),
                    'classification': fg_data.get('value_classification', 'Neutral'),
                    'timestamp': fg_data.get('timestamp', 'N/A')
                }
        except Exception as e:
            logger.warning(f"⚠️ Fear & Greed API hatası: {e}")
        
        return {
            'value': 50,
            'classification': 'Neutral',
            'timestamp': 'N/A'
        }
    
    def analyze_market_with_deepseek(self, news_list: List[Dict], fg_index: Dict) -> Dict:
        """
        GENEL PİYASA haberlerini DeepSeek ile analiz et
        
        Args:
            news_list: Haber listesi
            fg_index: Fear & Greed Index data
        
        Returns:
            Analysis dict with sentiment, reasoning, score
        """
        if not self.deepseek_client:
            logger.error("❌ DeepSeek client yok!")
            return {
                'sentiment': 'UNKNOWN',
                'reasoning': 'DeepSeek API unavailable',
                'score': 0,
                'impact': 'NONE'
            }
        
        if not news_list:
            return {
                'sentiment': 'NEUTRAL',
                'reasoning': 'No news found',
                'score': 50,
                'impact': 'NONE'
            }
        
        # Haberleri formatla
        news_text = ""
        for i, news in enumerate(news_list, 1):
            news_text += f"\n{i}. [{news['source']}] {news['title']}\n"
            news_text += f"   {news['description'][:200]}...\n"
        
        # DeepSeek Prompt
        prompt = f"""You are a professional crypto market analyst. Analyze the OVERALL CRYPTO MARKET sentiment based on recent news.

**FEAR & GREED INDEX:**
Current Value: {fg_index['value']}/100 ({fg_index['classification']})

**LATEST NEWS HEADLINES:**
{news_text}

**TASK:**
Analyze the GENERAL CRYPTO MARKET sentiment for the next 1-3 days based on:
1. News headlines and narratives
2. Fear & Greed Index level
3. Overall market psychology

Provide your analysis in this EXACT format:

SENTIMENT: [BULLISH/BEARISH/NEUTRAL]
SCORE: [0-100] (0=very bearish, 50=neutral, 100=very bullish)
IMPACT: [HIGH/MEDIUM/LOW]
REASONING: [2-3 sentences explaining the overall market direction]

Focus on MARKET-WIDE sentiment, not individual coins."""

        try:
            logger.info(f"🤖 DeepSeek'e piyasa haberleri gönderiliyor...")
            
            response = self.deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are a professional crypto market analyst specializing in market-wide sentiment analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Daha tutarlı sonuçlar
                max_tokens=500,
                stream=False
            )
            
            analysis_text = response.choices[0].message.content.strip()
            logger.info(f"✅ DeepSeek analizi geldi:\n{analysis_text}")
            
            # Parse response
            result = self._parse_deepseek_response(analysis_text)
            result['raw_analysis'] = analysis_text
            result['fear_greed'] = fg_index
            
            return result
            
        except Exception as e:
            logger.error(f"❌ DeepSeek API hatası: {e}", exc_info=True)
            return {
                'sentiment': 'ERROR',
                'reasoning': f'API Error: {str(e)}',
                'score': 0,
                'impact': 'NONE',
                'raw_analysis': ''
            }
    
    def _parse_deepseek_response(self, text: str) -> Dict:
        """Parse DeepSeek response"""
        result = {
            'sentiment': 'NEUTRAL',
            'score': 50,
            'impact': 'NONE',
            'reasoning': ''
        }
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            
            if line.startswith('SENTIMENT:'):
                sentiment = line.split(':', 1)[1].strip().upper()
                result['sentiment'] = sentiment
                
            elif line.startswith('SCORE:'):
                try:
                    score_text = line.split(':', 1)[1].strip()
                    score = int(''.join(filter(str.isdigit, score_text)))
                    result['score'] = min(100, max(0, score))
                except:
                    pass
                    
            elif line.startswith('IMPACT:'):
                impact = line.split(':', 1)[1].strip().upper()
                result['impact'] = impact
                
            elif line.startswith('REASONING:'):
                reasoning = line.split(':', 1)[1].strip()
                result['reasoning'] = reasoning
        
        # Reasoning yoksa raw text'in bir kısmını al
        if not result['reasoning']:
            result['reasoning'] = ' '.join(text.split('\n')[-3:])[:200]
        
        return result
    
    def send_telegram_report(self, news_count: int, analysis: Dict) -> bool:
        """
        Telegram'a GENEL PİYASA analiz raporu gönder
        
        Args:
            news_count: Bulunan haber sayısı
            analysis: DeepSeek analizi
        
        Returns:
            Success status
        """
        
        # Emoji mapping
        sentiment_emoji = {
            'BULLISH': '🚀',
            'BEARISH': '📉',
            'NEUTRAL': '➖',
            'ERROR': '❌',
            'UNKNOWN': '❓'
        }
        
        impact_emoji = {
            'HIGH': '🔥',
            'MEDIUM': '⚡',
            'LOW': '💡',
            'NONE': '💤'
        }
        
        # Score bar
        score = analysis.get('score', 50)
        bar_length = 10
        filled = int((score / 100) * bar_length)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        # Fear & Greed
        fg = analysis.get('fear_greed', {})
        fg_value = fg.get('value', 50)
        fg_class = fg.get('classification', 'Neutral')
        
        # Mesaj oluştur
        sentiment = analysis.get('sentiment', 'NEUTRAL')
        impact = analysis.get('impact', 'MEDIUM')
        
        message = f"""
📊 **CRYPTO MARKET ANALYSIS REPORT**

🌍 **Overall Market Sentiment**
📰 **News Analyzed:** {news_count} articles
⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━

{sentiment_emoji.get(sentiment, '❓')} **SENTIMENT:** {sentiment}
{impact_emoji.get(impact, '💤')} **IMPACT:** {impact}

📊 **Market Score:** {score}/100
{bar}

😨 **Fear & Greed Index:** {fg_value}/100 ({fg_class})

💬 **Market Analysis:**
{analysis.get('reasoning', 'No reasoning provided.')}

━━━━━━━━━━━━━━━━━━━━

🤖 *Analyzed by DeepSeek AI*
📈 *Based on {news_count} latest crypto news*
"""
        
        try:
            send_message(message)
            logger.info(f"✅ Piyasa raporu Telegram'a gönderildi")
            return True
        except Exception as e:
            logger.error(f"❌ Telegram gönderim hatası: {e}")
            return False
    
    def run_analysis_cycle(self) -> Dict:
        """
        TEK BİR analiz döngüsü çalıştır
        
        Returns:
            Complete analysis report
        """
        logger.info(f"{'='*60}")
        logger.info(f"🔍 CRYPTO MARKET NEWS ANALYSIS BAŞLADI")
        logger.info(f"{'='*60}")
        
        # 1. Haberleri topla
        news_list = self.fetch_all_news(max_news=30)
        
        # 2. Fear & Greed Index'i al
        fg_index = self.fetch_fear_greed_index()
        
        # 3. DeepSeek ile analiz et
        analysis = self.analyze_market_with_deepseek(news_list, fg_index)
        
        # 4. Telegram'a gönder
        if news_list:
            self.send_telegram_report(len(news_list), analysis)
        
        # 5. Full report
        report = {
            'timestamp': datetime.now().isoformat(),
            'news_count': len(news_list),
            'news_list': news_list[:5],  # Sadece ilk 5'i kaydet
            'analysis': analysis,
            'fear_greed': fg_index
        }
        
        logger.info(f"{'='*60}")
        logger.info(f"✅ ANALIZ TAMAMLANDI")
        logger.info(f"   Sentiment: {analysis.get('sentiment')}")
        logger.info(f"   Score: {analysis.get('score')}/100")
        logger.info(f"   Impact: {analysis.get('impact')}")
        logger.info(f"   F&G: {fg_index.get('value')}/100 ({fg_index.get('classification')})")
        logger.info(f"{'='*60}")
        
        return report
    
    def start_automated_analysis(self):
        """
        OTOMATIK analiz thread'ini başlat
        Background'da sürekli çalışır
        """
        if self.running:
            logger.warning("⚠️ Automated analysis zaten çalışıyor!")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self.thread.start()
        
        logger.info(f"✅ Automated News Analysis başlatıldı (interval: {self.check_interval/3600}h)")
    
    def stop_automated_analysis(self):
        """Otomatik analizi durdur"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("🛑 Automated News Analysis durduruldu")
    
    def _analysis_loop(self):
        """Background thread loop"""
        # İlk analizi hemen yap
        try:
            self.run_analysis_cycle()
        except Exception as e:
            logger.error(f"❌ İlk analiz hatası: {e}", exc_info=True)
        
        # Sonra interval'lerde tekrarla
        while self.running:
            try:
                logger.info(f"⏳ Sonraki analiz: {self.check_interval/3600} saat sonra...")
                time.sleep(self.check_interval)
                
                if self.running:  # Tekrar kontrol et
                    self.run_analysis_cycle()
                    
            except Exception as e:
                logger.error(f"❌ Analiz döngüsü hatası: {e}", exc_info=True)
                time.sleep(60)  # Hata durumunda 1 dk bekle


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    """Test the automated analyzer"""
    import sys
    
    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
    )
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Test
    analyzer = AutomatedNewsAnalyzer(check_interval_hours=4)
    
    print(f"\n🧪 TEST: Otomatik piyasa analizi yapılıyor...\n")
    
    # Tek döngü test
    report = analyzer.run_analysis_cycle()
    
    print(f"\n{'='*60}")
    print(f"📊 FINAL REPORT:")
    print(f"{'='*60}")
    print(f"News Count: {report['news_count']}")
    print(f"Sentiment: {report['analysis']['sentiment']}")
    print(f"Score: {report['analysis']['score']}/100")
    print(f"Impact: {report['analysis']['impact']}")
    print(f"F&G Index: {report['fear_greed']['value']}/100 ({report['fear_greed']['classification']})")
    print(f"Reasoning: {report['analysis']['reasoning']}")
    print(f"{'='*60}\n")
