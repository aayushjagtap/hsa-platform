import { useState } from 'react'
import type { LedgerEntry, MerchantCategory, Transaction } from '../api'
import { formatCents } from '../money'
import { DECLINE_LABELS } from '../labels'

interface Props {
  transactions: Transaction[]
  ledger: LedgerEntry[]
  categories: MerchantCategory[]
}

const time = (iso: string) =>
  new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit' })

export function History({ transactions, ledger, categories }: Props) {
  const [tab, setTab] = useState<'transactions' | 'ledger'>('transactions')
  const label = (value: string) => categories.find((c) => c.value === value)?.label ?? value

  return (
    <section className="panel">
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'transactions'} onClick={() => setTab('transactions')}>
          Authorizations ({transactions.length})
        </button>
        <button role="tab" aria-selected={tab === 'ledger'} onClick={() => setTab('ledger')}>
          Ledger ({ledger.length})
        </button>
      </div>

      {tab === 'transactions' ? (
        transactions.length === 0 ? (
          <p className="muted">No purchases yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Merchant</th>
                  <th>Category</th>
                  <th className="num">Amount</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t) => (
                  <tr key={t.id}>
                    <td className="muted">{time(t.created_at)}</td>
                    <td>{t.merchant_name}</td>
                    <td>{label(t.merchant_category)}</td>
                    <td className="num">{formatCents(t.amount_cents)}</td>
                    <td>
                      <span className={`pill ${t.status}`}>{t.status}</span>
                      {t.decline_reason && (
                        <span className="muted small"> {DECLINE_LABELS[t.decline_reason] ?? t.decline_reason}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : ledger.length === 0 ? (
        <p className="muted">No balance changes yet.</p>
      ) : (
        <div className="table-wrap">
          <p className="muted small">Append-only: every balance change, newest first. The latest balance-after always equals the account balance.</p>
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Entry</th>
                <th className="num">Amount</th>
                <th className="num">Balance after</th>
              </tr>
            </thead>
            <tbody>
              {ledger.map((e) => (
                <tr key={e.id}>
                  <td className="muted">{time(e.created_at)}</td>
                  <td>{e.description}</td>
                  <td className={`num ${e.amount_cents > 0 ? 'credit' : 'debit'}`}>
                    {e.amount_cents > 0 ? '+' : '−'}
                    {formatCents(Math.abs(e.amount_cents))}
                  </td>
                  <td className="num">{formatCents(e.balance_after_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
