# 🤖 ChimeraBot - Cryptocurrency Trading Bot

**Versiyon**: 6.0 (Percentage-based SL/TP System)  
**Son Güncelleme**: 7 Kasım 2025

ChimeraBot, teknik analiz, sentiment analizi ve risk yönetimi birleştirerek Binance Futures üzerinde otomatik trading sinyalleri üreten ve yöneten bir bottur.

## ✨ Özellikler

### 🎯 Trading Sistemi
- **v6.0 Percentage-based SL/TP**: Basit %10 SL / %20-40 kademeli TP
- **8x Sabit Kaldıraç**: Dinamik kaldıraç devre dışı
- **Akıllı Pozisyon Boyutlandırma**: $5 sabit risk bazlı hesaplama
- **Çoklu Strateji**: PULLBACK, MEAN_REVERSION, BREAKOUT

### 📊 Teknik Analiz
- **TA-Lib İndikatörleri**: EMA5/20/50, SMA50/200, RSI14, MACD, ADX14, ATR14, BB
- **Multi-Timeframe**: 1D, 4H, 1H analiz
- **Regime Detection**: BTC bazlı piyasa rejim tespiti

### 🧠 Sentiment Analizi
- **Fear & Greed Index**: Alternative.me API
- **News Sentiment**: RSS feeds + Google Gemini AI analizi
- **Reddit Sentiment**: r/CryptoCurrency, r/Bitcoin vb.
- **Google Trends**: Anahtar kelime arama hacmi

### 🛡️ Risk Yönetimi
- **Maksimum Pozisyon**: 15 eşzamanlı pozisyon
- **Kalite Filtreleme**: A/B/C/D grade sistemi (D sinyaller reddedilir)
- **Korelasyon Kontrolü**: Açık pozisyonlar arası korelasyon hesabı
- **Group Risk Limitleri**: Devre dışı (agresif mod)

### 📱 Bildirimler
- **Telegram Integration**: Gerçek zamanlı sinyal ve PnL bildirimleri
- **MarkdownV2 Formatting**: Zengin format destekli mesajlar

## 🚀 Hızlı Başlangıç

### Lokal Geliştirme

```bash
# 1. Repository'yi klonlayın
git clone <your-repo-url>
cd ChimeraBot

# 2. Virtual environment oluşturun
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 4. Environment variables ayarlayın
cp .env.example .env
# .env dosyasını düzenleyin ve API key'leri ekleyin

# 5. Botu çalıştırın
python -m src.main_orchestrator
```

### Coolify Deployment

Detaylı deployment rehberi için: **[DEPLOYMENT.md](DEPLOYMENT.md)**

**Kısa özet:**
1. Coolify'da yeni Docker Compose app oluşturun
2. Repository'nizi bağlayın
3. Environment variables'ı set edin (Binance API, Telegram vb.)
4. Deploy edin!

## 📋 Gereksinimler

### API Keys (Zorunlu)
- **Binance API**: Futures Trading + Read izinleri
- **Telegram Bot**: Bot token ve chat ID

### API Keys (Opsiyonel)
- **Reddit API**: PRAW credentials (sentiment analizi için)
- **Google Gemini**: News sentiment analizi için
- **Google Trends**: Otomatik, key gerekmez

### Sistem Gereksinimleri
- **Python**: 3.11+
- **RAM**: Minimum 512MB, önerilen 1GB
- **CPU**: 1 core yeterli
- **Disk**: 1GB (logs ve database için)

## 📁 Proje Yapısı

```
ChimeraBot/
├── src/
│   ├── main_orchestrator.py      # Ana kontrol hub'ı
│   ├── config.py                  # Tüm konfigürasyon
│   ├── alpha_engine/              # Sentiment analizi
│   │   ├── sentiment_analyzer.py
│   │   └── analyzer.py
│   ├── data_fetcher/              # Binance API
│   │   ├── binance_fetcher.py
│   │   └── realtime_manager.py
│   ├── database/                  # SQLAlchemy ORM
│   │   └── models.py
│   ├── notifications/             # Telegram
│   │   └── telegram.py
│   ├── risk_manager/              # SL/TP & position sizing
│   │   ├── calculator.py
│   │   └── correlation_manager.py
│   ├── technical_analyzer/        # TA-Lib strategies
│   │   ├── indicators.py
│   │   └── strategies.py
│   ├── trade_manager/             # Position monitoring
│   │   ├── manager.py
│   │   ├── executor.py
│   │   └── capital_manager.py
│   └── utils/                     # Helpers & utilities
├── data/                          # SQLite database
├── logs/                          # Log files
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Container image
├── docker-compose.yml             # Docker orchestration
└── .env.example                   # Environment template
```

## ⚙️ Konfigürasyon

### Ana Ayarlar (`src/config.py`)

