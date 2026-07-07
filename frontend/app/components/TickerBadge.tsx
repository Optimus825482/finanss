// Borsa kodu → Gösterim adı
const EXCHANGE_NAMES: Record<string, string> = {
  NMS: "NASDAQ",
  NGM: "NASDAQ GM",
  NCM: "NASDAQ CM",
  NYQ: "NYSE",
  ASE: "AMEX",
  IST: "BIST",
  LSE: "LSE",
  JPX: "TSE",
  TKS: "TSE",
  EBS: "SIX",
  HKG: "HKEX",
  SHH: "SSE",
  SZR: "SZSE",
  PAR: "Euronext",
  AMS: "Euronext",
  BRU: "Euronext",
  LIS: "Euronext",
  MCE: "BME",
  MIL: "Borsa Italiana",
  CPH: "Nasdaq Nordic",
  HEL: "Nasdaq Nordic",
  STO: "Nasdaq Nordic",
  OSL: "Oslo Børs",
  VIE: "Wiener Börse",
  TOR: "TSX",
  NEO: "NEO",
  PCX: "NYSE Arca",
  SAO: "B3",
  BUE: "BYMA",
};

function exchangeDisplay(exchange: string): string {
  return EXCHANGE_NAMES[exchange] || exchange;
}

// Exchange ve sektör renk haritaları
const EXCHANGE_COLORS: Record<string, { bg: string; text: string }> = {
  NMS:   { bg: "rgba(59,130,246,0.15)",  text: "#60A5FA" }, // NASDAQ — mavi
  NGM:   { bg: "rgba(59,130,246,0.15)",  text: "#60A5FA" }, // NASDAQ GM
  NCM:   { bg: "rgba(59,130,246,0.15)",  text: "#60A5FA" }, // NASDAQ CM
  NYQ:   { bg: "rgba(20,184,166,0.15)",  text: "#2DD4BF" }, // NYSE — turkuaz
  ASE:   { bg: "rgba(20,184,166,0.15)",  text: "#2DD4BF" }, // AMEX
  IST:   { bg: "rgba(234,179,8,0.15)",   text: "#FACC15" }, // BIST — altın
  LSE:   { bg: "rgba(168,85,247,0.15)",  text: "#C084FC" }, // Londra — mor
  JPX:   { bg: "rgba(251,146,60,0.15)",  text: "#FB923C" }, // Tokyo — turuncu
  TKS:   { bg: "rgba(251,146,60,0.15)",  text: "#FB923C" }, // Tokyo
  EBS:   { bg: "rgba(74,222,128,0.15)",  text: "#4ADE80" }, // İsviçre — yeşil
  HKG:   { bg: "rgba(236,72,153,0.15)",  text: "#F472B6" }, // Hong Kong — pembe
  SHH:   { bg: "rgba(239,68,68,0.15)",   text: "#F87171" }, // Şanghay — kırmızı
  SZR:   { bg: "rgba(239,68,68,0.15)",   text: "#F87171" }, // Shenzhen
  PAR:   { bg: "rgba(96,165,250,0.15)",  text: "#93C5FD" }, // Paris
  AMS:   { bg: "rgba(251,191,36,0.15)",  text: "#FCD34D" }, // Amsterdam
  BRU:   { bg: "rgba(167,139,250,0.15)", text: "#C4B5FD" }, // Brüksel
  LIS:   { bg: "rgba(52,211,153,0.15)",  text: "#6EE7B7" }, // Lizbon
  MCE:   { bg: "rgba(252,165,165,0.15)", text: "#FCA5A5" }, // Madrid
  MIL:   { bg: "rgba(196,204,140,0.15)", text: "#E2E8A0" }, // Milano
  CPH:   { bg: "rgba(147,197,253,0.15)", text: "#BFDBFE" }, // Kopenhag
  HEL:   { bg: "rgba(125,211,252,0.15)", text: "#BAE6FD" }, // Helsinki
  STO:   { bg: "rgba(165,180,252,0.15)", text: "#C7D2FE" }, // Stockholm
  OSL:   { bg: "rgba(252,211,77,0.15)",  text: "#FDE68A" }, // Oslo
  VIE:   { bg: "rgba(253,186,116,0.15)", text: "#FDBA74" }, // Viyana
  TOR:   { bg: "rgba(251,113,133,0.15)", text: "#FDA4AF" }, // Toronto
  PCX:   { bg: "rgba(94,234,212,0.15)",  text: "#99F6E4" }, // Pacific
  BUE:   { bg: "rgba(252,165,165,0.15)", text: "#FCA5A5" }, // Buenos Aires
  SAO:   { bg: "rgba(165,243,140,0.15)", text: "#B9F59C" }, // Sao Paulo
  NEO:   { bg: "rgba(196,181,253,0.15)", text: "#DDD6FE" }, // NEO
};

