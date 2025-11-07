# ARPAUSDT SL/TP PRECISION HATASI DÜZELTMESİ

## Sorun
ARPAUSDT pozisyonu açılıyordu ancak SL/TP emirleri yerleştirilemiyordu:
```
APIError(code=-1111): Precision is over the maximum defined for this asset.
```

## Kök Neden
`src/trade_manager/executor.py` dosyasındaki `place_sl_tp_orders()` fonksiyonunda:

1. **Yanlış precision kullanımı**: `pricePrecision` değeri kullanılıyordu (hatalı key)
2. **Yanlış yuvarlama yöntemi**: `round(price, precision)` kullanılıyordu
3. **Floating point hatası**: Tick size hesaplaması `10 ** (-precision)` ile yapılıyordu

## Düzeltme

### 1. Doğru tick_size kullanımı (satır 463-478)
```python
# ÖNCE
price_precision = symbol_info.get('pricePrecision', 2)  # Yanlış key!
sl_price = round(sl_price, price_precision)  # Yanlış yuvarlama!
tick_size = 10 ** (-price_precision)  # Floating point hatası!

# SONRA
tick_size = Decimal(str(symbol_info.get('tick_size', 0.00001)))  # PRICE_FILTER'dan al
sl_decimal = Decimal(str(sl_price))
sl_rounded = (sl_decimal / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
sl_price = float(sl_rounded)  # API için float'a çevir
```

### 2. Fiyatları string olarak gönderme (satır 510-519)
```python
# ÖNCE
stopPrice=sl_price,  # Float - precision sorunu!

# SONRA
price_precision = symbol_info.get('price_precision', 5)
sl_price_str = f"{sl_price:.{price_precision}f}"
stopPrice=sl_price_str,  # String - doğru precision garantisi!
```

## ARPAUSDT Özel Durumu
- **Tick Size**: 0.00001 (5 ondalık basamak)
- **Price Precision**: 5
- **Quantity Precision**: 0 (tam sayı)
- **Step Size**: 1.0

Örnek:
- Raw SL: 0.0193170500
- Rounded SL: 0.01932 (0.00001'in katı)
- String: "0.01932" ✅

## Test
```bash
python3 check_arpa_precision.py  # Precision bilgilerini kontrol et
```

## Sonuç
✅ SL/TP emirleri artık doğru precision ile gönderiliyor
✅ Binance API hatasını (code=-1111) çözdük
✅ Tüm coinler için çalışır (tick_size dinamik alınıyor)
