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
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <head>
        <Script id="theme-init" strategy="beforeInteractive">
          {`(function(){try{var t=localStorage.getItem('orbis-theme');if(t==='light'){document.documentElement.setAttribute('data-theme','light')}}catch(e){}})()`}
        </Script>
      </head>
      <body className="font-sans antialiased">
        <Navbar />
        <ErrorBoundary>{children}</ErrorBoundary>
      </body>
    </html>
  );
}
