"""Custom JSON Tool Router — anti-hallucination design.

LLM'nin tool çağırması için sağlam JSON router. LiteLLM native tool-call yerine
custom JSON şema + pydantic strict validation + retry + whitelist. Zayıf modellerde
(llama3.2, haiku) kırılmadan çalışır.

Anti-hallucination önlemleri:
1. Prompt'ta örnek JSON YOK (LLM kopyalayıp hallucinate etmesin).
2. Pydantic strict=True (ekstra alan reject, tip coerzion yok).
3. Whitelist: tool adı registry'de tam eşleşme olmalı.
4. Retry: sadece parse/validation hatasında, error feedback ile (LLM hatayı görür).
5. max_turns + max_retries sonsuz döngüyü engeller.
6. Handler'lar sadece okuma/DB-yazma yapar, asla kod execute etmez.
7. Audit log her çağrıyı kaydeder (debugging).

LLM çıktı formatı (fenced ```json):
  {"tool": "analyze_stock", "args": {"ticker": "AAPL"}}
ya da final:
  {"action": "finish", "content": "Sonuç metni..."}
"""
import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, ValidationError

from app.services.llm_bridge import generate

logger = logging.getLogger(__name__)

# Fenced ```json ... ``` bloğu için regex (en spesifik önce)
_FENCED_RE = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)
# Fallback: bare {.*?} (non-greedy — birden çok JSON objesi varsa ilk alır)
_BARE_RE = re.compile(r"\{[\s\S]*?\}")


class ToolSpec(BaseModel):
    """Router'a kayıtlı bir tool — isim, açıklama, strict args şeması, async handler.

    args_schema: pydantic BaseModel sınıfı (instance değil). Router bununla validate eder.
    handler: async callable (args dict + opsiyonel db alır) → dict (JSON-serializable).
    """
    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Callable[..., Awaitable[dict]]

    class Config:
        arbitrary_types_allowed = True


def _extract_json(text: str) -> Optional[str]:
    """LLM çıktısından JSON bloğu çıkar — önce fenced, fallback bare."""
    if not text:
        return None
    m = _FENCED_RE.search(text)
    if m:
        return m.group(1)
    m = _BARE_RE.search(text)
    if m:
        return m.group(0)
    return None


