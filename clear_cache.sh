#!/bin/bash
# Cache Temizleme Script - ChimeraBot
# 7 Kasım 2025

echo "🧹 Cache temizleniyor..."

# Python cache dosyalarını bul ve sil
echo "   📁 __pycache__ klasörleri siliniyor..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

echo "   🗑️  .pyc dosyaları siliniyor..."
find . -type f -name "*.pyc" -delete 2>/dev/null

echo "   🗑️  .pyo dosyaları siliniyor..."
find . -type f -name "*.pyo" -delete 2>/dev/null

echo ""
echo "✅ Cache başarıyla temizlendi!"
echo ""
echo "Temizlenen içerik:"
echo "   • __pycache__ klasörleri"
echo "   • .pyc dosyaları (bytecode)"
echo "   • .pyo dosyaları (optimized bytecode)"
echo ""
echo "💡 Bot'u yeniden başlatabilirsin: python src/main_orchestrator.py"
