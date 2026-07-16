"""
LLM Bridge: Model-agnostic tek arayüz. LiteLLM ile tüm sağlayıcıları destekler.
Desteklenen: Ollama (yerel), OpenAI, Claude, Gemini, Groq.
"""
import os
from typing import Optional

# LiteLLM lazy import — ilk çağrıda yüklenir
_litellm = None


def _get_litellm():
    global _litellm
    if _litellm is None:
        import litellm
        litellm.drop_params = True  # bilinmeyen parametreleri sessizce düşür
        _litellm = litellm
    return _litellm


def _has_ollama() -> bool:
    """Check if Ollama is reachable."""
    import socket
    try:
        host = os.getenv("OLLAMA_HOST", "localhost")
        port = 11434
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex((host.replace("http://", "").replace("https://", "").split(":")[0], port))
        s.close()
        return result == 0
    except Exception:
        return False


def get_default_model() -> str:
    """Ortam değişkenlerine göre varsayılan modeli belirle."""
    if os.getenv("OLLAMA_MODEL") and _has_ollama():
        return f"ollama/{os.environ['OLLAMA_MODEL']}"
    if os.getenv("GROQ_API_KEY"):
        return "groq/llama-3.1-70b-versatile"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini/gemini-1.5-flash"
    if os.getenv("OPENAI_API_KEY"):
        return "openai/gpt-4o-mini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude-3-haiku-20240307"
    # Hiçbiri yoksa None — caller handles missing LLM gracefully
    return None


async def generate(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """LiteLLM üzerinden tamamlama."""
    model = model or get_default_model()
    if model is None:
        raise RuntimeError("No LLM configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, or OLLAMA_MODEL + run Ollama.")

    litellm = _get_litellm()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


async def get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float] | None:
    """Metin embedding'i üret.

    Returns None when no embedding service is available (caller handles it gracefully).
    """
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_ollama = _has_ollama()

    if not has_openai and not has_ollama:
        return None  # Caller saves memory without embedding

    if not has_openai and has_ollama:
        return await _ollama_embed(text)

    litellm = _get_litellm()
    try:
        response = await litellm.aembedding(model=model, input=text)
        return response.data[0]["embedding"]
    except Exception:
        if has_ollama:
            return await _ollama_embed(text)
        return None


async def _ollama_embed(text: str) -> list[float]:
    """Ollama embedding (nomic-embed-text veya mxbai-embed-large)."""
    import httpx

    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{ollama_host}/api/embeddings",
            json={"model": embed_model, "prompt": text},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]


def _get_vision_model() -> Optional[str]:
    """Vision-capable model seç. Hiçbiri yoksa None döner (caller RuntimeError fırlatır).

    Öncelik: OpenAI gpt-4o-mini → Anthropic claude-3-5-sonnet → Gemini 1.5-pro
    → Ollama vision model (llava veya OLLAMA_VISION_MODEL).
    """
    if os.getenv("OPENAI_API_KEY"):
        return "openai/gpt-4o-mini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude-3-5-sonnet-20240620"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini/gemini-1.5-pro"
    if os.getenv("OLLAMA_MODEL") and _has_ollama():
        ollama_vision = os.getenv("OLLAMA_VISION_MODEL", "llava")
        return f"ollama/{ollama_vision}"
    return None


async def generate_vision(
    prompt: str,
    image_base64: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    """Vision-capable model ile görüntü analizi (LiteLLM multipart content).

    Kullanım: K-line grafik yorumu (skills.kline_chart), ekran görüntüsü analizi.
    image_base64: PNG gibi raw base64 string (data: prefix olmadan).

    Raises RuntimeError when no vision-capable model configured.
    """
    model = model or _get_vision_model()
    if model is None:
        raise RuntimeError(
            "No vision-capable model configured. Set OPENAI_API_KEY, "
            "ANTHROPIC_API_KEY, GEMINI_API_KEY, or OLLAMA_VISION_MODEL + Ollama."
        )

    litellm = _get_litellm()

    user_content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
    ]
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_content})

    response = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content
