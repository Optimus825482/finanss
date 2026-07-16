"use client";

import { useState, FormEvent } from "react";
import { API_BASE, apiHeaders } from "../lib/api";

const API = API_BASE;

interface Provider {
  id: number; name: string; slug: string; base_url: string;
  api_key_masked: string; has_api_key: boolean;
  is_active: boolean; model_count: number;
}

interface Model {
  id: number; provider_id: number; model_id: string;
  display_name: string; supports_chat: boolean;
  supports_embedding: boolean; max_tokens: number; is_active: boolean;
  provider_name: string;
}

interface ProviderCardProps {
  provider: Provider;
  models: Model[];
  onTest: (id: number) => void;
  onDelete: (id: number) => void;
  onUpdateKey: (id: number, api_key: string) => void;
  onAddModel: (providerId: number, data: { model_id: string; display_name: string; max_tokens: number }) => Promise<void>;
  onDeleteModel: (id: number) => void;
  testLoading: boolean;
  testResult: { ok: boolean; response?: string; error?: string } | null;
}

export default function ProviderCard({
  provider, models, onTest, onDelete, onUpdateKey, onAddModel, onDeleteModel,
  testLoading, testResult,
}: ProviderCardProps) {
  const [showModelForm, setShowModelForm] = useState(false);
  const [modelForm, setModelForm] = useState({ model_id: "", display_name: "", max_tokens: 4096 });
  const [showKeyInput, setShowKeyInput] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [keySaved, setKeySaved] = useState(false);
  const [modelTestLoading, setModelTestLoading] = useState<Record<number, boolean>>({});
  const [modelTestResults, setModelTestResults] = useState<Record<number, { ok: boolean; response?: string; error?: string }>>({});

  const handleModelTest = async (modelId: number) => {
    setModelTestLoading(p => ({ ...p, [modelId]: true }));
    setModelTestResults(p => ({ ...p, [modelId]: {} as any }));
    try {
      const res = await fetch(`${API}/api/admin/models/${modelId}/test`, { method: "POST", headers: apiHeaders() });
      const data = await res.json();
      setModelTestResults(p => ({ ...p, [modelId]: data }));
    } catch (e) {
      setModelTestResults(p => ({ ...p, [modelId]: { ok: false, error: `Bağlantı hatası: ${e instanceof Error ? e.message : "bilinmeyen"}` } }));
    } finally {
      setModelTestLoading(p => ({ ...p, [modelId]: false }));
    }
  };

  const providerModels = models.filter(m => m.provider_id === provider.id);

  const borderStyle = { borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" };
  const muted = { color: "var(--term-muted)" };
  const text = { color: "var(--term-text)" };

  const handleAddModel = async (e: FormEvent) => {
    e.preventDefault();
    await onAddModel(provider.id, modelForm);
    setShowModelForm(false);
    setModelForm({ model_id: "", display_name: "", max_tokens: 4096 });
  };

  return (
    <div className="rounded-sm p-4" style={borderStyle}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-semibold" style={text}>{provider.name}</span>
            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm" style={{ backgroundColor: provider.is_active ? "rgba(74,222,128,0.15)" : "rgba(248,113,113,0.15)", color: provider.is_active ? "var(--term-green)" : "var(--term-red)" }}>
              {provider.is_active ? "AKTİF" : "PASİF"}
            </span>
          </div>
          <div className="text-xs font-mono mt-1" style={muted}>{provider.base_url} · slug: {provider.slug}</div>
          <div className="text-xs font-mono mt-1" style={muted}>
            API Key: {provider.has_api_key ? provider.api_key_masked : "⚠️ GİRİLMEDİ"}
          </div>
          <div className="flex items-center gap-1 mt-1">
            {!showKeyInput ? (
              <button onClick={() => { setShowKeyInput(true); setKeySaved(false); }}
                className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm transition-none"
                style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}>
                {provider.has_api_key ? "DEĞİŞTİR" : "API KEY GİR"}
              </button>
            ) : (
              <>
                <input type="password" value={apiKeyInput}
                  onChange={e => setApiKeyInput(e.target.value)}
                  placeholder="nvapi-..."
                  className="rounded-sm px-2 py-1 text-xs font-mono focus:outline-none w-48"
                  style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }} />
                <button onClick={() => { onUpdateKey(provider.id, apiKeyInput); setShowKeyInput(false); setApiKeyInput(""); setKeySaved(true); }}
                  className="font-mono text-[10px] px-1.5 py-1 rounded-sm transition-none"
                  style={{ border: "1px solid var(--term-green)", color: "var(--term-green)" }}>KAYDET</button>
                <button onClick={() => setShowKeyInput(false)}
                  className="font-mono text-[10px] px-1.5 py-1 rounded-sm transition-none"
                  style={{ border: "1px solid var(--term-border)", color: "var(--term-muted)" }}>İPTAL</button>
              </>
            )}
            {keySaved && <span className="text-[10px] font-mono" style={{ color: "var(--term-green)" }}>✓ Kaydedildi</span>}
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => onTest(provider.id)} disabled={testLoading}
            className="font-mono text-[10px] px-2 py-1 rounded-sm transition-none disabled:opacity-40"
            style={{ border: "1px solid var(--term-green)", color: "var(--term-green)" }}>
            {testLoading ? "…" : "TEST ET"}
          </button>
          <button onClick={() => onDelete(provider.id)}
            className="font-mono text-[10px] px-2 py-1 rounded-sm transition-none"
            style={{ border: "1px solid var(--term-red)", color: "var(--term-red)" }}>SİL</button>
        </div>
      </div>

      {testResult && (
        <div className="text-xs font-mono mb-3 p-2 rounded-sm" style={{
          backgroundColor: testResult.ok ? "rgba(74,222,128,0.08)" : "rgba(248,113,113,0.08)",
          color: testResult.ok ? "var(--term-green)" : "var(--term-red)",
        }}>
          {testResult.ok ? `✅ ${testResult.response?.slice(0, 120)}` : `❌ ${testResult.error}`}
        </div>
      )}

      {/* Modeller */}
      <div className="text-[11px] tracking-wider font-mono mb-2" style={muted}>
        MODELLER ({providerModels.length})
      </div>
      <div className="space-y-1">
        {providerModels.map((m) => (
          <div key={m.id}>
            <div className="flex items-center justify-between text-xs font-mono py-1.5 px-2 rounded-sm"
              style={{ backgroundColor: "var(--term-bg)" }}>
              <div className="flex items-center gap-2">
                <span style={text}>{m.model_id}</span>
                <span style={muted}>({m.display_name})</span>
                <span style={muted}>max {m.max_tokens} token</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleModelTest(m.id)}
                  disabled={modelTestLoading[m.id]}
                  className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm transition-none disabled:opacity-40"
                  style={{ border: "1px solid var(--term-green)", color: "var(--term-green)" }}
                >
                  {modelTestLoading[m.id] ? "…" : "TEST"}
                </button>
                <button onClick={() => onDeleteModel(m.id)}
                  className="text-term-red text-[10px] transition-none">✕</button>
              </div>
            </div>
            {modelTestResults[m.id] && (
              <div className="text-[10px] font-mono mx-2 mb-1 p-1.5 rounded-sm" style={{
                backgroundColor: modelTestResults[m.id].ok ? "rgba(74,222,128,0.08)" : "rgba(248,113,113,0.08)",
                color: modelTestResults[m.id].ok ? "var(--term-green)" : "var(--term-red)",
              }}>
                {modelTestResults[m.id].ok
                  ? `✅ ${(modelTestResults[m.id].response || "").slice(0, 100)}`
                  : `❌ ${modelTestResults[m.id].error}`}
              </div>
            )}
          </div>
        ))}
      </div>

      <button onClick={() => setShowModelForm(true)}
        className="font-mono text-[10px] mt-2 px-2 py-1 rounded-sm transition-none"
        style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}>
        + MODEL EKLE
      </button>

      {showModelForm && (
        <form onSubmit={handleAddModel} className="grid grid-cols-4 gap-2 mt-3 p-3 rounded-sm" style={{ backgroundColor: "var(--term-bg)" }}>
          <input value={modelForm.model_id} onChange={e => setModelForm({ ...modelForm, model_id: e.target.value })}
            placeholder="Model ID (örn: gpt-4o)" className="col-span-2 rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
            style={{ backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)", color: "var(--term-text)" }} />
          <input value={modelForm.display_name} onChange={e => setModelForm({ ...modelForm, display_name: e.target.value })}
            placeholder="Görünen ad" className="rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
            style={{ backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)", color: "var(--term-text)" }} />
          <input value={modelForm.max_tokens} onChange={e => setModelForm({ ...modelForm, max_tokens: +e.target.value })}
            type="number" placeholder="Token" className="rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
            style={{ backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)", color: "var(--term-text)" }} />
          <div className="col-span-4 flex gap-2">
            <button type="submit" className="flex-1 font-mono text-[10px] py-1.5 rounded-sm transition-none"
              style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}>KAYDET</button>
            <button type="button" onClick={() => setShowModelForm(false)}
              className="font-mono text-[10px] py-1.5 px-2 rounded-sm transition-none"
              style={{ border: "1px solid var(--term-border)", color: "var(--term-muted)" }}>İPTAL</button>
          </div>
        </form>
      )}
    </div>
  );
}
