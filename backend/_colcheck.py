from dotenv import load_dotenv; load_dotenv()
from app.database import Base
from app.models import *

for tname in ("watchlist_items", "stock_picks", "portfolio_positions", "trading_decisions", "balance_transactions", "pending_orders", "portfolios", "system_settings"):
    t = Base.metadata.tables.get(tname)
    if t is None:
        print(tname, "=> NO TABLE IN METADATA")
        continue
    cols = sorted(t.columns.keys())
    print(tname, "=>", cols)
