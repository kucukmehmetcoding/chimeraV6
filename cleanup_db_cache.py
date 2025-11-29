#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database ve Cache Temizleme Script
Production, test ve backtest verilerini temizler
"""

import os
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime


def backup_database(db_path: str) -> str:
    """Database'i yedekle"""
    if not os.path.exists(db_path):
        return None
    
    backup_dir = "data/backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_name = os.path.basename(db_path)
    backup_path = os.path.join(backup_dir, f"{db_name}.backup_{timestamp}")
    
    shutil.copy2(db_path, backup_path)
    return backup_path


def clean_database(db_path: str, keep_backup: bool = True):
    """Database'i temizle"""
    if not os.path.exists(db_path):
        print(f"⚠️  {db_path} bulunamadı")
        return
    
    # Yedek al
    if keep_backup:
        backup_path = backup_database(db_path)
        if backup_path:
            print(f"✅ Yedek oluşturuldu: {backup_path}")
    
    # Dosya boyutunu göster
    size_mb = os.path.getsize(db_path) / 1024 / 1024
    print(f"📊 {os.path.basename(db_path)}: {size_mb:.2f} MB")
    
    # Tabloları temizle
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Tabloları listele
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        if tables:
            print(f"   Tablolar: {', '.join(tables)}")
            
            # Her tabloyu temizle
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
                print(f"   ✓ {table} temizlendi")
            
            conn.commit()
            
            # VACUUM (dosya boyutunu küçült)
            cursor.execute("VACUUM")
            conn.commit()
            
            print(f"   ✓ VACUUM tamamlandı")
        else:
            print(f"   ℹ️  Tablo bulunamadı")
        
        conn.close()
        
        # Yeni boyut
        new_size_mb = os.path.getsize(db_path) / 1024 / 1024
        print(f"   📉 Yeni boyut: {new_size_mb:.2f} MB (tasarruf: {size_mb - new_size_mb:.2f} MB)")
        
    except Exception as e:
        print(f"❌ Hata: {e}")


def clean_cache_directory(cache_dir: str):
    """Cache klasörünü temizle"""
    if not os.path.exists(cache_dir):
        print(f"⚠️  {cache_dir} bulunamadı")
        return
    
    # Dosya sayısı ve toplam boyut
    file_count = 0
    total_size = 0
    
    for root, dirs, files in os.walk(cache_dir):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                total_size += os.path.getsize(file_path)
                file_count += 1
            except:
                pass
    
    print(f"📊 {cache_dir}: {file_count} dosya, {total_size / 1024 / 1024:.2f} MB")
    
    # Temizle
    try:
        shutil.rmtree(cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        print(f"   ✓ {file_count} dosya silindi")
        print(f"   📉 Tasarruf: {total_size / 1024 / 1024:.2f} MB")
    except Exception as e:
        print(f"❌ Hata: {e}")


def main():
    """Ana temizleme fonksiyonu"""
    print("\n" + "="*70)
    print("  🧹 DATABASE VE CACHE TEMİZLEME")
    print("="*70 + "\n")
    
    # Seçenekler
    print("Temizlenecek öğeler:")
    print("  1. Production database (production_database.db)")
    print("  2. Test database (test_database.db)")
    print("  3. Live test database (live_test_database.db)")
    print("  4. Backtest cache (data/backtest_cache/)")
    print("  5. HEPSİNİ TEMİZLE")
    print("  0. İptal\n")
    
    choice = input("Seçiminiz (0-5, virgülle ayırarak çoklu seçim yapabilirsiniz): ").strip()
    
    if choice == '0':
        print("\n❌ İptal edildi\n")
        return
    
    # Onay
    confirm = input("\n⚠️  Devam edilsin mi? Veriler silinecek! (evet/hayır): ").strip().lower()
    if confirm not in ['evet', 'e', 'yes', 'y']:
        print("\n❌ İptal edildi\n")
        return
    
    print("\n" + "-"*70)
    print("🧹 TEMİZLEME BAŞLIYOR...")
    print("-"*70 + "\n")
    
    # Seçimleri parse et
    choices = [c.strip() for c in choice.split(',')]
    
    if '5' in choices or choice == '5':
        # Hepsini temizle
        choices = ['1', '2', '3', '4']
    
    # Database'leri temizle
    if '1' in choices:
        print("\n1️⃣  PRODUCTION DATABASE")
        clean_database("data/production_database.db")
    
    if '2' in choices:
        print("\n2️⃣  TEST DATABASE")
        clean_database("data/test_database.db")
    
    if '3' in choices:
        print("\n3️⃣  LIVE TEST DATABASE")
        clean_database("data/live_test_database.db")
    
    # Cache'i temizle
    if '4' in choices:
        print("\n4️⃣  BACKTEST CACHE")
        clean_cache_directory("data/backtest_cache")
    
    print("\n" + "="*70)
    print("  ✅ TEMİZLEME TAMAMLANDI")
    print("="*70 + "\n")
    
    # Yedek bilgisi
    backup_dir = "data/backups"
    if os.path.exists(backup_dir):
        backups = [f for f in os.listdir(backup_dir) if f.endswith('.backup_' + datetime.now().strftime("%Y%m%d"))]
        if backups:
            print(f"💾 Bugün oluşturulan yedekler: {len(backups)} dosya")
            print(f"   Klasör: {backup_dir}/\n")


if __name__ == "__main__":
    main()
