from dotenv import load_dotenv; load_dotenv()
import json, sys
sys.stdout.reconfigure(line_buffering=True)
from app.database import SessionLocal, init_db
from app.services.crypto_scalper import _tick, status
init_db()
db = SessionLocal()
try:
    _tick(db)
    print("TICK OK")
    with open("_scalper_test.json", "w") as f:
        json.dump(status(), f, default=str, indent=1)
finally:
    db.close()
