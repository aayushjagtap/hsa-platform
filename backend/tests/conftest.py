import os

# Tests run against a real Postgres database (not SQLite), because the
# concurrency guarantees under test are Postgres row-locking behavior.
# They use a separate TEST_DATABASE_URL so a stray DATABASE_URL can never
# point the suite (which truncates tables) at the app's real data.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://hsa:hsa@localhost:55432/hsa_test"
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    config = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE ledger_entries, transactions, cards, accounts CASCADE")
        )
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


# --- helpers ----------------------------------------------------------------


def make_account(client, email="pat@example.com", coverage="self_only", name="Pat Lee"):
    r = client.post(
        "/api/accounts",
        json={"holder_name": name, "email": email, "coverage_type": coverage},
    )
    assert r.status_code == 201, r.text
    return r.json()


def fund(client, account_id, cents):
    r = client.post(f"/api/accounts/{account_id}/deposits", json={"amount_cents": cents})
    assert r.status_code == 201, r.text
    return r.json()


def issue_card(client, account_id):
    r = client.post(f"/api/accounts/{account_id}/card")
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def funded_card(client):
    """An account with a $100.00 balance and an active card."""
    account = make_account(client)
    fund(client, account["id"], 10_000)
    card = issue_card(client, account["id"])
    return account, card
