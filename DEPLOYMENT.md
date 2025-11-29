# 🚀 ChimeraBot Coolify Deployment Guide

Bu rehber, ChimeraBot'u Coolify platformunda başarılı bir şekilde deploy etmek için tüm adımları içerir.

## 📋 Ön Gereksinimler

- **Coolify Hesabı**: [Coolify.io](https://coolify.io) üzerinde aktif hesap
- **Git Repository**: ChimeraBot kodunun bir Git repository'sinde olması
- **API Keys**: Binance ve Telegram API anahtarları

## 🔧 Deployment Adımları

### 1. Coolify'da Yeni Uygulama Oluşturma

1. Coolify dashboard'ına giriş yapın
2. **Applications** → **+ New Application** seçin
3. **Docker Compose** tipini seçin
4. Repository URL'nizi girin (GitHub, GitLab, vb.)
5. **Build Directory**: `/` (kök dizin)
6. **Docker Compose File**: `coolify.yaml` veya `docker-compose.yaml`

### 2. Environment Variables Ayarlama

**Coolify Secrets** bölümünde aşağıdaki değişkenleri tanımlayın:

#### 🔐 ZORUNLU SECRETS (Gizli Anahtarlar)

| Değişken | Açıklama | Örnek |
|----------|----------|-------|
| `BINANCE_API_KEY` | Binance API Key | `your_binance_api_key` |
| `BINANCE_SECRET_KEY` | Binance Secret Key | `your_binance_secret_key` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | `123456789` |

#### ⚙️ OPSİYONEL DEĞİŞKENLER

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `ENABLE_REAL_TRADING` | `false` | Gerçek trading modu |
| `BINANCE_TESTNET` | `true` | Testnet kullanımı |
| `AI_ENABLED` | `true` | AI sistemi aktif |
| `AI_PRIMARY_PROVIDER` | `deepseek` | AI sağlayıcı |
| `DEEPSEEK_API_KEY` | - | DeepSeek API key |
| `GROQ_API_KEY` | - | Groq API key |
| `GEMINI_API_KEY` | - | Gemini API key |
| `MAX_COINS_TO_SCAN` | `600` | Maksimum coin sayısı |
| `SCAN_INTERVAL_SECONDS` | `300` | Tarama aralığı (saniye) |

### 3. Production Deployment için Kritik Ayarlar

⚠️ **GERÇEK TRADING'E GEÇMEDEN ÖNCE:**

```bash
# Testnet modunda test edin
BINANCE_TESTNET=true
ENABLE_REAL_TRADING=false

# Production'a geçerken:
BINANCE_TESTNET=false
ENABLE_REAL_TRADING=true
```

### 4. Volume Configuration

Coolify otomatik olarak volume'leri yönetir. Aşağıdaki veriler kalıcı olarak saklanır:

- **Database**: `/app/data/chimerabot.db`
- **Logs**: `/app/logs/chimerabot.log`
- **Backups**: `/app/data/backups/`

### 5. Resource Limits

Coolify.yaml dosyasında optimize edilmiş resource limits:

- **Memory**: 1GB limit, 512MB reservation
- **CPU**: 1 core limit, 0.5 core reservation

## 🧪 Deployment Sonrası Testler

### 1. Container Logs Kontrolü

```bash
# Coolify dashboard'da logs sekmesini kontrol edin
# Başarılı başlangıç mesajı görmelisiniz:
# "🚀 ChimeraBot Container Starting..."
# "🎯 Starting ChimeraBot..."
```

### 2. Health Check

Container health check her 60 saniyede bir çalışır. "Health check OK" mesajı görmelisiniz.

### 3. Telegram Test

Bot çalıştıktan sonra Telegram'dan `/start` komutu gönderin. Hoş geldin mesajı almalısınız.

### 4. Binance Connection Test

İlk tarama döngüsünde Binance API bağlantısı test edilir. Başarısız olursa logs'ta hata görürsünüz.

## 🔍 Monitoring & Debugging

### Log Seviyeleri

- **DEBUG**: Detaylı debugging için `LOG_LEVEL=DEBUG`
- **INFO**: Normal operasyon için `LOG_LEVEL=INFO` (varsayılan)
- **WARNING**: Sadece uyarılar için `LOG_LEVEL=WARNING`

### Önemli Log Mesajları

```
✅ Database schema ready - Veritabanı hazır
🔍 Scanning 600 coins... - Tarama başladı
📊 Found X signals - Sinyal bulundu
💰 Position opened - Pozisyon açıldı
💸 Position closed - Pozisyon kapandı
```

### Common Issues & Solutions

#### 1. TA-Lib Build Hatası
**Problem**: TA-Lib kurulumu başarısız
**Çözüm**: Dockerfile'daki TA-Lib kurulumunu kontrol edin

#### 2. Binance Connection Hatası
**Problem**: API key'ler yanlış veya izinler eksik
**Çözüm**: 
- API key'leri doğrulayın
- Futures Trading + Read izinlerini kontrol edin
- IP whitelist ekleyin

#### 3. Database Permission Hatası
**Problem**: SQLite dosyasına yazma izni yok
**Çözüm**: Volume mount'ları kontrol edin

#### 4. Memory Limit Aşımı
**Problem**: Container memory limiti aşıldı
**Çözüm**: 
- `MAX_COINS_TO_SCAN` değerini düşürün (örn: 300)
- Resource limits artırın

## 🔄 Update & Maintenance

### Yeni Versiyon Deploy Etme

1. Kod değişikliklerini repository'ye push edin
2. Coolify otomatik olarak rebuild edecek
3. Yeni container deploy edilecek

### Database Backup

```bash
# Coolify volume backup'ını etkinleştirin
# Veya manuel backup için:
docker exec chimerabot cp /app/data/chimerabot.db /app/data/backups/
```

### Log Rotation

Log dosyaları otomatik olarak büyür. Düzenli olarak temizleyin veya log rotation kurun.

## 📊 Performance Optimization

### Resource Tuning

| Senaryo | Memory | CPU | MAX_COINS_TO_SCAN |
|---------|--------|-----|-------------------|
| Test | 512MB | 0.5 | 300 |
| Production | 1GB | 1.0 | 600 |
| High Frequency | 2GB | 2.0 | 800 |

### Scan Interval Optimization

| Frequency | SCAN_INTERVAL_SECONDS | Use Case |
|-----------|---------------------|----------|
| Low | 600 (10 dk) | Conservative |
| Medium | 300 (5 dk) | Balanced |
| High | 180 (3 dk) | Aggressive |

## 🔒 Security Best Practices

### 1. API Key Security
- Asla API key'leri kod içinde saklamayın
- Coolify Secrets kullanın
- IP whitelist etkinleştirin

### 2. Network Security
- Container'ı izole edin
- Gereksiz port açmayın
- VPN kullanın (önerilen)

### 3. Monitoring
- Logları düzenli kontrol edin
- Telegram bildirimlerini aktif tutun
- Balance monitoring etkinleştirin

## 🆘 Troubleshooting Checklist

- [ ] Container başlıyor mu?
- [ ] Database oluşturuldu mu?
- [ ] Binance API bağlantısı çalışıyor mu?
- [ ] Telegram bot mesaj gönderiyor mu?
- [ ] Health check başarılı mı?
- [ ] Memory/CPU kullanımı normal mi?
- [ ] Log dosyaları büyüyor mu?

## 📞 Support

- **GitHub Issues**: Teknik sorunlar için
- **Coolify Docs**: Deployment sorunları için
- **Binance Support**: API sorunları için

---

**🎉 Tebrikler!** ChimeraBot'u başarıyla Coolify'a deploy ettiniz. İlk tarama döngüsünün tamamlanmasını bekleyin ve Telegram bildirimlerini kontrol edin.

**⚠️ Unutmayın**: Production trading'e geçmeden önce testnet'te yeterince test yapın!
