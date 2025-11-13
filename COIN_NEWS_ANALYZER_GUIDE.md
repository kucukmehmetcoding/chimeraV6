# 📰 COIN NEWS ANALYZER - Kullanım Kılavuzu

## 🎯 Ne İşe Yarar?

Belirli bir coin için **haberleri toplayıp DeepSeek AI ile analiz eder** ve **Telegram'a rapor gönderir**.

### Örnek Senaryo:
```
📊 ONT coin için 5 haber bulundu
🤖 DeepSeek analizi:
   - SENTIMENT: BULLISH 🚀
   - SCORE: 78/100
   - IMPACT: HIGH 🔥
   - Reasoning: "Major partnership announced with Microsoft..."
📱 Telegram'a bildirim gönderildi!
```

---

## 🚀 Hızlı Başlangıç

### 1. Tek Bir Coin İçin Analiz

```bash
cd /Users/macbook/Desktop/ChimeraBot
python3 src/alpha_engine/coin_news_analyzer.py BTC
```

Çıktı:
```
🔍 BTC için haberler aranıyor...
   📰 Bulundu: Bitcoin hits new ATH...
   📰 Bulundu: Whale accumulation...
✅ BTC için 5 haber bulundu
🤖 DeepSeek analizi geldi:
   SENTIMENT: BULLISH
   SCORE: 85/100
   IMPACT: HIGH
📱 Telegram'a gönderildi!
```

### 2. Farklı Coin'ler

```bash
# Ontology
python3 src/alpha_engine/coin_news_analyzer.py ONTUSDT

# Ethereum
python3 src/alpha_engine/coin_news_analyzer.py ETH

# Solana
python3 src/alpha_engine/coin_news_analyzer.py SOL
```

---

## 📋 Özellikler

### ✅ Yapabilecekleri:

1. **Haber Toplama**
   - 8 farklı kripto haber kaynağından tarama
   - CoinTelegraph, CoinDesk, Bitcoin Magazine, vb.
   - Coin adı geçen tüm haberleri bulma

2. **DeepSeek AI Analizi**
   - Haberlerin fiyat etkisini değerlendirme
   - BULLISH/BEARISH/NEUTRAL sentiment tespiti
   - 0-100 arası skor verme
   - HIGH/MEDIUM/LOW etki değerlendirmesi
   - 2-3 cümle ile reasoning

3. **Telegram Bildirimi**
   - Otomatik rapor gönderimi
   - Emoji'li görsel format
   - Score bar gösterimi
   - Tam analiz metni

---

## 🔧 Programatik Kullanım

### Python Kodu İçinden

```python
from alpha_engine.coin_news_analyzer import CoinNewsAnalyzer

# Analyzer oluştur
analyzer = CoinNewsAnalyzer()

# Analiz yap
report = analyzer.analyze_coin_news(
    symbol="ONTUSDT",
    max_news=5,
    send_telegram=True
)

# Sonuçları kullan
print(f"Sentiment: {report['analysis']['sentiment']}")
print(f"Score: {report['analysis']['score']}/100")
print(f"Impact: {report['analysis']['impact']}")
print(f"Reasoning: {report['analysis']['reasoning']}")
```

---

## 📊 Telegram Rapor Formatı

```
📊 COIN NEWS ANALYSIS REPORT

🪙 Coin: BTC
📰 News Found: 5 articles
⏰ Time: 2025-11-13 20:34

━━━━━━━━━━━━━━━━━━━━

🚀 SENTIMENT: BULLISH
🔥 IMPACT: HIGH

📊 Score: 85/100
████████░░

💬 Analysis:
Multiple institutions including BlackRock and MicroStrategy 
announced increased Bitcoin purchases. ETF inflows hit $1.2B 
this week, showing strong institutional demand.

━━━━━━━━━━━━━━━━━━━━

🤖 Analyzed by DeepSeek AI
```

---

## ⚙️ Konfigürasyon

### Gerekli API Keys (.env dosyası):

```env
# DeepSeek API (Zorunlu)
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# Telegram (Opsiyonel - yoksa sadece log'a yazar)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=-1001234567890
```

### Özelleştirilebilir Parametreler:

```python
# Max haber sayısı (default: 5)
analyzer.analyze_coin_news(
    symbol="BTC",
    max_news=10,  # 10 haber topla
    send_telegram=False  # Telegram'a gönderme
)

# RSS feeds ekle/çıkar
analyzer.rss_feeds.append("https://yeni-kaynak.com/rss")

# Proximity threshold değiştir
analyzer.proximity_threshold = 1.0  # %1'e çıkar
```

---

## 🛠 Gelişmiş Kullanım

### Main Bot'a Entegrasyon

```python
# main_orchestrator.py içinde

from alpha_engine.coin_news_analyzer import CoinNewsAnalyzer

# Her scan sonrası sinyal bulunan coinler için haber analizi
def analyze_signal_news(symbol):
    analyzer = CoinNewsAnalyzer()
    report = analyzer.analyze_coin_news(symbol, max_news=3)
    
    # Sentiment ile sinyal kalitesini artır
    if report['analysis']['sentiment'] == 'BULLISH':
        signal_quality += 20  # Bullish news boost
    elif report['analysis']['sentiment'] == 'BEARISH':
        signal_quality -= 20  # Bearish news penalty
    
    return signal_quality
```

