# 🚀 Coolify Deployment Hazırlık Özeti

## 🚨 KRİTİK: DB Migration Gerekli!

**UYARI:** Deployment öncesi mutlaka migration çalıştırın!

**Hata:** `sqlite3.OperationalError: no such column: open_positions.initial_sl`

**Çözüm:**
```bash
# Coolify terminal'de
cd /app
python3 migrations/add_advanced_risk_columns.py
supervisorctl restart chimerabot
```

**Detaylı guide:** Aşağıda "DB Migration Guide" bölümüne bakın.

---

## ✅ Tamamlanan İşlemler

### 1. Requirements.txt Güncellendi
**Dosya**: `/requirements.txt`

**Eklenen Paketler**:
- ✅ `beautifulsoup4==4.12.3` - HTML/XML parsing (sentiment_analyzer.py)
- ✅ `lxml==5.1.0` - BeautifulSoup parser backend
- ✅ `feedparser==6.0.11` - RSS feeds
- ✅ `praw==7.7.1` - Reddit API
- ✅ `pytrends==4.9.2` - Google Trends
- ✅ `google-generativeai==0.3.2` - Gemini AI
- ✅ `SQLAlchemy==2.0.23` - Database ORM
- ✅ `psycopg2-binary==2.9.9` - PostgreSQL support (Coolify optional)
- ✅ `schedule==1.2.1` - Scan scheduling
- ✅ `tenacity==8.2.3` - Retry logic
- ✅ `grpcio` + `grpcio-status` - gRPC support
- ✅ `asyncio==3.4.3` - Async I/O
- ✅ `httplib2`, `httpx`, `h11`, `httpcore` - HTTP libraries
- ✅ `aiosignal`, `frozenlist`, `multidict`, `yarl` - Async utilities

**Toplam**: 60+ paket, tüm dependency'ler dahil

---

### 2. Dockerfile Oluşturuldu
**Dosya**: `/Dockerfile`

**Özellikler**:
- ✅ Python 3.11 slim base image
- ✅ TA-Lib C library kurulumu (wget + make)
- ✅ System dependencies (build-essential)
- ✅ Multi-stage build (cache optimization)
- ✅ Volume mounts: `/app/data`, `/app/logs`
- ✅ PYTHONUNBUFFERED=1 (log buffering kapalı)
- ✅ CMD: `python -m src.main_orchestrator`

---

### 3. Docker Compose Oluşturuldu
**Dosya**: `/docker-compose.yml`

**Yapılandırma**:
- ✅ Service: `chimerabot`
- ✅ Restart policy: `unless-stopped`
- ✅ Environment variables (11 adet)
- ✅ Volume persistence (data + logs)
- ✅ Health check (60s interval, log dosyası kontrolü)

**Environment Variables**:
- `BINANCE_API_KEY` (zorunlu)
- `BINANCE_SECRET_KEY` (zorunlu)
- `TELEGRAM_BOT_TOKEN` (zorunlu)
- `TELEGRAM_CHAT_ID` (zorunlu)
- `REDDIT_CLIENT_ID` (opsiyonel)
- `REDDIT_CLIENT_SECRET` (opsiyonel)
- `REDDIT_USER_AGENT` (opsiyonel)
- `GEMINI_API_KEY` (opsiyonel)
- `DATABASE_URL` (opsiyonel, default: SQLite)

---

### 4. .dockerignore Oluşturuldu
**Dosya**: `/.dockerignore`

