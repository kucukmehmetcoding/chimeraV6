# src/alpha_engine/gemini_client.py
"""
Google Gemini AI Client for ChimeraBot v11.5

Provides AI-enhanced signal validation with:
- Deep news sentiment analysis
- Market context awareness  
- Signal pre-approval system
- TP/SL optimization suggestions
"""

import time
import json
import logging
from typing import Optional, Dict, Any
import threading

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    HarmCategory = None
    HarmBlockThreshold = None

import logging
import time
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)

# Global rate limiter
class RateLimiter:
    """Thread-safe rate limiter for Gemini API"""
    def __init__(self, max_requests_per_minute: int):
        self.max_requests = max_requests_per_minute
        self.requests = []
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Block if rate limit exceeded"""
        with self.lock:
            now = time.time()
            # Remove requests older than 1 minute
            self.requests = [r for r in self.requests if now - r < 60]
            
            if len(self.requests) >= self.max_requests:
                # Wait until oldest request expires
                sleep_time = 60 - (now - self.requests[0]) + 0.1
                if sleep_time > 0:
                    logger.warning(f"⏳ Gemini rate limit reached. Waiting {sleep_time:.1f}s...")
                    time.sleep(sleep_time)
                    # Clean up after wait
                    now = time.time()
                    self.requests = [r for r in self.requests if now - r < 60]
            
            # Record this request
            self.requests.append(time.time())
    
    def get_remaining_quota(self) -> int:
        """Get remaining requests in current minute"""
        with self.lock:
            now = time.time()
            self.requests = [r for r in self.requests if now - r < 60]
            return self.max_requests - len(self.requests)


# Global instances
_gemini_model = None
_rate_limiter = None
_request_count = 0
_last_reset_time = time.time()


def initialize_gemini_client(config: object) -> bool:
    """
    Initialize Gemini API client
    
    Returns:
        True if successful, False if disabled or invalid API key
    """
    global _gemini_model, _rate_limiter
    
    if not config.GEMINI_ENABLED:
        logger.info("🤖 Gemini AI disabled in config")
        return False
    
    if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == "None":
        logger.warning("⚠️ Gemini API key not found. AI features disabled.")
        return False
    
    try:
        import google.generativeai as genai
        
        # Configure API
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        # Initialize model
        model_name = config.GEMINI_MODEL
        _gemini_model = genai.GenerativeModel(model_name)
        
        # Initialize rate limiter
        _rate_limiter = RateLimiter(config.GEMINI_MAX_REQUESTS_PER_MINUTE)
        
        logger.info(f"✅ Gemini AI initialized: {model_name}")
        logger.info(f"   Rate limit: {config.GEMINI_MAX_REQUESTS_PER_MINUTE} RPM")
        logger.info(f"   Features: News={config.GEMINI_NEWS_ANALYSIS}, "
                   f"Signal={config.GEMINI_SIGNAL_VALIDATION}, "
                   f"Market={config.GEMINI_MARKET_CONTEXT}, "
                   f"TPSL={config.GEMINI_TP_SL_OPTIMIZER}")
        
        return True
        
    except ImportError:
        logger.error("❌ google-generativeai package not installed!")
        logger.error("   Install: pip install google-generativeai")
        return False
    except Exception as e:
        logger.error(f"❌ Gemini initialization failed: {e}", exc_info=True)
        return False


def is_gemini_available() -> bool:
    """Check if Gemini client is ready"""
    return _gemini_model is not None


def call_gemini_api(
    prompt: str,
    parse_json: bool = True,
    config: object = None,
    retry_count: int = 0
) -> Optional[Dict[str, Any]]:
    """
    Call Gemini API with rate limiting and error handling
    
    Args:
        prompt: User prompt
        parse_json: Extract JSON from response
        config: Config object for retry settings
        retry_count: Internal retry counter
    
    Returns:
        Parsed JSON dict or raw text
    """
    global _request_count
    
    if not is_gemini_available():
        logger.warning("Gemini not available, skipping API call")
        return None
    
    # Get config values
    if config is None:
        try:
            from src import config as default_config
            config = default_config
        except ImportError:
            logger.error("Config not available for Gemini call")
            return None
    
    max_retries = config.GEMINI_RETRY_ATTEMPTS
    timeout = config.GEMINI_REQUEST_TIMEOUT
    
    try:
        # Rate limiting
        _rate_limiter.wait_if_needed()
        
        # Track usage
        _request_count += 1
        
        # Log request (truncate long prompts)
        prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        logger.debug(f"🤖 Gemini request #{_request_count}: {prompt_preview}")
        
        # Generate response with safety settings
        start_time = time.time()
        
        # Safety settings: BLOCK_NONE for all categories (crypto trading content)
        # Use proper enums from google.generativeai.types
        safety_settings = [
            {
                "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                "threshold": HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                "threshold": HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                "threshold": HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                "threshold": HarmBlockThreshold.BLOCK_NONE
            },
        ]
        
        response = _gemini_model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.3,  # Low temperature for consistent output
                'top_p': 0.95,
                'top_k': 40,
                'max_output_tokens': 1024,
            },
            safety_settings=safety_settings
        )
        
        elapsed = time.time() - start_time
        logger.debug(f"   Response time: {elapsed:.2f}s")
        
        # Extract text with safety check
        if not hasattr(response, 'text'):
            logger.warning(f"⚠️ Gemini response blocked (finish_reason: {response.candidates[0].finish_reason})")
            logger.warning(f"   Safety ratings: {response.candidates[0].safety_ratings}")
            
            # Return fallback for safety blocks
            if parse_json:
                return {
                    'decision': 'APPROVED',  # Default to approval when blocked
                    'confidence': 6.0,
                    'reasoning': 'Safety filter triggered, defaulting to technical analysis only'
                }
            return None
        
        if not response.text:
            logger.warning("Empty response from Gemini")
            return None
        
        response_text = response.text.strip()
        
        # Parse JSON if requested
        if parse_json:
            parsed = parse_json_from_response(response_text)
            if parsed:
                logger.debug(f"   Parsed JSON: {list(parsed.keys())}")
                return parsed
            else:
                logger.warning("Failed to parse JSON from Gemini response")
                return {'raw_text': response_text}
        else:
            return {'raw_text': response_text}
        
    except Exception as e:
        error_msg = str(e).lower()
        
        # Rate limit error
        if '429' in error_msg or 'quota' in error_msg or 'rate limit' in error_msg:
            logger.warning(f"⏳ Gemini rate limit hit. Waiting 60s...")
            time.sleep(60)
            
            if retry_count < max_retries:
                return call_gemini_api(prompt, parse_json, config, retry_count + 1)
            else:
                logger.error("Max retries exceeded for rate limit")
                return None
        
        # Other errors
        elif retry_count < max_retries:
            logger.warning(f"Gemini error (retry {retry_count + 1}/{max_retries}): {e}")
            time.sleep(2 ** retry_count)  # Exponential backoff
            return call_gemini_api(prompt, parse_json, config, retry_count + 1)
        else:
            logger.error(f"❌ Gemini API call failed: {e}", exc_info=True)
            return None


def parse_json_from_response(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from Gemini response text
    
    Handles:
    - Pure JSON
    - JSON in markdown code blocks
    - JSON with extra text before/after
    """
    try:
        # Try direct parse first
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try extracting from code blocks
    code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(code_block_pattern, text, re.DOTALL)
    
    if matches:
        try:
            return json.loads(matches[0])
        except json.JSONDecodeError:
            pass
    
    # Try finding JSON object in text
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_pattern, text, re.DOTALL)
    
    for match in matches:
        try:
            parsed = json.loads(match)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    
    logger.warning("Could not extract JSON from Gemini response")
    logger.debug(f"Response text: {text[:200]}")
    return None


