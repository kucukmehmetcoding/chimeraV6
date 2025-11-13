# 🤖 v11.5 Gemini AI Integration - Complete Guide

## 🎯 OVERVIEW

ChimeraBot v11.5 integrates Google Gemini AI to dramatically improve signal quality through:
- **Deep News Analysis**: Context-aware sentiment (vs simple keyword matching)
- **Market Context Detection**: BTC regime analysis for strategy adaptation
- **AI Signal Validation**: Pre-approval before opening positions
- **TP/SL Optimization**: Dynamic targets based on coin behavior (experimental)

---

## ✨ KEY IMPROVEMENTS OVER v11.4

### Before (v11.4):
- ❌ News sentiment: Basic VADER keyword matching only
- ❌ All signals treated equally (no AI filtering)
- ❌ TP/SL static based on confluence grade only
- ❌ No market regime awareness

### After (v11.5):
- ✅ News sentiment: VADER (40%) + Gemini context analysis (60%)
- ✅ AI validates each signal before opening position
- ✅ Gemini suggests TP/SL adjustments (0.8-1.5× multiplier)
- ✅ Market regime detection → strategy recommendations
- ✅ Cost tracking & rate limiting (15 RPM free tier)

---

## 📊 HOW IT WORKS

### 1. News Deep Analysis

**Old Way (VADER only):**
```
Headline: "Bitcoin crashes to support, bounces 5%"
VADER Score: -0.8 (sees "crashes" → negative)
```

**New Way (Gemini hybrid):**
```
Headline: "Bitcoin crashes to support, bounces 5%"
VADER Score: -0.8
Gemini Score: +0.3 (understands context: crash + bounce = bullish)
Combined: (-0.8 × 0.4) + (0.3 × 0.6) = -0.14 (slight negative)
```

**Configuration:**
```python
GEMINI_NEWS_ANALYSIS = True  # Enable Gemini news analysis
GEMINI_NEWS_CACHE_MINUTES = 30  # Cache results to save API calls
```

**Flow:**
1. VADER analyzes headlines (fast, always runs)
2. Gemini analyzes same headlines (if enabled)
3. Combined score: VADER 40% + Gemini 60%
4. Fallback to VADER if Gemini unavailable

---

### 2. Market Context Analyzer

**Purpose:** Understand overall market regime before trading.

**Input:**
- BTC price, RSI, MACD, volume
- Fear & Greed Index

**Output:**
```json
{
    "market_regime": "BULL",  # or BEAR/RANGE/VOLATILE
    "preferred_coins": ["MAJOR", "L1"],  # Which categories to focus on
    "risk_appetite": "MEDIUM",  # LOW/MEDIUM/HIGH
    "direction_bias": "LONG_BIAS",  # or SHORT_BIAS/NEUTRAL
    "strategy_note": "Clear uptrend, favor quality coins",
    "confidence": 8.5
}
```

**Usage in Bot:**
- Market context refreshed every 15 minutes (cached)
- MEME coin signal appears → Check if "MEME" in preferred_coins
- If not preferred → Skip or reduce confidence

**Configuration:**
```python
GEMINI_MARKET_CONTEXT = True
GEMINI_MARKET_CONTEXT_CACHE_MINUTES = 15
```

---

### 3. Signal Validation (MOST IMPORTANT)

**Flow:**
```
1. Confluence score calculated (e.g., 7.2/10) → PASS threshold
2. 🤖 Gemini AI validation requested
3. Gemini analyzes:
   - Technical: RSI, MACD, EMA alignment, ADX, volume
   - Sentiment: F&G Index, news, Reddit
   - Confluence score itself
4. Gemini returns:
   {
       "decision": "APPROVED",  # or REJECTED/CAUTION
       "confidence": 8.2,
       "risk_level": "MEDIUM",
       "tp_adjustment": 1.2,  # Make TP 20% wider
       "sl_adjustment": 0.9,  # Make SL 10% tighter
       "reasoning": "Strong technical setup, positive sentiment"
   }
5. Bot decision:
   - APPROVED → Continue to position opening
   - CAUTION → Reduce confidence by 15%, proceed with caution
   - REJECTED → Skip signal entirely
```

