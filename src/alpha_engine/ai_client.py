# src/alpha_engine/ai_client.py
"""
🤖 v11.6 UNIFIED MULTI-AI CLIENT

Supports multiple AI providers with automatic fallback:
1. DeepSeek (crypto-trained, primary)
2. Groq (ultra-fast, Llama 3.1 70B)
3. Gemini (Google, backup)

Fallback chain: DeepSeek → Groq → Gemini → Default
"""

import logging
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# PROVIDER CLIENTS
# ============================================================================

_deepseek_client = None
_groq_client = None
_gemini_client = None
_active_providers = []
_request_count = 0
_last_reset_time = time.time()


def initialize_ai_clients(config: object) -> Dict[str, bool]:
    """
    Initialize all available AI providers
    
    Returns:
        {
            'deepseek': True/False,
            'groq': True/False,
            'gemini': True/False,
            'any_available': True/False
        }
    """
    global _deepseek_client, _groq_client, _gemini_client, _active_providers
    
    status = {
        'deepseek': False,
        'groq': False,
        'gemini': False,
        'any_available': False
    }
    
    if not config.AI_ENABLED:
        logger.info("🤖 AI system disabled in config")
        return status
    
    # Initialize DeepSeek
    if config.DEEPSEEK_API_KEY and config.DEEPSEEK_API_KEY != "None":
        try:
            from openai import OpenAI
            _deepseek_client = OpenAI(
                api_key=config.DEEPSEEK_API_KEY,
                base_url=config.DEEPSEEK_BASE_URL
            )
            _active_providers.append('deepseek')
            status['deepseek'] = True
            logger.info(f"✅ DeepSeek initialized: {config.DEEPSEEK_MODEL}")
        except Exception as e:
            logger.warning(f"⚠️ DeepSeek initialization failed: {e}")
    
    # Initialize Groq
    if config.GROQ_API_KEY and config.GROQ_API_KEY != "None":
        try:
            from groq import Groq
            _groq_client = Groq(api_key=config.GROQ_API_KEY)
            _active_providers.append('groq')
            status['groq'] = True
            logger.info(f"✅ Groq initialized: {config.GROQ_MODEL}")
        except Exception as e:
            logger.warning(f"⚠️ Groq initialization failed: {e}")
    
    # Initialize Gemini (legacy)
    if config.GEMINI_API_KEY and config.GEMINI_API_KEY != "None":
        try:
            from src.alpha_engine import gemini_client
            if gemini_client.initialize_gemini_client(config):
                _active_providers.append('gemini')
                status['gemini'] = True
                logger.info(f"✅ Gemini initialized: {config.GEMINI_MODEL}")
        except Exception as e:
            logger.warning(f"⚠️ Gemini initialization failed: {e}")
    
    status['any_available'] = len(_active_providers) > 0
    
    if status['any_available']:
        logger.info(f"🤖 AI Providers active: {', '.join(_active_providers)}")
        logger.info(f"   Primary: {config.AI_PRIMARY_PROVIDER}")
    else:
        logger.warning("⚠️ No AI providers available - using fallback mode")
    
    return status


def is_ai_available() -> bool:
    """Check if any AI provider is available"""
    return len(_active_providers) > 0


# ============================================================================
# UNIFIED API CALL
# ============================================================================

