"""
Merkezi konfigurasyon: izlenecek hisse evreni, esik degerler, zamanlama.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# PostgreSQL (primary) — Docker'da 'db' hostname, lokal'de 'localhost'
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:518518Erkan@localhost:5432/orbis_finai")

# Kure edilmis global hisse evreni (borsa bazli).
# Ilk asama tarama (teknik filtre) bu listeden yapilir.
STOCK_UNIVERSE = {
    "NASDAQ": [
        # Teknoloji
        "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AMD","AVGO","CRM",
        "ADBE","NFLX","INTC","CSCO","PEP","COST","CMCSA","TXN","QCOM","INTU",
        "AMGN","GILD","ISRG","REGN","VRTX","ADP","MRNA","PYPL","AMAT","LRCX",
        "MU","ADI","KLAC","SNPS","CDNS","MELI","WDAY","SNOW","DDOG","CRWD",
        "ZS","NET","PLTR","MDB","TEAM","DASH","ABNB","ZM","DKNG",
        "PANW","FTNT","MRVL","NXPI","ASML","CTAS","ORLY","MAR","HLT",
        "PAYX","FAST","CTSH","BIIB","CHTR","LULU","EA","TTD","SPLK","HUBS",
    ],
    "NYSE": [
        # Finans
        "JPM","BAC","WFC","GS","MS","C","AXP","V","MA","BLK",
        "SCHW","PNC","USB","TFC","BK","COF","AIG","MET","PRU","ALL",
        # Saglik
        "JNJ","UNH","PFE","MRK","ABBV","LLY","TMO","DHR","ABT","BMY",
        "SYK","CI","HUM","CVS","ANTM","REGN","VRTX","GILD","AMGN","BIIB",
        # Enerji & Sanayi
        "XOM","CVX","CAT","GE","BA","HON","LMT","UNP","RTX","DE",
        "MMM","ITW","ETN","EMR","ROK","PH","NSC","FDX","UPS",
        # Tuketici & Perakende
        "WMT","HD","KO","PEP","PG","NKE","MCD","SBUX","TGT","LOW",
        "TJX","DG","ROST","BBY","AZO","ORLY","CMG","YUM","DPZ",
        # Diger
        "DIS","NFLX","VZ","T","TMUS","SPG","O","PLD","AMT","WELL",
        "DUK","SO","NEE","D","AEP","XEL","SRE","ED","PEG","EXC",
        "LIN","APD","ECL","SHW","FCX","NEM","GOLD","AEM",
    ],
    "BIST": [
        # Bankacilik
        "AKBNK.IS","GARAN.IS","ISCTR.IS","YKBNK.IS","VAKBN.IS",
        "HALKB.IS","TSKB.IS","ALBRK.IS",
        # Holding & Yatirim
        "KCHOL.IS","SAHOL.IS","SISE.IS","AGHOL.IS","ENKAI.IS",
        "TAVHL.IS","DOAS.IS","GUBRF.IS","KOZAL.IS","KOZAA.IS",
        # Sanayi & Metal
        "EREGL.IS","KRDMD.IS","CEMTS.IS","ISDMR.IS","CIMSA.IS",
        "TUPRS.IS","PETKM.IS","SASA.IS","HEKTS.IS","SOKM.IS",
        "FROTO.IS","TOASO.IS","TTRAK.IS","OTKAR.IS","ARCLK.IS",
        "VESTL.IS","FORD.IS","KARSN.IS","BRSAN.IS","PGSUS.IS",
        # Perakende & Gida
        "BIMAS.IS","MGROS.IS","AEFES.IS","CCOLA.IS",
        "ULKER.IS","KERVT.IS","OBAMS.IS",
        # Telekom & Teknoloji
        "TCELL.IS","TTKOM.IS","ASELS.IS","NETAS.IS","LOGO.IS",
        "MIATK.IS","ARDYZ.IS","SMART.IS",
        # Enerji
        "ZOREN.IS","AKSEN.IS","AYEN.IS","ODAS.IS","MAGEN.IS",
        "GWIND.IS","ESCOM.IS","ARTMS.IS",
        # Insaat & GYO
        "EKGYO.IS","ISGYO.IS","AKFGY.IS","TRGYO.IS","HLGYO.IS",
        "OYAKC.IS","KONTR.IS","ORGE.IS",
        # Sigorta & Finans
        "ANSGR.IS","TSGYO.IS","AKGRT.IS","RAYSG.IS",
        # Diger
        "THYAO.IS","PGSUS.IS","MAVI.IS",
        "KONYA.IS","BAGFS.IS","IZENR.IS","DOCO.IS",
        "KMPUR.IS","ALKA.IS","ORCAY.IS","UFUK.IS","AKFIS.IS",
    ],
    "LSE": [
        "AZN.L","SHEL.L","HSBA.L","ULVR.L","BP.L","GSK.L",
        "RIO.L","BATS.L","DGE.L","REL.L","LLOY.L","VOD.L",
        "NG.L","TSCO.L","PRU.L","BA.L","BT-A.L","AHT.L",
        "GLEN.L","STAN.L","BARC.L","NWG.L","LGEN.L","AV.L",
        "CPG.L","SDR.L","SMT.L","III.L","PSON.L","TW.L",
    ],
    "Euronext": [
        "ASML.AS","MC.PA","SAP.DE","SIE.DE","SAN.PA","BNP.PA",
        "TTE.PA","AIR.PA","OR.PA","DG.PA","CS.PA","INGA.AS",
        "ADYEN.AS","PRX.AS","DSY.PA","SU.PA","KER.PA",
        "AI.PA","EL.PA","RI.PA","VOW3.DE","DTE.DE","ALV.DE",
        "MBG.DE","BMW.DE","BAS.DE","BAYN.DE","IFX.DE",
    ],
}

# Varsayilan izleme evreni (geriye donuk uyumluluk)
WATCHLIST = STOCK_UNIVERSE["NASDAQ"][:15] + STOCK_UNIVERSE["NYSE"][:15] + STOCK_UNIVERSE["BIST"][:10]

BENCHMARK_TICKER = "^GSPC"

SCORING_WEIGHTS = {
    "fundamental": 0.40,
    "sentiment": 0.30,
    "risk": 0.30,
}

TOP_N_PICKS = 8

# Tarama esikleri
SCANNER_MIN_MOMENTUM_PCT = -100
SCANNER_LOOKBACK_DAYS = "3mo"

SCHEDULE_HOUR = 8
SCHEDULE_MINUTE = 0
TIMEZONE = "Europe/Istanbul"
