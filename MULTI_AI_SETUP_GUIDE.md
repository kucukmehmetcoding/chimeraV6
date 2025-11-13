# 🤖 Multi-AI System Setup Guide (v11.6)

## Overview
ChimeraBot v11.6 introduces **multi-AI support** with automatic fallback chain:

1. **DeepSeek** (Primary) - Crypto-trained, $0.14/M tokens
2. **Groq** (Fallback) - Ultra-fast, Llama 3.1 70B, FREE tier
3. **Gemini** (Backup) - Google, FREE tier

**Why Multiple AIs?**
- **Reliability**: If one blocks crypto trading prompts, others take over
- **Cost Optimization**: Free tiers for testing, paid for production
- **Performance**: DeepSeek for accuracy, Groq for speed

---

## 🔑 Getting API Keys

### 1. DeepSeek (PRIMARY - Recommended)
1. Visit: https://platform.deepseek.com/
2. Sign up / Login
3. Go to: **API Keys** section
4. Click **Create API Key**
5. Copy key → Add to `.env`:
   ```bash
   DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
   ```

**Cost:** FREE trial credits, then $0.14/M tokens (~$0.0001 per signal)

---

### 2. Groq (FAST FALLBACK - Recommended)
1. Visit: https://console.groq.com/
2. Sign up with GitHub/Google
3. Go to: **API Keys** → **Create API Key**
4. Copy key → Add to `.env`:
   ```bash
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx
   ```

**Cost:** 100% FREE (14,400 requests/day, 30 requests/min)

---

### 3. Gemini (BACKUP - Optional)
1. Visit: https://aistudio.google.com/apikey
2. Click **Get API Key**
3. Create in **existing Google Cloud project** or **new project**
4. Copy key → Add to `.env`:
   ```bash
   GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXX
   ```

**Cost:** FREE tier (15 RPM, 1M tokens/day)

**Note:** Gemini may block crypto trading prompts (safety filters)

---

## 📝 Configuration (.env)

Add these to your `.env` file:

```bash
# ============================================================================
# 🤖 MULTI-AI SYSTEM (v11.6)
# ============================================================================

# --- Master AI Switch ---
AI_ENABLED=True
AI_PRIMARY_PROVIDER=deepseek  # deepseek, groq, or gemini

# --- DeepSeek API (PRIMARY) ---
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
DEEPSEEK_MODEL=deepseek-chat  # or deepseek-coder

# --- Groq API (FALLBACK) ---
GROQ_API_KEY=gsk-your-groq-key-here
GROQ_MODEL=llama-3.1-70b-versatile  # or mixtral-8x7b-32768

# --- Gemini API (BACKUP) ---
GEMINI_API_KEY=AIzaSy-your-gemini-key-here
GEMINI_MODEL=gemini-2.5-flash

# --- AI Features ---
AI_NEWS_ANALYSIS=True  # Deep news sentiment
AI_SIGNAL_VALIDATION=True  # Pre-signal approval
AI_MARKET_CONTEXT=True  # Market regime detection
AI_TP_SL_OPTIMIZER=False  # Dynamic TP/SL (experimental)
```

---

## ✅ Testing

Test all providers:

```bash
python -c "
from src.alpha_engine import ai_client
from src import config

# Initialize
status = ai_client.initialize_ai_clients(config)

# Check status
for provider, available in status.items():
    print(f'{provider}: {\"✅\" if available else \"❌\"}')
"
```

**Expected Output:**
```
✅ deepseek: Available
✅ groq: Available
⚠️ gemini: Available (may have safety blocks)
✅ any_available: Available
```

---

## 🚀 How It Works

### Fallback Chain
```
Signal Detected
    ↓
1. Try DeepSeek → Success ✅ → Use Result
    ↓ (fail)
2. Try Groq → Success ✅ → Use Result
    ↓ (fail)
3. Try Gemini → Success ✅ → Use Result
    ↓ (fail)
4. Default APPROVED (confidence: 5.0/10)
```

