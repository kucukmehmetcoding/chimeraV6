# 🚀 Hızlı Başlangıç Rehberi - 15m Fast Mode

## Sistem Durumu

✅ **Binance Test Modu:** Aktif (gerçek para riski YOK)  
✅ **15m Fast Mode:** Aktif (Mehmet Küçük Stratejisi)  
✅ **Tüm Testler:** Başarılı

---

## Botu Çalıştırma

### 1. Test Script (Önerilen İlk Adım)

Sistemi test edin:

```bash
python test_fast_mode.py
```

**Beklenen Çıktı:**
- ✅ Configuration check
- ✅ 15m data fetched
- ✅ Indicators calculated
- ℹ️ Signal found veya No signal (piyasa durumuna göre)

### 2. Ana Bot'u Başlatma

```bash
python src/main_orchestrator.py
```

**Bot şunları yapacak:**
- Her 2 dakikada bir tara (SCAN_INTERVAL_MINUTES=2)
- 600 coini chunk'lara bölerek tara
- Mehmet Küçük stratejisiyle sinyal ara
- Sinyal bulunca:
  - Telegram bildirimi gönder
  - Testnet'te pozisyon aç
  - SL/TP set et

---

## Ayarları Değiştirme

### Fast Mode'u Kapatmak (Eski Sisteme Dönmek)

`.env` dosyasında:
```properties
ENABLE_15M_FAST_MODE=False
```

Bot'u yeniden başlatın.

### Parametreleri Ayarlamak

`src/config.py` dosyasında:

```python
# TP/SL yüzdelerini değiştir
FAST_MODE_TP_PERCENT = 20.0  # Varsayılan: 25.0
FAST_MODE_SL_PERCENT = 3.0   # Varsayılan: 5.0

# Kaldıraç değiştir
FAST_MODE_LEVERAGE = 15      # Varsayılan: 10

# Position size değiştir
FAST_MODE_BASE_SIZE_USD = 15.0  # Varsayılan: 10.0
```

**Not:** Bot yeniden başlatılmalı!

---

## Live Trading'e Geçiş (DİKKAT!)

### ⚠️ Önce Testnet'te Test Edin!

Minimum 1 hafta testnet'te çalıştırın:
- En az 10 sinyal izleyin
- Performansı değerlendirin
- SL/TP ayarlarını optimize edin

### Live Trading Adımları:

1. **Testnet'i Kapat**

`.env` dosyasında:
```properties
BINANCE_TESTNET=False
```

2. **Real API Keys Ekle**

`.env` dosyasında:
```properties
BINANCE_API_KEY=your_real_api_key_here
BINANCE_SECRET_KEY=your_real_secret_key_here
```

3. **Küçük Başla**

`src/config.py` dosyasında:
```python
FAST_MODE_BASE_SIZE_USD = 5.0  # Küçük başlayın!
```

4. **Bot'u Başlat**

```bash
python src/main_orchestrator.py
```

**İlk işlemde:**
- Telegram bildirimi gelecek
- Binance hesabınızda pozisyon açılacak
- SL/TP otomatik set edilecek

---

## Performans Takibi

### Telegram Bildirimleri

Her sinyal için:
- 📊 Symbol, direction, entry price
- 🎯 TP ve SL seviyeleri
- 💰 Position size ve risk
- ⭐ Quality grade

### Database Kayıtları

SQLite database: `data/chimerabot.db`

Pozisyonları görmek:
```bash
python - <<'PY'
from src.database.models import db_session, OpenPosition, TradeHistory

db = db_session()
positions = db.query(OpenPosition).all()

print(f"Açık pozisyonlar: {len(positions)}")
for p in positions:
    print(f"  {p.symbol} {p.direction} @ {p.entry_price}")

db_session.remove()
PY
```

### Logları İnceleme

```bash
tail -f logs/chimerabot.log
```

**Aranacak keyword'ler:**
- `MEHMET KÜÇÜK SIGNAL`: Yeni sinyal bulundu
- `FAST MODE Sizing`: Position size hesaplandı
- `TRADE OPENED`: Pozisyon açıldı
- `POSITION CLOSED`: Pozisyon kapandı (SL veya TP hit)

---

## Sorun Giderme

### "No signal found"

**Normal!** Mehmet Küçük stratejisi seçici:
- EMA cross olmalı
- MACD pozitif/negatif olmalı
- RSI 30-70 arası olmalı
- Volume yüksek olmalı

**Çözüm:** Sabırlı olun, sinyal gelecektir.

### "Testnet connection failed"

Testnet API keys kontrolü:
```bash
grep BINANCE_TESTNET .env
```

**Çözüm:** 
1. Binance Testnet'e giriş yapın: https://testnet.binancefuture.com/
2. API key oluşturun
3. `.env` dosyasına ekleyin

### "Insufficient margin"

Testnet hesabınızda bakiye yok.

**Çözüm:**
1. https://testnet.binancefuture.com/ adresine gidin
2. "Get Test Funds" butonuna tıklayın
3. Test USDT alın (ücretsiz!)

---

## Yararlı Komutlar

### Quick Test
```bash
python test_fast_mode.py
```

### Bot Çalıştır
```bash
python src/main_orchestrator.py
```

### Logs İzle
```bash
tail -f logs/chimerabot.log | grep "MEHMET KÜÇÜK"
```

### Performans Özeti
```bash
python profit_tracker.py
```

### Syntax Check
```bash
python -m py_compile src/main_orchestrator.py
python -m py_compile src/technical_analyzer/strategies.py
```

---

## Başarı İpuçları

1. **Sabırlı Olun:** İyi sinyaller bekler
2. **Küçük Başlayın:** Önce testnet, sonra küçük pozisyonlar
3. **Logları İzleyin:** Sistem ne yapıyor anlamak önemli
4. **Parametreleri Ayarlayın:** Backtest sonuçlarına göre optimize edin
5. **Risk Yönetimi:** Asla tüm sermayenizi tek trade'de kullanmayın

---

## Destek

- 📧 Telegram: Bot bildirimler gönderecek
- 📊 Logs: `logs/chimerabot.log`
- 🧪 Test: `test_fast_mode.py`
- 📝 Docs: `15M_FAST_MODE_IMPLEMENTATION.md`

**İyi şanslar!** 🎯🚀
