"use client";

import { useEffect, useState } from "react";

interface Provider { id: number; name: string; slug: string; base_url: string; is_active: boolean }
interface Model { id: number; provider_id: number; model_id: string; display_name: string; supports_chat: boolean; supports_embedding: boolean }
interface VLMConfig { vlm_model?: string | null; configured: boolean }

const API = process.env.NEXT_PUBLIC_API_URL;

export default function VLMTab() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [config, setConfig] = useState<VLMConfig | null>(null);
  const [selectedModel, setSelectedModel] = useState("");
  const [testResult, setTestResult] = useState<{ ok: boolean; response?: string; error?: string } | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = async () => {
    try {
      const [pRes, mRes, cRes] = await Promise.all([
        fetch(`${API}/api/admin/providers`),
        fetch(`${API}/api/admin/models`),
        fetch(`${API}/api/admin/vlm-config`),
      ]);
      if (pRes.ok) setProviders(await pRes.json());
      if (mRes.ok) setModels(await mRes.json());
      if (cRes.ok) {
        const data = await cRes.json();
        setConfig(data);
        if (data.vlm_model) setSelectedModel(data.vlm_model);
      }
    } catch { /* */ }
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!selectedModel.trim()) return;
    try {
      await fetch(`${API}/api/admin/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          key: "vlm_model",
          value: selectedModel.trim(),
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

  const handleTest = async () => {
    if (!selectedModel.trim()) return;
    setTestLoading(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API}/api/admin/vlm-test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: selectedModel.trim() }),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (e) {
      setTestResult({ ok: false, error: `Bağlantı hatası: ${e instanceof Error ? e.message : "bilinmeyen"}` });
    } finally {
      setTestLoading(false);
    }
  };

  // Seçili modelin provider'ını bul
  const modelSlug = selectedModel.split("/")[0]; // openai/gpt-4o → openai
  const provider = providers.find(p => p.slug === modelSlug);
  const providerModels = models.filter(m => {
    const pid = provider?.id;
    return pid ? m.provider_id === pid : false;
  });

  const borderStyle = { borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" };
  const muted = { color: "var(--term-muted)" };

  return (
    <div className="space-y-6">
      <div className="rounded-sm p-4" style={borderStyle}>
        <div className="font-mono text-sm font-semibold mb-1" style={{ color: "var(--term-text)" }}>
          VLM MODEL SEÇİMİ
        </div>
        <p className="text-xs font-mono mb-4" style={muted}>
          K-line grafik analizinde kullanılacak vision-capable LLM modeli.
          Kayıtlı provider/model listesinden seç veya manuel liteLLM formatı gir.
        </p>

        {/* Mevcut config */}
        {config?.configured && (
          <div className="mb-4 p-2 rounded-sm text-xs font-mono" style={{ backgroundColor: "var(--term-bg)", color: "var(--term-green)" }}>
            Aktif: {config.vlm_model}
          </div>
        )}

        {/* Provider dropdown */}
        <div className="mb-3">
          <div className="text-[10px] font-mono tracking-wider mb-1.5" style={muted}>PROVIDER</div>
          <select
            value={modelSlug}
            onChange={(e) => {
              const slug = e.target.value;
              if (!slug) { setSelectedModel(""); return; }
              // provider'ın ilk modelini seç
              const p = providers.find(x => x.slug === slug);
              if (!p) return;
              const pm = models.find(m => m.provider_id === p.id);
              setSelectedModel(pm ? `${p.slug}/${pm.model_id}` : "");
            }}
            className="w-full rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
            style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }}
          >
            <option value="">Provider seç</option>
            {providers.filter(p => p.is_active).map(p => (
              <option key={p.id} value={p.slug}>{p.name}</option>
            ))}
          </select>
        </div>

        {/* Model dropdown (seçili provider'ın modelleri) */}
        {providerModels.length > 0 && (
          <div className="mb-3">
            <div className="text-[10px] font-mono tracking-wider mb-1.5" style={muted}>MODEL</div>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
              style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }}
            >
              <option value="">Model seç</option>
              {providerModels.map(m => {
                const fullName = `${modelSlug}/${m.model_id}`;
                return (
                  <option key={m.id} value={fullName}>
                    {m.model_id} ({m.display_name})
                  </option>
                );
              })}
            </select>
          </div>
        )}

        {/* Manuel input (provider yoksa / özel model) */}
        <div className="mb-3">
          <div className="text-[10px] font-mono tracking-wider mb-1.5" style={muted}>
            VEYA MANUEL (liteLLM formatı: provider/model)
          </div>
          <input
            type="text"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            placeholder="openai/gpt-4o-mini"
            className="w-full rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
            style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }}
          />
        </div>

        {/* Butonlar */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={save}
            disabled={!selectedModel.trim()}
            className="font-mono text-xs px-4 py-2 rounded-sm transition-none disabled:opacity-40"
            style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}
          >
            KAYDET
          </button>
          <button
            onClick={handleTest}
            disabled={!selectedModel.trim() || testLoading}
            className="font-mono text-xs px-4 py-2 rounded-sm transition-none disabled:opacity-40"
            style={{ border: "1px solid var(--term-green)", color: "var(--term-green)" }}
          >
            {testLoading ? "TEST EDİLİYOR…" : "TEST ET"}
          </button>
        </div>

        {msg && (
          <div className="text-xs font-mono mb-2" style={{ color: msg.startsWith("✅") ? "var(--term-green)" : "var(--term-red)" }}>
            {msg}
          </div>
        )}

        {/* Test sonucu */}
        {testResult && (
          <div className={`rounded-sm p-3 font-mono text-xs ${testResult.ok ? "" : ""}`}
            style={{
              border: `1px solid ${testResult.ok ? "var(--term-green)" : "var(--term-red)"}`,
              backgroundColor: testResult.ok ? "rgba(34,197,94,0.05)" : "rgba(239,68,68,0.05)",
            }}
          >
            <div style={{ color: testResult.ok ? "var(--term-green)" : "var(--term-red)", fontWeight: 600 }}>
              {testResult.ok ? "✅ TEST BAŞARILI" : "❌ TEST BAŞARISIZ"}
            </div>
            <div className="mt-1" style={muted}>
              Model: {selectedModel}
            </div>
            {testResult.ok && testResult.response && (
              <div className="mt-1" style={{ color: "var(--term-text)" }}>
                Yanıt: {testResult.response}
              </div>
            )}
            {testResult.error && (
              <div className="mt-1" style={{ color: "var(--term-red)" }}>
                {testResult.error}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Vision-capable model bilgi */}
      <div className="rounded-sm p-4" style={borderStyle}>
        <div className="font-mono text-xs font-semibold mb-2" style={{ color: "var(--term-text)" }}>
          HANGİ MODELLER DESTEKLENİR?
        </div>
        <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
          <div style={{ color: "var(--term-green)" }}>✓ OpenAI: gpt-4o, gpt-4o-mini</div>
          <div style={{ color: "var(--term-green)" }}>✓ Anthropic: claude-3-5-sonnet</div>
          <div style={{ color: "var(--term-green)" }}>✓ Gemini: gemini-1.5-pro/flash</div>
          <div style={{ color: "var(--term-green)" }}>✓ Ollama: llava, llama3.2-vision</div>
        </div>
        <p className="text-xs font-mono mt-3" style={muted}>
          Test butonu 1x1 siyah PNG gönderir. Başarılı yanıt gelirse model vision destekler ve K-line analizinde kullanılabilir.
          Test yoksa veya başarısızsa sistem otomatik metin teknik analiz fallback kullanır.
        </p>
      </div>
    </div>
  );
}
