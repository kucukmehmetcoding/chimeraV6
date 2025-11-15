# ChimeraBot Range Bot - Coolify Deployment Guide

## 📋 Prerequisites

- Coolify server installed and running
- Git repository connected to Coolify
- Binance API keys (Testnet or Production)
- Telegram Bot token and Chat ID

## 🚀 Deployment Steps

### 1. Create New Service in Coolify

1. Go to Coolify Dashboard
2. Click **"+ New Resource"**
3. Select **"Docker Compose"**
4. Name: `chimerabot-range`
5. Repository: Select your ChimeraBot repository
6. Branch: `main`
7. Docker Compose File: `docker-compose.range.yaml`

### 2. Configure Environment Variables

Add the following environment variables in Coolify's Environment tab:

#### Required Variables
```env
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

#### Optional Variables (with defaults)
```env
# Trading Parameters
RANGE_LEVERAGE=7
RANGE_MARGIN_PER_TRADE=10.0
RANGE_MAX_OPEN_POSITIONS=3
RANGE_SCAN_INTERVAL=300

# Range Detection
RANGE_MIN_WIDTH=0.035
RANGE_MIN_TOUCHES=3
RANGE_MAX_AGE_HOURS=168
RANGE_VOLUME_WEIGHT=0.3

# Risk Management
RANGE_MIN_SL_DISTANCE=0.008
RANGE_MIN_RR_RATIO=2.0
RANGE_MAX_POSITIONS_PER_SYMBOL=1
RANGE_SL_BUFFER=0.008
RANGE_TP_BUFFER=0.008

# Quality Filters
RANGE_MIN_QUALITY=B
RANGE_ALLOW_FALSE_BREAKOUTS=False
RANGE_MAX_FALSE_BREAKOUTS=0

# Multi-Timeframe
RANGE_USE_HTF_CONFIRMATION=True
RANGE_HTF_TIMEFRAME=1h
RANGE_HTF_MIN_OVERLAP=0.7

# System
BINANCE_TESTNET=True
LOG_LEVEL=INFO
```

### 3. Deploy

1. Click **"Deploy"** button
2. Monitor build logs for errors
3. Wait for container to start (30-60 seconds)
4. Check logs for successful initialization

## 📊 Monitoring

### View Logs
```bash
# In Coolify dashboard
Logs tab → Real-time logs

# Or via Docker
docker logs -f chimerabot_range
```

### Check Health
```bash
docker ps | grep chimerabot_range
# Should show "healthy" status after 30 seconds
```

### Database Access
```bash
# Connect to container
docker exec -it chimerabot_range /bin/bash

# View database
cd data
sqlite3 chimerabot.db
SELECT * FROM open_positions;
```

## 🔧 Parameter Tuning

You can adjust parameters directly from Coolify dashboard without code changes:

### To Change Leverage (e.g., 7x → 10x)
1. Go to Environment tab
2. Edit `RANGE_LEVERAGE=10`
3. Click **"Redeploy"**

### To Adjust Min Range Width (e.g., 3.5% → 4%)
1. Edit `RANGE_MIN_WIDTH=0.04`
2. Redeploy

### To Change Quality Filter (e.g., B → A only)
1. Edit `RANGE_MIN_QUALITY=A`
2. Redeploy

## ⚠️ Important Notes

### Testnet vs Production
- **Testnet**: Set `BINANCE_TESTNET=True` (default)
- **Production**: Set `BINANCE_TESTNET=False` and use production API keys

### Data Persistence
- Database and logs are stored in Docker volumes
- Data persists across deployments
- To reset: Stop container → Delete volumes → Redeploy

### Resource Limits
- CPU: 1.0 core max, 0.5 core reserved
- Memory: 512MB max, 256MB reserved
- Adjust in `docker-compose.range.yaml` if needed

## 🐛 Troubleshooting

### Container Won't Start
```bash
# Check logs
docker logs chimerabot_range

# Common issues:
# - Missing environment variables
# - Invalid API keys
# - Database locked (delete data/chimerabot.db)
```

### No Positions Opening
Check logs for:
- `"🔴 Kalite filtresi"` → Quality too low (D grade)
- `"❌ RR oranı yetersiz"` → Risk-reward ratio too low
- `"❌ Range genişliği yetersiz"` → Range width < MIN_RANGE_WIDTH
- `"🚫 False breakout riski"` → Too many false breakouts detected

**Solution**: Lower quality filter or min width in environment variables.

### Database Errors
```bash
# Reset database
docker exec -it chimerabot_range rm data/chimerabot.db
docker restart chimerabot_range
```

### Telegram Not Working
1. Verify `TELEGRAM_BOT_TOKEN` is correct
2. Verify `TELEGRAM_CHAT_ID` is correct (negative for groups)
3. Check bot has permission to send messages to chat
4. Test: `docker exec -it chimerabot_range python3 test_telegram.py`

## 📈 Performance Metrics

Expected behavior with current settings:
- **Scan Rate**: 516 symbols every 5 minutes
- **Signal Rate**: 1-3 quality signals per hour
- **Win Rate Target**: >60%
- **Max Drawdown**: <5% (with 3 positions @ $10 each)

## 🔄 Updating Code

1. Push changes to git repository
2. In Coolify, click **"Redeploy"**
3. Monitor build logs
4. Verify new version is running

## 📞 Support

- Check logs first: `docker logs -f chimerabot_range`
- Review recent trades: Query `trade_history` table
- Monitor position status: Query `open_positions` table
- Telegram alerts provide real-time updates

## 🎯 Optimization Tips

1. **Start Conservative**: Use default settings for first 24 hours
2. **Monitor Win Rate**: Aim for >55% before increasing leverage
3. **Quality Over Quantity**: Better to skip signals than force bad trades
4. **Track Metrics**: Check `trade_history` table daily
5. **Adjust Gradually**: Change one parameter at a time, observe for 12-24 hours