const SECTOR_COLORS: Record<string, { bg: string; text: string }> = {
  Technology:              { bg: "rgba(59,130,246,0.15)",  text: "#60A5FA" }, // Mavi
  "Consumer Electronics":  { bg: "rgba(59,130,246,0.15)",  text: "#60A5FA" },
  "Software—Application":  { bg: "rgba(59,130,246,0.15)",  text: "#60A5FA" },
  "Semiconductors":        { bg: "rgba(59,130,246,0.15)",  text: "#60A5FA" },
  "Financial Services":    { bg: "rgba(234,179,8,0.15)",   text: "#FACC15" }, // Altın
  Banking:                 { bg: "rgba(234,179,8,0.15)",   text: "#FACC15" },
  "Banks—Diversified":     { bg: "rgba(234,179,8,0.15)",   text: "#FACC15" },
  Insurance:               { bg: "rgba(234,179,8,0.15)",   text: "#FACC15" },
  Healthcare:              { bg: "rgba(74,222,128,0.15)",  text: "#4ADE80" }, // Yeşil
  Biotechnology:           { bg: "rgba(74,222,128,0.15)",  text: "#4ADE80" },
  "Drug Manufacturers":    { bg: "rgba(74,222,128,0.15)",  text: "#4ADE80" },
  Energy:                  { bg: "rgba(239,68,68,0.15)",   text: "#F87171" }, // Kırmızı
  "Oil & Gas":              { bg: "rgba(239,68,68,0.15)",   text: "#F87171" },
  "Consumer Cyclical":      { bg: "rgba(20,184,166,0.15)",  text: "#2DD4BF" }, // Turkuaz
  "Consumer Defensive":     { bg: "rgba(20,184,166,0.15)",  text: "#2DD4BF" },
  Retail:                   { bg: "rgba(20,184,166,0.15)",  text: "#2DD4BF" },
  Industrials:              { bg: "rgba(148,163,184,0.15)", text: "#94A3B8" }, // Gri
  "Aerospace & Defense":    { bg: "rgba(148,163,184,0.15)", text: "#94A3B8" },
  Transportation:           { bg: "rgba(148,163,184,0.15)", text: "#94A3B8" },
  "Real Estate":            { bg: "rgba(168,85,247,0.15)",  text: "#C084FC" }, // Mor
  Utilities:                { bg: "rgba(251,191,36,0.15)",  text: "#FCD34D" }, // Sarı
  "Communication Services": { bg: "rgba(236,72,153,0.15)",  text: "#F472B6" }, // Pembe
  "Basic Materials":        { bg: "rgba(251,146,60,0.15)",  text: "#FB923C" }, // Turuncu
};

function getExchangeStyle(exchange: string) {
  return EXCHANGE_COLORS[exchange] || { bg: "rgba(148,163,184,0.10)", text: "var(--term-muted)" };
}

function getSectorStyle(sector: string) {
  for (const [key, style] of Object.entries(SECTOR_COLORS)) {
    if (sector.toLowerCase().includes(key.toLowerCase())) {
      return style;
    }
  }
  return { bg: "rgba(148,163,184,0.10)", text: "var(--term-muted)" };
}

export function ExchangeBadge({ exchange, name }: { exchange: string; name: string }) {
  const style = getExchangeStyle(exchange);
  const display = exchangeDisplay(name || exchange);
  return (
    <span
      className="font-mono text-[9px] px-1.5 py-0.5 rounded-sm shrink-0"
      style={{
        backgroundColor: style.bg,
        color: style.text,
        border: `1px solid ${style.text}20`,
      }}
    >
      {display}
    </span>
  );
}

export function SectorBadge({ sector }: { sector: string }) {
  if (!sector) return null;
  const style = getSectorStyle(sector);
  return (
    <span
      className="font-mono text-[9px] px-1.5 py-0.5 rounded-sm shrink-0"
      style={{
        backgroundColor: style.bg,
        color: style.text,
        border: `1px solid ${style.text}20`,
      }}
    >
      {sector}
    </span>
  );
}
