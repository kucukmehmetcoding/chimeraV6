# 🚨 DB Migration Emergency Fix

## Sorun
Coolify deployment'ında kritik hata:
```
sqlite3.OperationalError: no such column: open_positions.initial_sl
```

## Hızlı Çözüm

**Coolify terminal'de tek komut:**
```bash
cd /app && ./emergency_db_fix.sh
```

**Veya manuel:**
```bash
python3 migrations/add_advanced_risk_columns.py
supervisorctl restart chimerabot
```

## Detaylar
- **Eksik kolonlar:** 20 adet (initial_sl, trailing_stop_distance, high_water_mark, vb.)
- **Sebep:** Model güncellendi ama migration çalıştırılmadı
- **Çözüm:** `migrations/add_advanced_risk_columns.py` çalıştır

## Verification
```bash
# Migration sonrası kontrol
sqlite3 data/chimerabot.db "SELECT COUNT(*) FROM pragma_table_info('open_positions') WHERE name='initial_sl';"
# Beklenen çıktı: 1
```

## Dosyalar
- `migrations/add_advanced_risk_columns.py` - Migration script
- `emergency_db_fix.sh` - Otomatik hotfix + verification
- `run_migration.sh` - Basit migration runner
- `COOLIFY_READY.md` - Detaylı deployment guide

## Güvenlik
✅ Idempotent (birden fazla çalıştırılabilir)  
✅ Mevcut veri korunur  
✅ Yalnızca yeni kolonlar eklenir  
⚠️ Backup öneririz (isteğe bağlı)

## Deployment Checklist
1. [ ] Git push (migration scriptleri dahil)
2. [ ] Coolify otomatik deploy bekle
3. [ ] Coolify terminal → `./emergency_db_fix.sh`
4. [ ] Bot restart → Logları kontrol et
5. [ ] İlk scan cycle → Error yok mu kontrol
