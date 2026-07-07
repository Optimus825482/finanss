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


def get_default_model() -> str:
    """Ortam değişkenlerine göre varsayılan modeli belirle."""
    if os.getenv("OLLAMA_MODEL"):
        return f"ollama/{os.environ['OLLAMA_MODEL']}"
    if os.getenv("GROQ_API_KEY"):
        return "groq/llama-3.1-70b-versatile"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini/gemini-1.5-flash"
    if os.getenv("OPENAI_API_KEY"):
        return "openai/gpt-4o-mini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude-3-haiku-20240307"
    # Hiçbiri yoksa Ollama varsayılan
    return "ollama/llama3.2"


async def generate(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """LiteLLM üzerinden tamamlama."""
    litellm = _get_litellm()
    model = model or get_default_model()

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


async def get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Metin embedding'i üret. Yerel model için Ollama embedding kullanır."""
    litellm = _get_litellm()

    # Ollama embedding için fallback
    if "ollama" in model or not os.getenv("OPENAI_API_KEY"):
        return await _ollama_embed(text)

    response = await litellm.aembedding(model=model, input=text)
    return response.data[0]["embedding"]


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
