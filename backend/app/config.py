"""
Merkezi konfigürasyon: izlenecek hisse evreni, eşik değerler, zamanlama.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "reports.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Uluslararası hisse evreni: ABD, Avrupa, Asya karışık.
# Bu liste genişletilebilir / ileride dinamik tarama (index constituents) ile değiştirilebilir.
WATCHLIST = [
    # ABD - Teknoloji & Büyüme
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD", "AVGO", "CRM",
    # ABD - Finans & Sanayi
    "JPM", "V", "UNH", "XOM", "CAT",
    # Avrupa
    "ASML.AS", "SAP.DE", "SIE.DE", "MC.PA", "NESN.SW", "NOVN.SW", "AZN.L", "SHEL.L",
    # Asya
    "7203.T", "6758.T", "005930.KS", "0700.HK", "TSM",
]

BENCHMARK_TICKER = "^GSPC"

SCORING_WEIGHTS = {
    "fundamental": 0.40,
    "sentiment": 0.30,
    "risk": 0.30,  # risk skoru ters çevrilerek (düşük risk = yüksek katkı) hesaba katılır
}

TOP_N_PICKS = 8

# Tarama eşikleri
SCANNER_MIN_MOMENTUM_PCT = -100  # şimdilik tüm evreni geçir, filtre gerektiğinde sıkılaştırılır
SCANNER_LOOKBACK_DAYS = "3mo"

SCHEDULE_HOUR = 8
SCHEDULE_MINUTE = 0
TIMEZONE = "Europe/Istanbul"
