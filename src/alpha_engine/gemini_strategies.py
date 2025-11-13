# src/alpha_engine/gemini_strategies.py
"""
🤖 v11.5 GEMINI AI STRATEGIES

AI-powered signal enhancement modules:
1. News Deep Analysis
2. Market Context Detection
3. Signal Validation
4. TP/SL Optimization
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Import Gemini client
try:
    from src.alpha_engine import gemini_client
except ImportError:
    logger.warning("gemini_client not available")
    gemini_client = None


# ============================================================================
# 1. NEWS DEEP ANALYSIS
# ============================================================================

def analyze_news_with_gemini(
    headlines: List[Dict[str, Any]],
    symbol: str,
    config: object
) -> Optional[Dict[str, Any]]:
    """
    Deep news analysis using Gemini AI
    
    Args:
        headlines: List of news headlines with title/summary
        symbol: Trading symbol (e.g., 'BTCUSDT')
        config: Config object
    
    Returns:
        {
            'sentiment_score': -1 to +1,
            'long_impact': 'POSITIVE/NEGATIVE/NEUTRAL',
            'short_impact': 'POSITIVE/NEGATIVE/NEUTRAL',
            'urgency': 'HIGH/MEDIUM/LOW',
            'key_themes': ['theme1', 'theme2'],
            'summary': 'Brief explanation',
            'confidence': 0-10
        }
    """
    if not config.GEMINI_NEWS_ANALYSIS or not gemini_client.is_gemini_available():
        return None
    
    try:
        # Filter relevant headlines (last 24h)
        relevant_headlines = _filter_relevant_news(headlines, symbol, config)
        
        if not relevant_headlines:
            logger.debug(f"No relevant news for {symbol}")
            return None
        
        # Check cache first
        cache_key = f"gemini_news_{symbol}"
        cached = _get_from_cache(cache_key, config.GEMINI_NEWS_CACHE_MINUTES)
        if cached:
            logger.debug(f"Using cached Gemini news analysis for {symbol}")
            return cached
        
        # Build prompt
        headlines_text = "\n".join([
            f"• [{h.get('source', 'Unknown')}] {h.get('title', '')}"
            for h in relevant_headlines[:10]  # Max 10 headlines
        ])
        
        base_symbol = symbol.replace('USDT', '').replace('BUSD', '')
        
        prompt = f"""
EDUCATIONAL ANALYSIS ONLY - NOT INVESTMENT ADVICE
This is a cryptocurrency market analysis exercise for research purposes.

Analyze these crypto news headlines for {base_symbol}:

{headlines_text}

Provide analysis in JSON format:
{{
    "sentiment_score": -1.0 to +1.0 (negative to positive),
    "long_impact": "POSITIVE" | "NEGATIVE" | "NEUTRAL",
    "short_impact": "POSITIVE" | "NEGATIVE" | "NEUTRAL",
    "urgency": "HIGH" | "MEDIUM" | "LOW",
    "key_themes": ["theme1", "theme2"],
    "summary": "1-2 sentence summary",
    "confidence": 0-10 (how confident in this analysis)
}}

Guidelines:
- sentiment_score: Overall market sentiment (-1=very bearish, +1=very bullish)
- long_impact: How this affects LONG positions specifically
- short_impact: How this affects SHORT positions specifically
- urgency: HIGH=immediate action, MEDIUM=trend developing, LOW=background noise
- key_themes: Main topics (regulation, adoption, technical, macroeconomic, etc.)
- confidence: Higher if multiple sources agree, lower if contradictory
"""
        
        # Call Gemini
        response = gemini_client.call_gemini_api(prompt, parse_json=True, config=config)
        
        if not response:
            return None
        
        # Validate response
        result = {
            'sentiment_score': float(response.get('sentiment_score', 0.0)),
            'long_impact': response.get('long_impact', 'NEUTRAL'),
            'short_impact': response.get('short_impact', 'NEUTRAL'),
            'urgency': response.get('urgency', 'LOW'),
            'key_themes': response.get('key_themes', []),
            'summary': response.get('summary', 'No summary'),
            'confidence': float(response.get('confidence', 5.0))
        }
        
        # Clamp values
        result['sentiment_score'] = max(-1.0, min(1.0, result['sentiment_score']))
        result['confidence'] = max(0.0, min(10.0, result['confidence']))
        
        # Cache result
        _save_to_cache(cache_key, result)
        
        logger.info(f"🤖 Gemini News Analysis ({symbol}): "
                   f"Sentiment={result['sentiment_score']:.2f}, "
                   f"Long={result['long_impact']}, "
                   f"Urgency={result['urgency']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Gemini news analysis error: {e}", exc_info=True)
        return None


# ============================================================================
# 2. MARKET CONTEXT ANALYZER
# ============================================================================

def get_market_context_from_gemini(
    btc_data: Dict[str, Any],
    fear_greed: int,
    config: object
) -> Optional[Dict[str, Any]]:
    """
    Get overall market regime and strategy from Gemini
    
    Args:
        btc_data: BTC price, indicators, volume
        fear_greed: Fear & Greed Index
        config: Config object
    
    Returns:
        {
            'market_regime': 'BULL/BEAR/RANGE/VOLATILE',
            'preferred_coins': ['MAJOR', 'ALTCOIN', 'MEME'],
            'risk_appetite': 'LOW/MEDIUM/HIGH',
            'direction_bias': 'LONG_BIAS/SHORT_BIAS/NEUTRAL',
            'strategy_note': 'Brief recommendation',
            'confidence': 0-10
        }
    """
    if not config.GEMINI_MARKET_CONTEXT or not gemini_client.is_gemini_available():
        return None
    
    try:
        # Check cache
        cache_key = "gemini_market_context"
        cached = _get_from_cache(cache_key, config.GEMINI_MARKET_CONTEXT_CACHE_MINUTES)
        if cached:
            logger.debug("Using cached Gemini market context")
            return cached
        
        # Build prompt
        prompt = f"""
