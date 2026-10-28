import uuid

from sqlalchemy import func, select

from app.models import LedgerEntry
from tests.conftest import fund, issue_card, make_account


def purchase(client, card_id, amount_cents, category="pharmacy", key=None, merchant="CVS"):
    return client.post(
        "/api/transactions",
        json={
            "card_id": card_id,
            "merchant_name": merchant,
            "merchant_category": category,
            "amount_cents": amount_cents,
            "idempotency_key": key or str(uuid.uuid4()),
        },
    )


def balance(client, account_id):
    return client.get(f"/api/accounts/{account_id}").json()["balance_cents"]


# --- accounts ---------------------------------------------------------------


def test_create_account_starts_at_zero(client):
    account = make_account(client)
    assert account["balance_cents"] == 0
    assert account["coverage_type"] == "self_only"


def test_duplicate_email_is_rejected(client):
    make_account(client, email="pat@example.com")
    r = client.post(
        "/api/accounts",
        json={"holder_name": "Other", "email": "PAT@example.com", "coverage_type": "family"},
    )
    assert r.status_code == 409


def test_invalid_account_input_is_rejected(client):
    r = client.post(
        "/api/accounts",
        json={"holder_name": "   ", "email": "not-an-email", "coverage_type": "gold"},
    )
    assert r.status_code == 422


def test_unknown_account_is_404(client):
    assert client.get(f"/api/accounts/{uuid.uuid4()}").status_code == 404


# --- deposits ---------------------------------------------------------------


def test_deposit_increases_balance_and_ytd(client):
    account = make_account(client)
    fund(client, account["id"], 25_050)
    detail = client.get(f"/api/accounts/{account['id']}").json()
    assert detail["balance_cents"] == 25_050
    assert detail["contributions_this_year_cents"] == 25_050
    assert detail["annual_limit_cents"] == 440_000


def test_deposit_rejects_non_positive_amounts(client):
    account = make_account(client)
    for amount in (0, -500):
        r = client.post(f"/api/accounts/{account['id']}/deposits", json={"amount_cents": amount})
        assert r.status_code == 422


def test_deposit_cannot_exceed_annual_limit(client):
    account = make_account(client, coverage="self_only")
    fund(client, account["id"], 440_000)  # exactly the 2026 self-only limit is allowed
    r = client.post(f"/api/accounts/{account['id']}/deposits", json={"amount_cents": 1})
    assert r.status_code == 422
    assert "annual contribution limit" in r.json()["detail"]
    assert balance(client, account["id"]) == 440_000


def test_family_coverage_has_higher_limit(client):
    account = make_account(client, coverage="family")
    fund(client, account["id"], 875_000)
    r = client.post(f"/api/accounts/{account['id']}/deposits", json={"amount_cents": 1})
    assert r.status_code == 422


# --- cards ------------------------------------------------------------------


def test_issue_card(client):
    account = make_account(client)
    card = issue_card(client, account["id"])
    assert card["status"] == "active"
    assert len(card["last4"]) == 4 and card["last4"].isdigit()
    detail = client.get(f"/api/accounts/{account['id']}").json()
    assert detail["card"]["id"] == card["id"]


def test_only_one_card_per_account(client):
    account = make_account(client)
    issue_card(client, account["id"])
    assert client.post(f"/api/accounts/{account['id']}/card").status_code == 409


def test_freeze_and_unfreeze_card(client, funded_card):
    account, card = funded_card
    r = client.patch(f"/api/cards/{card['id']}", json={"status": "frozen"})
    assert r.json()["status"] == "frozen"
    declined = purchase(client, card["id"], 1_000).json()
    assert declined["decline_reason"] == "card_not_active"

    client.patch(f"/api/cards/{card['id']}", json={"status": "active"})
    assert purchase(client, card["id"], 1_000).json()["status"] == "approved"


# --- transactions -----------------------------------------------------------


def test_qualified_purchase_is_approved_and_debits(client, funded_card):
    account, card = funded_card
    r = purchase(client, card["id"], 2_500, category="pharmacy")
    assert r.status_code == 201
    txn = r.json()
    assert txn["status"] == "approved"
    assert txn["balance_after_cents"] == 7_500
    assert balance(client, account["id"]) == 7_500


def test_examples_from_the_spec(client, funded_card):
    _, card = funded_card
    expected = {
        "pharmacy": "approved",
        "hospital": "approved",
        "restaurant": "declined",
        "electronics": "declined",
    }
    for category, status in expected.items():
        txn = purchase(client, card["id"], 100, category=category).json()
        assert txn["status"] == status, category


def test_non_qualified_purchase_is_declined_without_debit(client, funded_card):
    account, card = funded_card
    txn = purchase(client, card["id"], 2_500, category="restaurant").json()
    assert txn["status"] == "declined"
    assert txn["decline_reason"] == "not_qualified_expense"
    assert balance(client, account["id"]) == 10_000


def test_insufficient_funds_is_declined(client, funded_card):
    account, card = funded_card
    txn = purchase(client, card["id"], 10_001).json()
    assert txn["status"] == "declined"
    assert txn["decline_reason"] == "insufficient_funds"
    assert balance(client, account["id"]) == 10_000


def test_exact_balance_purchase_is_approved(client, funded_card):
    account, card = funded_card
    assert purchase(client, card["id"], 10_000).json()["status"] == "approved"
    assert balance(client, account["id"]) == 0


def test_unknown_category_is_rejected(client, funded_card):
    _, card = funded_card
    assert purchase(client, card["id"], 100, category="casino").status_code == 422


def test_unknown_card_is_404(client):
    assert purchase(client, str(uuid.uuid4()), 100).status_code == 404


def test_idempotent_retry_charges_once(client, funded_card):
    account, card = funded_card
    first = purchase(client, card["id"], 3_000, key="retry-1")
    second = purchase(client, card["id"], 3_000, key="retry-1")
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert balance(client, account["id"]) == 7_000


def test_reused_key_with_different_details_is_rejected(client, funded_card):
    account, card = funded_card
    assert purchase(client, card["id"], 2_500, key="order-1").status_code == 201

    changed_amount = purchase(client, card["id"], 7_500, key="order-1")
    changed_category = purchase(client, card["id"], 2_500, category="hospital", key="order-1")
    changed_merchant = purchase(client, card["id"], 2_500, key="order-1", merchant="Walgreens")

    for r in (changed_amount, changed_category, changed_merchant):
        assert r.status_code == 409
    assert balance(client, account["id"]) == 7_500  # only the original $25 was charged


def test_declines_are_recorded(client, funded_card):
    account, card = funded_card
    purchase(client, card["id"], 100, category="restaurant")
    purchase(client, card["id"], 100, category="pharmacy")
    history = client.get(f"/api/accounts/{account['id']}/transactions").json()
    assert sorted(t["status"] for t in history) == ["approved", "declined"]


def test_ledger_matches_balance(client, db, funded_card):
    account, card = funded_card
    purchase(client, card["id"], 1_234)
    purchase(client, card["id"], 99_999)  # declined, no ledger row
    fund(client, account["id"], 500)
    ledger_total = db.scalar(
        select(func.sum(LedgerEntry.amount_cents)).where(
            LedgerEntry.account_id == uuid.UUID(account["id"])
        )
    )
    assert ledger_total == balance(client, account["id"]) == 9_266


def test_merchant_categories_endpoint(client):
    categories = {c["value"]: c["qualified"] for c in client.get("/api/merchant-categories").json()}
    assert categories["pharmacy"] is True
    assert categories["restaurant"] is False
