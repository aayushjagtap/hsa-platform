"""Request and response shapes. Amounts cross the API as integer cents."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain import CardStatus, CoverageType, MerchantCategory

# Upper bound on a single deposit or purchase ($1,000,000) to reject absurd input early.
MAX_AMOUNT_CENTS = 100_000_000


class AccountCreate(BaseModel):
    holder_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    coverage_type: CoverageType

    @field_validator("holder_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("holder_name must not be blank")
        return value


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    last4: str
    expiry_month: int
    expiry_year: int
    status: CardStatus
    created_at: datetime


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    holder_name: str
    email: str
    coverage_type: CoverageType
    balance_cents: int
    created_at: datetime


class AccountDetail(AccountOut):
    card: CardOut | None
    contributions_this_year_cents: int
    annual_limit_cents: int


class DepositCreate(BaseModel):
    amount_cents: int = Field(gt=0, le=MAX_AMOUNT_CENTS)


class CardStatusUpdate(BaseModel):
    status: CardStatus


class TransactionCreate(BaseModel):
    card_id: uuid.UUID
    merchant_name: str = Field(min_length=1, max_length=200)
    merchant_category: MerchantCategory
    amount_cents: int = Field(gt=0, le=MAX_AMOUNT_CENTS)
    # Client-generated key so a retried request can't charge twice.
    idempotency_key: str = Field(min_length=1, max_length=100)

    @field_validator("merchant_name")
    @classmethod
    def strip_merchant(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("merchant_name must not be blank")
        return value


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    card_id: uuid.UUID
    idempotency_key: str
    merchant_name: str
    merchant_category: MerchantCategory
    amount_cents: int
    status: str
    decline_reason: str | None
    balance_after_cents: int | None
    created_at: datetime


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entry_type: str
    amount_cents: int
    balance_after_cents: int
    transaction_id: uuid.UUID | None
    description: str
    created_at: datetime


class MerchantCategoryOut(BaseModel):
    value: MerchantCategory
    label: str
    qualified: bool
