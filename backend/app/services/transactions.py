"""Card authorization: the part of the system that has to be correct under concurrency."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain import (
    CardStatus,
    DeclineReason,
    LedgerEntryType,
    TransactionStatus,
    is_qualified,
)
from app.errors import ConflictError, NotFoundError
from app.models import Account, Card, LedgerEntry, Transaction
from app.schemas import TransactionCreate


def find_by_idempotency_key(
    db: Session, card_id: uuid.UUID, idempotency_key: str
) -> Transaction | None:
    return db.scalar(
        select(Transaction).where(
            Transaction.card_id == card_id,
            Transaction.idempotency_key == idempotency_key,
        )
    )


def process_transaction(db: Session, data: TransactionCreate) -> tuple[Transaction, bool]:
    """Authorize a card purchase. Returns (transaction, replayed).

    Order of checks:
      1. Idempotency: a repeated key returns the original result unchanged.
      2. Card must exist and be active.
      3. Merchant category must be a qualified medical expense.
      4. Funds: one atomic conditional UPDATE debits the balance only if it
         covers the amount. This is the concurrency guarantee, see below.

    Declines are recorded too, so every authorization attempt is auditable.
    """
    existing = find_by_idempotency_key(db, data.card_id, data.idempotency_key)
    if existing is not None:
        return _replay(existing, data), True

    # Shared lock on the card: a concurrent freeze waits for this authorization
    # to finish, and this authorization sees the card's committed status.
    card = db.scalar(
        select(Card).where(Card.id == data.card_id).with_for_update(read=True)
    )
    if card is None:
        db.rollback()
        raise NotFoundError("Card not found")

    txn = Transaction(
        account_id=card.account_id,
        card_id=card.id,
        idempotency_key=data.idempotency_key,
        merchant_name=data.merchant_name,
        merchant_category=data.merchant_category.value,
        amount_cents=data.amount_cents,
    )

    if card.status != CardStatus.ACTIVE.value:
        _decline(txn, DeclineReason.CARD_NOT_ACTIVE)
    elif not is_qualified(data.merchant_category):
        _decline(txn, DeclineReason.NOT_QUALIFIED_EXPENSE)
    else:
        # The concurrency guarantee lives in this single statement.
        #
        #   UPDATE accounts SET balance_cents = balance_cents - :amount
        #   WHERE id = :account_id AND balance_cents >= :amount
        #   RETURNING balance_cents
        #
        # Postgres takes a row lock for the UPDATE. If two purchases race,
        # the second waits for the first to commit, then re-checks the WHERE
        # clause against the *new* balance. So with $100 and purchases of
        # $80 and $50, whichever commits first is approved and the other
        # matches zero rows and is declined. The balance can't go negative,
        # and the CHECK constraint on accounts backs that up.
        new_balance = db.scalar(
            update(Account)
            .where(
                Account.id == card.account_id,
                Account.balance_cents >= data.amount_cents,
            )
            .values(balance_cents=Account.balance_cents - data.amount_cents)
            .returning(Account.balance_cents)
        )
        if new_balance is None:
            _decline(txn, DeclineReason.INSUFFICIENT_FUNDS)
        else:
            txn.status = TransactionStatus.APPROVED.value
            txn.balance_after_cents = new_balance

    db.add(txn)
    try:
        db.flush()
        if txn.status == TransactionStatus.APPROVED.value:
            db.add(
                LedgerEntry(
                    account_id=card.account_id,
                    entry_type=LedgerEntryType.PURCHASE.value,
                    amount_cents=-data.amount_cents,
                    balance_after_cents=txn.balance_after_cents,
                    transaction_id=txn.id,
                    description=f"{data.merchant_name} ({data.merchant_category.value})",
                )
            )
        db.commit()
    except IntegrityError:
        # Two requests with the same idempotency key raced past the lookup
        # above. The unique constraint let only one insert win. Rolling back
        # also undoes this request's debit, so the customer is charged once.
        db.rollback()
        winner = find_by_idempotency_key(db, data.card_id, data.idempotency_key)
        if winner is None:
            raise
        return _replay(winner, data), True

    db.refresh(txn)
    return txn, False


def _replay(existing: Transaction, data: TransactionCreate) -> Transaction:
    """Return the original result for a retried request.

    A key identifies one specific purchase. Reusing it with a different
    amount or merchant is a client bug; silently returning the old result
    would hide that, so it's rejected instead.
    """
    same_request = (
        existing.amount_cents == data.amount_cents
        and existing.merchant_name == data.merchant_name
        and existing.merchant_category == data.merchant_category.value
    )
    if not same_request:
        raise ConflictError(
            "This idempotency key was already used for a different purchase"
        )
    return existing


def _decline(txn: Transaction, reason: DeclineReason) -> None:
    txn.status = TransactionStatus.DECLINED.value
    txn.decline_reason = reason.value
    txn.balance_after_cents = None


def list_transactions(db: Session, account_id: uuid.UUID, limit: int = 100) -> list[Transaction]:
    return list(
        db.scalars(
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
    )


def list_ledger(db: Session, account_id: uuid.UUID, limit: int = 100) -> list[LedgerEntry]:
    return list(
        db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.account_id == account_id)
            .order_by(LedgerEntry.created_at.desc())
            .limit(limit)
        )
    )
