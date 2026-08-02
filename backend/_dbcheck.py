from dotenv import load_dotenv; load_dotenv()
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ["DATABASE_URL"])
c = e.connect()
for t in ("alembic_version", "portfolios", "positions", "trades", "agent_runs"):
    print(t, "=>", c.execute(text(f"select to_regclass('public.{t}')")).scalar())
c.close()