EDUCATIONAL MARKET ANALYSIS - NOT TRADING ADVICE
This is a cryptocurrency market research exercise for educational purposes.

Analyze current crypto market conditions:

**Bitcoin (Market Leader):**
- Price: ${btc_data.get('price', 0):,.2f}
- 24h Change: {btc_data.get('change_24h', 0):.2f}%
- RSI(14): {btc_data.get('rsi', 50):.1f}
- MACD: {'Bullish' if btc_data.get('macd_hist', 0) > 0 else 'Bearish'}
- Volume Trend: {btc_data.get('volume_trend', 'Normal')}

**Sentiment:**
- Fear & Greed Index: {fear_greed}/100 ({'Extreme Fear' if fear_greed < 25 else 'Fear' if fear_greed < 45 else 'Neutral' if fear_greed < 55 else 'Greed' if fear_greed < 75 else 'Extreme Greed'})

**Question:**
1. What's the current market regime?
2. Which coin categories should traders focus on?
3. What's the appropriate risk level?
4. Should we bias towards LONG or SHORT positions?

Respond in JSON:
{{
    "market_regime": "BULL" | "BEAR" | "RANGE" | "VOLATILE",
    "preferred_coins": ["MAJOR", "L1", "L2", "DEFI", "MEME", "AI"],
    "risk_appetite": "LOW" | "MEDIUM" | "HIGH",
    "direction_bias": "LONG_BIAS" | "SHORT_BIAS" | "NEUTRAL",
    "strategy_note": "Brief 1-2 sentence recommendation",
    "confidence": 0-10
}}

Guidelines:
- BULL: Clear uptrend, high confidence, favor LONG
- BEAR: Clear downtrend, high confidence, favor SHORT
- RANGE: Sideways, lower confidence, favor mean reversion
- VOLATILE: High volatility, be cautious
- preferred_coins: Which categories look strong (max 3)
- risk_appetite: Based on clarity and volatility
"""
        
        # Call Gemini
        response = gemini_client.call_gemini_api(prompt, parse_json=True, config=config)
        
        if not response:
            return None
        
        # Validate response
        result = {
            'market_regime': response.get('market_regime', 'RANGE'),
            'preferred_coins': response.get('preferred_coins', ['MAJOR']),
            'risk_appetite': response.get('risk_appetite', 'MEDIUM'),
            'direction_bias': response.get('direction_bias', 'NEUTRAL'),
            'strategy_note': response.get('strategy_note', 'No specific recommendation'),
            'confidence': float(response.get('confidence', 5.0))
        }
        
        # Clamp confidence
        result['confidence'] = max(0.0, min(10.0, result['confidence']))
        
        # Cache result
        _save_to_cache(cache_key, result)
        
        logger.info(f"🌍 Gemini Market Context: "
                   f"Regime={result['market_regime']}, "
                   f"Bias={result['direction_bias']}, "
                   f"Risk={result['risk_appetite']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Gemini market context error: {e}", exc_info=True)
        return None


# ============================================================================
# 3. SIGNAL VALIDATION
# ============================================================================

def validate_signal_with_gemini(
    symbol: str,
    direction: str,
    technical_data: Dict[str, Any],
    sentiment_scores: Dict[str, Any],
    confluence_score: float,
    config: object
) -> Optional[Dict[str, Any]]:
    """
    AI validation before opening position
    
    Returns:
        {
            'decision': 'APPROVED/REJECTED/CAUTION',
            'confidence': 0-10,
            'risk_level': 'LOW/MEDIUM/HIGH',
            'tp_adjustment': 0.8-1.5 (multiplier for TP),
            'sl_adjustment': 0.8-1.2 (multiplier for SL),
            'reasoning': 'Explanation'
        }
    """
    if not config.GEMINI_SIGNAL_VALIDATION or not gemini_client.is_gemini_available():
        return None
    
    try:
        base_symbol = symbol.replace('USDT', '').replace('BUSD', '')
        
        prompt = f"""