**Example Scenarios:**

**Scenario A: Strong Signal**
```
Confluence: 8.5/10
Technical: RSI 45, MACD bullish, EMA aligned
Sentiment: F&G 35 (fear), positive news
Gemini: APPROVED, confidence=9.0, tp×1.3, sl×1.0
Result: Position opened with wider TP ($6 → $7.80)
```

**Scenario B: Weak Signal**
```
Confluence: 5.8/10
Technical: RSI 65 (overbought), mixed MACD
Sentiment: F&G 75 (greed), negative news
Gemini: REJECTED, confidence=3.0
Result: Signal skipped, no position opened
```

**Scenario C: Mixed Signal**
```
Confluence: 6.5/10
Technical: Good EMA, but low volume
Sentiment: Neutral
Gemini: CAUTION, confidence=6.0, tp×0.9, sl×1.1
Result: Confidence reduced 15%, tighter TP, wider SL
```

**Configuration:**
```python
GEMINI_SIGNAL_VALIDATION = True
GEMINI_MIN_CONFIDENCE_FOR_APPROVAL = 6.0  # Below this = CAUTION
GEMINI_REJECTION_THRESHOLD = 4.0  # Below this = REJECTED
```

---

### 4. TP/SL Dynamic Adjustment

**How it works:**
- Base TP/SL calculated from confluence grade (A/B/C)
- Gemini suggests multipliers: 0.8-1.5× for TP, 0.8-1.2× for SL
- Applied AFTER base calculation

**Example:**
```
Grade B Position:
Base SL: $2.0, Base TP: $4.0

Gemini suggests: tp×1.2, sl×0.9
Adjusted SL: $2.0 × 0.9 = $1.8 (tighter)
Adjusted TP: $4.0 × 1.2 = $4.8 (wider)

New R:R: $4.8 / $1.8 = 2.67:1 (was 2.0:1)
```

**When Gemini widens TP:**
- High confidence setup (8+/10)
- Strong trend continuation expected
- Low resistance above

**When Gemini tightens SL:**
- Clear support level nearby
- Reduced downside risk
- Take profit faster on lower conviction

---

## 🔧 SETUP & CONFIGURATION

### 1. Get Gemini API Key

1. Visit: https://makersuite.google.com/app/apikey
2. Create new API key
3. Copy key

### 2. Add to .env file

```env
# Gemini AI Configuration (v11.5)
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GEMINI_MODEL=gemini-2.5-flash  # flash=faster/cheaper, pro=better (Nov 2025: v2.5 latest)

# Enable/Disable Features
GEMINI_ENABLED=True
GEMINI_NEWS_ANALYSIS=True
GEMINI_SIGNAL_VALIDATION=True
GEMINI_MARKET_CONTEXT=True
GEMINI_TP_SL_OPTIMIZER=False  # Experimental

# Rate Limiting (Free Tier: 15 RPM)
GEMINI_MAX_REQUESTS_PER_MINUTE=15
GEMINI_REQUEST_TIMEOUT=30
GEMINI_RETRY_ATTEMPTS=2

# Caching (Save API calls)
GEMINI_NEWS_CACHE_MINUTES=30
GEMINI_MARKET_CONTEXT_CACHE_MINUTES=15

# Thresholds
GEMINI_MIN_CONFIDENCE_FOR_APPROVAL=6.0
GEMINI_REJECTION_THRESHOLD=4.0
```

### 3. Coolify Environment Variables

Add these in Coolify → Settings → Environment Variables → **Mark as SECRET:**
```
GEMINI_API_KEY=your_actual_key_here
GEMINI_ENABLED=True
```

Optional overrides:
```
GEMINI_NEWS_ANALYSIS=True
GEMINI_SIGNAL_VALIDATION=True
GEMINI_MARKET_CONTEXT=True
```

