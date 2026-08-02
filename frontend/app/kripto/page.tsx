"use client";

import { useEffect, useState, useCallback } from "react";
import {
  api, AgentPortfolio, CryptoKline, ScalpCardsResponse, ScalpCard,
} from "../lib/api";
import CryptoChart from "../components/CryptoChart";

/**
 * KRİPTO PORTFÖY YÖNETİMİ — otonom scalper kontrol paneli.
 *
 * Üst: M5 mum grafiği (sembol seçici).
 * Orta: kural bazlı AL/HOLD/SELL kartları — gerçekleşen şart highlight.
 * Alt: açık pozisyonlar — canlı PnL hesabı (1s güncellenir).
 * Otonom trade: backend crypto_scalper döngüsü (▶ BAŞLAT / ■ DURDUR).
 */

const BORDER = "var(--term-border)";
const GREEN = "var(--term-green)";
const RED = "var(--term-red)";
const AMBER = "var(--term-amber)";
const MUTED = "var(--term-muted)";
const TEXT = "var(--term-text)";
const PANEL = "var(--term-panel)";

const ACTION_META: Record<ScalpCard["action"], { label: string; color: string; glow: boolean }> = {
  buy:  { label: "AL",    color: GREEN, glow: true },
  sell: { label: "SAT",   color: RED,   glow: true },
  hold: { label: "HOLD",  color: AMBER, glow: false },
  wait: { label: "BEKLE", color: MUTED, glow: false },
};

