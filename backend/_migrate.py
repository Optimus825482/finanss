"""Migration'ı .env ile uygula."""
from dotenv import load_dotenv

load_dotenv(".env")

import alembic.config

alembic.config.main(argv=["upgrade", "head"])
