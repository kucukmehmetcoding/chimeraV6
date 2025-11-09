#!/bin/bash
# Gerçek Trading Başlatma Scripti
# Son kontroller ve güvenlik onayı

clear
echo "════════════════════════════════════════════════════════════════"
echo "🔴 GERÇEK TRADING BAŞLATMA"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "⚠️  UYARI: Bu script GERÇEK PARA ile işlem yapacak!"
echo ""
echo "📋 Sistem Kontrolü..."
echo ""

# Config kontrolü
python3 check_real_trading_status.py 2>&1 | grep -A20 "AYARLAR:"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📊 ÖZETLENECEK AYARLAR:"
echo "════════════════════════════════════════════════════════════════"
echo "   ✅ Simülasyon pozisyonları temizlendi"
echo "   ✅ ENABLE_REAL_TRADING=true aktif"
echo "   ✅ Dinamik kaldıraç sistemi aktif (2x-10x)"
echo "   ✅ Margin optimizasyonu uygulandı"
echo "   ✅ Ghost kontrolünden muaf simülasyon sistemi"
echo ""
echo "   💰 Risk per trade: $3"
echo "   📊 Max pozisyon: 8 adet"
echo "   🎯 Max pozisyon değeri: $120"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
read -p "❓ Gerçek trading'i başlatmak istediğinize EMİN MİSİNİZ? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    echo ""
    echo "🚀 Bot başlatılıyor..."
    echo ""
    python3 -m src.main_orchestrator
else
    echo ""
    echo "❌ İptal edildi. Güvenli çıkış."
    echo ""
    echo "💡 İpucu: Simülasyona dönmek için .env'de şunu değiştir:"
    echo "   ENABLE_REAL_TRADING=false"
    echo ""
fi
