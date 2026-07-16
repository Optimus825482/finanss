"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";

interface Provider { id: number; name: string; slug: string; base_url: string }
interface Model { id: number; provider_id: number; model_id: string; display_name: string; supports_chat: boolean; supports_embedding: boolean; max_tokens: number }

export default function PredictionTab() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [config, setConfig] = useState<any>(null);
  const [form, setForm] = useState({ provider_id: "", model_id: "" });
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const [pRes, mRes, cRes] = await Promise.all([
        apiFetch("/api/admin/providers"),
        apiFetch("/api/admin/models"),
        apiFetch("/api/admin/prediction-config"),
      ]);
      if (pRes.ok) setProviders(await pRes.json());
      if (mRes.ok) setModels(await mRes.json());
      if (cRes.ok) setConfig(await cRes.json());
    })();
  }, []);

  const save = async () => {
    const { provider_id, model_id } = form;
    const h = { "Content-Type": "application/json" };
    if (provider_id) await apiFetch("/api/admin/settings", { method: "POST", headers: h, body: JSON.stringify({ key: "prediction_provider_id", value: provider_id, description: "Öngörü için LLM provider ID" }) });
    if (model_id) await apiFetch("/api/admin/settings", { method: "POST", headers: h, body: JSON.stringify({ key: "prediction_model_id", value: model_id, description: "Öngörü için LLM model ID" }) });
    setMsg("✅ Öngörü ayarları kaydedildi");
    const cRes = await apiFetch("/api/admin/prediction-config");
    if (cRes.ok) setConfig(await cRes.json());
    setTimeout(() => setMsg(null), 3000);
  };

  const sid = form.provider_id || config?.provider_id || "";
  const borderStyle = { borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" };

  return (
    <div className="space-y-6">
      <div className="rounded-sm p-4" style={borderStyle}>
        <div className="font-mono text-sm font-semibold mb-3" style={{ color: "var(--term-text)" }}>ÖNGÖRÜ MODELİ SEÇİMİ</div>
        <p className="text-xs font-mono mb-4" style={{ color: "var(--term-muted)" }}>
          Fiyat öngörüsü oluşturmak için kullanılacak LLM modelini seç. Özellik vektörleri bu modelle analiz edilir.
        </p>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <div className="text-[10px] font-mono tracking-wider mb-1.5" style={{ color: "var(--term-muted)" }}>PROVIDER</div>
            <select value={sid} onChange={e => setForm({ ...form, provider_id: e.target.value })}
              className="w-full rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
              style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }}>
              <option value="">Seçilmedi</option>
              {providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <div className="text-[10px] font-mono tracking-wider mb-1.5" style={{ color: "var(--term-muted)" }}>MODEL</div>
            <select value={form.model_id || config?.model_id || ""} onChange={e => setForm({ ...form, model_id: e.target.value })}
              className="w-full rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
              style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }}>
              <option value="">Seçilmedi</option>
              {sid ? models.filter(m => m.provider_id === Number(sid) && m.supports_chat).map(m => <option key={m.id} value={m.id}>{m.model_id} ({m.display_name})</option>)
                : models.filter(m => m.supports_chat).map(m => <option key={m.id} value={m.id}>{m.model_id} ({m.display_name})</option>)}
            </select>
          </div>
        </div>

        <button onClick={save} className="font-mono text-xs px-4 py-2 rounded-sm transition-none"
          style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}>KAYDET</button>
        {msg && <div className="text-xs font-mono mt-2" style={{ color: "var(--term-green)" }}>{msg}</div>}
        {config?.model_display && (
          <div className="mt-4 p-2 rounded-sm text-xs font-mono" style={{ backgroundColor: "var(--term-bg)", color: "var(--term-amber)" }}>
            Aktif: {config.provider_name} → {config.model_display} ({config.model_name})
          </div>
        )}
      </div>
    </div>
  );
}