EDUCATIONAL ANALYSIS ONLY - NOT FINANCIAL ADVICE
This is a technical analysis exercise for a trading simulation system.

Validate this crypto trading signal:

**Symbol:** {base_symbol}
**Direction:** {direction}

**Technical Indicators (Multi-Timeframe):**
- Confluence Score: {confluence_score:.1f}/10.0
- 1H Trend: {technical_data.get('h1_trend', 'Unknown')}
- 15M Trend: {technical_data.get('m15_trend', 'Unknown')}
- RSI(14): {technical_data.get('rsi', 50):.1f}
- MACD: {technical_data.get('macd_status', 'Unknown')}
- EMA Alignment: {technical_data.get('ema_aligned', False)}
- ADX(14): {technical_data.get('adx', 0):.1f} (trend strength)
- Volume: {technical_data.get('volume_status', 'Normal')}

**Sentiment:**
- Fear & Greed: {sentiment_scores.get('fng_index', 50)}
- News Sentiment: {sentiment_scores.get('news_sentiment', 0):.2f}
- Reddit Sentiment: {sentiment_scores.get('reddit_sentiment', 0):.2f}

**Question:**
Should this {direction} signal be executed?

Consider:
1. Technical + sentiment alignment
2. Risk vs reward potential
3. Current market conditions
4. Optimal TP/SL sizing

Respond in JSON:
{{
    "decision": "APPROVED" | "REJECTED" | "CAUTION",
    "confidence": 0-10 (in this decision),
    "risk_level": "LOW" | "MEDIUM" | "HIGH",
    "tp_adjustment": 0.8-1.5 (1.0 = no change, >1.0 = widen TP, <1.0 = tighten TP),
    "sl_adjustment": 0.8-1.2 (1.0 = no change, >1.0 = widen SL, <1.0 = tighten SL),
    "reasoning": "Brief 1-2 sentence explanation"
}}

