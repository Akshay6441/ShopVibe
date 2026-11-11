import os
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from config import settings


def _normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _sqlite_fallback_url() -> str:
    """Return a writable SQLite URL for serverless/demo runs."""
    db_path = os.path.join(tempfile.gettempdir(), "shopvibe.db").replace("\\", "/")
    if db_path.startswith("/"):
        return f"sqlite:////{db_path.lstrip('/')}"
    return f"sqlite:///{db_path}"


def _build_engine():
    db_url = _normalize_db_url(settings.database_url)
    is_memory = db_url in ("sqlite://", "sqlite:///:memory:")

    if is_memory:
        # Shared in-memory DB — used by tests via StaticPool
        return db_url, create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    if db_url.startswith("sqlite"):
        return db_url, create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 15},
        )

    if settings.app_env == "test":
        return db_url, create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )

    is_vercel = bool(os.getenv("VERCEL"))
    is_default_local_pg = (not db_url) or ("localhost" in db_url) or ("127.0.0.1" in db_url)

    # Skip waiting on localhost Postgres inside Vercel serverless containers
    if db_url and not (is_vercel and is_default_local_pg):
        try:
            connect_args = {"connect_timeout": 3} if is_default_local_pg else {}
            pg_engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                connect_args=connect_args,
            )
            with pg_engine.connect():
                pass
            return db_url, pg_engine
        except Exception:
            if not is_default_local_pg:
                raise

    fallback_url = _sqlite_fallback_url()
    return fallback_url, create_engine(
        fallback_url,
        connect_args={"check_same_thread": False, "timeout": 15},
    )


DATABASE_URL, engine = _build_engine()
IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_POSTGRES = not IS_SQLITE

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

_init_hook = None


def register_db_init(hook) -> None:
    """Register a lazy DB initializer called before opening non-test sessions."""
    global _init_hook
    _init_hook = hook


def get_db():
    if _init_hook is not None:
        _init_hook()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
