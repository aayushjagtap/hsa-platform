"""Concurrency tests.

Each worker thread gets its own database session (its own Postgres
connection), and a Barrier releases them at the same instant, so the
requests genuinely race inside Postgres rather than running one by one.
"""

import threading
import uuid

from sqlalchemy import func, select

from app.db import SessionLocal
from app.domain import MerchantCategory
from app.errors import ContributionLimitError
from app.models import Account, LedgerEntry, Transaction
from app.schemas import TransactionCreate
from app.services import accounts as account_service
from app.services import transactions as transaction_service
from tests.conftest import fund, issue_card, make_account


def race(fns):
    """Run each callable in its own thread, all released at once. Returns results in order."""
    barrier = threading.Barrier(len(fns))
    results = [None] * len(fns)
    errors = []

    def worker(i, fn):
        try:
            barrier.wait()
            results[i] = fn()
        except Exception as exc:  # noqa: BLE001 - surfaced below
            errors.append(exc)
            results[i] = exc

    threads = [threading.Thread(target=worker, args=(i, fn)) for i, fn in enumerate(fns)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results, errors


def buy(card_id, amount_cents, key=None):
    def run():
        db = SessionLocal()
        try:
            txn, _ = transaction_service.process_transaction(
                db,
                TransactionCreate(
                    card_id=card_id,
                    merchant_name="Walgreens",
                    merchant_category=MerchantCategory.PHARMACY,
                    amount_cents=amount_cents,
                    idempotency_key=key or str(uuid.uuid4()),
                ),
            )
            return txn.status, txn.decline_reason, txn.id
        finally:
            db.close()

    return run


def account_state(account_id):
    db = SessionLocal()
    try:
        account = db.get(Account, account_id)
        ledger_sum = db.scalar(
            select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0)).where(
                LedgerEntry.account_id == account_id
            )
        )
        txn_count = db.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.account_id == account_id)
        )
        return account.balance_cents, ledger_sum, txn_count
    finally:
        db.close()


def test_spec_example_80_and_50_against_100(client):
    """Balance $100, purchases of $80 and $50 at the same moment.

    Exactly one can be approved. Repeated many times so a lucky
    ordering can't hide a race.
    """
    for _ in range(25):
        account = make_account(client, email=f"{uuid.uuid4()}@example.com")
        fund(client, account["id"], 10_000)
        card = issue_card(client, account["id"])
        account_id = uuid.UUID(account["id"])

        results, errors = race([buy(card["id"], 8_000), buy(card["id"], 5_000)])
        assert not errors

        statuses = [status for status, _, _ in results]
        assert statuses.count("approved") == 1
        assert statuses.count("declined") == 1
        declined_reason = next(r for s, r, _ in results if s == "declined")
        assert declined_reason == "insufficient_funds"

        balance, ledger_sum, _ = account_state(account_id)
        assert balance in (2_000, 5_000)  # $100 - $80 or $100 - $50
        assert balance >= 0
        assert ledger_sum == balance


def test_many_concurrent_purchases_never_overdraw(client, funded_card):
    """$100 balance, 30 simultaneous $10 purchases: exactly 10 approved."""
    account, card = funded_card
    results, errors = race([buy(card["id"], 1_000) for _ in range(30)])
    assert not errors

    approved = [r for r in results if r[0] == "approved"]
    assert len(approved) == 10

    balance, ledger_sum, txn_count = account_state(uuid.UUID(account["id"]))
    assert balance == 0
    assert ledger_sum == 0
    assert txn_count == 30  # declines are recorded too


def test_concurrent_retries_with_same_key_charge_once(client, funded_card):
    """A client retrying the same request 10 times at once is charged once."""
    account, card = funded_card
    results, errors = race([buy(card["id"], 2_500, key="same-key") for _ in range(10)])
    assert not errors

    transaction_ids = {txn_id for _, _, txn_id in results}
    assert len(transaction_ids) == 1

    balance, ledger_sum, txn_count = account_state(uuid.UUID(account["id"]))
    assert balance == 7_500
    assert ledger_sum == 7_500
    assert txn_count == 1


def test_concurrent_deposits_respect_annual_limit(client):
    """Self-only limit is $4,400. Ten simultaneous $500 deposits: exactly 8 fit."""
    account = make_account(client, coverage="self_only")
    account_id = uuid.UUID(account["id"])

    def deposit():
        db = SessionLocal()
        try:
            account_service.deposit(db, account_id, 50_000)
            return "ok"
        except ContributionLimitError:
            return "limit"
        finally:
            db.close()

    results, errors = race([deposit for _ in range(10)])
    assert not errors
    assert results.count("ok") == 8
    assert results.count("limit") == 2

    balance, ledger_sum, _ = account_state(account_id)
    assert balance == ledger_sum == 400_000


def test_purchases_racing_a_deposit_stay_consistent(client, funded_card):
    """Deposits and purchases interleaving still leave balance == ledger."""
    account, card = funded_card
    account_id = uuid.UUID(account["id"])

    def deposit():
        db = SessionLocal()
        try:
            account_service.deposit(db, account_id, 5_000)
            return "deposit"
        finally:
            db.close()

    fns = [buy(card["id"], 2_000) for _ in range(10)] + [deposit, deposit]
    results, errors = race(fns)
    assert not errors

    balance, ledger_sum, _ = account_state(account_id)
    approved = sum(1 for r in results if isinstance(r, tuple) and r[0] == "approved")
    assert balance == 10_000 + 2 * 5_000 - approved * 2_000
    assert balance >= 0
    assert ledger_sum == balance
