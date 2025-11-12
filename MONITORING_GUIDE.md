# 📊 ChimeraBot Pozisyon İzleme Araçları

## 🎯 Amaç
ChimeraBot'un açtığı pozisyonları, gerçek zamanlı kar/zarar durumunu ve trade geçmişini izlemek için araçlar.

## 🛠️ Kullanılabilir Araçlar

### 1️⃣ **monitor_positions.py** - Detaylı Snapshot
Tek seferlik detaylı pozisyon raporu

```bash
python3 monitor_positions.py
```

**Gösterdiği Bilgiler:**
- ✅ Açık pozisyonlar (gerçek zamanlı fiyat ile)
- 📊 Her pozisyonun PnL'i (USD ve %)
- 📈 Toplam istatistikler
- 📜 Son 10 trade detayı
- ⚖️ Profit Factor, Win Rate, Average Win/Loss

---

### 2️⃣ **live_monitor.py** - Canlı İzleme
5 saniyede bir otomatik güncellenen live dashboard

```bash
python3 live_monitor.py
```

**Özellikler:**
- 🔄 Her 5 saniyede otomatik yenileme
- 💰 Gerçek zamanlı PnL hesaplama
- 🎯 Net toplam kar/zarar (açık + kapalı)
- 📊 Live trade istatistikleri
- ⌨️ Ctrl+C ile çıkış

---

## 📋 Gösterilen Bilgiler

### Açık Pozisyonlar
```
Symbol      Direction  Entry      Current    PnL        SL/TP      
BTCUSDT     LONG      $89,500    $90,200    +$140 (+1.56%)
ETHUSDT     SHORT     $3,200     $3,180     +$80 (+1.25%)
```

### Trade İstatistikleri
```
💰 Gerçekleşen Toplam PnL: $-7.20
📊 Toplam Trade: 6 (✅ 1 | ❌ 5)
🎯 Win Rate: 16.7%
📈 Ortalama Kazanç: $0.70
📉 Ortalama Kayıp: $1.58
⚖️ Profit Factor: 0.09
```

### Kapalı Trade'ler
```
Status  Symbol    Dir    Entry     Exit      PnL      Reason
✅      BANKUSDT  SHORT  $0.0840   $0.0834   $0.70    TP_HIT
❌      LAUSDT    SHORT  $0.4186   $0.4336   -$3.58   SL_HIT
```

---

## 🔍 Veritabanı Sorgulama

### Manuel DB Kontrolü
```python
from src.database.models import db_session, OpenPosition, TradeHistory

db = db_session()

# Açık pozisyonlar
positions = db.query(OpenPosition).all()
for p in positions:
    print(f"{p.symbol} - {p.direction} @ ${p.entry_price}")

# Son 10 trade
trades = db.query(TradeHistory).order_by(
    TradeHistory.close_time.desc()
).limit(10).all()

db_session.remove()
```

---

## ⚙️ Gereksinimler

```bash
pip install tabulate  # Tablo görselleştirme için
```

Diğer gereksinimler zaten `requirements.txt`'te mevcut.

---

## 🚀 Hızlı Başlangıç

```bash
# 1. Detaylı rapor al
python3 monitor_positions.py

# 2. Live izleme başlat (arka planda)
python3 live_monitor.py &

# 3. Bot çalışırken başka terminal'de izle
python3 live_monitor.py
```

---

## 📊 Örnek Çıktı

```
====================================================================
📊 CHIMERABOT LIVE MONITOR - 2025-11-11 22:26:05
====================================================================

🔴 AÇIK POZİSYONLAR: 2
--------------------------------------------------------------------

1. BTCUSDT - LONG 3x
   Entry: $89,500.0000 → Current: $90,200.0000
   🟢 PnL: $156.82 (+2.34%)
   SL: $88,900.0000 | TP: $91,500.0000

2. ETHUSDT - SHORT 2x
   Entry: $3,200.0000 → Current: $3,180.0000
   🟢 PnL: $62.50 (+1.25%)
   SL: $3,250.0000 | TP: $3,100.0000

💵 Toplam Gerçekleşmemiş PnL: $219.32

📈 GENEL İSTATİSTİKLER
--------------------------------------------------------------------
💰 Gerçekleşen Toplam PnL: $-7.20
📊 Toplam Trade: 8 (✅ 3 | ❌ 5)
🎯 Win Rate: 37.5%

💎 NET TOPLAM PnL: $212.12

====================================================================
⏱️  Sonraki güncelleme 5 saniye sonra... (Ctrl+C ile çıkış)
====================================================================
```

---

## 🔧 Sorun Giderme

### Timestamp Hataları
Eğer tarihler 1970 yılında görünüyorsa:
```python
# Timestamp milisaniye cinsinden olmalı
open_timestamp = pos.open_time / 1000 if pos.open_time > 1000000000000 else pos.open_time
```

### Fiyat Alamama
Binance API bağlantısı kontrol edin:
```bash
# .env dosyasını kontrol et
cat .env | grep BINANCE

# Test bağlantısı
python3 -c "from src.data_fetcher.binance_fetcher import get_current_price; print(get_current_price('BTCUSDT'))"
```

---

## 📝 Notlar

- **Gerçek Zamanlı Fiyatlar**: Binance API'den alınır
- **PnL Hesaplama**: Kaldıraçlı hesaplama yapılır
- **Veritabanı**: SQLite (`data/chimerabot.db`)
- **Güncelleme**: Live monitor 5 saniyede bir yenilenir

---

## 🎯 Gelecek Özellikler

- [ ] Web dashboard (Flask/Streamlit)
- [ ] Grafik görselleştirme (matplotlib/plotly)
- [ ] Telegram bildirim entegrasyonu
- [ ] Export (CSV, Excel)
- [ ] Performans metrikleri (Sharpe Ratio, Max Drawdown)
