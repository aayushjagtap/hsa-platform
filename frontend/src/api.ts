export type CoverageType = 'self_only' | 'family'
export type CardStatus = 'active' | 'frozen'

export interface Account {
  id: string
  holder_name: string
  email: string
  coverage_type: CoverageType
  balance_cents: number
  created_at: string
}

export interface Card {
  id: string
  account_id: string
  last4: string
  expiry_month: number
  expiry_year: number
  status: CardStatus
  created_at: string
}

export interface AccountDetail extends Account {
  card: Card | null
  contributions_this_year_cents: number
  annual_limit_cents: number
}

export interface Transaction {
  id: string
  account_id: string
  card_id: string
  idempotency_key: string
  merchant_name: string
  merchant_category: string
  amount_cents: number
  status: 'approved' | 'declined'
  decline_reason: string | null
  balance_after_cents: number | null
  created_at: string
}

export interface LedgerEntry {
  id: string
  entry_type: 'deposit' | 'purchase'
  amount_cents: number
  balance_after_cents: number
  transaction_id: string | null
  description: string
  created_at: string
}

export interface MerchantCategory {
  value: string
  label: string
  qualified: boolean
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function send<T>(path: string, init?: RequestInit): Promise<{ body: T; status: number }> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(response.status, describeError(body) ?? `Request failed (${response.status})`)
  }
  return { body: body as T, status: response.status }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return (await send<T>(path, init)).body
}

// FastAPI returns either {detail: "message"} or {detail: [{loc, msg}, ...]}.
function describeError(body: unknown): string | null {
  if (!body || typeof body !== 'object' || !('detail' in body)) return null
  const detail = (body as { detail: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = d.loc?.[d.loc.length - 1]
        return field ? `${String(field).replace(/_/g, ' ')}: ${d.msg}` : d.msg
      })
      .join('; ')
  }
  return null
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  categories: () => request<MerchantCategory[]>('/merchant-categories'),
  listAccounts: () => request<Account[]>('/accounts'),
  getAccount: (id: string) => request<AccountDetail>(`/accounts/${id}`),
  createAccount: (body: { holder_name: string; email: string; coverage_type: CoverageType }) =>
    post<Account>('/accounts', body),
  deposit: (id: string, amount_cents: number) =>
    post<LedgerEntry>(`/accounts/${id}/deposits`, { amount_cents }),
  issueCard: (id: string) => post<Card>(`/accounts/${id}/card`),
  setCardStatus: (cardId: string, status: CardStatus) =>
    request<Card>(`/cards/${cardId}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  transactions: (id: string) => request<Transaction[]>(`/accounts/${id}/transactions`),
  ledger: (id: string) => request<LedgerEntry[]>(`/accounts/${id}/ledger`),
  // The server answers 201 for a new authorization and 200 when the
  // idempotency key was already used, so "replayed" comes from the server,
  // not from which button the user clicked.
  purchase: async (body: {
    card_id: string
    merchant_name: string
    merchant_category: string
    amount_cents: number
    idempotency_key: string
  }) => {
    const { body: txn, status } = await send<Transaction>('/transactions', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    return { txn, replayed: status === 200 }
  },
}