def _parse_json_robust(raw: str) -> dict:
    """json_repair ile tolere ederek parse. Hata → raise."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json
            repaired = repair_json(raw, return_objects=True)
            if isinstance(repaired, dict):
                return repaired
        except Exception:
            pass
        raise ValueError(f"JSON parse başarısız: {raw[:200]!r}")


def _build_system_prompt(tools: list[ToolSpec], db_context: Optional[str] = None) -> str:
    """Sistem promptu — sadece tool şemaları + format talimatı.

    Örnek JSON YOK → LLM kopyalayıp hallucinate etmesin.
    """
    lines = [
        "Sen bir finans analiz asistanısın. Aşağıdaki tool'ları çağırabilirsin.",
        "",
        "## Tool Şemaları",
        "",
    ]
    for t in tools:
        schema = t.args_schema.model_json_schema()
        lines.append(f"### {t.name}")
        lines.append(f"Açıklama: {t.description}")
        lines.append(f"Arg şeması (JSON Schema): {json.dumps(schema, ensure_ascii=False, indent=2)}")
        lines.append("")

    lines.extend([
        "## Çıktı Formatı (ZORUNLU)",
        "",
        "Her cevapta SADECE aşağıdaki iki formattan birini ver, ```json fenced blok içinde:",
        "",
        "Tool çağırma:",
        '```json',
        '{"tool": "<tool_adı>", "args": {<şemaya uygun argümanlar>}}',
        '```',
        "",
        "Final cevap (tool kalmadığında):",
        '```json',
        '{"action": "finish", "content": "<kullanıcıya Türkçe final metni>"}',
        '```',
        "",
        "## Kurallar",
        "- Şemada olmayan ekstra alan ekleme (reject edilir).",
        "- Argüman tiplerine uy (string için string, float için sayı).",
        "- Hiçbir değeri uydurma; veri yoksa '暂缺' veya 'veri yok' işaretle.",
        "- Final metin Türkçe olmalı.",
        "",
    ])
    if db_context:
        lines.append("## Bağlam")
        lines.append(db_context)
    return "\n".join(lines)


class SkillRouter:
    """Custom JSON tool router — anti-hallucination döngü."""

    def __init__(
        self,
        tools: list[ToolSpec],
        model: Optional[str] = None,
        max_turns: int = 5,
        max_retries: int = 2,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ):
        if not tools:
            raise ValueError("tools boş olamaz")
        self._tools = {t.name: t for t in tools}
        self._tool_list = tools
        self.model = model
        self.max_turns = max_turns
        self.max_retries = max_retries
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.audit_log: list[dict] = []

    async def run(
        self,
        user_prompt: str,
        system: Optional[str] = None,
        db=None,
        db_context: Optional[str] = None,
    ) -> dict:
        """Multi-turn tool çağırma döngüsü.

        Returns:
            {
                "content": final_text,
                "tool_calls": [{"name","args","result","duration_ms"}],
                "turns": int,
                "retries": int,
            }
        """
        system_prompt = system or _build_system_prompt(self._tool_list, db_context=db_context)
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        tool_calls: list[dict] = []
        total_retries = 0
        final_content = ""

        for turn in range(1, self.max_turns + 1):
            # LLM'ye tüm history ver (conversation context)
            prompt_for_call = messages[-1]["content"] if len(messages) == 2 else None
            # Basit yaklaşım: her turda tüm history'yi tek user message olarak birleştir
            history_text = "\n\n".join(
                m["content"] if isinstance(m["content"], str) else json.dumps(m["content"], ensure_ascii=False)
                for m in messages[1:]  # system hariç
            )

            attempt = 0
            parsed = None
            error_feedback = None
            while attempt <= self.max_retries:
                user_msg = history_text if not error_feedback else f"{history_text}\n\nÖnceki hata: {error_feedback}\n\nLütfen tekrar dene."
                response = await generate(
                    prompt=user_msg,
                    system=system_prompt,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )

                raw = _extract_json(response)
                if raw is None:
                    error_feedback = f"Çıktıda JSON bulunamadı. Çıktı: {response[:300]!r}"
                    attempt += 1
                    total_retries += 1
                    continue

                try:
                    parsed = _parse_json_robust(raw)
                    break
                except ValueError as e:
                    error_feedback = f"JSON parse hatası: {e}"
                    attempt += 1
                    total_retries += 1
                    continue

            if parsed is None:
                # Tüm retry'ler başarısız — final content olarak son response'u al
                logger.warning(
                    "skill_router: parse failed after %d retries on turn %d. Response: %r",
                    attempt, turn, response[:300],
                )
                final_content = response
                break

            # Finish?
            if parsed.get("action") == "finish":
                final_content = parsed.get("content", "")
                break

            # Tool call?
            tool_name = parsed.get("tool")
            args = parsed.get("args", {})

            if tool_name is None:
                # Ne tool ne finish — final content kabul et
                final_content = response
                logger.warning("skill_router: turn %d — no tool/finish, treating as final", turn)
                break

            # Whitelist kontrolü
            tool = self._tools.get(tool_name)
            if tool is None:
                error_feedback = f"Bilinmeyen tool: {tool_name!r}. Mevcut tool'lar: {list(self._tools.keys())}"
                messages.append({"role": "user", "content": user_msg if False else f"Önceki hata: {error_feedback}"})
                continue

            # Pydantic strict validate
            try:
                validated = tool.args_schema.model_validate(args)
            except ValidationError as e:
                error_feedback = f"Tool {tool_name} arg validation hatası: {e}"
                messages.append({
                    "role": "user",
                    "content": f"Önceki hata: {error_feedback}. Lütfen şemaya uygun tekrar dene.",
                })
                continue

            valid_args = validated.model_dump(exclude_none=True)

            # Handler çağır (sync handler'lar asyncio.to_thread ile sar).
            # Handler pydantic instance alır (strict tip); audit log için args dict tutulur.
            import time as _time
            t0 = _time.perf_counter()
            try:
                handler = tool.handler
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(validated, db=db) if _handler_takes_db(handler) else await handler(validated)
                else:
                    fn = lambda: handler(validated, db=db) if _handler_takes_db(handler) else handler(validated)
                    result = await asyncio.to_thread(fn)
            except Exception as e:
                logger.exception("skill_router: handler %s failed", tool_name)
                result = {"error": f"Tool {tool_name} çalıştırma hatası: {e}"}

            duration_ms = (_time.perf_counter() - t0) * 1000
            call_record = {
                "name": tool_name,
                "args": valid_args,
                "result": result,
                "duration_ms": round(duration_ms, 1),
            }
            tool_calls.append(call_record)
            self.audit_log.append({**call_record, "turn": turn})

            # Tool sonucunu conversation'a ekle — LLM görüp devam etsin
            messages.append({
                "role": "user",
                "content": f"Tool {tool_name} sonucu:\n```json\n{json.dumps(result, ensure_ascii=False, default=str)[:2000]}\n```\n\nDevam et veya finish.",
            })

        else:
            # max_turns aşıldı — son content yok, audit log warning
            logger.warning("skill_router: max_turns (%d) aşıldı", self.max_turns)
            final_content = final_content or "Maksimum tur sayısına ulaşıldı, sonuç eksik."

        return {
            "content": final_content,
            "tool_calls": tool_calls,
            "turns": len(tool_calls),
            "retries": total_retries,
        }


def _handler_takes_db(handler: Callable) -> bool:
    """Handler'ın imzasında db parametresi var mı kontrol et."""
    import inspect
    try:
        sig = inspect.signature(handler)
        return "db" in sig.parameters
    except (ValueError, TypeError):
        return False