Guidelines:
- APPROVED: Strong alignment, high confidence
- CAUTION: Mixed signals, proceed with caution
- REJECTED: Poor setup, don't trade
- tp_adjustment: 1.2 = make TP 20% wider for high-confidence setups
- sl_adjustment: 0.9 = make SL 10% tighter if strong support/resistance
"""
        
        # Call Gemini
        response = gemini_client.call_gemini_api(prompt, parse_json=True, config=config)
        
        if not response:
            # Fallback: approve with neutral adjustments
            return {
                'decision': 'APPROVED',
                'confidence': 5.0,
                'risk_level': 'MEDIUM',
                'tp_adjustment': 1.0,
                'sl_adjustment': 1.0,
                'reasoning': 'Gemini unavailable, proceeding with default'
            }
        
        # Validate response
        result = {
            'decision': response.get('decision', 'APPROVED'),
            'confidence': float(response.get('confidence', 5.0)),
            'risk_level': response.get('risk_level', 'MEDIUM'),
            'tp_adjustment': float(response.get('tp_adjustment', 1.0)),
            'sl_adjustment': float(response.get('sl_adjustment', 1.0)),
            'reasoning': response.get('reasoning', 'No reasoning provided')
        }
        
        # Clamp values
        result['confidence'] = max(0.0, min(10.0, result['confidence']))
        result['tp_adjustment'] = max(0.8, min(1.5, result['tp_adjustment']))
        result['sl_adjustment'] = max(0.8, min(1.2, result['sl_adjustment']))
        
        logger.info(f"🤖 Gemini Signal Validation ({symbol} {direction}): "
                   f"{result['decision']}, "
                   f"Confidence={result['confidence']:.1f}, "
                   f"TP×{result['tp_adjustment']:.2f}, "
                   f"SL×{result['sl_adjustment']:.2f}")
        
        if result['decision'] != 'APPROVED':
            logger.info(f"   Reasoning: {result['reasoning']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Gemini signal validation error: {e}", exc_info=True)
        # Fallback to approval
        return {
            'decision': 'APPROVED',
            'confidence': 5.0,
            'risk_level': 'MEDIUM',
            'tp_adjustment': 1.0,
            'sl_adjustment': 1.0,
            'reasoning': 'Validation error, proceeding with default'
        }


# ============================================================================
# 4. TP/SL OPTIMIZATION (EXPERIMENTAL)
# ============================================================================

def optimize_tp_sl_with_gemini(
    symbol: str,
    atr: float,
    recent_performance: Dict[str, Any],
    config: object
) -> Optional[Dict[str, Any]]:
    """
    Get coin-specific TP/SL recommendations
    
    Returns:
        {
            'grade_a_sl_mult': 0.8-1.2,
            'grade_a_tp_mult': 0.8-1.5,
            'grade_b_sl_mult': 0.8-1.2,
            'grade_b_tp_mult': 0.8-1.5,
            'grade_c_sl_mult': 0.8-1.2,
            'grade_c_tp_mult': 0.8-1.5,
            'reasoning': 'Explanation'
        }
    """
    if not config.GEMINI_TP_SL_OPTIMIZER or not gemini_client.is_gemini_available():
        return None
    
    # TODO: Implement if needed
    # This feature is marked experimental and can be added later
    return None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

_cache_store = {}

def _filter_relevant_news(
    headlines: List[Dict[str, Any]],
    symbol: str,
    config: object
) -> List[Dict[str, Any]]:
    """Filter news relevant to symbol"""
    try:
        from src.alpha_engine.sentiment_analyzer import _get_search_terms
        search_terms = _get_search_terms(symbol, config)
    except ImportError:
        # Fallback to basic filtering
        base_symbol = symbol.replace('USDT', '').replace('BUSD', '').lower()
        search_terms = {base_symbol}
    
    relevant = []
    cutoff_time = datetime.now().timestamp() - (24 * 3600)  # Last 24h
    
    for h in headlines:
        # Check timestamp
        if h.get('published_timestamp', 0) < cutoff_time:
            continue
        
        # Check if relevant
        title = h.get('title', '').lower()
        summary = h.get('summary', '').lower()
        text = f"{title} {summary}"
        
        if any(term in text for term in search_terms):
            relevant.append(h)
    
    return relevant


def _get_from_cache(key: str, max_age_minutes: int) -> Optional[Any]:
    """Get from memory cache if not expired"""
    if key not in _cache_store:
        return None
    
    cached_data, timestamp = _cache_store[key]
    age_minutes = (datetime.now().timestamp() - timestamp) / 60
    
    if age_minutes > max_age_minutes:
        del _cache_store[key]
        return None
    
    return cached_data


def _save_to_cache(key: str, data: Any):
    """Save to memory cache"""
    _cache_store[key] = (data, datetime.now().timestamp())


# ============================================================================
# TEST MODE
# ============================================================================

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*80)
    print("🤖 GEMINI STRATEGIES TEST")
    print("="*80 + "\n")
    
    # Mock config
    class MockConfig:
        GEMINI_ENABLED = True
        GEMINI_API_KEY = "YOUR_API_KEY"
        GEMINI_MODEL = "gemini-1.5-flash"
        GEMINI_NEWS_ANALYSIS = True
        GEMINI_SIGNAL_VALIDATION = True
        GEMINI_MARKET_CONTEXT = True
        GEMINI_TP_SL_OPTIMIZER = False
        GEMINI_MAX_REQUESTS_PER_MINUTE = 15
        GEMINI_REQUEST_TIMEOUT = 30
        GEMINI_RETRY_ATTEMPTS = 2
        GEMINI_NEWS_CACHE_MINUTES = 30
        GEMINI_MARKET_CONTEXT_CACHE_MINUTES = 15
    
    config = MockConfig()
    
    # Initialize client
    print("Initializing Gemini client...")
    if not gemini_client.initialize_gemini_client(config):
        print("❌ Failed to initialize. Check API key.")
        exit(1)
    
    print("✅ Client initialized\n")
    
    # Test market context
    print("Testing market context analysis...")
    btc_data = {
        'price': 37500,
        'change_24h': 2.5,
        'rsi': 55,
        'macd_hist': 50,
        'volume_trend': 'Increasing'
    }
    
    context = get_market_context_from_gemini(btc_data, 65, config)
    if context:
        print(f"✅ Market Context: {context}")
    
    print("\n" + "="*80)
    print("✅ TEST COMPLETED")
    print("="*80 + "\n")
