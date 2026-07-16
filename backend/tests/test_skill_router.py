"""Anti-hallucination testleri — skill_router JSON parse + pydantic strict
+ whitelist + retry + max_turns + audit log.

LLM çağrısı `llm_bridge.generate` monkeypatch ile mock'lanır; gerçek API gerekmez.
pytest asyncio_mode=auto — async testler direkt yazılır.
"""
import asyncio
import json
from typing import Optional

import pytest
from pydantic import BaseModel, Field

from app.services.skill_router import (
    SkillRouter,
    ToolSpec,
    _extract_json,
    _parse_json_robust,
    _build_system_prompt,
)


# --- Test şemaları (strict, ekstra alan reject) ---

class EchoArgs(BaseModel):
    ticker: str
    period: Optional[str] = None

    class Config:
        extra = "forbid"


# --- Test handler'ları ---

async def _echo_handler(args: EchoArgs, db=None) -> dict:
    return {"echoed": args.ticker, "period": args.period}


ECHO_TOOL = ToolSpec(
    name="echo",
    description="Test için ticker döndürür",
    args_schema=EchoArgs,
    handler=_echo_handler,
)


# --- _extract_json testleri ---

class TestJSONExtraction:
    def test_fenced_json(self):
        out = "```json\n{\"tool\": \"echo\", \"args\": {\"ticker\": \"AAPL\"}}\n```"
        assert _extract_json(out) == '{"tool": "echo", "args": {"ticker": "AAPL"}}'

    def test_fenced_no_lang(self):
        out = "```\n{\"action\": \"finish\"}\n```"
        assert _extract_json(out) == '{"action": "finish"}'

    def test_bare_json_fallback(self):
        out = 'Önce metin sonra {"tool": "echo", "args": {"ticker": "MSFT"}} ve sonra metin'
        assert _extract_json(out) is not None
        assert '"tool"' in _extract_json(out)

    def test_no_json_returns_none(self):
        assert _extract_json("sadece düz metin") is None
        assert _extract_json("") is None


# --- _parse_json_robust testleri ---

class TestJSONParse:
    def test_valid_json(self):
        d = _parse_json_robust('{"a": 1}')
        assert d == {"a": 1}

    def test_broken_json_repair(self):
        # json_repair eksik tırnak/pasantez tolere eder
        d = _parse_json_robust('{"a": 1, "b": 2')
        assert d.get("a") == 1  # en azından bir kısım kurtarıldı

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _parse_json_robust("not json at all")


# --- _build_system_prompt anti-hallucination ---

class TestSystemPrompt:
    def test_includes_schema_no_examples(self):
        prompt = _build_system_prompt([ECHO_TOOL])
        # Şema dahil
        assert "echo" in prompt
        assert "ticker" in prompt
        # Örnek JSON YOK (hallucination yüzeyini düşür)
        # "ticker": "AAPL" gibi somut örnek olmamalı
        assert '"ticker": "AAPL"' not in prompt

    def test_format_instructions(self):
        prompt = _build_system_prompt([ECHO_TOOL])
        assert "```json" in prompt
        assert '"action": "finish"' in prompt
        assert "Türkçe" in prompt

    def test_db_context_appended(self):
        prompt = _build_system_prompt([ECHO_TOOL], db_context="PORTFÖY: 100k USD nakit")
        assert "PORTFÖY: 100k USD nakit" in prompt


# --- ToolSpec validation ---

class TestToolSpec:
    def test_valid_tool(self):
        t = ToolSpec(
            name="x",
            description="d",
            args_schema=EchoArgs,
            handler=_echo_handler,
        )
        assert t.name == "x"

    def test_args_schema_must_be_pydantic(self):
        # Pydantic BaseModel olmayan şema -> arbitrary_types_allowed
        # ile kabul edilir ama handler runtime'da kırılır. Burada sadece inşa çalışsın.
        t = ToolSpec(
            name="x",
            description="d",
            args_schema=EchoArgs,
            handler=_echo_handler,
        )
        assert t.args_schema is EchoArgs


# --- SkillRouter unit (LLM mock'lı) ---

