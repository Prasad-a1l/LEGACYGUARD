from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .config import GEMINI_API_KEY

_model = None
_pool = ThreadPoolExecutor(max_workers=2)


def _model_client():
    global _model
    if _model is not None:
        return _model
    if not GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel("gemini-2.0-flash")
        return _model
    except Exception:
        return None


def llm_complete(prompt: str, fallback: str) -> str:
    """Real Gemini call when configured; otherwise return structured fallback.

    The harness still executes either way. LLM text never becomes FACT memory.
    """
    model = _model_client()
    if not model:
        return fallback

    def _call() -> str:
        result = model.generate_content(prompt[:4000])
        return ((result.text or "").strip() or fallback)

    try:
        return _pool.submit(_call).result(timeout=18)
    except Exception:
        return fallback


def llm_available() -> bool:
    return _model_client() is not None