### AI Decision Output
```json
{
  "decision": "APPROVED",  // APPROVED, CAUTION, REJECTED
  "confidence": 8.5,       // 0-10 scale
  "risk_level": "MEDIUM",  // LOW, MEDIUM, HIGH
  "tp_adjustment": 1.2,    // 1.0 = no change, >1.0 = widen TP
  "sl_adjustment": 0.9,    // 1.0 = no change, <1.0 = tighten SL
  "reasoning": "Strong bullish setup with high confluence..."
}
```

---

## 💰 Cost Comparison

| Provider | Free Tier | Paid Cost | Speed | Crypto-Friendly |
|----------|-----------|-----------|-------|-----------------|
| **DeepSeek** | Trial credits | $0.14/M tokens | Medium | ✅ YES |
| **Groq** | 14.4K req/day | N/A (free only) | ⚡ Ultra-fast | ✅ YES |
| **Gemini** | 15 RPM | Free tier enough | Fast | ⚠️ May block |

**Estimated Cost (DeepSeek):**
- ~2000 tokens per validation
- 100 signals/day = 200K tokens
- Cost: **$0.028/day** (~$0.84/month)

**Recommendation:** Use **Groq free tier** for testing, **DeepSeek** for production.

---

## 🔍 Monitoring

Check AI performance in logs:

```bash
tail -f logs/chimerabot.log | grep "AI\|DeepSeek\|Groq\|Gemini"
```

**Example Log:**
```
🤖 Trying DEEPSEEK...
✅ DEEPSEEK responded successfully
   Decision: APPROVED
   Confidence: 8.5/10
   Reasoning: Strong bullish setup with RSI confirmation...
```

---

## 🛠️ Troubleshooting

### Issue: "No AI providers available"
**Solution:** Add at least one API key to `.env`

### Issue: "DeepSeek API error: 401 Unauthorized"
**Solution:** Check API key is correct and has credits

### Issue: "Groq rate limit exceeded"
**Solution:** Free tier: 30 req/min. Wait or upgrade

### Issue: "All AI providers failed"
**Solution:** Bot will continue with default APPROVED (confidence: 5.0)

---

## 🎯 Best Practices

1. **Configure All 3 Providers**: Maximum reliability
2. **Start with Groq**: 100% free for testing
3. **Monitor Costs**: DeepSeek usage in console
4. **Check Logs**: Verify AI decisions are reasonable
5. **Adjust Confidence Thresholds**: In `config.py`:
   ```python
   AI_MIN_CONFIDENCE_FOR_APPROVAL = 6.0  # Require 6+ confidence
   AI_REJECTION_THRESHOLD = 4.0  # Reject below 4.0
   ```

---

## 📊 Performance Metrics

Monitor AI decision quality:

```python
# In main_orchestrator.py logs
✅ AI Decision: APPROVED (8.5/10)
   Provider: DeepSeek
   Reasoning: Strong confluence (7.5/10) + bullish news sentiment...
```

Compare win rates:
- With AI: Track PnL of AI-approved signals
- Without AI: Track PnL of all signals

**Goal:** AI should improve win rate by 5-10%

---

## 🔗 Resources

- **DeepSeek**: https://platform.deepseek.com/
- **Groq**: https://console.groq.com/
- **Gemini**: https://aistudio.google.com/
- **Code**: `src/alpha_engine/ai_client.py`
- **Strategies**: `src/alpha_engine/gemini_strategies.py`

---

## ⚡ Quick Start (TL;DR)

```bash
# 1. Get free Groq API key
https://console.groq.com/keys

# 2. Add to .env
GROQ_API_KEY=gsk-your-key-here

# 3. Test
python -c "from src.alpha_engine import ai_client; from src import config; ai_client.initialize_ai_clients(config)"

# 4. Run bot
python -m src.main_orchestrator
```

**Done!** AI validation now active 🚀
