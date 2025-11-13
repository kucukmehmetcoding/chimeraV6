# 📰 Automated News Analyzer v11.7

**Otomatik Piyasa Haber Analizi - DeepSeek AI ile Market Sentiment Takibi**

## 🎯 Özellikler

### Tam Otomasyonlu Sistem
- ✅ **Bot başlatıldığında otomatik çalışır** (background thread)
- ✅ **Periyodik analizler** (varsayılan: 4 saatte bir)
- ✅ **Manuel coin seçimi YOK** - genel kripto piyasası analizi
- ✅ **Fear & Greed Index entegrasyonu**
- ✅ **DeepSeek AI ile derin sentiment analizi**
- ✅ **Telegram otomatik raporlama**

### Veri Kaynakları
**8 RSS Feed:**
1. CoinTelegraph
2. CoinDesk
3. CryptoNews
4. Bitcoin Magazine
5. CryptoSlate
6. Decrypt
7. CryptoPotato
8. U.Today

**Sentiment API:**
- Fear & Greed Index (https://api.alternative.me/fng/)

### AI Analizi
**DeepSeek Chat Model:**
- Market-wide sentiment scoring (0-100)
- Impact assessment (LOW/MEDIUM/HIGH)
- Direction prediction (BULLISH/BEARISH/NEUTRAL)
- Detailed reasoning with F&G context

---

## 🚀 Kullanım

### 1. Environment Variables (.env)
```env
# Zaten mevcut
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx

# Opsiyonel (config.py'de varsayılan değerler var)
NEWS_ANALYZER_ENABLED=True
NEWS_CHECK_INTERVAL_HOURS=4
NEWS_MAX_ARTICLES=30
```

### 2. Otomatik Başlatma
Bot'u normal şekilde başlat, news analyzer otomatik aktif olacak:

```bash
python3 src/main_orchestrator.py
```

Log çıktısı:
```
📰 Automated News Analyzer başlatılıyor...
   ✅ News Analyzer aktif (interval: 4h)
   🌐 RSS feeds: 8
   😨 Fear & Greed Index: Enabled
   🤖 AI Analysis: DeepSeek
```

### 3. Manuel Test (Bağımsız)
Tek analiz yapmak için:

```bash
python3 src/alpha_engine/coin_news_analyzer.py
```

---

## 📊 Telegram Rapor Formatı

```
📊 CRYPTO MARKET ANALYSIS REPORT

🌍 Overall Market Sentiment
📰 News Analyzed: 30 articles
⏰ Time: 2025-11-13 20:45

━━━━━━━━━━━━━━━━━━━━

📉 SENTIMENT: BEARISH
⚡ IMPACT: HIGH

📊 Market Score: 25/100
███░░░░░░░

😨 Fear & Greed Index: 15/100 (Extreme Fear)

💬 Market Analysis:
The Fear & Greed Index at 15 indicates extreme market panic, 
amplified by headlines showing Bitcoin plunging to $100K levels 
and multiple altcoins breaking key support levels...

━━━━━━━━━━━━━━━━━━━━

🤖 Analyzed by DeepSeek AI
📈 Based on 30 latest crypto news
```

---

## 🔧 Konfigürasyon

### config.py Ayarları
```python
# Master switch
NEWS_ANALYZER_ENABLED = True

# Analiz sıklığı (saat)
NEWS_CHECK_INTERVAL_HOURS = 4

# Maksimum haber sayısı
NEWS_MAX_ARTICLES = 30
```

### Analiz Döngüsü
1. **İlk Analiz:** Bot başladığında hemen çalışır
2. **Periyodik:** Her N saatte bir tekrarlar
3. **Telegram:** Her analiz sonrası otomatik rapor
4. **Cache:** DeepSeek sonuçları log'da saklanır

---

## 🧪 Test Sonuçları (13 Kasım 2025, 20:45)

### Input
- **News Count:** 30 articles
- **Fear & Greed:** 15/100 (Extreme Fear)

### DeepSeek Output
- **Sentiment:** BEARISH
- **Score:** 25/100
- **Impact:** HIGH
- **Reasoning:** "Bitcoin plunging to $100K levels, altcoin weakness, extreme panic dominates..."

### Performance
- **Fetch Time:** 3.2 seconds (30 articles from 8 feeds)
- **AI Analysis Time:** 5.3 seconds
- **Total Cycle:** ~9 seconds
- **Cost:** ~$0.001 per analysis

---

## 🛠️ Teknik Detaylar

### Background Thread
```python
# main_orchestrator.py içinde otomatik başlatılır
news_analyzer_instance = AutomatedNewsAnalyzer(
    check_interval_hours=4
)
news_analyzer_instance.start_automated_analysis()
```

### Analiz Döngüsü
```python
def _analysis_loop(self):
    # İlk analizi hemen yap
    self.run_analysis_cycle()
    
    # Interval'lerde tekrarla
    while self.running:
        time.sleep(self.check_interval)
        self.run_analysis_cycle()
```

### Graceful Shutdown
```python
# SIGINT/SIGTERM ile temiz kapanış
news_analyzer_instance.stop_automated_analysis()
```

---

## 📝 API Endpoints

### Fear & Greed Index
```python
GET https://api.alternative.me/fng/

Response:
{
  "data": [{
    "value": "15",
    "classification": "Extreme Fear",
    "timestamp": "1699996800"
  }]
}
```

### DeepSeek Chat
```python
POST https://api.deepseek.com/chat/completions

Body:
{
  "model": "deepseek-chat",
  "messages": [...],
  "temperature": 0.3,
  "max_tokens": 500
}
```

---

## 🔍 Farklar: v1.0 (Manual) vs v2.0 (Automated)

| Özellik | v1.0 (Manual) | v2.0 (Automated) |
|---------|---------------|------------------|
| **Başlatma** | `python3 coin_news_analyzer.py BTC` | Otomatik (bot ile) |
| **Hedef** | Tek coin analizi | Genel piyasa analizi |
| **Haber Filtresi** | Coin keyword'leri | Tüm kripto haberleri |
| **Fear & Greed** | ❌ Yok | ✅ Entegre |
| **Periyodik Çalışma** | ❌ Tek seferlik | ✅ N saatte bir |
| **Telegram** | Manuel çağrı | Otomatik rapor |
| **Threading** | ❌ Sync | ✅ Background daemon |
| **Integration** | Standalone | main_orchestrator.py |

---

## 🐛 Troubleshooting

### Problem: "News Analyzer başlatılamadı"
**Çözüm:**
```bash
# DEEPSEEK_API_KEY kontrolü
grep DEEPSEEK_API_KEY .env

# Manuel test
python3 src/alpha_engine/coin_news_analyzer.py
```

### Problem: "Telegram gönderim hatası"
**Çözüm:**
```bash
# TELEGRAM_BOT_TOKEN kontrolü
grep TELEGRAM_BOT_TOKEN .env

# Test
python3 test_telegram.py
```

### Problem: "Fear & Greed API timeout"
**Çözüm:**
- API geçici down olabilir
- Retry mekanizması devrede
- DeepSeek analizinde F&G olmadan devam eder

---

## 📈 Gelecek Geliştirmeler

### v11.8 Planlanan
- [ ] Historical F&G trend tracking (7-day/30-day)
- [ ] On-chain metrics integration (Glassnode/IntoTheBlock)
- [ ] Social media sentiment (Twitter/X API)
- [ ] Multi-language news support (TR/CN/JP)
- [ ] Custom alert thresholds (örn: F&G < 10 → LONG signal)

### v12.0 Roadmap
- [ ] News-based trade signals (AI + Sentiment → Auto position)
- [ ] Correlation analysis (News sentiment vs BTC price)
- [ ] Event detection (Binance listings, SEC news, etc.)
- [ ] Sentiment-based position sizing

---

## 📚 İlgili Dosyalar

- `src/alpha_engine/coin_news_analyzer.py` - Ana analyzer class
- `src/main_orchestrator.py` - Entegrasyon kodu
- `src/config.py` - Konfigürasyon ayarları
- `test_telegram.py` - Telegram test script

---

## ✅ Checklist: Deployment

- [x] DeepSeek API key configured
- [x] Telegram bot token configured
- [x] NEWS_ANALYZER_ENABLED=True
- [x] RSS feeds accessible
- [x] Fear & Greed API responsive
- [x] Background thread tested
- [x] Graceful shutdown tested
- [x] First analysis successful

---

**Versiyon:** v11.7  
**Tarih:** 13 Kasım 2025  
**Yazar:** ChimeraBot AI Team  
**Status:** ✅ Production Ready
