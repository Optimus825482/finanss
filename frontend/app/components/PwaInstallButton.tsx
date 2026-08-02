"use client";

import { useEffect, useState } from "react";

/**
 * PWA kurulum butonu: beforeinstallprompt yakalar,
 * "Uygulama Olarak Yükle" ile install prompt açar.
 * iOS (Safari) için manifest + apple-touch-icon zaten layout'ta.
 */
export default function PwaInstallButton() {
  const [deferred, setDeferred] = useState<Event | null>(null);
  const [ios, setIos] = useState(false);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setDeferred(e);
    };
    const onInstalled = () => { setInstalled(true); setDeferred(null); };

    // iOS Safari: standalone'daysa kurulmuş demektir, değilse paylaş menüsü anlat
    const ua = navigator.userAgent;
    const isIOS = /iphone|ipad|ipod/i.test(ua);
    const isStandalone = window.matchMedia("(display-mode: standalone)").matches || (navigator as unknown as { standalone?: boolean }).standalone === true;

    setIos(isIOS && !isStandalone);
    setInstalled(isStandalone);

    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (installed) return null;
  if (!deferred && !ios) return null;

  const handleInstall = async () => {
    if (deferred) {
      const promptEvent = deferred as unknown as { prompt: () => Promise<void> };
      await promptEvent.prompt();
      setDeferred(null);
    }
  };

  return (
    <button onClick={handleInstall}
      className="font-mono text-[11px] tracking-wider px-3 py-1.5 rounded-sm transition-none"
      style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}
      title={ios ? "Safari'de Paylaş → Ana Ekrana Ekle" : "Uygulama olarak yükle"}>
      {ios ? "📲 İOS'TA YÜKLE" : "📲 UYGULAMA OLARAK YÜKLE"}
    </button>
  );
}
