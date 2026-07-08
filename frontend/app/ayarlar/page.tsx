"use client";

import { useEffect, useState } from "react";
import ThemeToggle from "../components/ThemeToggle";
import ProviderCard from "./ProviderCard";
import ProviderForm from "./ProviderForm";
import TranslationTab from "./TranslationTab";
import PredictionTab from "./PredictionTab";

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

const API = process.env.NEXT_PUBLIC_API_URL;

export default function AyarlarPage() {
  const [tab, setTab] = useState<"providers" | "translation" | "prediction">("providers");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [showProviderForm, setShowProviderForm] = useState(false);
  const [testResults, setTestResults] = useState<Record<number, { ok: boolean; response?: string; error?: string }>>({});
  const [testLoading, setTestLoading] = useState<Record<number, boolean>>({});

  const loadProviders = async () => {
    const res = await fetch(`${API}/api/admin/providers`);
    if (res.ok) setProviders(await res.json());
  };

  const loadModels = async () => {
    const res = await fetch(`${API}/api/admin/models`);
    if (res.ok) setModels(await res.json());
  };

  useEffect(() => { loadProviders(); loadModels(); }, []);

  const addProvider = async (data: { name: string; slug: string; base_url: string; api_key: string }) => {
    await fetch(`${API}/api/admin/providers`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    setShowProviderForm(false);
    loadProviders();
  };

  const testProvider = (id: number) => {
    setTestLoading(prev => ({ ...prev, [id]: true }));
    fetch(`${API}/api/admin/providers/${id}/test`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: "Merhaba test" }) })
      .then(r => r.json()).then(r => setTestResults(prev => ({ ...prev, [id]: r })))
      .catch(e => console.warn("Failed to test provider", e))
      .finally(() => setTestLoading(prev => ({ ...prev, [id]: false })));
  };

  const deleteProvider = async (id: number) => {
    if (!confirm("Bu provider'ı silmek istediğine emin misin? Tüm modelleri de silinecek.")) return;
    await fetch(`${API}/api/admin/providers/${id}`, { method: "DELETE" });
    loadProviders();
    loadModels();
  };

  const addModel = async (providerId: number, data: { model_id: string; display_name: string; max_tokens: number }) => {
    await fetch(`${API}/api/admin/models`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider_id: providerId, ...data }),
    });
    loadModels();
  };

  const deleteModel = async (id: number) => {
    await fetch(`${API}/api/admin/models/${id}`, { method: "DELETE" });
    loadModels();
  };

  const updateProviderKey = async (id: number, api_key: string) => {
    await fetch(`${API}/api/admin/providers/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key }),
    });
    loadProviders();
  };

  const borderStyle = { backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" };
  const muted = { color: "var(--term-muted)" };

  return (
    <main className="min-h-screen px-6 py-8 max-w-5xl mx-auto">
      <div className="rounded-sm px-6 py-4 mb-6" style={borderStyle}>
        <h1 className="font-mono text-xl font-semibold mb-1" style={{ color: "var(--term-text)" }}>AYARLAR</h1>
        <p className="text-xs font-mono" style={muted}>Sistem ayarları, LLM provider/modeller ve çeviri yapılandırması</p>
      </div>

      {/* Sekmeler */}
      <div className="flex gap-1 mb-6">
        {[
          ["providers", "LLM PROVIDER'LAR"],
          ["translation", "ÇEVİRİ"],
          ["prediction", "ÖNGÖRÜ"],
        ].map(([key, label]) => (
          <button key={key} onClick={() => setTab(key as any)}
            className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none"
            style={{
              borderColor: "var(--term-border)",
              backgroundColor: tab === key ? "var(--term-border)" : "var(--term-panel)",
              color: tab === key ? "var(--term-amber)" : "var(--term-muted)",
              border: "1px solid var(--term-border)",
            }}>
            {label}
          </button>
        ))}
        <div className="flex-1" />
        <ThemeToggle />
      </div>

      {tab === "providers" && (
        <div className="space-y-6">
          {providers.map((p) => (
            <ProviderCard
              key={p.id}
              provider={p}
              models={models}
              onTest={testProvider}
              onDelete={deleteProvider}
              onUpdateKey={updateProviderKey}
              onAddModel={addModel}
              onDeleteModel={deleteModel}
              testLoading={!!testLoading[p.id]}
              testResult={testResults[p.id] || null}
            />
          ))}

          {!showProviderForm ? (
            <button onClick={() => setShowProviderForm(true)}
              className="w-full font-mono text-xs py-3 rounded-sm transition-none"
              style={{ border: "1px dashed var(--term-border)", color: "var(--term-amber)", backgroundColor: "var(--term-panel)" }}>
              + YENİ PROVIDER EKLE
            </button>
          ) : (
            <ProviderForm onSubmit={addProvider} onCancel={() => setShowProviderForm(false)} />
          )}
        </div>
      )}

      {tab === "translation" && <TranslationTab />}
      {tab === "prediction" && <PredictionTab />}
    </main>
  );
}
