# Fibonacci Bot - Spot Dip Alım Botu

## 🎯 Proje Özeti

Fibonacci retracement seviyelerinde **kademeli alım** yapan spot kripto para botu. Düşüş yapan coinlerde Fibonacci 0.618, 0.786 ve 1.000 seviyelerinde RSI ve candlestick pattern onayıyla pozisyon açar.

## 📊 Strateji

### Fibonacci Seviyeleri
- **Swing High**: Son 90 günün en yükseği
- **Swing Low**: Swing High'dan sonraki en düşük
- **0.618 Retracement**: %20 bütçe
- **0.786 Retracement**: %35 bütçe
- **1.000 Retracement** (Swing Low): %45 bütçe

### Giriş Koşulları

#### Level 0.618 (En Muhafazakar)
- ✅ RSI < 30 (aşırı satım)
- ✅ Bullish candlestick pattern (Hammer, Doji, Dragonfly Doji, Inverted Hammer)
- ✅ Fiyat seviye civarında (±%0.5)

#### Level 0.786 (Orta Seviye)
- ✅ RSI < 35
- ✅ Fiyat seviye civarında (±%0.5)

#### Level 1.000 (Swing Low - Koşulsuz)
- ✅ Sadece fiyat seviye civarında (±%0.5)

### Çıkış Stratejisi
- **Target 1**: +%10 kar → Pozisyonun %50'sini sat
- **Target 2**: +%25 kar → Kalan %50'yi sat

### Filtreler
- ✅ 24 saat düşüş > %8
- ✅ 24 saat hacim > 1M USD
- ✅ ADX(14) < 40 (güçlü trend riski)
- ✅ Stablecoin ve leverage token değil

## 🏗️ Modüler Mimari

```
fibonacci_bot/
├── database.py           # SQLite veritabanı yönetimi
├── scanner.py            # Spot market taraması (24h losers)
├── calculator.py         # Fibonacci seviye hesaplama
├── entry_manager.py      # Giriş sinyali validasyonu (TA-Lib patterns)
├── exit_manager.py       # Çıkış stratejisi yönetimi
├── portfolio_manager.py  # Portföy risk yönetimi
├── fibonacci_bot.py      # Ana orchestrator (5 dakika döngü)
└── __init__.py           # Package tanımı
```

## 🗄️ Veritabanı Şeması

### `positions` Tablosu
- Açık/kapalı pozisyonlar
- Entry/exit fiyatları, miktar
- PnL hesaplamaları

### `fibonacci_levels` Tablosu
- Coin bazlı Fibonacci seviyeleri
- Swing High/Low tarih ve fiyatları

### `level_status` Tablosu
- Hangi seviyelerin doldurulduğu takibi

### `portfolio_summary` Tablosu
- Coin bazlı toplam pozisyonlar
- Ortalama maliyet hesabı

## 🚀 Kurulum

### 1. Gereksinimler
```bash
pip install python-binance pandas numpy talib
```

**Not**: TA-Lib kurulumu için sistem kütüphaneleri gereklidir:
```bash
# macOS
brew install ta-lib

# Ubuntu/Debian
sudo apt-get install ta-lib

# Windows
# Binary wheel: https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
```

### 2. Binance API Ayarları
`.env` dosyasına Binance API anahtarlarını ekleyin:
```env
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key
```

**Not**: Spot market için sadece okuma izinleri yeterli (bot gerçek alım yapmaz, simülasyon modunda çalışır).

### 3. Veritabanı Başlatma
```bash
cd fibonacci_bot
python database.py  # Test modu - tablo oluşturma
```

## 📖 Kullanım

### Temel Kullanım
```bash
python fibonacci_bot.py
```

### Özelleştirilmiş Parametreler
```python
from fibonacci_bot import FibonacciBot

bot = FibonacciBot(
    scan_interval_minutes=5,      # Tarama aralığı
    max_total_budget=1000.0,       # Toplam bütçe limit
    max_budget_per_coin=100.0,     # Coin başına limit
    lookback_days=90,              # Fibonacci hesaplama periyodu
    adx_threshold=40.0             # Trend filtresi
)

bot.run()
```

### Modül Bazlı Test

#### Scanner Test
```bash
python scanner.py
# Output: Top 10 düşüş yapan coin (>%8, >1M USD hacim)
```

#### Calculator Test
```bash
python calculator.py
# Output: BTCUSDT, ETHUSDT, BNBUSDT için Fibonacci seviyeleri
```

#### Entry Manager Test
```bash
python entry_manager.py
# Output: Giriş sinyali validasyonu (RSI + patterns)
```

#### Exit Manager Test
```bash
python exit_manager.py
# Output: Açık pozisyonlar için çıkış kontrolü
```

#### Portfolio Manager Test
```bash
python portfolio_manager.py
# Output: Portföy durumu ve istatistikler
```

