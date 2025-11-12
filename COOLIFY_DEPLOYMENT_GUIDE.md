# ChimeraBot Coolify Deployment Guide

## 🎯 Pre-Deployment Checklist

### ✅ Completed Tasks (v11.1)
- [x] Telegram bot initialization added to main()
- [x] Docker configuration updated with all environment variables
- [x] Healthcheck improved (database connectivity test)
- [x] .env.example template created with Coolify instructions
- [x] Security review completed (API keys handled as secrets)
- [x] HTF-LTF strategy implemented and tested
- [x] Risk management optimized (SL multiplier 1.0, R:R 2.0:1)
- [x] Live monitor precision fixed
- [x] Safety mechanisms enabled (auto-close, position limits)

### ⚠️ Deployment Configuration Required

#### 1. Environment Variables (Coolify Secrets)
Set these in Coolify's Environment Variables section:

**REQUIRED - Mark as SECRET:**
- `BINANCE_API_KEY` - Your Binance API key
- `BINANCE_SECRET_KEY` - Your Binance secret key
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token (@BotFather)
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID

**REQUIRED - Production Mode:**
- `BINANCE_TESTNET=False` - ⚠️ Enables LIVE TRADING with real money
- `ENABLE_REAL_TRADING=true` - Additional safety confirmation

**OPTIONAL - Sentiment Analysis:**
- `REDDIT_CLIENT_ID` - Reddit API client ID
- `REDDIT_CLIENT_SECRET` - Reddit API secret
- `GEMINI_API_KEY` - Google Gemini API key for news sentiment

**OPTIONAL - Configuration:**
- `MAX_COINS_TO_SCAN=600` - Maximum coins to scan per cycle
- `SCAN_INTERVAL_SECONDS=300` - Scan frequency (5 minutes)
- `LOG_LEVEL=INFO` - Logging verbosity
- `DATABASE_URL=sqlite:///data/chimerabot.db` - Database connection string

#### 2. Volume Mounts
Configure these persistent volumes in Coolify:

```yaml
volumes:
  - ./data:/app/data      # Database persistence
  - ./logs:/app/logs      # Log files
```

#### 3. Healthcheck Configuration
Already configured in docker-compose.yaml:
- **Test:** Database connectivity check
- **Interval:** 60 seconds
- **Timeout:** 10 seconds
- **Retries:** 3
- **Start Period:** 30 seconds

## 🚀 Deployment Steps

### Step 1: Push to Git Repository
```bash
git add .
git commit -m "v11.1: Coolify deployment ready - Telegram fix, Docker improvements"
git push origin main
```

### Step 2: Create Coolify Application
1. Log in to your Coolify instance
2. Navigate to **Applications** → **New Application**
3. Select **Docker Compose** as application type
4. Connect your Git repository
5. Select the branch (main/master)
6. Set **Base Directory:** `/` (root of repository)

### Step 3: Configure Environment Variables
1. Go to **Environment Variables** tab
2. Add all variables from section 1 above
3. Mark sensitive variables as **SECRET**:
   - BINANCE_API_KEY
   - BINANCE_SECRET_KEY
   - TELEGRAM_BOT_TOKEN

### Step 4: Configure Volumes (CRITICAL)
1. Go to **Volumes** tab
2. Add persistent volume: `./data:/app/data`
3. Add log volume: `./logs:/app/logs`

⚠️ **WARNING:** Without volume persistence, all positions and trade history will be lost on container restart!

### Step 5: Deploy Application
1. Click **Deploy** button
2. Monitor build logs for errors
3. Wait for healthcheck to pass (green status)
4. Check logs for startup messages

### Step 6: Verify Deployment
Run verification script locally:
```bash
./verify_coolify_ready.sh
```

Check Coolify logs:
```
🤖 ChimeraBot v11.1
Database başlatılıyor...
   ✅ Database hazır
Telegram bot başlatılıyor...
   ✅ Telegram bot hazır
Trade Manager thread başlatılıyor...
   ✅ Trade Manager thread aktif
Multi-Timeframe Scanner başlatılıyor...
   ✅ Multi-Timeframe Scanner thread aktif
```

## 🔒 Security Best Practices

### API Key Management
- **NEVER** commit `.env` file to git
- Always use Coolify Secrets for sensitive data
- Verify `.gitignore` includes `.env`
- Use `.env.example` as template only

### Binance API Permissions
For production API key, enable only:
- ✅ Enable Reading
- ✅ Enable Futures (if trading futures)
- ❌ Enable Withdrawals (NEVER enable this!)
- ❌ Enable Internal Transfer (not needed)

### IP Whitelist
Configure Binance API key to accept requests only from:
- Your Coolify server IP address
- Add backup IPs if using failover

## 📊 Monitoring & Logs

### Coolify Dashboard
- **Healthcheck Status:** Green = running, Red = failed
- **Resource Usage:** CPU, Memory, Network
- **Deployment History:** Previous versions and rollback

### Log Access
View logs in Coolify:
```bash
# In Coolify terminal
tail -f /app/logs/chimerabot.log
```

Or download logs locally:
```bash
docker cp chimerabot:/app/logs/chimerabot.log ./
```

### Telegram Notifications
You should receive:
- ✅ Startup confirmation
- ✅ New position alerts (with confidence score)
- ✅ Position closed alerts (with PnL)
- ✅ Circuit breaker alerts (if daily loss > 5%)
- ✅ Error notifications (critical failures)

