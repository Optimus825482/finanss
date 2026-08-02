from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Ensure pgvector extension exists + idempotent migration check.

    Docker'da docker-entrypoint.sh `alembic upgrade head` zaten çalıştırır.
    Lokal/manuel başlatmada da şema güncel kalsın: alembic_version yoksa
    veya head'den geriyse `alembic upgrade head` çalıştır (subprocess, idempotent).
    create_all KULLANILMAZ — schema drift'i maskeler (migration'lar tek kaynak).
    """
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Idempotent migration check: alembic_version tablosu var mı?
    try:
        with engine.connect() as conn:
            has_version = conn.execute(text(
                "SELECT to_regclass('public.alembic_version')"
            )).scalar() is not None
    except Exception:
        has_version = False

    # Version tablosu yoksa veya head'den geriyse migration çalıştır.
    # Postgres'te to_regclass çalışır; SQLite'ta yoksa yine deneriz.
    if not has_version:
        _run_alembic_upgrade()
    else:
        try:
            with engine.connect() as conn:
                from alembic.config import Config
                from alembic.script import ScriptDirectory
                from alembic.runtime.migration import MigrationContext
                ctx = MigrationContext.configure(conn)
                current = set(ctx.get_current_heads())
                script = ScriptDirectory.from_config(Config("alembic.ini"))
                heads = set(script.get_heads())
                if current != heads:
                    _run_alembic_upgrade()
        except Exception:
            # Migration check başarısızsa sessiz geç — Docker zaten hallediyor.
            pass


def _run_alembic_upgrade():
    """`alembic upgrade head` çalıştır (subprocess). Hata sessiz geçilir —
    Docker entrypoint zaten migration'ı çalıştırır; burada local dev kolaylığı."""
    import logging
    import os
    import subprocess
    import sys
    logger = logging.getLogger(__name__)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            logger.info("Alembic migration otomatik uygulandı (upgrade head)")
        else:
            logger.warning("Alembic otomatik migration başarısız: %s", result.stderr[-500:])
    except Exception as e:
        logger.warning("Alembic otomatik migration çalıştırılamadı: %s", e)
