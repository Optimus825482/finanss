"use client";

import { useState, FormEvent } from "react";

interface ProviderFormProps {
  onSubmit: (data: { name: string; slug: string; base_url: string; api_key: string }) => Promise<void>;
  onCancel: () => void;
}

export default function ProviderForm({ onSubmit, onCancel }: ProviderFormProps) {
  const [form, setForm] = useState({ name: "", slug: "", base_url: "", api_key: "" });

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await onSubmit(form);
    setForm({ name: "", slug: "", base_url: "", api_key: "" });
  };

  const borderStyle = { borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" };

  return (
    <form onSubmit={handleSubmit} className="rounded-sm p-4 space-y-3" style={borderStyle}>
      <div className="font-mono text-xs font-semibold" style={{ color: "var(--term-text)" }}>YENİ PROVIDER</div>
      <div className="grid grid-cols-2 gap-3">
        <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
          placeholder="Ad (örn: OpenAI)" className="rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none" required
          style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }} />
        <input value={form.slug} onChange={e => setForm({ ...form, slug: e.target.value })}
          placeholder="Slug (örn: openai)" className="rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none" required
          style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }} />
        <input value={form.base_url} onChange={e => setForm({ ...form, base_url: e.target.value })}
          placeholder="Base URL" className="col-span-2 rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none" required
          style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }} />
        <input value={form.api_key} onChange={e => setForm({ ...form, api_key: e.target.value })}
          placeholder="API Key" type="password" className="col-span-2 rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
          style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }} />
      </div>
      <div className="flex gap-2">
        <button type="submit" className="px-3 py-1.5 font-mono text-xs rounded-sm transition-none"
          style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}>KAYDET</button>
        <button type="button" onClick={onCancel}
          className="px-3 py-1.5 font-mono text-xs rounded-sm transition-none"
          style={{ border: "1px solid var(--term-border)", color: "var(--term-muted)" }}>İPTAL</button>
      </div>
    </form>
  );
}