export default function KriptoPage() {
  // Grafik
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [klines, setKlines] = useState<CryptoKline[]>([]);
  const [universe, setUniverse] = useState<string[]>([]);

  // Scalper kartları + durum
  const [scalp, setScalp] = useState<ScalpCardsResponse | null>(null);
  const [scalpBusy, setScalpBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Açık pozisyonlar (portföy API)
  const [portfolio, setPortfolio] = useState<AgentPortfolio | null>(null);

  const loadUniverse = useCallback(async () => {
    try { const u = await api.cryptoUniverse(); setUniverse(u.symbols); } catch { /* */ }
  }, []);

  const loadKlines = useCallback(async () => {
    try { const k = await api.cryptoKlines(symbol, "5m", 200); setKlines(k.klines); } catch { /* */ }
  }, [symbol]);

  const loadScalp = useCallback(async () => {
    try { setScalp(await api.cryptoScalpCards()); } catch { /* scalper kapalı */ }
  }, []);

  const loadPortfolio = useCallback(async () => {
    try { setPortfolio(await api.getAgentPortfolio("crypto")); } catch { /* */ }
  }, []);

  // 3s canlı: kartlar + açık pozisyonlar. Grafik 30s.
  useEffect(() => {
    loadScalp();
    loadPortfolio();
    const i = setInterval(() => { loadScalp(); loadPortfolio(); }, 3_000);
    return () => clearInterval(i);
  }, [loadScalp, loadPortfolio]);

  useEffect(() => {
    loadKlines();
    const i = setInterval(loadKlines, 30_000);
    return () => clearInterval(i);
  }, [loadKlines]);

  useEffect(() => { loadUniverse(); }, [loadUniverse]);

  const handleStart = async () => {
    setScalpBusy(true); setError(null);
    try { await api.cryptoScalpStart(); await loadScalp(); }
    catch (e) { setError(`Scalper başlatılamadı: ${e instanceof Error ? e.message : "?"}`); }
    finally { setScalpBusy(false); }
  };

  const handleStop = async () => {
    setScalpBusy(true); setError(null);
    try { await api.cryptoScalpStop(); await loadScalp(); }
    catch (e) { setError(`Scalper durdurulamadı: ${e instanceof Error ? e.message : "?"}`); }
    finally { setScalpBusy(false); }
  };

  const lastRound = scalp?.status?.last_round as Record<string, unknown> | null;
  const equity = lastRound?.equity_usdt as number | undefined;
  const openPos = portfolio?.positions ?? [];
  const buyCards = scalp?.cards.filter(c => c.action === "buy") ?? [];
  const sellCards = scalp?.cards.filter(c => c.action === "sell") ?? [];

  const fmtPrice = (p: number | null | undefined) =>
    p == null ? "—" : `$${p >= 1 ? p.toFixed(2) : p.toFixed(6)}`;

  return (
    <div className="max-w-6xl mx-auto px-3 sm:px-6 py-4 space-y-4">
      {/* Başlık + durum */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="font-mono text-sm font-bold tracking-wider" style={{ color: GREEN }}>
          ₿ KRİPTO PORTFÖY YÖNETİMİ
        </h1>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px]" style={{ color: scalp?.running ? GREEN : RED }}>
            {scalp?.running ? "● OTONOM TRADE ÇALIŞIYOR" : "○ OTONOM TRADE DURDU"}
          </span>
          {scalp?.running ? (
            <button onClick={handleStop} disabled={scalpBusy}
              className="font-mono text-[10px] px-3 py-1.5 rounded-sm transition-none disabled:opacity-40"
              style={{ border: `1px solid ${RED}`, color: RED }}>
              ■ DURDUR
            </button>
          ) : (
            <button onClick={handleStart} disabled={scalpBusy}
              className="font-mono text-[10px] px-3 py-1.5 rounded-sm transition-none disabled:opacity-40"
              style={{ border: `1px solid ${GREEN}`, color: GREEN }}>
              ▶ BAŞLAT
            </button>
          )}
        </div>
      </div>
      {error && (
        <div className="font-mono text-[11px] px-3 py-2 rounded-sm"
          style={{ border: `1px solid ${RED}`, color: RED, backgroundColor: PANEL }}>
          {error}
        </div>
      )}

      {/* Parametreler + son tur özeti */}
      {scalp?.params && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] px-3 py-2 rounded-sm"
          style={{ border: `1px solid ${BORDER}`, color: MUTED, backgroundColor: PANEL }}>
          <span>AL ≥ {scalp.params.buy_threshold}</span>
          <span>STOP -{scalp.params.stop_loss_pct}%</span>
          <span>KÂR +{scalp.params.take_profit_pct}%</span>
          <span>MAX {scalp.params.max_open_positions} poz</span>
          <span>${scalp.params.position_usd}/poz</span>
          <span>Tur {scalp.status?.rounds ?? 0}</span>
          {equity != null && <span style={{ color: AMBER }}>Equity ${equity.toFixed(2)}</span>}
          {lastRound && (
            <span className="ml-auto">
              Son tur: {lastRound.ok ? `${lastRound.scanned} taranan · ${lastRound.open_positions} açık poz` : String(lastRound.error ?? "hata")}
            </span>
          )}
        </div>
      )}

      {/* ── ÜST: M5 GRAFİK ── */}
      <div className="rounded-sm p-3" style={{ border: `1px solid ${BORDER}`, backgroundColor: PANEL }}>
        <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
          <div className="font-mono text-xs tracking-wider" style={{ color: MUTED }}>
            M5 MUM GRAFİĞİ — <span className="font-bold" style={{ color: TEXT }}>{symbol}</span>
          </div>
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)}
            className="font-mono text-[10px] px-2 py-1 rounded-sm transition-none"
            style={{ backgroundColor: "var(--term-bg)", border: `1px solid ${BORDER}`, color: TEXT }}>
            {(universe.length ? universe : ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]).map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <CryptoChart klines={klines} height={360} />
      </div>

      {/* ── ORTA: AL/HOLD/SELL KARTLARI (gerçekleşen şart highlight) ── */}
      <div className="rounded-sm p-3" style={{ border: `1px solid ${BORDER}`, backgroundColor: PANEL }}>
        <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
          <div className="font-mono text-xs tracking-wider" style={{ color: MUTED }}>
            KURAL BAZLI AL / HOLD / SAT — <span style={{ color: AMBER }}>gerçekleşen şartlar vurgulu</span>
          </div>
          <div className="flex gap-3 font-mono text-[10px]">
            <span style={{ color: GREEN }}>▲ AL {buyCards.length}</span>
            <span style={{ color: RED }}>▼ SAT {sellCards.length}</span>
            <span style={{ color: MUTED }}>Açık {openPos.length}</span>
          </div>
        </div>

        {!scalp || scalp.cards.length === 0 ? (
          <div className="py-10 text-center font-mono text-xs" style={{ color: MUTED }}>
            Kartlar yükleniyor…
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
            {scalp.cards.map((c) => {
              const meta = ACTION_META[c.action];
              const triggered = c.action === "buy" || c.action === "sell";
              const cardBorder = triggered ? meta.color : BORDER;
              const cardBg = triggered ? (c.action === "buy" ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)") : "rgba(0,0,0,0.2)";
              const pnl = c.pnl_pct;
              const pnlColor = pnl == null ? MUTED : pnl >= 0 ? GREEN : RED;
              return (
                <div key={c.ticker} className="rounded-sm p-3 relative"
                  style={{
                    border: `2px solid ${cardBorder}`,
                    backgroundColor: cardBg,
                    boxShadow: meta.glow ? `0 0 12px ${c.action === "buy" ? "rgba(34,197,94,0.35)" : "rgba(239,68,68,0.35)"}` : "none",
                  }}>
                  {triggered && (
                    <span className="absolute top-1.5 right-1.5 font-mono text-[8px] tracking-wider px-1 py-0.5 rounded-sm"
                      style={{ backgroundColor: meta.color, color: "#0b0b0f", fontWeight: 700 }}>
                      ŞART TUTTU
                    </span>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm font-bold" style={{ color: TEXT }}>{c.ticker}</span>
                    <span className="font-mono text-[11px] px-2 py-0.5 rounded-sm font-bold"
                      style={{ backgroundColor: meta.color, color: "#0b0b0f" }}>
                      {meta.label}
                    </span>
                  </div>
                  <div className="font-mono text-lg font-bold mt-1" style={{ color: TEXT }}>
                    {fmtPrice(c.price)}
                  </div>
                  <div className="font-mono text-[10px] mt-1" style={{ color: MUTED }}>
                    COMP <span style={{ color: TEXT }}>{c.composite != null ? c.composite.toFixed(2) : "—"}</span>
                    {" · "}RSI {c.rsi != null ? c.rsi.toFixed(0) : "—"}
                  </div>
                  <div className="font-mono text-[10px]" style={{ color: MUTED }}>
                    M5 {c.momentum_5m != null ? c.momentum_5m.toFixed(0) : "—"}
                    {c.momentum_15m != null ? ` / 15m ${c.momentum_15m.toFixed(0)}` : ""}
                    {c.momentum_1h != null ? ` / 1h ${c.momentum_1h.toFixed(0)}` : ""}
                  </div>
                  {c.position_open && (
                    <div className="font-mono text-[10px] mt-1" style={{ color: pnlColor }}>
                      POZ x{c.position_qty} @ {fmtPrice(c.entry_price)}
                      {" · "}{pnl != null ? `${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}%` : ""}
                    </div>
                  )}
                  <div className="font-mono text-[10px] mt-1.5 leading-tight" style={{ color: triggered ? meta.color : MUTED }}>
                    {c.rule}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── ALT: AÇIK POZİSYONLAR (canlı PnL) ── */}
      <div className="rounded-sm p-3" style={{ border: `1px solid ${BORDER}`, backgroundColor: PANEL }}>
        <div className="font-mono text-xs tracking-wider mb-2" style={{ color: MUTED }}>
          AÇIK POZİSYONLAR {openPos.length > 0 && <span style={{ color: AMBER }}>({openPos.length})</span>}
        </div>

        {openPos.length === 0 ? (
          <div className="py-6 text-center font-mono text-xs" style={{ color: MUTED }}>
            Açık pozisyon yok. ▶ BAŞLAT ile otonom trade devreye girer; sinyal koşulları tutunca otomatik alım yapılır.
          </div>
        ) : (
          <div className="space-y-1">
            {openPos.map((pos) => {
              const pnl = pos.unrealized_pl ?? 0;
              const pnlPct = pos.entry_price > 0 ? (pnl / (pos.entry_price * pos.quantity)) * 100 : 0;
              const col = pnl >= 0 ? GREEN : RED;
              return (
                <div key={pos.id} className="flex items-center justify-between px-3 py-2 font-mono text-xs rounded-sm"
                  style={{ border: `1px solid ${BORDER}`, backgroundColor: "rgba(0,0,0,0.2)" }}>
                  <div>
                    <span className="font-bold" style={{ color: TEXT }}>{pos.ticker}</span>
                    <span style={{ color: MUTED }}> x{pos.quantity}</span>
                    <span style={{ color: MUTED }}> @ {fmtPrice(pos.entry_price)}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    {pos.current_price != null && (
                      <span style={{ color: MUTED }}>{fmtPrice(pos.current_price)}</span>
                    )}
                    <span className="font-bold" style={{ color: col }}>
                      {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}
                      <span className="text-[10px] font-normal"> ({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%)</span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Otonom trade açıklaması */}
      <div className="font-mono text-[10px] px-3 py-2 rounded-sm" style={{ border: `1px dashed ${BORDER}`, color: MUTED }}>
        OTONOM TRADE: her saniye evren taranır → composite ≥ AL eşiği (65) ise otomatik alım; açık pozda stop-loss
        (-1.5%), take-profit (+2.5%) veya sinyal zayıflaması (&lt; 55) ise otomatik satım. Maksimum {scalp?.params.max_open_positions ?? 3} eşzamanlı poz, ${scalp?.params.position_usd ?? 25}/poz.
      </div>
    </div>
  );
}