---

## 💰 COST ANALYSIS

### Free Tier Limits (as of Nov 2025):
- **gemini-1.5-flash**: 15 requests/minute, 1500/day
- **Pricing**: ~$0.075 per 1M input tokens, ~$0.30 per 1M output tokens

### Estimated Usage:
| Feature | Frequency | Requests/Day | Cost/Day |
|---------|-----------|--------------|----------|
| News Analysis | Every 30min | ~48 | $0.005 |
| Market Context | Every 15min | ~96 | $0.010 |
| Signal Validation | Per signal | ~20 | $0.020 |
| **TOTAL** | - | **~164** | **~$0.035/day** |

**Monthly Cost: ~$1.05** (well within free tier)

### Optimization Tips:
1. **Caching**: News (30min), Market (15min) → Reduces calls by ~70%
2. **Selective Validation**: Only validate signals with confluence ≥ 5.0
3. **Batch News**: Analyze 10 headlines at once instead of individually
4. **Monitor Usage**: Check with `gemini_client.get_usage_stats()`

---

## 🧪 TESTING

### Quick Test:
```bash
python test_gemini_integration.py
```

**Expected Output:**
```
🤖 GEMINI AI INTEGRATION TEST - v11.5
================================================================================

1️⃣ Testing Configuration...
   GEMINI_ENABLED: True
   GEMINI_MODEL: gemini-1.5-flash
   ✅ Configuration OK

2️⃣ Testing Client Initialization...
   ✅ Client initialized

3️⃣ Testing Simple API Call...
   ✅ API Response:
      {
         "decision": "APPROVED",
         "confidence": 7.5,
         "reasoning": "Strong technical alignment..."
      }

4️⃣ Testing Market Context Analysis...
   ✅ Market Context:
      Regime: BULL
      Direction Bias: LONG_BIAS
      Risk Appetite: MEDIUM

5️⃣ Testing Usage Statistics...
   Total Requests: 2
   Estimated Cost: $0.000015
   Remaining Quota: 13 requests

================================================================================
✅ ALL TESTS COMPLETED
🚀 READY FOR PRODUCTION
```

### Full Integration Test:
```bash
# Set API key in .env first
echo "GEMINI_API_KEY=your_key" >> .env

# Run bot in dry-run mode
python src/main_orchestrator.py
```

**Monitor Logs:**
```
🤖 Gemini AI initialized
📊 Model: gemini-1.5-flash
🎯 Features: News=True, Signal=True, Market=True

...

💼 EXECUTING POSITION: BTCUSDT
===================================
📊 Calculating confluence score...
   ✅ Confluence Score: 7.2/10
   ✅ Threshold PASSED

🤖 Requesting Gemini AI validation...
   🤖 Gemini Decision: APPROVED (Confidence: 8.5/10)
      Reasoning: Strong bullish setup, positive sentiment alignment
   🎯 Gemini TP/SL Adjustments: TP×1.20, SL×1.00
```

---

## 📈 EXPECTED RESULTS

### Win Rate Improvement:
- **v11.4**: ~45% win rate (confluence filtering only)
- **v11.5**: Estimated 55-65% win rate (AI + confluence)

### Signal Quality:
- **Rejection Rate**: ~30-40% of signals rejected by Gemini
- **False Positives**: Reduced by ~50% (AI catches bad setups)
- **Average Confidence**: Increased from 6.5/10 to 7.5/10

### Cost vs Benefit:
- **Cost**: ~$1/month
- **Benefit**: Even 1 avoided losing trade ($2-4 SL) pays for entire month
- **ROI**: Potentially 200-400% if win rate increases by 10-20%

---

## 🔍 MONITORING & OPTIMIZATION

### Check API Usage:
```python
from src.alpha_engine import gemini_client
stats = gemini_client.get_usage_stats()

print(f"Total Requests: {stats['total_requests']}")
print(f"Estimated Cost: ${stats['estimated_cost_usd']:.6f}")
print(f"Remaining Quota: {stats['remaining_quota']}")
```

