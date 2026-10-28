import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain import ANNUAL_CONTRIBUTION_LIMIT_CENTS, CoverageType, LedgerEntryType
from app.errors import ConflictError, ContributionLimitError, NotFoundError
from app.models import Account, Card, LedgerEntry
from app.schemas import AccountCreate


def create_account(db: Session, data: AccountCreate) -> Account:
    account = Account(
        holder_name=data.holder_name,
        email=data.email.lower(),
        coverage_type=data.coverage_type.value,
        balance_cents=0,
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("An account with this email already exists")
    db.refresh(account)
    return account


def list_accounts(db: Session) -> list[Account]:
    return list(db.scalars(select(Account).order_by(Account.created_at.desc())))


def get_account(db: Session, account_id: uuid.UUID) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account not found")
    return account


def get_card_for_account(db: Session, account_id: uuid.UUID) -> Card | None:
    return db.scalar(select(Card).where(Card.account_id == account_id))


def contributions_this_year(db: Session, account_id: uuid.UUID) -> int:
    """Sum of deposits since Jan 1 of the current year (database clock, UTC)."""
    total = db.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0)).where(
            LedgerEntry.account_id == account_id,
            LedgerEntry.entry_type == LedgerEntryType.DEPOSIT.value,
            LedgerEntry.created_at >= func.date_trunc("year", func.now()),
        )
    )
    return int(total)


def annual_limit(account: Account) -> int:
    return ANNUAL_CONTRIBUTION_LIMIT_CENTS[CoverageType(account.coverage_type)]


def deposit(db: Session, account_id: uuid.UUID, amount_cents: int) -> LedgerEntry:
    """Add funds, enforcing the IRS annual contribution limit.

    The limit check is read-then-write (sum this year's deposits, then add),
    so the account row is locked with SELECT ... FOR UPDATE. Two concurrent
    deposits on the same account run one after the other, and neither can
    push the total past the limit.
    """
    account = db.scalar(
        select(Account).where(Account.id == account_id).with_for_update()
    )
    if account is None:
        db.rollback()
        raise NotFoundError("Account not found")

    limit = annual_limit(account)
    contributed = contributions_this_year(db, account_id)
    if contributed + amount_cents > limit:
        db.rollback()
        remaining = max(limit - contributed, 0)
        raise ContributionLimitError(
            f"Deposit would exceed the ${limit / 100:,.2f} annual contribution limit; "
            f"${remaining / 100:,.2f} remaining this year"
        )

    account.balance_cents += amount_cents
    entry = LedgerEntry(
        account_id=account.id,
        entry_type=LedgerEntryType.DEPOSIT.value,
        amount_cents=amount_cents,
        balance_after_cents=account.balance_cents,
        description="Deposit",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
