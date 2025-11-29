#!/bin/bash
# -*- coding: utf-8 -*-
################################################################################
# Quick Live Test Setup Script
# Testnet trading botunu hızlı başlatmak için kullanılır
################################################################################

set -e  # Hata durumunda durdur

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Header
clear
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}          ${MAGENTA}🤖 AI TRADING BOT - QUICK SETUP${NC}                  ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Python kontrolü
echo -e "${BLUE}🔍 Python kontrolü...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 bulunamadı!${NC}"
    echo -e "${YELLOW}💡 Python 3.8+ yükleyin: https://www.python.org${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✅ Python $PYTHON_VERSION bulundu${NC}"
echo ""

# Virtual environment kontrolü (opsiyonel)
echo -e "${BLUE}🔍 Virtual environment kontrolü...${NC}"
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment bulunamadı${NC}"
    read -p "Virtual environment oluşturulsun mu? (y/n): " create_venv
    
    if [[ $create_venv =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}📦 Virtual environment oluşturuluyor...${NC}"
        python3 -m venv venv
        echo -e "${GREEN}✅ Virtual environment oluşturuldu${NC}"
        
        echo -e "${BLUE}🔧 Aktivasyon ediliyor...${NC}"
        source venv/bin/activate
        echo -e "${GREEN}✅ Virtual environment aktif${NC}"
    fi
else
    echo -e "${YELLOW}📦 Virtual environment bulundu, aktivasyon ediliyor...${NC}"
    source venv/bin/activate
    echo -e "${GREEN}✅ Virtual environment aktif${NC}"
fi
echo ""

# Gerekli dizinleri oluştur
echo -e "${BLUE}📁 Dizinler oluşturuluyor...${NC}"
mkdir -p data logs
echo -e "${GREEN}✅ Dizinler hazır${NC}"
echo ""

# Kütüphane yükleme
echo -e "${BLUE}📚 Gerekli kütüphaneler kontrol ediliyor...${NC}"
echo ""

# Minimal requirements kullan (live test için yeterli)
if [ -f "requirements_minimal.txt" ]; then
    echo -e "${YELLOW}📄 Minimal requirements yükleniyor (live test için)...${NC}"
    pip install --quiet --upgrade pip
    
    if pip install --quiet -r requirements_minimal.txt; then
        echo -e "${GREEN}✅ Kütüphaneler yüklendi${NC}"
    else
        echo -e "${YELLOW}⚠️  Bazı paketler yüklenemedi, temel paketler yükleniyor...${NC}"
        
        # Core paketleri teker teker yükle
        CORE_PACKAGES=(
            "python-binance"
            "pandas"
            "numpy"
            "SQLAlchemy"
            "python-dotenv"
            "schedule"
            "tenacity"
        )
        
        for package in "${CORE_PACKAGES[@]}"; do
            echo -e "${BLUE}  • $package...${NC}"
            pip install --quiet --upgrade "$package" 2>/dev/null || echo -e "${RED}    ✗ Failed${NC}"
        done
        
        echo -e "${GREEN}✅ Core kütüphaneler yüklendi${NC}"
    fi
    
    # TA-Lib özel kurulum
    echo -e "${BLUE}  • TA-Lib kontrol ediliyor...${NC}"
    if python3 -c "import talib" 2>/dev/null; then
        echo -e "${GREEN}    ✅ TA-Lib zaten yüklü${NC}"
    else
        echo -e "${YELLOW}    ⚠️  TA-Lib bulunamadı${NC}"
        if pip install --quiet TA-Lib 2>/dev/null; then
            echo -e "${GREEN}    ✅ TA-Lib yüklendi${NC}"
        else
            echo -e "${RED}    ❌ TA-Lib yüklenemedi!${NC}"
            echo -e "${YELLOW}    💡 Manuel kurulum gerekli:${NC}"
            echo -e "${YELLOW}       macOS: brew install ta-lib && pip install TA-Lib${NC}"
            echo -e "${YELLOW}       Linux: sudo apt-get install libta-lib0-dev && pip install TA-Lib${NC}"
            echo ""
            read -p "    TA-Lib olmadan devam edilsin mi? (y/n): " skip_talib
            if [[ ! $skip_talib =~ ^[Yy]$ ]]; then
                echo -e "${RED}❌ Kurulum iptal edildi${NC}"
                exit 1
            fi
        fi
    fi
    
elif [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}📄 requirements.txt bulundu, yükleniyor...${NC}"
    pip install --quiet --upgrade pip
    
    # Önce conflict'siz yüklemeyi dene
    if pip install --quiet -r requirements.txt 2>/dev/null; then
        echo -e "${GREEN}✅ Kütüphaneler yüklendi${NC}"
    else
        echo -e "${YELLOW}⚠️  Dependency conflict tespit edildi, esnek yükleme yapılıyor...${NC}"
        
        # Esnek versiyon yükleme (>= yerine == kullanmayan)
        pip install --quiet --upgrade pip
        pip install --quiet --no-deps -r requirements.txt 2>/dev/null || true
        
        # Temel paketleri manuel yükle
        echo -e "${BLUE}  • Core packages yükleniyor...${NC}"
        pip install --quiet python-binance pandas numpy python-dotenv requests schedule tenacity
        
        echo -e "${BLUE}  • Google AI packages yükleniyor...${NC}"
        pip install --quiet 'google-generativeai>=0.8.0' 'google-auth>=2.25.0'
        
        echo -e "${BLUE}  • Telegram bot yükleniyor...${NC}"
        pip install --quiet 'python-telegram-bot>=21.0'
        
        echo -e "${BLUE}  • Sentiment analysis yükleniyor...${NC}"
        pip install --quiet feedparser beautifulsoup4 praw vaderSentiment pytrends
        
        echo -e "${GREEN}✅ Temel kütüphaneler yüklendi (dependency conflicts çözüldü)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  requirements.txt bulunamadı, manuel yükleme yapılıyor...${NC}"
    
    # Core kütüphaneler
    PACKAGES=(
        "python-binance"
        "pandas"
        "numpy"
        "python-dotenv"
        "requests"
    )
    
    for package in "${PACKAGES[@]}"; do
        echo -e "${BLUE}  • Installing $package...${NC}"
        pip install --quiet --upgrade "$package"
    done
    
    # TA-Lib (özel kurulum gerekebilir)
    echo -e "${YELLOW}  • TA-Lib yükleniyor (zaman alabilir)...${NC}"
    if pip install --quiet TA-Lib; then
        echo -e "${GREEN}    ✅ TA-Lib yüklendi${NC}"
    else
        echo -e "${RED}    ❌ TA-Lib yüklenemedi!${NC}"
        echo -e "${YELLOW}    💡 Manuel kurulum gerekebilir:${NC}"
        echo -e "${YELLOW}       macOS: brew install ta-lib${NC}"
        echo -e "${YELLOW}       Linux: sudo apt-get install libta-lib0-dev${NC}"
        echo -e "${YELLOW}       Sonra: pip install TA-Lib${NC}"
    fi
    
    echo -e "${GREEN}✅ Temel kütüphaneler yüklendi${NC}"
fi
echo ""

# .env dosyası kontrolü
echo -e "${BLUE}🔑 API anahtarları kontrol ediliyor...${NC}"

if [ -f ".env" ]; then
    echo -e "${GREEN}✅ .env dosyası bulundu${NC}"
    
    # Testnet anahtarlarını kontrol et
    if grep -q "BINANCE_TESTNET_API_KEY" .env && ! grep -q "your_testnet_api_key_here" .env; then
        echo -e "${GREEN}✅ Testnet API anahtarları mevcut${NC}"
        SKIP_API_SETUP=true
    else
        echo -e "${YELLOW}⚠️  Testnet API anahtarları eksik veya placeholder${NC}"
        SKIP_API_SETUP=false
    fi
else
    echo -e "${YELLOW}⚠️  .env dosyası bulunamadı${NC}"
    SKIP_API_SETUP=false
fi

# API anahtarlarını iste (gerekirse)
if [ "$SKIP_API_SETUP" = false ]; then
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}           ${YELLOW}Binance Testnet API Kurulumu${NC}                      ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}📌 Testnet hesabınız yoksa:${NC}"
    echo -e "   1. https://testnet.binancefuture.com adresine gidin"
    echo -e "   2. Ücretsiz hesap oluşturun (gerçek para yok!)"
    echo -e "   3. API Management → Create API Key"
    echo -e "   4. API Key ve Secret'i kopyalayın"
    echo ""
    
    read -p "Binance Testnet API Key: " api_key
    echo ""
    read -s -p "Binance Testnet Secret Key: " api_secret
    echo ""
    echo ""
    
    # .env dosyasını oluştur/güncelle
    if [ -f ".env" ]; then
        echo -e "${BLUE}🔧 .env dosyası güncelleniyor...${NC}"
        
        # Testnet anahtarlarını güncelle
        if grep -q "BINANCE_TESTNET_API_KEY" .env; then
            sed -i.bak "s/BINANCE_TESTNET_API_KEY=.*/BINANCE_TESTNET_API_KEY=$api_key/" .env
            sed -i.bak "s/BINANCE_TESTNET_SECRET_KEY=.*/BINANCE_TESTNET_SECRET_KEY=$api_secret/" .env
        else
            echo "" >> .env
            echo "# Testnet API Keys" >> .env
            echo "BINANCE_TESTNET_API_KEY=$api_key" >> .env
            echo "BINANCE_TESTNET_SECRET_KEY=$api_secret" >> .env
        fi
        
        # BINANCE_TESTNET flag ekle
        if ! grep -q "BINANCE_TESTNET" .env; then
            echo "BINANCE_TESTNET=True" >> .env
        fi
        
        rm -f .env.bak  # Backup dosyasını temizle
    else
        echo -e "${BLUE}🔧 .env dosyası oluşturuluyor...${NC}"
        cat > .env << EOF