### Zamanlanmış Analiz (Cronjob)

```bash
# Her 4 saatte bir BTC analizi
0 */4 * * * cd /Users/macbook/Desktop/ChimeraBot && python3 src/alpha_engine/coin_news_analyzer.py BTC >> logs/news_analyzer.log 2>&1
```

### Toplu Analiz

```bash
# Birden fazla coin için loop
for coin in BTC ETH SOL ONTUSDT LINK; do
    python3 src/alpha_engine/coin_news_analyzer.py $coin
    sleep 10  # Rate limit için bekleme
done
```

---

## 📈 DeepSeek Prompt Detayları

Sistem şu prompt'u kullanıyor:

```
You are a crypto market analyst. Analyze the following news 
articles about {SYMBOL} coin.

TASK:
Analyze how these news will affect {SYMBOL} coin price in 
the SHORT TERM (1-7 days).

Provide your analysis in this EXACT format:

SENTIMENT: [BULLISH/BEARISH/NEUTRAL]
SCORE: [0-100] (0=very bearish, 50=neutral, 100=very bullish)
IMPACT: [HIGH/MEDIUM/LOW/NONE]
REASONING: [2-3 sentences explaining why]
```

---

## 🐛 Troubleshooting

### Hata: "No news found"
- **Neden**: Coin çok yeni veya az bilinen
- **Çözüm**: Daha genel sembol kullan (ONTUSDT → ONT)

### Hata: "DeepSeek API unavailable"
- **Neden**: API key eksik veya geçersiz
- **Çözüm**: `.env` dosyasını kontrol et

### Hata: "ModuleNotFoundError"
- **Neden**: Dependencies eksik
- **Çözüm**: `pip install -r requirements.txt`

### Telegram'a göndermiyor
- **Neden**: Token/Chat ID eksik
- **Çözüm**: `.env` dosyasına ekle veya `send_telegram=False` kullan

---

## 📝 Örnek Kullanım Senaryoları

### 1. Sinyal Doğrulama
```python
# Bot sinyal verdi, haberleri kontrol et
signal = find_trading_signal("ONTUSDT")
if signal:
    news_report = analyzer.analyze_coin_news("ONTUSDT")
    
    # Sentiment uyumsuzsa uyar
    if signal['direction'] == 'LONG' and news_report['analysis']['sentiment'] == 'BEARISH':
        logger.warning("⚠️ LONG sinyali ama haberler BEARISH!")
```

### 2. Pozisyon Giriş Filtreleme
```python
# Sadece pozitif haberli coinlere gir
def should_open_position(symbol):
    news = analyzer.analyze_coin_news(symbol, send_telegram=False)
    
    if news['analysis']['score'] > 60:  # Bullish
        return True
    elif news['analysis']['score'] < 40:  # Bearish  
        return False  # Skip
    else:  # Neutral
        return True  # Technical'a bak
```

### 3. Günlük Piyasa Raporu
```python
# Top 10 coin için haber analizi
top_coins = ["BTC", "ETH", "SOL", "BNB", "ADA", "DOT", "MATIC", "LINK", "UNI", "AVAX"]

daily_report = []
for coin in top_coins:
    report = analyzer.analyze_coin_news(coin, max_news=3, send_telegram=False)
    daily_report.append({
        'symbol': coin,
        'sentiment': report['analysis']['sentiment'],
        'score': report['analysis']['score']
    })

# En bullish coin'i bul
most_bullish = max(daily_report, key=lambda x: x['score'])
print(f"🚀 Most Bullish: {most_bullish['symbol']} ({most_bullish['score']}/100)")
```

---

## 🎓 Notlar

1. **Haber Kaynakları**: RSS feed'leri güncel tutulmalı
2. **Rate Limiting**: Her feed arasında 0.5s bekleme var
3. **DeepSeek Cost**: ~$0.14/1M tokens (çok ucuz)
4. **Telegram**: Send_message hata vermeden continue eder
5. **NaN Handling**: Haber bulunamazsa NEUTRAL dönüyor

---

## 🔗 İlgili Dosyalar

- `src/alpha_engine/coin_news_analyzer.py` - Ana kod
- `src/notifications/telegram.py` - Telegram entegrasyonu
- `.env` - API keys
- `logs/chimerabot.log` - Analiz logları

---

## 💡 İleri Seviye İpuçları

1. **Custom RSS Feeds**: Kendi kaynaklarınızı ekleyebilirsiniz
2. **Sentiment Threshold**: Score'a göre auto-trade tetikleyebilirsiniz
3. **Multi-Language**: DeepSeek Türkçe de destekliyor
4. **Caching**: Aynı coin için 1 saat cache yapabilirsiniz
5. **Webhook**: Telegram yerine Discord/Slack kullanabilirsiniz

---

✅ **Sistem hazır! İyi analiz
ler!** 🚀
