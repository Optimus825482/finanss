import os
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL", ""))
from app.database import SessionLocal
from sqlalchemy import text as sqltext
s = SessionLocal()
print("portfolios:", [r[0] for r in s.execute(sqltext("SELECT slug FROM portfolios")).fetchall()])
print("settings:", [r[0] for r in s.execute(sqltext("SELECT key FROM system_settings")).fetchall()])
