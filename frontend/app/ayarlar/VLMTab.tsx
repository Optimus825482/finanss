"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL;

const SUGGESTIONS = [
  "openai/gpt-4o-mini",
  "openai/gpt-4o",
  "anthropic/claude-3-5-sonnet-20240620",
  "gemini/gemini-1.5-pro",
  "ollama/llava",
  "ollama/llama3.2-vision",
];

export default function VLMTab() {
  const [vlmModel, setVlmModel] = useState("");
  const [configured, setConfigured] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = async () => {
    try {
      const res = await fetch(`${API}/api/admin/vlm-config`);
      if (res.ok) {
        const data = await res.json();
        setConfigured(data.vlm_model);
        if (!vlmModel && data.vlm_model) setVlmModel(data.vlm_model);
      }
    } catch { /* */ }
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!vlmModel.trim()) return;
    try {
      await fetch(`${API}/api/admin/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          key: "vlm_model",
          value: vlmModel.trim(),
          description: "K-line grafik analizi için VLM modeli (liteLLM formatı)",
        }),
      });
      setMsg("✅ VLM modeli kaydedildi");
      await load();
      setTimeout(() => setMsg(null), 3000);
    } catch {
      setMsg("✗ Kaydetme başarısız");
    }
  };

  const borderStyle = { borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" };
  const muted = { color: "var(--term-muted)" };

  return (
    <div className="space-y-6">
      <div className="rounded-sm p-4" style={borderStyle}>
        <div className="font-mono text-sm font-semibold mb-1" style={{ color: "var(--term-text)" }}>
          VLM MODEL SEÇİMİ
        </div>
        <p className="text-xs font-mono mb-4" style={muted}>
          K-line grafik analizinde (skills/kline_chart) kullanılacak vision-capable LLM modeli.
          LiteLLM formatında gir: <code style={{ color: "var(--term-amber)" }}>provider/model</code>
        </p>

        {/* Mevcut config */}
        {configured && (
          <div className="mb-4 p-2 rounded-sm text-xs font-mono" style={{ backgroundColor: "var(--term-bg)", color: "var(--term-green)" }}>
            Aktif: {configured}
          </div>
        )}

        {/* Text input */}
        <div className="mb-3">
          <div className="text-[10px] font-mono tracking-wider mb-1.5" style={muted}>MODEL (LITELLM FORMAT)</div>
          <input
            type="text"
            value={vlmModel}
            onChange={(e) => setVlmModel(e.target.value)}
            placeholder="openai/gpt-4o-mini"
            className="w-full rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
            style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }}
          />
        </div>

        {/* Hazır öneriler */}
        <div className="text-[10px] font-mono tracking-wider mb-1.5" style={muted}>HAZIR ÖNERİLER</div>
        <div className="flex flex-wrap gap-2 mb-4">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setVlmModel(s)}
              className="font-mono text-[11px] px-2.5 py-1 rounded-sm transition-none"
              style={{
                border: "1px solid var(--term-border)",
                backgroundColor: vlmModel === s ? "var(--term-border)" : "var(--term-bg)",
                color: vlmModel === s ? "var(--term-amber)" : "var(--term-muted)",
              }}
            >
              {s}
            </button>
          ))}
        </div>

        <button
          onClick={save}
          disabled={!vlmModel.trim()}
          className="font-mono text-xs px-4 py-2 rounded-sm transition-none disabled:opacity-40"
          style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}
        >
          KAYDET
        </button>
        {msg && <div className="text-xs font-mono mt-2" style={{ color: msg.startsWith("✅") ? "var(--term-green)" : "var(--term-red)" }}>{msg}</div>}
      </div>

      {/* Bilgi kartı */}
      <div className="rounded-sm p-4" style={borderStyle}>
        <div className="font-mono text-xs font-semibold mb-2" style={{ color: "var(--term-text)" }}>
          VLM NEDİR?
        </div>
        <p className="text-xs font-mono" style={muted}>
          Vision-Language Model — grafik/screenshot gibi görüntüleri analiz edebilen LLM.
          K-line mum grafiğini VLM'e gönderir, pattern (doji/hammer/engulfing) + kısa vadeli görünüm döner.
          VLM yapılandırılmazsa metin teknik analiz fallback kullanılır.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] font-mono">
          <div style={{ color: "var(--term-green)" }}>✓ OpenAI: gpt-4o, gpt-4o-mini</div>
          <div style={{ color: "var(--term-green)" }}>✓ Anthropic: claude-3-5-sonnet</div>
          <div style={{ color: "var(--term-green)" }}>✓ Gemini: 1.5-pro, 1.5-flash</div>
          <div style={{ color: "var(--term-green)" }}>✓ Ollama: llava, llama3.2-vision</div>
        </div>
      </div>
    </div>
  );
}
