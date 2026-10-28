"""Business rules that are configuration, not data: merchant categories and IRS limits."""

from enum import StrEnum


class CoverageType(StrEnum):
    SELF_ONLY = "self_only"
    FAMILY = "family"


# 2026 IRS HSA contribution limits, in cents (self-only $4,400; family $8,750).
# Catch-up contributions for holders 55+ are out of scope; see architecture.md.
ANNUAL_CONTRIBUTION_LIMIT_CENTS = {
    CoverageType.SELF_ONLY: 440_000,
    CoverageType.FAMILY: 875_000,
}


class MerchantCategory(StrEnum):
    # Qualified medical expenses
    PHARMACY = "pharmacy"
    HOSPITAL = "hospital"
    DOCTOR_OFFICE = "doctor_office"
    DENTAL = "dental"
    VISION = "vision"
    LABORATORY = "laboratory"
    # Not qualified
    RESTAURANT = "restaurant"
    ELECTRONICS = "electronics"
    GROCERY = "grocery"
    GAS_STATION = "gas_station"
    CLOTHING = "clothing"


# Allowlist: a category is qualified only if it is listed here.
# Anything new defaults to NOT qualified, which is the safe failure mode for tax-advantaged money.
QUALIFIED_CATEGORIES = frozenset(
    {
        MerchantCategory.PHARMACY,
        MerchantCategory.HOSPITAL,
        MerchantCategory.DOCTOR_OFFICE,
        MerchantCategory.DENTAL,
        MerchantCategory.VISION,
        MerchantCategory.LABORATORY,
    }
)

CATEGORY_LABELS = {
    MerchantCategory.PHARMACY: "Pharmacy",
    MerchantCategory.HOSPITAL: "Hospital",
    MerchantCategory.DOCTOR_OFFICE: "Doctor's office",
    MerchantCategory.DENTAL: "Dental",
    MerchantCategory.VISION: "Vision",
    MerchantCategory.LABORATORY: "Laboratory",
    MerchantCategory.RESTAURANT: "Restaurant",
    MerchantCategory.ELECTRONICS: "Electronics",
    MerchantCategory.GROCERY: "Grocery",
    MerchantCategory.GAS_STATION: "Gas station",
    MerchantCategory.CLOTHING: "Clothing",
}


def is_qualified(category: MerchantCategory) -> bool:
    return category in QUALIFIED_CATEGORIES


class CardStatus(StrEnum):
    ACTIVE = "active"
    FROZEN = "frozen"


class TransactionStatus(StrEnum):
    APPROVED = "approved"
    DECLINED = "declined"


class DeclineReason(StrEnum):
    CARD_NOT_ACTIVE = "card_not_active"
    NOT_QUALIFIED_EXPENSE = "not_qualified_expense"
    INSUFFICIENT_FUNDS = "insufficient_funds"


class LedgerEntryType(StrEnum):
    DEPOSIT = "deposit"
    PURCHASE = "purchase"
