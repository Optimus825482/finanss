"use client";

import { useEffect, useState } from "react";
import ThemeToggle from "../components/ThemeToggle";
import { API_BASE, apiHeaders } from "../lib/api";

interface Provider {
  id: number; name: string; slug: string; base_url: string;
}

interface Model {
  id: number; provider_id: number; model_id: string;
  display_name: string; supports_chat: boolean;
  supports_embedding: boolean; max_tokens: number;
}

interface TranslationConfig {
  provider_id: number | null; provider_name: string;
  model_id: number; model_name: string; model_display: string;
  error?: string;
}

const API = API_BASE;

export default function TranslationTab() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [transConfig, setTransConfig] = useState<TranslationConfig | null>(null);
  const [transForm, setTransForm] = useState({ provider_id: "", model_id: "" });
  const [transMsg, setTransMsg] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const [pRes, mRes, cRes] = await Promise.all([
        fetch(`${API}/api/admin/providers`, { headers: apiHeaders() }),
        fetch(`${API}/api/admin/models`, { headers: apiHeaders() }),
        fetch(`${API}/api/admin/translation-config`, { headers: apiHeaders() }),
      ]);
      if (pRes.ok) setProviders(await pRes.json());
      if (mRes.ok) setModels(await mRes.json());
      if (cRes.ok) setTransConfig(await cRes.json());
    })();
  }, []);

  const saveTransConfig = async () => {
    const pid = transForm.provider_id;
    const mid = transForm.model_id;
    const h = apiHeaders({ "Content-Type": "application/json" });
    if (pid) {
      await fetch(`${API}/api/admin/settings`, {
        method: "POST", headers: h,
        body: JSON.stringify({ key: "translation_provider_id", value: pid, description: "Çeviri için LLM provider ID" }),
      });
    }
    if (mid) {
      await fetch(`${API}/api/admin/settings`, {
        method: "POST", headers: h,
        body: JSON.stringify({ key: "translation_model_id", value: mid, description: "Çeviri için LLM model ID" }),
      });
    }
    setTransMsg("✅ Çeviri ayarları kaydedildi");
    const cRes = await fetch(`${API}/api/admin/translation-config`, { headers: apiHeaders() });
    if (cRes.ok) setTransConfig(await cRes.json());
    setTimeout(() => setTransMsg(null), 3000);
  };

  const borderStyle = { borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" };
  const muted = { color: "var(--term-muted)" };
  const text = { color: "var(--term-text)" };

  const selectedProviderId = transForm.provider_id || transConfig?.provider_id || "";

  return (
    <div className="space-y-6">
      <div className="rounded-sm p-4" style={borderStyle}>
        <div className="font-mono text-sm font-semibold mb-3" style={text}>ÇEVİRİ MODELİ SEÇİMİ</div>
        <p className="text-xs font-mono mb-4" style={muted}>
          Hisse detayları, haber başlıkları ve şirket açıklamaları bu model kullanılarak Türkçe&apos;ye çevrilir.
        </p>

        {transConfig?.error && (
          <div className="text-xs font-mono mb-3 p-2 rounded-sm" style={{ backgroundColor: "rgba(248,113,113,0.08)", color: "var(--term-red)" }}>
            ⚠ {transConfig.error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <div className="text-[10px] font-mono tracking-wider mb-1.5" style={muted}>PROVIDER</div>
            <select value={transForm.provider_id || transConfig?.provider_id || ""}
              onChange={e => setTransForm({ ...transForm, provider_id: e.target.value })}
              className="w-full rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
              style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }}>
              <option value="">Seçilmedi</option>
              {providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>

          <div>
            <div className="text-[10px] font-mono tracking-wider mb-1.5" style={muted}>MODEL</div>
            <select value={transForm.model_id || transConfig?.model_id || ""}
              onChange={e => setTransForm({ ...transForm, model_id: e.target.value })}
              className="w-full rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
              style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }}>
              <option value="">Seçilmedi</option>
              {selectedProviderId
                ? models
                    .filter(m => m.provider_id === Number(selectedProviderId))
                    .filter(m => m.supports_chat)
                    .map(m => <option key={m.id} value={m.id}>{m.model_id} ({m.display_name})</option>)
                : models.filter(m => m.supports_chat).map(m => <option key={m.id} value={m.id}>{m.model_id} ({m.display_name})</option>)
              }
            </select>
          </div>
        </div>

        <button onClick={saveTransConfig}
          className="font-mono text-xs px-4 py-2 rounded-sm transition-none"
          style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}>
          KAYDET
        </button>

        {transMsg && (
          <div className="text-xs font-mono mt-2" style={{ color: "var(--term-green)" }}>{transMsg}</div>
        )}

        {transConfig?.model_display && (
          <div className="mt-4 p-2 rounded-sm text-xs font-mono" style={{ backgroundColor: "var(--term-bg)", color: "var(--term-amber)" }}>
            Aktif: {transConfig.provider_name} → {transConfig.model_display} ({transConfig.model_name})
          </div>
        )}
      </div>

      {/* Tema */}
      <div className="rounded-sm p-5" style={borderStyle}>
        <div className="flex items-center justify-between">
          <div>
            <div className="font-mono text-sm font-semibold" style={text}>TEMA</div>
            <div className="text-xs font-mono mt-1" style={muted}>Karanlık / Aydınlık tema arasında geçiş yap</div>
          </div>
          <ThemeToggle />
        </div>
      </div>
    </div>
  );
}
