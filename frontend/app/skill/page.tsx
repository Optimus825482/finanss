"use client";

import SkillPanel from "../components/SkillPanel";

export default function SkillPage() {
  const borderColor = "var(--term-border)";

  return (
    <main className="min-h-screen px-6 py-8 max-w-5xl mx-auto">
      <div
        className="rounded-sm px-6 py-4 mb-6"
        style={{
          backgroundColor: "var(--term-panel)",
          border: `1px solid ${borderColor}`,
        }}
      >
        <h1 className="font-mono text-xl font-semibold mb-1" style={{ color: "var(--term-text)" }}>
          SEMBOL ANALİZ MODÜLÜ
        </h1>
        <p className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>
          4 komut: hisse analizi · temettü · rumor tarama · K-line grafik · LLM destekli karar gerekçesi
        </p>
      </div>

      <SkillPanel />
    </main>
  );
}
