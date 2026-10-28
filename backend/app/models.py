"""Database tables. All money is stored as integer cents (BIGINT), never floats."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        # Defense in depth: even if application logic had a bug,
        # Postgres itself refuses to store a negative balance.
        CheckConstraint("balance_cents >= 0", name="ck_accounts_balance_non_negative"),
        CheckConstraint(
            "coverage_type IN ('self_only', 'family')", name="ck_accounts_coverage_type"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    holder_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    coverage_type: Mapped[str] = mapped_column(String(20))
    balance_cents: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'frozen')", name="ck_cards_status"),
        # One card per account, enforced by the database.
        UniqueConstraint("account_id", name="uq_cards_account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    # The full card number is never stored. A real issuer keeps the PAN in a
    # PCI-scoped vault and hands the app a token; here the card id plays that role.
    last4: Mapped[str] = mapped_column(String(4))
    expiry_month: Mapped[int]
    expiry_year: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Transaction(Base):
    """Every card authorization attempt, approved or declined, is recorded."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "status IN ('approved', 'declined')", name="ck_transactions_status"
        ),
        CheckConstraint(
            "(status = 'approved' AND decline_reason IS NULL)"
            " OR (status = 'declined' AND decline_reason IS NOT NULL)",
            name="ck_transactions_decline_reason",
        ),
        # A retried request with the same key returns the original result
        # instead of charging twice.
        UniqueConstraint(
            "card_id", "idempotency_key", name="uq_transactions_card_idempotency_key"
        ),
        Index("ix_transactions_account_created", "account_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cards.id"))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    merchant_name: Mapped[str] = mapped_column(String(200))
    merchant_category: Mapped[str] = mapped_column(String(40))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20))
    decline_reason: Mapped[str | None] = mapped_column(String(40))
    balance_after_cents: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class LedgerEntry(Base):
    """Append-only record of every balance change.

    Invariant: an account's balance_cents equals the sum of its ledger amounts.
    Rows are only ever inserted, never updated or deleted.
    """

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('deposit', 'purchase')", name="ck_ledger_entry_type"
        ),
        CheckConstraint(
            "(entry_type = 'deposit' AND amount_cents > 0)"
            " OR (entry_type = 'purchase' AND amount_cents < 0)",
            name="ck_ledger_amount_sign",
        ),
        CheckConstraint("balance_after_cents >= 0", name="ck_ledger_balance_after"),
        Index("ix_ledger_account_created", "account_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    entry_type: Mapped[str] = mapped_column(String(20))
    # Signed: deposits positive, purchases negative.
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    balance_after_cents: Mapped[int] = mapped_column(BigInteger)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id")
    )
    description: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
