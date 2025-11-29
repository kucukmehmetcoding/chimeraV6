# ChimeraBot (Fibonacci Bot) Coolify Deployment Guide

Bu rehber, ChimeraBot'unuzu (Fibonacci Bot) Coolify ile GitHub üzerinden otomatik ve güvenli şekilde deploy etmek için hazırlanmıştır. Algoritma ve canlı işlem mantığına dokunulmaz, sadece deployment ve çalışma ortamı ayarlanır.

## Önemli Not: Python 3.12 distutils Sorunu Çözüldü
- Coolify Nixpacks kullanır ve otomatik olarak Python 3.12'ye geçebilir
- Python 3.12'de `distutils` modülü kaldırıldığı için hata alabilirsiniz
- Bu sorun `nixpacks.toml` ve `.nixpacks/config.toml` dosyaları ile çözüldü
- Python versiyonu 3.11 olarak sabitlendi

---

## 1. GitHub Bağlantısı
- Kodunuzu GitHub'da özel veya açık bir repoda tutun.
- Coolify panelinden yeni bir **Uygulama (App)** oluşturun.
- "GitHub" seçin ve repoyu, branch'i (örn. `main`) bağlayın.

## 2. Ortam Değişkenleri (Secrets)
- `.env.example` dosyasındaki tüm değişkenleri Coolify panelinde **Environment Variables** veya **Secrets** olarak tanımlayın.
- API anahtarları, canlı/deneme modları ve Telegram tokenları kesinlikle gizli tutulmalı, kodda bırakılmamalı.

## 3. Dockerfile ve Başlatma
- Projede hazır bir `Dockerfile` ve `docker-entrypoint.sh` mevcut.
- Coolify otomatik olarak Dockerfile'ı algılar ve kullanır.
- Başlatma komutu: `python -m src.main_orchestrator` (Dockerfile'da zaten ayarlı)

## 4. Klasör ve Dosya İzinleri
- Gerekli klasörler (`/app/data`, `/app/logs`) otomatik oluşturulur.
- Gerekirse log ve veri klasörleri için yazma izni verin.

## 5. Otomatik Yeniden Başlatma
- Coolify panelinde "Restart Policy" ayarını **Always** veya **On Failure** olarak seçin.
- Uygulama kapanırsa otomatik yeniden başlar.

## 6. Log ve Hata Takibi
- Coolify panelinden canlı logları izleyebilirsiniz.
- Hatalı deploylarda logları kontrol edin, API anahtarlarını ve ortam değişkenlerini doğrulayın.

## 7. Güvenlik ve Uyarılar
- **Gerçek para ile işlem yapıyorsanız, API anahtarlarınızı asla kodda bırakmayın!**
- Tüm hassas bilgiler sadece Coolify ortam değişkenlerinde tutulmalı.
- Kodda veya algoritmada hiçbir değişiklik yapmayın, sadece deploy ortamı ayarlayın.

---

## Kısa Özet
- Kodunuzu GitHub'a pushlayın.
- Coolify'da yeni bir Docker App oluşturun, repoyu bağlayın.
- Ortam değişkenlerini girin.
- Deploy edin ve logları izleyin.
- Botunuz otomatik ve sürekli çalışacaktır.

---

Herhangi bir hata veya özel ihtiyaç için: [Coolify Docs](https://coolify.io/docs) veya bana tekrar danışabilirsiniz.
