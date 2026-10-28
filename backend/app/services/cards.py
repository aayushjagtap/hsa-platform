import secrets
import uuid
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain import CardStatus
from app.errors import ConflictError, NotFoundError
from app.models import Account, Card

CARD_VALIDITY_YEARS = 3


def issue_card(db: Session, account_id: uuid.UUID) -> Card:
    if db.get(Account, account_id) is None:
        raise NotFoundError("Account not found")

    today = date.today()
    card = Card(
        account_id=account_id,
        # Simulated: a real issuer generates the PAN in its card vault.
        last4=f"{secrets.randbelow(10_000):04d}",
        expiry_month=today.month,
        expiry_year=today.year + CARD_VALIDITY_YEARS,
        status=CardStatus.ACTIVE.value,
    )
    db.add(card)
    try:
        db.commit()
    except IntegrityError:
        # The unique constraint on account_id caught a second card,
        # including the case where two "issue card" clicks race each other.
        db.rollback()
        raise ConflictError("This account already has a card")
    db.refresh(card)
    return card


def set_card_status(db: Session, card_id: uuid.UUID, status: CardStatus) -> Card:
    card = db.get(Card, card_id, with_for_update=True)
    if card is None:
        db.rollback()
        raise NotFoundError("Card not found")
    card.status = status.value
    db.commit()
    db.refresh(card)
    return card
