# ChimeraBot Coolify Deployment Guide

## 📋 Ön Gereksinimler

1. **Coolify Sunucusu**: Aktif bir Coolify instance
2. **API Keys**: 
   - Binance API Key & Secret (Futures Trading izinli)
   - Telegram Bot Token & Chat ID
   - (Opsiyonel) Reddit API credentials
   - (Opsiyonel) Google Gemini API key

## 🚀 Deployment Adımları

### 1. Coolify'da Yeni Uygulama Oluşturma

```bash
# Coolify Dashboard > New Resource > Docker Compose
```

**Uygulama Ayarları:**
- **Name**: ChimeraBot
- **Type**: Docker Compose
- **Repository**: GitHub/GitLab repository URL'niz
- **Branch**: main
- **Build Path**: /
- **Docker Compose Path**: docker-compose.yml

### 2. Environment Variables Ayarlama

Coolify Dashboard > Your App > Environment Variables:

```env
# ZORUNLU
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# OPSİYONEL (Sentiment analizi için)
REDDIT_CLIENT_ID=your_reddit_id
REDDIT_CLIENT_SECRET=your_reddit_secret
REDDIT_USER_AGENT=ChimeraBot/1.0
GEMINI_API_KEY=your_gemini_key
```

### 3. Volume Persistence Ayarlama

Coolify otomatik volume oluşturur, ancak manuel kontrol için:

```yaml
volumes:
  - chimerabot-data:/app/data
  - chimerabot-logs:/app/logs
```

### 4. Deploy!

```bash
# Coolify Dashboard > Deploy
```

Container build edilecek ve başlatılacak.

## 📊 Monitoring & Logs

### Log İzleme

```bash
# Coolify Dashboard > Logs sekmesi
# veya terminal ile:
docker logs -f chimerabot --tail=100
```

### Telegram'dan Kontrol

Bot başladığında Telegram'a şu mesajı gönderir:
```
🤖 ChimeraBot Başlatıldı
Tarama döngüsü başlıyor...
```

### Health Check

Health check her 60 saniyede bir çalışır:
- Log dosyası varlığını kontrol eder
- 3 başarısız deneme sonrası container restart olur

## 🔧 Troubleshooting

### Problem: TA-Lib import hatası

**Çözüm**: Dockerfile'da TA-Lib C library kurulumu doğru yapılmış durumda. Eğer hata alırsanız:

```dockerfile
# Dockerfile'da bu satırların olduğundan emin olun:
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && make install
```

### Problem: Database bağlantı hatası

**Çözüm**: 
- SQLite için `/app/data` volume'ün mount edildiğinden emin olun
- PostgreSQL için `DATABASE_URL` environment variable'ı set edin

### Problem: Binance API rate limit

**Çözüm**: 
- `src/config.py` içinde `SCAN_DELAY_SECONDS` değerini artırın (önerilen: 2.0)
- `SCAN_INTERVAL_MINUTES` değerini artırın (önerilen: 10)

### Problem: Telegram mesaj gönderilmiyor

**Çözüm**:
1. Bot token'ı doğru mu kontrol edin
2. Chat ID negatif sayı mı? (`-1234567890` formatında olmalı)
3. Bot'u gruba eklediniz mi?

## 📝 Post-Deployment Checklist

- [ ] Container başarıyla çalışıyor (`docker ps`)
- [ ] Telegram'a "Bot başlatıldı" mesajı geldi
- [ ] Logs akıyor (`docker logs -f chimerabot`)
- [ ] İlk scan cycle tamamlandı (10 dakika sonra)
- [ ] Data dizini oluşturuldu (`/app/data/chimerabot.db`)
- [ ] Logs dizini oluşturuldu (`/app/logs/chimerabot.log`)

## 🔄 Update & Restart

### Code Güncellemesi

```bash
# Coolify Dashboard > Redeploy
# veya Git push sonrası otomatik deploy (webhook kuruluysa)
```

### Manuel Restart

```bash
docker restart chimerabot
```

### Emergency Stop

```bash
docker stop chimerabot
```

## 📈 Performance Optimization

### Resource Limits (docker-compose.yml)

```yaml
services:
  chimerabot:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### Scan Interval Ayarları

**Düşük kaynak için:**
```python
# src/config.py
SCAN_INTERVAL_MINUTES = 15  # 15 dakikada bir tara
SCAN_DELAY_SECONDS = 3.0    # Coin arası 3 saniye bekle
```

**Agresif trading için:**
```python
SCAN_INTERVAL_MINUTES = 5   # 5 dakikada bir tara
SCAN_DELAY_SECONDS = 1.5    # Coin arası 1.5 saniye bekle
```

## 🛡️ Security Best Practices

1. **API Key İzinleri**: Sadece Futures Trading + Read permissions
2. **IP Whitelist**: Binance'te sunucu IP'sini whitelist'e ekleyin
3. **Environment Variables**: Coolify encrypted storage kullanır
4. **Secrets Management**: Hassas bilgileri asla kod içine yazmayın

## 📞 Support

- **GitHub Issues**: Repository'de issue açın
- **Telegram**: Bot çalışmazsa log dosyalarını kontrol edin
- **Email**: [Destek e-posta adresiniz]

## 🎯 Next Steps

1. İlk pozisyon açılışını izleyin
2. TP/SL seviyelerinin doğru set edildiğini Binance'ten kontrol edin
3. Trade history'yi takip edin (`/app/data/chimerabot.db`)
4. Performance metrics'i analiz edin (gelecek feature)

---

**Son Güncelleme**: 7 Kasım 2025  
**Version**: 6.0 (Percentage-based SL/TP System)