## 🛑 Emergency Procedures

### Stop Trading Immediately
Create emergency stop flag in container:
```bash
# In Coolify terminal
touch /app/EMERGENCY_STOP.flag
```

Or stop the container:
```bash
# In Coolify dashboard
Applications → ChimeraBot → Stop
```

### Rollback to Previous Version
1. Go to **Deployments** tab
2. Find previous successful deployment
3. Click **Redeploy**

### Check Open Positions
Access database:
```bash
# In Coolify terminal
python -c "from src.database.models import db_session, OpenPosition; db=db_session(); positions=db.query(OpenPosition).all(); print(f'Open positions: {len(positions)}'); db_session.remove()"
```

## 🧪 Testing Before Production

### Test Mode (Recommended First)
Keep these settings for initial deployment:
```env
BINANCE_TESTNET=True
ENABLE_REAL_TRADING=false
```

Monitor for 24-48 hours to verify:
- ✅ No crashes or errors
- ✅ Telegram notifications working
- ✅ Positions opening/closing correctly
- ✅ Database persistence working
- ✅ Healthcheck always green

### Switch to Production
Once confident, update environment variables:
```env
BINANCE_TESTNET=False
ENABLE_REAL_TRADING=true
```

Then **Restart** the application in Coolify.

## 📈 System Configuration (v11.1)

### Trading Strategy
- **HTF Filter (1H):** EMA50 + RSI14 + MACD → Direction
- **LTF Trigger (15M):** EMA5 x EMA20 crossover + confirmations
- **Risk Filters:** ATR < 2% + Volume > SMA20
- **Scan Frequency:** 5 minutes (~515 coins)

### Risk Management
- **Max Positions:** 15 concurrent
- **SL Multiplier:** 1.0x ATR (optimized from 1.2x)
- **TP Multiplier:** 2.0x ATR
- **Expected R:R:** 2.0:1
- **Max SL per Trade:** $2.50
- **Min TP per Trade:** $2.00
- **Auto-Close Trigger:** -50% daily drawdown

### Safety Mechanisms
- ✅ Emergency stop file monitoring
- ✅ Auto-close on circuit breaker
- ✅ Position limit enforcement
- ✅ Daily risk limits (5% max drawdown)
- ✅ Database transaction rollback on errors
- ✅ Thread-safe position management

## 🐛 Troubleshooting

### Healthcheck Failing
**Symptom:** Red status in Coolify, container keeps restarting

**Solution:**
1. Check logs for startup errors
2. Verify database directory has write permissions
3. Ensure all required environment variables are set
4. Check if migrations ran successfully

### Telegram Not Sending
**Symptom:** No notifications received

**Solution:**
1. Verify `TELEGRAM_BOT_TOKEN` is correct
2. Verify `TELEGRAM_CHAT_ID` is correct
3. Check logs for "Telegram bot hazır" message
4. Test bot manually: Send `/start` to bot

### No Positions Opening
**Symptom:** Scanner running but no signals found

**Solution:**
1. Check if `BINANCE_TESTNET` matches API keys
2. Verify API keys have correct permissions
3. Check logs for "HTF Filtered: X coins" statistics
4. Review market conditions (low volatility = fewer signals)

### Database Errors
**Symptom:** SQLAlchemy errors in logs

**Common Error:**
```
sqlite3.OperationalError: no such column: open_positions.amount
```

**Solution:**
1. **Option 1 - Clean Start (Recommended for fresh deployment):**
   ```bash
   # Set environment variable in Coolify
   FORCE_CLEAN_START=true
   ```
   Then redeploy. This will wipe old database and create fresh one.

2. **Option 2 - Manual Database Delete:**
   ```bash
   # In Coolify terminal
   rm /app/data/chimerabot.db
   ```
   Then restart container. Migration will create proper schema.

3. **Option 3 - Auto-Migration (Already Included):**
   - Entrypoint script runs `add_amount_column.py` on startup
   - Should fix schema automatically
   - If not working, check logs for migration errors

**Prevention:**
- Always use `FORCE_CLEAN_START=true` for major version upgrades
- Check migration scripts in `/app/migrations/` directory
- Verify volume mount: `./data:/app/data`

### High Memory Usage
**Symptom:** Container using >1GB RAM

**Solution:**
1. Reduce `MAX_COINS_TO_SCAN` (e.g., 300 instead of 600)
2. Increase `SCAN_INTERVAL_SECONDS` (e.g., 600 = 10 min)
3. Allocate more RAM in Coolify resource limits

## 📞 Support

For issues or questions:
1. Check logs first: `/app/logs/chimerabot.log`
2. Review this deployment guide
3. Verify all environment variables are set
4. Test in TESTNET mode first

## 🎉 Success Indicators

Your deployment is successful when you see:
- ✅ Healthcheck status: **Green** in Coolify
- ✅ Telegram message: "ChimeraBot v11.1 başlatıldı"
- ✅ Logs show: "HTF-LTF Scanner aktif"
- ✅ No error messages in logs for 10+ minutes
- ✅ Scanner statistics logged every cycle

**Current Version:** v11.1  
**Last Updated:** 2025-01-15  
**Deployment Status:** ✅ Ready for Coolify