**Hariç Tutulanlar**:
- ✅ Python cache (`__pycache__`, `*.pyc`)
- ✅ Virtual environments
- ✅ IDE dosyaları (`.vscode`, `.idea`)
- ✅ Test dosyaları (`test_*.py`, `debug_*.py`, etc.)
- ✅ Logs (container'da oluşacak)
- ✅ Database (container'da oluşacak)
- ✅ .env (Coolify'dan inject edilecek)
- ✅ Git files
- ✅ Documentation (`.md` dosyaları - README hariç)

**Sonuç**: Image boyutu optimize, sadece production code

---

### 5. .env.example Oluşturuldu
**Dosya**: `/.env.example`

**İçerik**:
- ✅ Binance API placeholders
- ✅ Telegram placeholders
- ✅ Reddit API (opsiyonel)
- ✅ Gemini API (opsiyonel)
- ✅ Database URL (opsiyonel)
- ✅ Açıklayıcı yorumlar

---

### 6. .gitignore Güncellendi
**Dosya**: `/.gitignore`

**Eklenenler**:
- ✅ Test dosyaları (deployment'a gitmemeli)
- ✅ Database dosyaları (`*.db`, `*.sqlite`)
- ✅ Log dosyaları (`logs/*.log`)
- ✅ CSV/JSON data dosyaları
- ✅ OS-specific files

---

### 7. DEPLOYMENT.md Oluşturuldu
**Dosya**: `/DEPLOYMENT.md`

**Bölümler**:
- ✅ Ön Gereksinimler
- ✅ Coolify Deployment Adımları (6 adım)
- ✅ Environment Variables Ayarlama
- ✅ Volume Persistence
- ✅ Monitoring & Logs
- ✅ Troubleshooting (5 yaygın sorun + çözümleri)
- ✅ Post-Deployment Checklist
- ✅ Update & Restart
- ✅ Performance Optimization
- ✅ Security Best Practices

---

### 8. README.md Oluşturuldu
**Dosya**: `/README.md`

**Kapsamlı Dokümantasyon**:
- ✅ Proje genel bakış
- ✅ Özellikler (Trading, Teknik Analiz, Sentiment, Risk)
- ✅ Hızlı başlangıç (lokal + Coolify)
- ✅ Gereksinimler (API keys, sistem)
- ✅ Proje yapısı
- ✅ Konfigürasyon
- ✅ Monitoring & Logs
- ✅ Testing
- ✅ Troubleshooting
- ✅ Performance metrics
- ✅ Security
- ✅ Roadmap

---

## 📦 Dosya Özeti

| Dosya | Durum | Açıklama |
|-------|-------|----------|
| `requirements.txt` | ✅ Güncellendi | 60+ paket, eksiksiz dependency listesi |
| `Dockerfile` | ✅ Oluşturuldu | TA-Lib destekli Python 3.11 image |
| `docker-compose.yml` | ✅ Oluşturuldu | Coolify-ready orchestration |
| `.dockerignore` | ✅ Oluşturuldu | Optimize image size |
| `.env.example` | ✅ Oluşturuldu | Environment template |
| `.gitignore` | ✅ Güncellendi | Production-ready |
| `DEPLOYMENT.md` | ✅ Oluşturuldu | Kapsamlı deployment rehberi |
| `README.md` | ✅ Oluşturuldu | Proje dokümantasyonu |

---

## 🎯 Coolify'da Deployment Adımları

### 1️⃣ Repository'yi Hazırla
```bash
# Değişiklikleri commit et
git add requirements.txt Dockerfile docker-compose.yml .dockerignore .env.example .gitignore README.md DEPLOYMENT.md
git commit -m "feat: Coolify deployment ready - complete requirements & Docker setup"
git push origin main
```

### 2️⃣ Coolify'da Uygulama Oluştur
1. **Coolify Dashboard** → **New Resource** → **Docker Compose**
2. **Repository URL**: GitHub/GitLab repo URL'niz
3. **Branch**: `main`
4. **Docker Compose Path**: `docker-compose.yml`

### 3️⃣ Environment Variables Set Et
Coolify Dashboard → Your App → **Environment Variables**:

```env
BINANCE_API_KEY=your_real_api_key
BINANCE_SECRET_KEY=your_real_secret_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Opsiyonel (sentiment analizi için):
REDDIT_CLIENT_ID=your_reddit_id
REDDIT_CLIENT_SECRET=your_reddit_secret
GEMINI_API_KEY=your_gemini_key
```

### 4️⃣ Deploy!
**Deploy** butonuna tıklayın. Container:
1. Build edilir (TA-Lib kurulumu ~5 dakika)
2. Dependencies yüklenir
3. Başlatılır
4. Health check başlar

### 5️⃣ İlk Kontroller
- ✅ Telegram'a "Bot başlatıldı" mesajı gelmeli
- ✅ Logs akmalı: `docker logs -f chimerabot`
- ✅ Database oluşmalı: `/app/data/chimerabot.db`
- ✅ İlk scan cycle ~10 dakikada tamamlanmalı

---

## 🔍 Test Checklist (Deployment Öncesi)

### Lokal Test (Opsiyonel)
```bash
# Docker build test
docker build -t chimerabot-test .

# Container çalıştırma (test mode)
docker run --rm -it \
  -e BINANCE_API_KEY=test \
  -e BINANCE_SECRET_KEY=test \
  -e TELEGRAM_BOT_TOKEN=test \
  -e TELEGRAM_CHAT_ID=test \
  chimerabot-test python -c "import src.config; print('Config OK')"

# TA-Lib import test
docker run --rm chimerabot-test python -c "import talib; print('TA-Lib OK')"
```

### Requirements Test
```bash
# Virtual environment'ta test
python -m venv test_env
source test_env/bin/activate
pip install -r requirements.txt
python -c "
from src.alpha_engine.sentiment_analyzer import SentimentAnalyzer
from src.technical_analyzer.indicators import calculate_all_indicators
print('All imports OK!')
"
deactivate
rm -rf test_env
```

---

## ⚠️ Kritik Notlar

### TA-Lib Kurulumu
- Dockerfile içinde C library build ediliyor
- Build süresi: ~5 dakika (ilk deploy)
- Sonraki deployments: Docker cache sayesinde hızlı

### Database
- **Varsayılan**: SQLite (`/app/data/chimerabot.db`)
- **Upgrade**: PostgreSQL için `DATABASE_URL` set edin
- Volume persistence sayesinde data kaybolmaz

### Secrets Management
- ✅ `.env` dosyası Git'e commit edilmiyor
- ✅ Coolify encrypted storage kullanıyor
- ✅ Environment variables container'a inject ediliyor

### Monitoring
- **Logs**: Coolify Dashboard > Logs sekmesi
- **Health**: Her 60s kontrol, 3 fail → restart
- **Telegram**: Real-time notifications

---

## � DB Migration Guide (KRİTİK!)

### Sorun
Coolify deployment'ında SQLite DB'de 20 adet kolon eksik:
- `initial_sl`, `trailing_stop_distance`, `high_water_mark`
- `partial_tp_1_price`, `partial_tp_2_price`
- `volatility_score`, `sentiment_alignment`, `kelly_percent`
- ... ve 12 kolon daha

### Hızlı Çözüm

**Yöntem 1: Manuel Migration (Önerilen)**
```bash
# Coolify terminal'de
cd /app
python3 migrations/add_advanced_risk_columns.py
supervisorctl restart chimerabot
```

**Yöntem 2: Shell Script**
```bash
cd /app
chmod +x run_migration.sh
./run_migration.sh
```

**Yöntem 3: Dockerfile'a Ekle (Otomatik)**
```dockerfile
# Dockerfile içinde, CMD'den önce:
RUN python3 migrations/add_advanced_risk_columns.py || true
```

### Doğrulama
```bash
# Migration sonrası kontrol
sqlite3 /app/data/chimerabot.db "PRAGMA table_info(open_positions);" | grep initial_sl

# Beklenen çıktı:
# 19|initial_sl|REAL|0||0
```

### Güvenlik
```bash
# Migration öncesi backup (isteğe bağlı)
cp /app/data/chimerabot.db /app/data/chimerabot_backup_$(date +%Y%m%d).db
```

**Not:** Migration idempotent (birden fazla çalıştırılabilir), mevcut veri kaybolmaz.

---

## �🚨 Deployment Sonrası Yapılacaklar

1. ✅ **DB Migration çalıştır** (yukarıdaki guide)
2. ✅ İlk scan cycle'ı bekle (10 dakika)
3. ✅ Telegram bildirimlerini kontrol et
4. ✅ Database'e bak: `docker exec chimerabot ls -lh /app/data/`
5. ✅ Logs'u incele: `docker logs chimerabot --tail=100`
6. ✅ İlk pozisyon açılışını izle
7. ✅ Binance'te TP/SL orderları kontrol et
8. ✅ Performance metrics'i takip et (ilk 24 saat)


---

## 📞 Destek

Sorun yaşarsanız:
1. **Logs**: `docker logs chimerabot -f`
2. **DEPLOYMENT.md**: Troubleshooting bölümü
3. **GitHub Issues**: Hata raporu açın
4. **Telegram**: Bot loglarını kontrol edin

---

**Hazırlayan**: GitHub Copilot  
**Tarih**: 7 Kasım 2025  
**Versiyon**: 6.0 (Percentage-based SL/TP)

**✅ SİSTEM COOLIFY DEPLOYMENT'A HAZIR!**
