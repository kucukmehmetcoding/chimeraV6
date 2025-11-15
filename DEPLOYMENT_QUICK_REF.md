# 🚀 Range Bot Coolify Deployment - Quick Reference

## ✅ What Was Done

1. **Environment Configuration** (`.env.range_bot`)
   - Template with all 20+ configurable parameters
   - Includes API keys, trading params, risk management, quality filters

2. **Docker Configuration** (`Dockerfile.range`)
   - Python 3.11 base image
   - TA-Lib installation from source
   - Optimized for range bot (runs `range_main.py`)
   - Health checks included

3. **Docker Compose** (`docker-compose.range.yaml`)
   - Complete service definition
   - All parameters exposed as ENV variables
   - Persistent volumes for data/logs
   - Resource limits (512MB RAM, 1 CPU)
   - Network isolation

4. **Code Update** (`range_main.py`)
   - Added `from dotenv import load_dotenv`
   - Replaced hardcoded values with `os.getenv()`
   - All parameters now configurable via ENV
   - Startup logs show loaded configuration

5. **Documentation** (`COOLIFY_DEPLOYMENT.md`)
   - Complete deployment guide
   - Environment variable reference
   - Troubleshooting section
   - Performance metrics
   - Tuning tips

## 📦 Files Ready for Git Push

```bash
git status
# Shows:
A  .env.range_bot                    # ENV template
A  Dockerfile.range                  # Docker build file
A  docker-compose.range.yaml         # Compose configuration
M  COOLIFY_DEPLOYMENT.md             # Deployment guide
M  range_main.py                     # Updated with ENV support
```

## 🎯 Next Steps

### 1. Push to GitHub
```bash
git push origin main
```

### 2. Configure Coolify

**Create New Service:**
- Resource Type: Docker Compose
- Repository: kucukmehmetcoding/chimeraV6
- Branch: main
- Docker Compose File: `docker-compose.range.yaml`

**Add Environment Variables (Minimum Required):**
```env
BINANCE_API_KEY=your_testnet_api_key
BINANCE_SECRET_KEY=your_testnet_secret_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
BINANCE_TESTNET=True
```

**Optional Variables (defaults are good to start):**
```env
RANGE_LEVERAGE=7              # Default: 7x
RANGE_MIN_WIDTH=0.035         # Default: 3.5%
RANGE_MIN_QUALITY=B           # Default: B grade
RANGE_MAX_OPEN_POSITIONS=3    # Default: 3
```

### 3. Deploy
- Click "Deploy" button
- Monitor build logs (2-3 minutes)
- Wait for "healthy" status
- Check logs for startup messages

### 4. Monitor
```bash
# View logs in Coolify dashboard
# Or via Docker:
docker logs -f chimerabot_range
```

## 🎛️ Parameter Tuning Cheatsheet

**From Coolify Dashboard → Environment Tab:**

### Increase Aggressiveness
```env
RANGE_MIN_WIDTH=0.03          # 3.5% → 3.0% (more signals)
RANGE_MIN_QUALITY=C           # B → C (lower quality ok)
RANGE_LEVERAGE=10             # 7x → 10x (higher profit/loss)
RANGE_MAX_OPEN_POSITIONS=5    # 3 → 5 (more concurrent)
```

### Increase Conservativeness
```env
RANGE_MIN_WIDTH=0.04          # 3.5% → 4.0% (fewer signals)
RANGE_MIN_QUALITY=A           # B → A (only best)
RANGE_LEVERAGE=5              # 7x → 5x (safer)
RANGE_MIN_RR_RATIO=2.5        # 2.0 → 2.5 (better RR required)
```

### Debug Low Signal Rate
```env
RANGE_MIN_WIDTH=0.03          # Lower threshold
RANGE_MIN_QUALITY=C           # Accept C grade
RANGE_ALLOW_FALSE_BREAKOUTS=True  # Less strict
LOG_LEVEL=DEBUG               # More detailed logs
```

**After changing any parameter:** Click "Redeploy" in Coolify

## 📊 Expected Behavior

**Startup Logs:**
```
📊 Range Bot Configuration Loaded:
  Leverage: 7x | Margin: $10.0 | Max Positions: 3
  Min Range Width: 3.5% | Min RR: 2.0:1
  Quality Filter: B+ | HTF Confirmation: True
```

**Scan Cycle (every 5 min):**
```
🔍 Tarama başlıyor: 516 coin...
📊 BTCUSDT analiz ediliyor...
✅ Range tespit edildi: Support 91234.56, Resistance 94567.89
🟢 LONG sinyal - Kalite: B | RR: 2.4:1
✅ Pozisyon açıldı: BTCUSDT LONG @ 91500
```

**Position Monitoring:**
```
📊 Pozisyon monitörü çalışıyor...
🎯 TP vurdu! BTCUSDT LONG | PnL: +$17.50
```

## ⚠️ Important Notes

1. **Start with testnet** (`BINANCE_TESTNET=True`)
2. **Monitor first 24 hours** before increasing leverage/positions
3. **Check logs regularly** for quality of signals
4. **Track win rate** in database: `SELECT * FROM trade_history;`
5. **One parameter at a time** when tuning

## 🐛 Common Issues

**"No positions opening for hours"**
- Check logs for rejection reasons
- Lower `RANGE_MIN_WIDTH` or `RANGE_MIN_QUALITY`
- Check if false breakout filter too strict

**"Container keeps restarting"**
- Verify API keys are correct
- Check `BINANCE_TESTNET` matches your API keys
- Look for "Signature" errors in logs

**"Database locked"**
- Stop container
- Delete `data/chimerabot.db`
- Restart container (will recreate)

## 📞 Support Commands

```bash
# View live logs
docker logs -f chimerabot_range

# Check container health
docker ps | grep chimerabot_range

# Access database
docker exec -it chimerabot_range sqlite3 /app/data/chimerabot.db
SELECT * FROM open_positions;

# Restart container
docker restart chimerabot_range

# View environment
docker exec -it chimerabot_range env | grep RANGE_
```

## ✅ Current System Status

**Local Testing:**
- ✅ Bot running and scanning
- ✅ Filters working correctly
- ✅ Multi-timeframe confirmation active
- ✅ Quality grading operational
- ⏳ Waiting for first A/B quality signal

**Deployment:**
- ✅ All files committed to git
- ⏳ Ready to push to GitHub
- ⏳ Ready to deploy on Coolify

**Configuration:**
- Leverage: 7x
- Margin: $10 per trade
- Max Positions: 3
- Min Range Width: 3.5%
- Quality Filter: B+
- Min RR: 2.0:1
