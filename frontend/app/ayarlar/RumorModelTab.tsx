"use client";

import { useEffect, useState } from "react";

interface Provider { id: number; name: string; slug: string; base_url: string; is_active: boolean }
interface Model { id: number; provider_id: number; model_id: string; display_name: string; supports_chat: boolean; supports_embedding: boolean }

const API = process.env.NEXT_PUBLIC_API_URL;

export default function RumorModelTab() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [config, setConfig] = useState<{ rumor_model?: string | null; configured: boolean; is_default?: boolean } | null>(null);
  const [selectedModel, setSelectedModel] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  const load = async () => {
    try {
      const [pRes, mRes, cRes] = await Promise.all([
        fetch(`${API}/api/admin/providers`),
        fetch(`${API}/api/admin/models`),
        fetch(`${API}/api/admin/rumor-config`),
      ]);
      if (pRes.ok) setProviders(await pRes.json());
      if (mRes.ok) setModels(await mRes.json());
      if (cRes.ok) {
        const data = await cRes.json();
        setConfig(data);
        if (data.rumor_model) setSelectedModel(data.rumor_model);
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
        body: JSON.stringify({ key: "rumor_model", value: selectedModel.trim(), description: "Rumor tarama için LLM sınıflandırma modeli" }),
      });
      setMsg("✅ Rumor modeli kaydedildi");
      await load();
      setTimeout(() => setMsg(null), 3000);
    } catch {
      setMsg("✗ Kaydetme başarısız");
    }
  };

  const modelSlug = selectedModel.split("/")[0];
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
          RUMOR MODEL SEÇİMİ
        </div>
        <p className="text-xs font-mono mb-4" style={muted}>
          Haber başlıklarını 5 tipe (ma/insider/analyst/regulatory/earnings) sınıflandırmak için LLM modeli.
          Ayarlanmazsa sistem varsayılan modeli (Ollama→Groq→Gemini→OpenAI) kullanır.
          LLM başarısız olursa keyword+VADER fallback devreye girer.
        </p>

        {config?.configured ? (
          <div className="mb-4 p-2 rounded-sm text-xs font-mono" style={{ backgroundColor: "var(--term-bg)", color: "var(--term-green)" }}>
            Aktif: {config.rumor_model}
          </div>
        ) : (
          <div className="mb-4 p-2 rounded-sm text-xs font-mono" style={{ backgroundColor: "var(--term-bg)", color: "var(--term-amber)" }}>
            {config?.is_default ? `Varsayılan: ${config.rumor_model || "bulunamadı"} (env var tabanlı)` : "Model ayarlanmamış — varsayılan kullanılıyor"}
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
              const p = providers.find(x => x.slug === slug);
              if (!p) return;
              const pm = models.find(m => m.provider_id === p.id && m.supports_chat);
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

        {/* Model dropdown */}
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

        {/* Manuel input */}
        <div className="mb-4">
          <div className="text-[10px] font-mono tracking-wider mb-1.5" style={muted}>VEYA MANUEL (provider/model)</div>
          <input
            type="text"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            placeholder="groq/llama-3.1-70b-versatile"
            className="w-full rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
            style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }}
          />
        </div>

        <button onClick={save} disabled={!selectedModel.trim()}
          className="font-mono text-xs px-4 py-2 rounded-sm transition-none disabled:opacity-40"
          style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}>
          KAYDET
        </button>
        {msg && <div className="text-xs font-mono mt-2" style={{ color: msg.startsWith("✅") ? "var(--term-green)" : "var(--term-red)" }}>{msg}</div>}
      </div>
    </div>
  );
}
