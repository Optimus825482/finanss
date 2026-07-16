# ORBIS FINAI — ORBIS Finance Analyze Team

5-agent AI research pipeline (Scan → Fundamental → Sentiment → Risk → Report).
Daily 08:00 Europe/Istanbul schedule + manual trigger via Next.js UI.

## Stack

- **DB:** PostgreSQL + pgvector required (`DATABASE_URL`). No SQLite.
- **Backend:** FastAPI on port **8012**
- **Frontend:** Next.js on port **3009**

## Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
# set DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/orbis
uvicorn app.main:app --reload --port 8012
```

## Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# set NEXT_PUBLIC_API_KEY to match backend API_KEY
npm run dev
```

UI: http://localhost:3009 · API: http://localhost:8012

## Auth / admin

- Backend `API_KEY` + frontend `NEXT_PUBLIC_API_KEY` for request auth.
- Destructive admin reset needs header `X-Confirm-Reset: yes` (and `API_KEY` or local `ALLOW_DESTRUCTIVE_RESET=1`).

## Universe & scoring

- Stock universe: `backend/app/config.py` → `STOCK_UNIVERSE` (NASDAQ/NYSE/BIST/…).
- Weights: `SCORING_WEIGHTS` in same file.
- Optional outbound alerts: `WEBHOOK_URL` (Slack-ish JSON).

## Notes

- yfinance free/unofficial — rate limits possible; agents skip bad symbols.
- Schedule: `SCHEDULE_HOUR` / `SCHEDULE_MINUTE` in config.
- Portfolio buy sizing uses numpy mean-variance search (no scipy).
