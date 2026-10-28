import uuid

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain import CATEGORY_LABELS, MerchantCategory, is_qualified
from app.errors import DomainError
from app.schemas import (
    AccountCreate,
    AccountDetail,
    AccountOut,
    CardOut,
    CardStatusUpdate,
    DepositCreate,
    LedgerEntryOut,
    MerchantCategoryOut,
    TransactionCreate,
    TransactionOut,
)
from app.services import accounts as account_service
from app.services import cards as card_service
from app.services import transactions as transaction_service

# No CORS setup: the browser only ever calls this API through the same origin
# (nginx in Docker, the Vite proxy in development).
app = FastAPI(title="HSA Platform", version="1.0.0")


@app.exception_handler(DomainError)
def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/merchant-categories", response_model=list[MerchantCategoryOut])
def merchant_categories() -> list[MerchantCategoryOut]:
    return [
        MerchantCategoryOut(value=c, label=CATEGORY_LABELS[c], qualified=is_qualified(c))
        for c in MerchantCategory
    ]


# --- Accounts ---------------------------------------------------------------


@app.post("/api/accounts", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    return account_service.create_account(db, data)


@app.get("/api/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return account_service.list_accounts(db)


@app.get("/api/accounts/{account_id}", response_model=AccountDetail)
def get_account(account_id: uuid.UUID, db: Session = Depends(get_db)):
    account = account_service.get_account(db, account_id)
    card = account_service.get_card_for_account(db, account_id)
    return AccountDetail(
        **AccountOut.model_validate(account).model_dump(),
        card=CardOut.model_validate(card) if card else None,
        contributions_this_year_cents=account_service.contributions_this_year(db, account_id),
        annual_limit_cents=account_service.annual_limit(account),
    )


@app.post(
    "/api/accounts/{account_id}/deposits",
    response_model=LedgerEntryOut,
    status_code=status.HTTP_201_CREATED,
)
def deposit(account_id: uuid.UUID, data: DepositCreate, db: Session = Depends(get_db)):
    return account_service.deposit(db, account_id, data.amount_cents)


@app.get("/api/accounts/{account_id}/ledger", response_model=list[LedgerEntryOut])
def ledger(account_id: uuid.UUID, db: Session = Depends(get_db)):
    account_service.get_account(db, account_id)
    return transaction_service.list_ledger(db, account_id)


@app.get("/api/accounts/{account_id}/transactions", response_model=list[TransactionOut])
def account_transactions(account_id: uuid.UUID, db: Session = Depends(get_db)):
    account_service.get_account(db, account_id)
    return transaction_service.list_transactions(db, account_id)


# --- Cards ------------------------------------------------------------------


@app.post(
    "/api/accounts/{account_id}/card",
    response_model=CardOut,
    status_code=status.HTTP_201_CREATED,
)
def issue_card(account_id: uuid.UUID, db: Session = Depends(get_db)):
    return card_service.issue_card(db, account_id)


@app.patch("/api/cards/{card_id}", response_model=CardOut)
def update_card(card_id: uuid.UUID, data: CardStatusUpdate, db: Session = Depends(get_db)):
    return card_service.set_card_status(db, card_id, data.status)


# --- Transactions -----------------------------------------------------------


@app.post("/api/transactions", response_model=TransactionOut)
def create_transaction(
    data: TransactionCreate, response: Response, db: Session = Depends(get_db)
):
    """Authorize a purchase. A decline is a normal business outcome (201),
    not an HTTP error. A replayed idempotency key returns the original
    result with 200."""
    txn, replayed = transaction_service.process_transaction(db, data)
    response.status_code = status.HTTP_200_OK if replayed else status.HTTP_201_CREATED
    return txn