def call_ai_api(
    prompt: str,
    parse_json: bool = False,
    config: object = None,
    preferred_provider: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Call AI API with automatic provider fallback
    
    Args:
        prompt: The prompt to send
        parse_json: Whether to parse response as JSON
        config: Config object
        preferred_provider: Force specific provider (deepseek/groq/gemini)
    
    Returns:
        Parsed JSON dict if parse_json=True, else {'text': response_text}
        None if all providers fail
    """
    if not is_ai_available():
        logger.warning("No AI providers available")
        return None
    
    # Determine provider order
    if preferred_provider and preferred_provider in _active_providers:
        providers_to_try = [preferred_provider] + [p for p in _active_providers if p != preferred_provider]
    else:
        # Use priority order from config
        primary = config.AI_PRIMARY_PROVIDER if config else 'deepseek'
        if primary in _active_providers:
            providers_to_try = [primary] + [p for p in _active_providers if p != primary]
        else:
            providers_to_try = _active_providers.copy()
    
    # Try each provider
    for provider in providers_to_try:
        try:
            logger.debug(f"🤖 Trying {provider.upper()}...")
            
            if provider == 'deepseek':
                response = _call_deepseek(prompt, parse_json, config)
            elif provider == 'groq':
                response = _call_groq(prompt, parse_json, config)
            elif provider == 'gemini':
                response = _call_gemini(prompt, parse_json, config)
            else:
                continue
            
            if response:
                logger.info(f"✅ {provider.upper()} responded successfully")
                return response
            
        except Exception as e:
            logger.warning(f"⚠️ {provider.upper()} failed: {str(e)[:100]}")
            continue
    
    # All providers failed
    logger.error("❌ All AI providers failed")
    return None


# ============================================================================
# PROVIDER-SPECIFIC IMPLEMENTATIONS
# ============================================================================

def _call_deepseek(prompt: str, parse_json: bool, config: object) -> Optional[Dict[str, Any]]:
    """Call DeepSeek API"""
    if not _deepseek_client:
        return None
    
    try:
        # Add JSON instruction if needed
        if parse_json:
            prompt += "\n\nRespond ONLY with valid JSON. No markdown, no code blocks."
        
        response = _deepseek_client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": "You are a crypto trading analysis expert. Provide concise, actionable insights."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=config.DEEPSEEK_MAX_TOKENS,
            temperature=config.DEEPSEEK_TEMPERATURE,
            timeout=config.AI_REQUEST_TIMEOUT
        )
        
        text = response.choices[0].message.content.strip()
        
        if parse_json:
            # Clean markdown code blocks if present
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            
            result = json.loads(text)
            result['provider'] = 'deepseek'  # Add provider info
            return result
        else:
            return {'text': text, 'provider': 'deepseek'}
            
    except json.JSONDecodeError as e:
        logger.error(f"DeepSeek JSON parse error: {e}")
        logger.debug(f"Raw response: {text[:500]}")
        return None
    except Exception as e:
        logger.error(f"DeepSeek API error: {e}")
        return None


def _call_groq(prompt: str, parse_json: bool, config: object) -> Optional[Dict[str, Any]]:
    """Call Groq API"""
    if not _groq_client:
        return None
    
    try:
        # Add JSON instruction
        if parse_json:
            prompt += "\n\nRespond ONLY with valid JSON. No markdown, no code blocks."
        
        response = _groq_client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a crypto trading analysis expert. Provide concise, actionable insights."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=config.GROQ_MAX_TOKENS,
            temperature=config.GROQ_TEMPERATURE,
            timeout=config.AI_REQUEST_TIMEOUT
        )
        
        text = response.choices[0].message.content.strip()
        
        if parse_json:
            # Clean markdown
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            
            result = json.loads(text)
            result['provider'] = 'groq'  # Add provider info
            return result
        else:
            return {'text': text, 'provider': 'groq'}
            
    except json.JSONDecodeError as e:
        logger.error(f"Groq JSON parse error: {e}")
        logger.debug(f"Raw response: {text[:500]}")
        return None
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return None


def _call_gemini(prompt: str, parse_json: bool, config: object) -> Optional[Dict[str, Any]]:
    """Call Gemini API (legacy fallback)"""
    try:
        from src.alpha_engine import gemini_client
        return gemini_client.call_gemini_api(prompt, parse_json, config)
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_active_providers() -> List[str]:
    """Get list of active AI providers"""
    return _active_providers.copy()


def get_provider_status() -> Dict[str, bool]:
    """Get status of all providers"""
    return {
        'deepseek': 'deepseek' in _active_providers,
        'groq': 'groq' in _active_providers,
        'gemini': 'gemini' in _active_providers
    }
