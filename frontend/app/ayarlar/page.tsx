"use client";

import { useEffect, useState } from "react";
import ThemeToggle from "../components/ThemeToggle";
import ProviderCard from "./ProviderCard";
import ProviderForm from "./ProviderForm";
import TranslationTab from "./TranslationTab";
import PredictionTab from "./PredictionTab";
import VLMTab from "./VLMTab";
import RumorModelTab from "./RumorModelTab";
import { api, apiFetch } from "../lib/api";

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

export default function AyarlarPage() {
  const [tab, setTab] = useState<"providers" | "translation" | "prediction" | "vlm" | "rumor" | "system">("providers");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [showProviderForm, setShowProviderForm] = useState(false);
  const [testResults, setTestResults] = useState<Record<number, { ok: boolean; response?: string; error?: string }>>({});
  const [testLoading, setTestLoading] = useState<Record<number, boolean>>({});
  const [resetLoading, setResetLoading] = useState<"" | "portfolio" | "reports" | "all">("");
  const [resetResult, setResetResult] = useState<string | null>(null);
  const [resetPortfolioSlug, setResetPortfolioSlug] = useState<"bist" | "us" | "all">("all");

  const loadProviders = async () => {
    const res = await apiFetch("/api/admin/providers");
    if (res.ok) setProviders(await res.json());
  };

  const loadModels = async () => {
    const res = await apiFetch("/api/admin/models");
    if (res.ok) setModels(await res.json());
  };

  useEffect(() => { loadProviders(); loadModels(); }, []);

  const addProvider = async (data: { name: string; slug: string; base_url: string; api_key: string }) => {
    await apiFetch("/api/admin/providers", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    setShowProviderForm(false);
    loadProviders();
  };

  const testProvider = (id: number) => {
    setTestLoading(prev => ({ ...prev, [id]: true }));
    apiFetch(`/api/admin/providers/${id}/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "Merhaba test" }),
    })
      .then(r => r.json()).then(r => setTestResults(prev => ({ ...prev, [id]: r })))
      .catch(e => console.warn("Failed to test provider", e))
      .finally(() => setTestLoading(prev => ({ ...prev, [id]: false })));
  };

  const deleteProvider = async (id: number) => {
    if (!confirm("Bu provider'ı silmek istediğine emin misin? Tüm modelleri de silinecek.")) return;
    await apiFetch(`/api/admin/providers/${id}`, { method: "DELETE" });
    loadProviders();
    loadModels();
  };

  const addModel = async (providerId: number, data: { model_id: string; display_name: string; max_tokens: number }) => {
    await apiFetch("/api/admin/models", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider_id: providerId, ...data }),
    });
    loadModels();
  };

  const deleteModel = async (id: number) => {
    await apiFetch(`/api/admin/models/${id}`, { method: "DELETE" });
    loadModels();
  };

  const updateProviderKey = async (id: number, api_key: string) => {
    await apiFetch(`/api/admin/providers/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key }),
    });
    loadProviders();
  };

  // ── Sistem Sıfırlama ──
  const _slugParam = () => resetPortfolioSlug === "all" ? undefined : resetPortfolioSlug;

  const handleResetPortfolio = async () => {
    const label = resetPortfolioSlug === "all" ? "TÜM PORTFÖYLERİ" : `${resetPortfolioSlug.toUpperCase()} PORTFÖYÜNÜ`;
    if (!confirm(`${label} SIFIRLA\n\nTüm pozisyonlar, kararlar ve balance transactions silinecek.\nBakiye $10.000'a ayarlanacak.\n\nGERİ ALINAMAZ. Onaylıyor musun?`)) return;
    setResetLoading("portfolio");
    setResetResult(null);
    try {
      const r = await api.resetPortfolio(_slugParam());
      const scope = resetPortfolioSlug === "all" ? "Tüm portföyler" : `${resetPortfolioSlug.toUpperCase()} portföyü`;
      setResetResult(`✓ ${scope} sıfırlandı. Pozisyonlar: ${r.deleted.portfolio_positions ?? 0} · Kararlar: ${r.deleted.trading_decisions ?? 0} · Bakiye: $${r.balance_cash}`);
    } catch (e) {
      setResetResult(`✗ Hata: ${e instanceof Error ? e.message : "bilinmeyen"}`);
    } finally {
      setResetLoading("");
    }
  };

  const handleResetReports = async () => {
    if (!confirm("RAPORLARI SIFIRLA\n\nTüm raporlar, stock picks ve predictions silinecek.\n\nGERİ ALINAMAZ. Onaylıyor musun?")) return;
    setResetLoading("reports");
    setResetResult(null);
    try {
      const r = await api.resetReports();
      setResetResult(`✓ Raporlar sıfırlandı. Raporlar: ${r.deleted.reports ?? 0} · Picks: ${r.deleted.stock_picks ?? 0} · Predictions: ${r.deleted.predictions ?? 0}`);
    } catch (e) {
      setResetResult(`✗ Hata: ${e instanceof Error ? e.message : "bilinmeyen"}`);
    } finally {
      setResetLoading("");
    }
  };

  const handleResetAll = async () => {
    const label = resetPortfolioSlug === "all" ? "TÜM SİSTEMİ (BIST + US)" : `${resetPortfolioSlug.toUpperCase()} + RAPORLAR`;
    if (!confirm(`${label} SIFIRLA\n\nSeçili portföy + raporlar tamamen sıfırlanacak.\nBakiye $10.000'dan başlatılacak.\n\nGERİ ALINAMAZ. Onaylıyor musun?`)) return;
    setResetLoading("all");
    setResetResult(null);
    try {
      const r = await api.resetAll(_slugParam());
      const scope = resetPortfolioSlug === "all" ? "Sistem (tüm portföyler)" : `${resetPortfolioSlug.toUpperCase()} portföyü`;
      setResetResult(`✓ ${scope} + raporlar sıfırlandı. Portföy: ${r.portfolio.deleted.portfolio_positions ?? 0} pozisyon · Raporlar: ${r.reports.deleted.reports ?? 0} rapor · Bakiye: $${r.portfolio.balance_cash}`);
    } catch (e) {
      setResetResult(`✗ Hata: ${e instanceof Error ? e.message : "bilinmeyen"}`);
    } finally {
      setResetLoading("");
    }
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
          ["vlm", "VLM"],
          ["rumor", "RUMOR"],
          ["system", "SİSTEM SIFIRLAMA"],
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
      {tab === "vlm" && <VLMTab />}
      {tab === "rumor" && <RumorModelTab />}

      {tab === "system" && (
        <div className="space-y-4">
          <div className="rounded-sm px-4 py-3" style={borderStyle}>
            <div className="font-mono text-sm font-semibold mb-1" style={{ color: "var(--term-red)" }}>
              ⚠ DİKKAT — GERİ ALINAMAZ İŞLEMLER
            </div>
            <p className="text-xs font-mono" style={muted}>
              Aşağıdaki butonlar veritabanındaki kayıtları kalıcı olarak siler. Sistem sıfırlama, otonom ajanın yeni başlangıç ​​yapması için kullanılır.
            </p>
          </div>

          {resetResult && (
            <div className="rounded-sm px-4 py-3 font-mono text-sm" style={borderStyle}>
              <span style={{ color: resetResult.startsWith("✓") ? "var(--term-green)" : "var(--term-red)" }}>
                {resetResult}
              </span>
            </div>
          )}

          {/* Portföy seçici — hangi portföy sıfırlanacak */}
          <div className="rounded-sm px-4 py-3" style={borderStyle}>
            <div className="font-mono text-xs tracking-wider mb-2" style={muted}>
              HEDEF PORTFÖY
            </div>
            <div className="flex gap-2">
              {(["bist", "us", "all"] as const).map((slug) => (
                <button
                  key={slug}
                  onClick={() => setResetPortfolioSlug(slug)}
                  className="font-mono text-[11px] tracking-wider px-3 py-1.5 rounded-sm transition-none"
                  style={{
                    border: "1px solid var(--term-border)",
                    backgroundColor: resetPortfolioSlug === slug ? "var(--term-border)" : "var(--term-bg)",
                    color: resetPortfolioSlug === slug ? "var(--term-amber)" : "var(--term-muted)",
                  }}
                >
                  {slug === "bist" ? "BIST" : slug === "us" ? "US (NASDAQ+DJIA)" : "TÜMÜ"}
                </button>
              ))}
            </div>
            <p className="text-[10px] font-mono mt-1.5" style={muted}>
              {resetPortfolioSlug === "all"
                ? "İki portföy birden (BIST + US) sıfırlanır."
                : `Sadece ${resetPortfolioSlug.toUpperCase()} portföyü sıfırlanır.`}
            </p>
          </div>

          {/* Portföy sıfırla */}
          <div className="rounded-sm px-4 py-4" style={borderStyle}>
            <div className="font-mono text-sm font-semibold mb-1" style={{ color: "var(--term-text)" }}>
              PORTFÖYÜ SIFIRLA
            </div>
            <p className="text-xs font-mono mb-3" style={muted}>
              Tüm pozisyonlar, al/sat kararları ve balance transactions silinir. Bakiye <span style={{ color: "var(--term-green)" }}>$10.000</span>'a ayarlanır. Raporlar ve picks korunur.
            </p>
            <button
              onClick={handleResetPortfolio}
              disabled={resetLoading !== ""}
              className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none disabled:opacity-40"
              style={{ border: "1px solid var(--term-red)", color: "var(--term-red)", backgroundColor: "var(--term-bg)" }}
            >
              {resetLoading === "portfolio" ? "SIFIRLANIYOR..." : "PORTFÖYÜ SIFIRLA"}
            </button>
          </div>

          {/* Raporları sıfırla */}
          <div className="rounded-sm px-4 py-4" style={borderStyle}>
            <div className="font-mono text-sm font-semibold mb-1" style={{ color: "var(--term-text)" }}>
              RAPORLARI SIFIRLA
            </div>
            <p className="text-xs font-mono mb-3" style={muted}>
              Tüm raporlar, stock picks ve predictions silinir. Portföy ve bakiye korunur.
            </p>
            <button
              onClick={handleResetReports}
              disabled={resetLoading !== ""}
              className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none disabled:opacity-40"
              style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)", backgroundColor: "var(--term-bg)" }}
            >
              {resetLoading === "reports" ? "SIFIRLANIYOR..." : "RAPORLARI SIFIRLA"}
            </button>
          </div>

          {/* Tümünü sıfırla */}
          <div className="rounded-sm px-4 py-4" style={{ ...borderStyle, borderColor: "var(--term-red)" }}>
            <div className="font-mono text-sm font-semibold mb-1" style={{ color: "var(--term-red)" }}>
              TÜM SİSTEMİ SIFIRLA
            </div>
            <p className="text-xs font-mono mb-3" style={muted}>
              Portföy + raporlar + bakiye tamamen sıfırlanır. Sistem <span style={{ color: "var(--term-green)" }}>$10.000</span> bakiye ile sıfırdan başlatılır. <strong style={{ color: "var(--term-red)" }}>En tehlikeli işlem — tüm geçmiş veri kaybı.</strong>
            </p>
            <button
              onClick={handleResetAll}
              disabled={resetLoading !== ""}
              className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none disabled:opacity-40"
              style={{ border: "2px solid var(--term-red)", color: "var(--term-red)", backgroundColor: "var(--term-bg)" }}
            >
              {resetLoading === "all" ? "SİSTEM SIFIRLANIYOR..." : "TÜMÜNÜ SIFIRLA"}
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
