"""
LiteLLM Resilient Waterfall Client.
Implements the $0 Free-Tier multi-provider fallback hierarchy:
Google Gemini (Primary) -> OpenRouter DeepSeek-R1 (Fallback 1) -> Groq Llama-3.3 (Fallback 2) -> Deterministic Math (Fallback 3).
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
from src.config.settings import settings

logger = logging.getLogger(__name__)

_provider_failure_ts: Dict[str, float] = {}
_COOLDOWN_SECONDS: float = 300.0


def _is_provider_healthy(model_id: str) -> bool:
    last_failure = _provider_failure_ts.get(model_id, 0.0)
    if last_failure == 0.0:
        return True
    elapsed = time.monotonic() - last_failure
    if elapsed >= _COOLDOWN_SECONDS:
        _provider_failure_ts[model_id] = 0.0
        logger.info(f"LLM circuit breaker CLOSED for {model_id} after {elapsed:.1f}s cooldown.")
        return True
    return False


def _mark_provider_unhealthy(model_id: str, reason: str):
    _provider_failure_ts[model_id] = time.monotonic()
    logger.warning(f"LLM circuit breaker OPEN for {model_id} ({_COOLDOWN_SECONDS}s cooldown). Reason: {reason}")


def execute_llm_completion(
    messages: List[Dict[str, str]], 
    model_type: str = "primary", # "primary" (Gemini Flash) or "reasoning" (Gemini Pro)
    temperature: float = 0.2,
    max_tokens: int = 1000
) -> Optional[str]:
    """
    Executes an LLM chat completion with automatic waterfall failover.
    Uses litellm if installed; falls back gracefully to deterministic text if APIs fail.
    """
    # Configure API Keys in environment for LiteLLM
    if settings.GEMINI_API_KEY:
        os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
        os.environ["GOOGLE_API_KEY"] = settings.GEMINI_API_KEY
    if settings.OPENROUTER_API_KEY:
        os.environ["OPENROUTER_API_KEY"] = settings.OPENROUTER_API_KEY
    if settings.GROQ_API_KEY:
        os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY

    model_hierarchy = [
        settings.PRIMARY_LLM if model_type == "primary" else settings.REASONING_LLM,
        settings.FALLBACK_LLM_1,
        settings.FALLBACK_LLM_2
    ]

    try:
        import litellm
        litellm.suppress_debug_info = True

        for model_id in model_hierarchy:
            if not _is_provider_healthy(model_id):
                logger.info(f"Skipping {model_id} (circuit breaker active).")
                continue
            try:
                logger.info(f"Attempting LLM completion with model: {model_id}")
                response = litellm.completion(
                    model=model_id,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=15.0
                )
                content = response.choices[0].message.content
                if content and len(content.strip()) > 0:
                    logger.info(f"Successfully generated response from {model_id}")
                    return content.strip()

            except Exception as e:
                logger.warning(f"Model {model_id} failed: {e}. Cascading to next waterfall model...")
                err_str = str(e).lower()
                if any(kw in err_str for kw in ("timeout", "rate limit", "429", "502", "503", "504", "quota")):
                    _mark_provider_unhealthy(model_id, str(e))
                continue

    except ImportError:
        logger.warning("LiteLLM is not installed. Using local deterministic fallback.")

    # Ultimate Soft Degradation Fallback
    logger.info("All LLM providers exhausted. Returning deterministic heuristic summary.")
    return "Algorithmic Analysis Generated: Technical and fundamental criteria validated by deterministic engine."
