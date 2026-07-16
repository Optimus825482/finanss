import Link from "next/link";

export default function NotFound() {
  return (
    <main className="min-h-[60vh] flex flex-col items-center justify-center gap-4 px-6">
      <p className="font-mono text-2xl font-bold" style={{ color: "var(--term-amber)" }}>
        404
      </p>
      <p className="font-mono text-xs" style={{ color: "var(--term-muted)" }}>
        Sayfa bulunamadı
      </p>
      <Link
        href="/"
        className="font-mono text-xs px-4 py-2 rounded-sm"
        style={{ border: "1px solid var(--term-border)", color: "var(--term-text)" }}
      >
        ANA SAYFA
      </Link>
    </main>
  );
}
