#!/bin/bash
# Quick Production Test Launcher

cd /Users/macbook/Desktop/ChimeraBot

echo "🤖 ChimeraBot Production Test - Quick Launcher"
echo ""
echo "Sembol seçimi:"
echo "  1) Top 15 sembol (Hızlı)"
echo "  2) Tüm Binance (512 sembol)"
echo ""
read -p "Seçim (1/2, default=1): " choice

if [ "$choice" = "2" ]; then
    echo "2" | python run_production_test.py
else
    echo "1" | python run_production_test.py
fi