## 🔄 Bot Döngüsü (5 Dakika)

1. **Market Taraması**: 24h düşüş yapan coinleri tespit et
2. **Fibonacci Hesaplama**: Her coin için Swing High/Low + retracement seviyeleri
3. **ADX Filtresi**: ADX > 40 olan coinleri atla
4. **Giriş Kontrolü**: Her seviye için RSI ve pattern validasyonu
5. **Risk Yönetimi**: Portföy limitleri kontrolü
6. **Pozisyon Açma**: Geçerli sinyaller için DB'ye kayıt
7. **Çıkış Kontrolü**: Açık pozisyonlarda +%10/+%25 hedefleri
8. **Kısmi Çıkış**: Target tetiklendiğinde %50 satış

## 💼 Risk Yönetimi

### Bütçe Limitleri
- **Toplam Portföy**: Max 1000 USD (varsayılan)
- **Coin Başına**: Max 100 USD (varsayılan)
- **Seviye Dağılımı**: 0.618 (%20) + 0.786 (%35) + 1.000 (%45)

### Pozisyon Kontrolü
- Coin başına maksimum bütçe aşımı kontrolü
- Toplam portföy bütçesi kontrolü
- Her giriş öncesi son risk validasyonu

## 📈 Performans Takibi

### Portföy Özeti
- Toplam pozisyon sayısı
- Toplam yatırım miktarı
- Kalan bütçe
- Bütçe kullanım oranı

### İstatistikler
- Toplam trade sayısı
- Kazanan/Kaybeden trade
- Win rate (%)
- Toplam PnL
- Ortalama kazanç/kayıp

## 🧪 Test Modu

Bot varsayılan olarak **simülasyon modunda** çalışır:
- ✅ Binance API'den gerçek veriler alır
- ✅ Fibonacci seviyeleri hesaplar
- ✅ Giriş/çıkış sinyalleri üretir
- ⚠️ Gerçek emir göndermez (sadece DB'ye kaydeder)

**Gerçek Trading**: Bot kodunda sipariş yönetimi yok. Gerçek alım için `entry_manager.py` ve `exit_manager.py`'de Binance order fonksiyonları eklenmelidir.

## 📝 Loglama

Loglar hem console'a hem dosyaya yazılır:
```
logs/fibonacci_bot.log
```

Log seviyeleri:
- **DEBUG**: İç state, hesaplamalar
- **INFO**: Döngü adımları, sinyal bildirimleri
- **WARNING**: Atlanmış coinler, yetersiz bütçe
- **ERROR**: API hataları, veritabanı sorunları

## 🔧 Teknik Detaylar

### Kullanılan Kütüphaneler
- **python-binance**: Binance API client
- **pandas**: DataFrame işlemleri
- **TA-Lib**: Teknik indikatörler ve candlestick pattern tespiti
- **SQLAlchemy**: ORM ve veritabanı yönetimi

### Candlestick Patterns (TA-Lib)
- Hammer (Çekiç)
- Inverted Hammer
- Doji
- Dragonfly Doji
- Bullish Engulfing (Yutan Mum)
- Morning Star (Sabah Yıldızı)
- Piercing Pattern (Delici Model)

### Teknik İndikatörler
- **RSI(14)**: Momentum göstergesi
- **ADX(14)**: Trend gücü filtresi

## 🚨 Uyarılar

1. **Gerçek Para Riski**: Küçük bütçe ile test edin
2. **TA-Lib Kurulumu**: Platform bazlı farklılıklar olabilir
3. **API Rate Limit**: Binance 1200 istek/dakika limiti (scanner dikkatli)
4. **ADX Filtresi**: Güçlü trenddeki coinler atlanır (risk azaltma)
5. **Partial Exit**: Database şeması mevcut, ancak kısmi satış logic basitleştirilmiş

## 🔮 Geliştirme Önerileri

- [ ] Telegram bildirimleri (pozisyon açma/kapama)
- [ ] Backtest modu (geçmiş verilerde simülasyon)
- [ ] Trailing stop (kar kilitleme)
- [ ] Kısmi çıkış için daha gelişmiş position tracking
- [ ] Multi-timeframe confirmation (4H + 1H alignment)
- [ ] Stop-loss mekanizması (şu anda sadece profit target)

## 📄 Lisans

Bu proje ChimeraBot ekosisteminin bir parçasıdır.

## 🤝 Katkıda Bulunma

Geliştirmeler için pull request açabilirsiniz:
1. Calculator iyileştirmeleri (farklı Fibonacci seviyeleri)
2. Entry manager pattern library genişletme
3. Exit stratejisi alternatifleri (trailing, time-based)
4. Risk yönetimi algoritmaları (Kelly criterion, etc.)

---

**Not**: Bu bot eğitim ve araştırma amaçlıdır. Gerçek parayla kullanmadan önce detaylı testler yapın.