```python
# Trading
USE_PERCENTAGE_SL_TP = True           # v6.0 sistem
SL_PERCENT = 10.0                     # %10 zarar durdur
PARTIAL_TP_1_PROFIT_PERCENT = 20.0    # İlk TP %20
PARTIAL_TP_2_PROFIT_PERCENT = 40.0    # İkinci TP %40

# Leverage
FUTURES_LEVERAGE = 8                  # 8x sabit
DYNAMIC_LEVERAGE_ENABLED = False

# Risk
FIXED_RISK_USD = 5.0                  # Pozisyon başına $5 risk
MAX_OPEN_POSITIONS = 15               # Maksimum pozisyon

# Scanning
SCAN_INTERVAL_MINUTES = 10            # 10 dakikada bir tara
SCAN_DELAY_SECONDS = 2.0              # Coin arası bekleme
```

### Strateji Seçimi

Bot otomatik olarak BTC analizine göre strateji seçer:
- **PULLBACK**: Trend takip (ADX > 25 + BB expansion)
- **MEAN_REVERSION**: Range trading (ADX < 20)
- **BREAKOUT**: Volatilite patlaması (BB expansion + volume)
- **STOP**: Belirsiz piyasa (hiçbir strateji uygulanmaz)

## 🔍 Monitoring & Logs

### Log Seviyeleri
- **DEBUG**: İç state, döngü iterasyonları
- **INFO**: Büyük adımlar, onaylar
- **WARNING**: Eksik data, atlanan sinyaller
- **ERROR**: Exception'lar (exc_info=True ile)

### Telegram Bildirimleri
- ✅ Yeni pozisyon açılışı (sinyal detayları + quality grade)
- 💰 Pozisyon kapanışı (PnL USD + %)
- ⚠️ Error notifications

### Database İnceleme

```bash
# SQLite veritabanını aç
sqlite3 data/chimerabot.db

# Açık pozisyonları göster
SELECT * FROM open_positions;

# Trade history
SELECT * FROM trade_history ORDER BY close_timestamp DESC LIMIT 10;

# Sentiment cache
SELECT * FROM alpha_cache ORDER BY last_updated DESC;
```

## 🧪 Testing

```bash
# Telegram test
python test_telegram.py

# Binance connection test
python test_binance_data.py

# Percentage SL/TP test
python test_percentage_sltp.py

# 8x leverage test
python test_leverage_8x.py
```

## 🛠️ Troubleshooting

### TA-Lib Import Hatası
```bash
# macOS
brew install ta-lib
pip install TA-Lib

# Linux (Ubuntu/Debian)
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
pip install TA-Lib
```

### Database Locked Hatası
```python
# session kullanımından sonra mutlaka:
finally:
    db_session.remove()
```

### Rate Limit Aşımı
```python
# config.py'da artırın:
SCAN_DELAY_SECONDS = 3.0
SCAN_INTERVAL_MINUTES = 15
```

## 📊 Performance Metrics

### Mevcut Durum (7 Kasım 2025)
- **Bakiye**: $188.63 USDT
- **Açık Pozisyonlar**: 3 (LISTAUSDT, BIOUSDT, AVAAIUSDT)
- **Max Capacity**: 15 pozisyon (~$93.75 margin gereksinimi)
- **Risk Kullanımı**: %49.7

### Hedefler
- **Win Rate**: >60% (quality filtering ile)
- **Avg R:R**: >2.0 (percentage sistem hedefi)
- **Max Drawdown**: <20%

## 🔐 Güvenlik

1. **API Key Permissions**: Sadece Futures Trading + Read
2. **IP Whitelist**: Binance'te sunucu IP'sini whitelist'e ekleyin
3. **Environment Variables**: Asla .env dosyasını commit etmeyin
4. **Secrets Management**: Coolify encrypted storage kullanır

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

[MIT License](LICENSE) veya proje sahibinin belirlediği lisans

## 📞 Support

- **Issues**: GitHub Issues bölümünde rapor edin
- **Documentation**: [DEPLOYMENT.md](DEPLOYMENT.md), [LIVE_TRADING_GUIDE.md](LIVE_TRADING_GUIDE.md)
- **Email**: [Destek e-posta adresiniz]

## 🎯 Roadmap

- [x] v6.0 Percentage-based SL/TP
- [x] Fixed 8x leverage
- [x] Group risk limit removal
- [ ] Web dashboard (React + FastAPI)
- [ ] Backtesting engine
- [ ] Multi-exchange support (Bybit, OKX)
- [ ] Machine learning signal scoring
- [ ] Advanced portfolio optimization

---

**⚠️ Risk Uyarısı**: Kripto para ticareti yüksek risk içerir. Kaybetmeyi göze alamayacağınız parayla işlem yapmayın. Bu bot eğitim amaçlıdır ve finansal tavsiye değildir.

**Made with ❤️ by ChimeraBot Team**
