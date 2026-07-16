"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="min-h-[60vh] flex flex-col items-center justify-center gap-4 px-6">
      <p className="font-mono text-sm" style={{ color: "var(--term-red)" }}>
        HATA
      </p>
      <p className="font-mono text-xs max-w-md text-center" style={{ color: "var(--term-muted)" }}>
        {error.message || "Beklenmeyen hata"}
      </p>
      <button
        onClick={reset}
        className="font-mono text-xs px-4 py-2 rounded-sm"
        style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}
      >
        TEKRAR DENE
      </button>
    </main>
  );
}
