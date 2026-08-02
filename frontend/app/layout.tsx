import type { Metadata } from "next";
import Navbar from "./components/Navbar";
import ErrorBoundary from "./components/ErrorBoundary";
import Script from "next/script";
import "./globals.css";

export const metadata: Metadata = {
  title: "ORBIS FINAI | AI-Powered Hisse Araştırma",
  description:
    "ORBIS Finance Analyze Team — 5 ajanlı AI araştırma ekibi tarafından üretilen günlük hisse senedi raporu",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, title: "ORBIS", statusBarStyle: "black-translucent" },
  icons: {
    apple: "/icons/apple-touch-icon.png",
    icon: [{ url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <head>
        <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
        <Script id="theme-init" strategy="beforeInteractive">
          {`(function(){try{var t=localStorage.getItem('orbis-theme');if(t==='light'){document.documentElement.setAttribute('data-theme','light')}}catch(e){}})()`}
        </Script>
        <Script id="sw-register" strategy="afterInteractive">
          {`if('serviceWorker' in navigator && location.protocol==='https:'){navigator.serviceWorker.register('/sw.js').catch(function(){})}`}
        </Script>
      </head>
      <body className="font-sans antialiased">
        <Navbar />
        <ErrorBoundary>{children}</ErrorBoundary>
      </body>
    </html>
  );
}