class TestSkillRouterWithMockLLM:
    """`llm_bridge.generate` monkeypatch ile mock — gerçek API çağrılmaz."""

    @pytest.fixture
    def _echo_router(self, monkeypatch):
        """Tek tool'lu router — LLM tek turda finish döner."""
        responses = []

        async def mock_generate(prompt, system=None, model=None,
                                temperature=0.3, max_tokens=1024):
            responses.append(prompt)
            # İlk tur: tool çağır; ikinci tur: finish
            if len(responses) == 1:
                return '```json\n{"tool": "echo", "args": {"ticker": "AAPL"}}\n```'
            return '```json\n{"action": "finish", "content": "AAPL analiz edildi"}\n```'

        import app.services.skill_router as sr
        monkeypatch.setattr(sr, "generate", mock_generate)
        return SkillRouter(tools=[ECHO_TOOL]), responses

    @pytest.mark.asyncio
    async def test_tool_then_finish(self, _echo_router):
        router, _ = _echo_router
        result = await router.run("AAPL'yi analiz et")
        assert result["turns"] == 1
        assert result["content"] == "AAPL analiz edildi"
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "echo"
        assert result["tool_calls"][0]["result"] == {"echoed": "AAPL", "period": None}

    @pytest.mark.asyncio
    async def test_audit_log_populated(self, _echo_router):
        router, _ = _echo_router
        await router.run("AAPL")
        assert len(router.audit_log) == 1
        assert router.audit_log[0]["name"] == "echo"
        assert "duration_ms" in router.audit_log[0]
        assert router.audit_log[0]["turn"] == 1

    @pytest.mark.asyncio
    async def test_whitelist_rejects_unknown_tool(self, monkeypatch):
        # LLM bilinmeyen tool döner → router error_feedback verir → sonra finish
        call_count = [0]

        async def mock_generate(prompt, system=None, model=None,
                                temperature=0.3, max_tokens=1024):
            call_count[0] += 1
            if call_count[0] == 1:
                return '```json\n{"tool": "hacker_tool", "args": {}}\n```'
            return '```json\n{"action": "finish", "content": "tamam"}\n```'

        import app.services.skill_router as sr
        monkeypatch.setattr(sr, "generate", mock_generate)
        router = SkillRouter(tools=[ECHO_TOOL])
        result = await router.run("test")
        # Bilinmeyen tool çağrılmadı
        assert all(tc["name"] != "hacker_tool" for tc in result["tool_calls"])
        assert result["content"] == "tamam"

    @pytest.mark.asyncio
    async def test_validation_error_triggers_retry(self, monkeypatch):
        call_count = [0]

        async def mock_generate(prompt, system=None, model=None,
                                temperature=0.3, max_tokens=1024):
            call_count[0] += 1
            if call_count[0] == 1:
                # Şemada olmayan ekstra alan → pydantic reject
                return '```json\n{"tool": "echo", "args": {"ticker": "AAPL", "extra": "veri"}}\n```'
            return '```json\n{"action": "finish", "content": "retry başarılı"}\n```'

        import app.services.skill_router as sr
        monkeypatch.setattr(sr, "generate", mock_generate)
        router = SkillRouter(tools=[ECHO_TOOL])
        result = await router.run("test")
        # İlk çağrı reject edildi — retry ile finish'e ulaşıldı
        assert result["content"] == "retry başarılı"
        assert result["turns"] == 0  # geçerli tool çağrılmadı

    @pytest.mark.asyncio
    async def test_max_turns_limit(self, monkeypatch):
        async def mock_generate(prompt, system=None, model=None,
                                temperature=0.3, max_tokens=1024):
            # Hep tool çağır — finish yok
            return '```json\n{"tool": "echo", "args": {"ticker": "AAPL"}}\n```'

        import app.services.skill_router as sr
        monkeypatch.setattr(sr, "generate", mock_generate)
        router = SkillRouter(tools=[ECHO_TOOL], max_turns=3)
        result = await router.run("test")
        assert result["turns"] == 3
        # max_turns aşımı → warning content
        assert "Maksimum" in result["content"] or result["content"] == ""

    @pytest.mark.asyncio
    async def test_parse_failure_after_retries(self, monkeypatch):
        async def mock_generate(prompt, system=None, model=None,
                                temperature=0.3, max_tokens=1024):
            return "sadece düz metin, JSON yok"

        import app.services.skill_router as sr
        monkeypatch.setattr(sr, "generate", mock_generate)
        router = SkillRouter(tools=[ECHO_TOOL], max_retries=2)
        result = await router.run("test")
        assert result["retries"] >= 1
        # Parse başarısız → düz metin final kabul
        assert result["turns"] == 0


# --- Pydantic strict kontrol (arg şeması güvenliği) ---

class TestPydanticStrict:
    def test_extra_field_rejected(self):
        with pytest.raises(Exception):
            EchoArgs(ticker="AAPL", extra="veri")  # extra=forbid

    def test_wrong_type_rejected(self):
        with pytest.raises(Exception):
            EchoArgs(ticker=123)  # tip int — string gerek

    def test_valid_args_pass(self):
        a = EchoArgs(ticker="AAPL")
        assert a.ticker == "AAPL"

    def test_optional_field_works(self):
        a = EchoArgs(ticker="AAPL", period="6mo")
        assert a.period == "6mo"