def get_usage_stats() -> Dict[str, Any]:
    """Get Gemini API usage statistics"""
    global _request_count, _last_reset_time
    
    elapsed_hours = (time.time() - _last_reset_time) / 3600
    rpm_actual = _request_count / (elapsed_hours * 60) if elapsed_hours > 0 else 0
    
    # Gemini pricing (approximate, as of Nov 2025)
    # flash: $0.075 per 1M input tokens, $0.30 per 1M output tokens
    # Avg estimate: ~500 tokens input, ~200 tokens output per request
    estimated_cost = _request_count * ((500 * 0.075 + 200 * 0.30) / 1_000_000)
    
    return {
        'total_requests': _request_count,
        'elapsed_hours': elapsed_hours,
        'avg_rpm': rpm_actual,
        'estimated_cost_usd': estimated_cost,
        'remaining_quota': _rate_limiter.get_remaining_quota() if _rate_limiter else 0
    }


def reset_usage_stats():
    """Reset usage counter (for testing or new day)"""
    global _request_count, _last_reset_time
    _request_count = 0
    _last_reset_time = time.time()
    logger.info("🔄 Gemini usage stats reset")


# ============================================================================
# TEST MODE
# ============================================================================

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*80)
    print("🤖 GEMINI CLIENT TEST")
    print("="*80 + "\n")
    
    # Mock config for testing
    class MockConfig:
        GEMINI_ENABLED = True
        GEMINI_API_KEY = "YOUR_API_KEY_HERE"  # Replace with real key
        GEMINI_MODEL = "gemini-1.5-flash"
        GEMINI_MAX_REQUESTS_PER_MINUTE = 15
        GEMINI_REQUEST_TIMEOUT = 30
        GEMINI_RETRY_ATTEMPTS = 2
    
    config = MockConfig()
    
    # Test 1: Initialization
    print("\n1️⃣ Testing Gemini initialization...")
    success = initialize_gemini_client(config)
    
    if not success:
        print("❌ Initialization failed. Set GEMINI_API_KEY in MockConfig.")
        exit(1)
    
    print("✅ Initialization successful\n")
    
    # Test 2: Simple API call
    print("2️⃣ Testing simple API call (JSON parsing)...")
    prompt = """
    Analyze this crypto signal:
    - Symbol: BTCUSDT
    - Direction: LONG
    - RSI: 45
    - MACD: Bullish
    
    Return JSON:
    {
        "decision": "APPROVED" or "REJECTED",
        "confidence": 0-10,
        "reasoning": "brief explanation"
    }
    """
    
    result = call_gemini_api(prompt, parse_json=True, config=config)
    
    if result:
        print(f"✅ Response received:")
        print(json.dumps(result, indent=2))
    else:
        print("❌ API call failed")
    
    # Test 3: Usage stats
    print("\n3️⃣ Testing usage stats...")
    stats = get_usage_stats()
    print(f"✅ Stats:")
    print(f"   Requests: {stats['total_requests']}")
    print(f"   Estimated cost: ${stats['estimated_cost_usd']:.6f}")
    print(f"   Remaining quota: {stats['remaining_quota']}")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS COMPLETED")
    print("="*80 + "\n")