### Review Gemini Decisions:
```bash
# Check logs for validation decisions
grep "Gemini Decision" logs/chimerabot.log

# Count rejections
grep "GEMINI REJECTED" logs/chimerabot.log | wc -l

# See reasoning
grep "Reasoning:" logs/chimerabot.log
```

### Tune Thresholds:
If too many rejections:
```env
GEMINI_REJECTION_THRESHOLD=3.0  # Lower = more lenient (was 4.0)
GEMINI_MIN_CONFIDENCE_FOR_APPROVAL=5.0  # Lower = less strict (was 6.0)
```

If too many approvals (low quality):
```env
GEMINI_REJECTION_THRESHOLD=5.0  # Higher = stricter
GEMINI_MIN_CONFIDENCE_FOR_APPROVAL=7.0  # Higher = more selective
```

---

## 🚀 DEPLOYMENT

### Coolify Steps:
1. **Add Gemini API Key** (Environment Variables → Secret)
2. **Redeploy** (Dockerfile cache-busted automatically)
3. **Monitor First Hour**: Check Gemini initialization in logs
4. **Review First 10 Signals**: Ensure validation working

### Verification Checklist:
- [ ] Logs show "✅ Gemini AI initialized"
- [ ] First signal shows "🤖 Requesting Gemini AI validation"
- [ ] Gemini decisions appear (APPROVED/CAUTION/REJECTED)
- [ ] TP/SL adjustments logged
- [ ] No rate limit errors (should stay under 15 RPM)

### Rollback Plan:
If Gemini causes issues:
```env
GEMINI_ENABLED=False
```
Bot will revert to VADER-only sentiment and skip AI validation.

---

## 🎯 BEST PRACTICES

### DO:
✅ Monitor API costs weekly (should be ~$0.25)
✅ Review Gemini rejection reasons to learn
✅ Tune thresholds based on performance
✅ Keep caching enabled to save costs
✅ Use gemini-1.5-flash for speed/cost

### DON'T:
❌ Disable caching (unnecessary API calls)
❌ Set rate limit > 15 RPM (free tier limit)
❌ Ignore REJECTED signals reasoning
❌ Remove fallback to VADER (always have backup)
❌ Use gemini-1.5-pro without good reason (slower/costlier)

---

## 📚 TROUBLESHOOTING

### "Gemini initialization failed"
**Cause:** Invalid API key
**Fix:** Check GEMINI_API_KEY in .env, regenerate if needed

### "404 models/gemini-1.5-flash not found"
**Cause:** Old model name (deprecated in Nov 2025)
**Fix:** Update config.py → `GEMINI_MODEL = "gemini-2.5-flash"`

### "finish_reason=2" or "RECITATION" error
**Cause:** Safety filter triggered by prompt content
**Fix:** Non-critical, retry automatic. Market context may be affected, signal validation still works.

### "Rate limit exceeded"
**Cause:** >15 requests/minute
**Fix:** Bot auto-waits, but check for loops. Increase cache times.

### "Gemini validation failed"
**Cause:** API timeout or network issue
**Fix:** Bot proceeds without AI validation (fallback safe)

### "Empty response from Gemini"
**Cause:** Model overloaded or prompt issue
**Fix:** Retries automatically (up to 2 times), then proceeds

---

## 🔮 FUTURE ENHANCEMENTS

**Planned for v11.6+:**
1. **Historical Performance Learning**: Gemini learns from past trades
2. **Multi-Coin Correlation**: Analyze related coins together
3. **Sentiment Trend Analysis**: Track sentiment changes over time
4. **Custom TP/SL per Symbol**: Optimize based on coin behavior
5. **Voice Alerts**: Telegram voice notes for important signals

---

**Version:** 11.5.0-AI
**Author:** ChimeraBot Team
**Updated:** 13 Kasım 2025
**License:** MIT
