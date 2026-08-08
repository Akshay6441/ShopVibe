"""Shared pytest fixtures — runs against real PostgreSQL (CI service container)."""
import os

# Set environment variables FIRST, before any imports from the app
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/mydatabase"
)

os.environ["DATABASE_URL"] = DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-32chars-for-tests!")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_placeholder")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_placeholder")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
# Keep tests hermetic: never let real credentials from backend/.env leak in.
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("SF_CLIENT_ID", "")
os.environ.setdefault("SF_CLIENT_SECRET", "")
os.environ.setdefault("SF_USERNAME", "")
os.environ.setdefault("SF_PRIVATE_KEY", "")
os.environ.setdefault("SF_LOGIN_URL", "")
os.environ.setdefault("SF_INSTANCE_URL", "")

# NOW import app modules (after env vars are set)
import pytest                                # noqa: E402
from fastapi.testclient import TestClient    # noqa: E402
from sqlalchemy.orm import sessionmaker      # noqa: E402
from sqlalchemy import text as _sql          # noqa: E402

from database import Base, get_db, engine   # noqa: E402
from main import app                         # noqa: E402
import models                                # noqa: E402
from auth import hash_password               # noqa: E402

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create all tables once per session, drop after all tests."""
    # Create PostgreSQL ENUM types if using Postgres
    is_postgres = "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL
    if is_postgres:
        _CREATE_ENUMS = """
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
        CREATE TYPE userrole AS ENUM ('customer', 'admin');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'orderstatus') THEN
        CREATE TYPE orderstatus AS ENUM ('pending', 'processing', 'shipped', 'delivered', 'cancelled');
    END IF;
END $$;
"""
        with engine.connect() as conn:
            conn.execute(_sql(_CREATE_ENUMS))
            conn.commit()

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db():
    """Each test gets a clean transaction that is rolled back after."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db):
    user = models.User(
        name="Admin", email="admin@test.com",
        hashed_password=hash_password("adminpass"),
        role=models.UserRole.admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def regular_user(db):
    user = models.User(
        name="Alice", email="alice@test.com",
        hashed_password=hash_password("alicepass"),
        role=models.UserRole.customer,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def category(db):
    cat = models.Category(
        name="Electronics", slug="electronics", description="Gadgets"
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@pytest.fixture
def product(db, category):
    p = models.Product(
        name="Test Laptop", slug="test-laptop",
        description="A great laptop", price=999.99,
        stock_quantity=10, category_id=category.id,
        brand="TestBrand", is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def auth_headers(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
