export default function Loader({ text = "YÜKLENİYOR" }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <div className="relative w-10 h-10">
        {/* Dönen halka */}
        <div
          className="absolute inset-0 rounded-full border-2 border-transparent animate-spin"
          style={{
            borderTopColor: "var(--term-amber)",
            borderRightColor: "var(--term-amber)",
            animationDuration: "0.8s",
          }}
        />
        {/* İç halka - ters yönde */}
        <div
          className="absolute inset-1 rounded-full border border-transparent animate-spin"
          style={{
            borderBottomColor: "var(--term-amber)",
            borderLeftColor: "var(--term-amber)",
            animationDuration: "1.2s",
            animationDirection: "reverse",
          }}
        />
        {/* Merkez nokta */}
        <div className="absolute inset-[14px] rounded-full" style={{ backgroundColor: "var(--term-amber)", opacity: 0.3 }} />
      </div>
      <span className="font-mono text-xs tracking-[0.3em] animate-pulse" style={{ color: "var(--term-amber)" }}>
        {text}
      </span>
    </div>
  );
}
