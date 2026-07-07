"use client";

export default function AdminRedirect() {
  return (
    <main className="min-h-screen px-6 py-8 max-w-3xl mx-auto">
      <div className="rounded-sm px-6 py-4 mb-6" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
        <h1 className="font-mono text-xl font-semibold mb-1" style={{ color: "var(--term-text)" }}>ADMİN PANEL</h1>
        <p className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>
          ORBIS FINAI sistem ayarları — Ayarlar sayfasından yönetilir
        </p>
      </div>
      <div className="rounded-sm p-6 space-y-4" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
        {[
          ["/ayarlar", "SİSTEM AYARLARI", "LLM Provider, model, API key yönetimi, çeviri yapılandırması, tema"],
          ["/api/docs", "API DOKÜMANTASYON", "Swagger UI — tüm endpoint'ler ve test arayüzü (backend :8012 adresinde)"],
        ].map(([href, title, desc]) => (
          <a key={href} href={href}
            className="block rounded-sm p-4 transition-none"
            style={{ border: "1px solid var(--term-border)", backgroundColor: "var(--term-bg)" }}>
            <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-amber)" }}>{title}</div>
            <div className="text-xs font-mono mt-1" style={{ color: "var(--term-muted)" }}>{desc}</div>
          </a>
        ))}
      </div>
    </main>
  );
}
