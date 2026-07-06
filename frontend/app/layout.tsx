import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Masa | Uluslararası Hisse Araştırma Masası",
  description: "5 ajanlı araştırma ekibi tarafından üretilen günlük hisse senedi raporu",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
