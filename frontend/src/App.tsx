import { useCallback, useEffect, useState } from 'react'
import {
  api,
  type Account,
  type AccountDetail,
  type LedgerEntry,
  type MerchantCategory,
  type Transaction,
} from './api'
import { AccountOverview } from './components/AccountOverview'
import { ConcurrencyDemo } from './components/ConcurrencyDemo'
import { CreateAccountForm } from './components/CreateAccountForm'
import { History } from './components/History'
import { PurchaseForm } from './components/PurchaseForm'
import { formatCents } from './money'

export default function App() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [categories, setCategories] = useState<MerchantCategory[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<AccountDetail | null>(null)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [ledger, setLedger] = useState<LedgerEntry[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  const loadAccounts = useCallback(async () => {
    try {
      setAccounts(await api.listAccounts())
      setLoadError(null)
    } catch (e) {
      setLoadError(`Can't reach the API: ${(e as Error).message}`)
    }
  }, [])

  const loadSelected = useCallback(async (id: string) => {
    const [d, t, l] = await Promise.all([api.getAccount(id), api.transactions(id), api.ledger(id)])
    setDetail(d)
    setTransactions(t)
    setLedger(l)
  }, [])

  // Data fetching on mount/selection: state is set after each request resolves,
  // so the linter's "setState in effect" warning doesn't apply here.
  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    loadAccounts()
    api.categories().then(setCategories).catch(() => setCategories([]))
  }, [loadAccounts])

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    if (selectedId) loadSelected(selectedId)
  }, [selectedId, loadSelected])

  const refresh = useCallback(() => {
    loadAccounts()
    if (selectedId) loadSelected(selectedId)
  }, [loadAccounts, loadSelected, selectedId])

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden>+</span>
          <span>HSA Platform</span>
        </div>
        <span className="muted small">Local simulation · amounts in USD</span>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <section className="panel">
            <h2>New account</h2>
            <CreateAccountForm
              onCreated={(account) => {
                loadAccounts()
                setSelectedId(account.id)
              }}
            />
          </section>

          <section className="panel">
            <h2>Accounts</h2>
            {loadError && <p className="message error">{loadError}</p>}
            {accounts.length === 0 && !loadError && <p className="muted">No accounts yet.</p>}
            <ul className="account-list">
              {accounts.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    className={a.id === selectedId ? 'account-item selected' : 'account-item'}
                    onClick={() => setSelectedId(a.id)}
                  >
                    <span>{a.holder_name}</span>
                    <span className="muted">{formatCents(a.balance_cents)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </aside>

        <main className="main">
          {!detail || detail.id !== selectedId ? (
            <section className="panel empty">
              <h2>Select or create an account</h2>
              <p className="muted">
                Create an account, deposit funds, issue a card, then simulate purchases and the
                concurrency test.
              </p>
            </section>
          ) : (
            <>
              {/* key={detail.id}: switching accounts remounts these, so a retry or
                  result from one account can never carry over to another. */}
              <AccountOverview key={`overview-${detail.id}`} account={detail} onChange={refresh} />
              <div className="two-col">
                <PurchaseForm
                  key={`purchase-${detail.id}`}
                  cardId={detail.card?.id ?? null}
                  categories={categories}
                  onChange={refresh}
                />
                <ConcurrencyDemo
                  key={`race-${detail.id}`}
                  cardId={detail.card?.id ?? null}
                  balanceCents={detail.balance_cents}
                  onChange={refresh}
                />
              </div>
              <History transactions={transactions} ledger={ledger} categories={categories} />
            </>
          )}
        </main>
      </div>
    </div>
  )
}