# Binance Testnet API Keys
BINANCE_TESTNET_API_KEY=$api_key
BINANCE_TESTNET_SECRET_KEY=$api_secret
BINANCE_TESTNET=True

# Binance Live API Keys (optional - kullanılmayacak)
BINANCE_API_KEY=your_live_api_key_here
BINANCE_SECRET_KEY=your_live_secret_key_here
EOF
    fi
    
    echo -e "${GREEN}✅ API anahtarları kaydedildi${NC}"
fi
echo ""

# Testnet bağlantı testi
echo -e "${BLUE}🔌 Testnet bağlantısı test ediliyor...${NC}"
if python3 testnet_setup.py > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Testnet bağlantısı başarılı${NC}"
else
    echo -e "${RED}❌ Testnet bağlantısı başarısız${NC}"
    echo -e "${YELLOW}💡 API anahtarlarınızı kontrol edin${NC}"
    
    read -p "Yine de devam edilsin mi? (y/n): " continue_anyway
    if [[ ! $continue_anyway =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ Kurulum iptal edildi${NC}"
        exit 1
    fi
fi
echo ""

# Son onay
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}              ${GREEN}✅ KURULUM TAMAMLANDI${NC}                           ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}📊 Live test başlatmaya hazır!${NC}"
echo ""
echo -e "${MAGENTA}Test özellikleri:${NC}"
echo -e "  • ${GREEN}Testnet${NC} ile çalışır (gerçek para riski YOK)"
echo -e "  • ${CYAN}Fake money${NC} ile paper trading"
echo -e "  • ${BLUE}Real-time${NC} fiyat verisi"
echo -e "  • ${YELLOW}Multi-timeframe${NC} analiz"
echo ""

read -p "🚀 Live test başlatılsın mı? (y/n): " start_test

if [[ $start_test =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}              ${MAGENTA}🤖 BOT BAŞLATILIYOR...${NC}                          ${GREEN}║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Live test başlat
    python3 run_live_test.py
else
    echo ""
    echo -e "${CYAN}ℹ️  Manuel başlatma için:${NC}"
    echo -e "   ${YELLOW}python3 run_live_test.py${NC}"
    echo ""
    echo -e "${GREEN}🎉 İyi şanslar!${NC}"
fi
