import { useState } from 'react'
import { api, type Transaction } from '../api'
import { formatCents, parseDollarsToCents } from '../money'
import { TransactionResult } from './TransactionResult'

interface Props {
  cardId: string | null
  balanceCents: number
  onChange: () => void
}

export function ConcurrencyDemo({ cardId, balanceCents, onChange }: Props) {
  const [amountA, setAmountA] = useState('80')
  const [amountB, setAmountB] = useState('50')
  const [run, setRun] = useState<{ before: number; results: Transaction[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!cardId) return null

  async function fire() {
    const id = cardId
    if (!id) return
    const a = parseDollarsToCents(amountA)
    const b = parseDollarsToCents(amountB)
    if (a === null || b === null) {
      setError('Enter two positive dollar amounts')
      return
    }
    setBusy(true)
    setError(null)
    const before = balanceCents
    const purchase = (cents: number, name: string) =>
      api.purchase({
        card_id: id,
        merchant_name: name,
        merchant_category: 'pharmacy',
        amount_cents: cents,
        idempotency_key: crypto.randomUUID(),
      })
    try {
      // Both requests leave the browser together; neither waits for the other.
      const responses = await Promise.all([purchase(a, 'Transaction A'), purchase(b, 'Transaction B')])
      setRun({ before, results: responses.map((r) => r.txn) })
      onChange()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const approvedTotal = run?.results
    .filter((t) => t.status === 'approved')
    .reduce((sum, t) => sum + t.amount_cents, 0)

  return (
    <section className="panel">
      <h2>Concurrency test</h2>
      <p className="muted">
        Sends two pharmacy purchases at the same instant. With a $100 balance, $80 and $50 can't both
        succeed: one is approved and the other is declined, and the balance never goes negative.
      </p>
      <div className="row">
        <label>
          Transaction A (USD)
          <input inputMode="decimal" value={amountA} onChange={(e) => setAmountA(e.target.value)} />
        </label>
        <label>
          Transaction B (USD)
          <input inputMode="decimal" value={amountB} onChange={(e) => setAmountB(e.target.value)} />
        </label>
      </div>
      <button type="button" disabled={busy} onClick={fire}>
        {busy ? 'Sending…' : `Send both at once (balance ${formatCents(balanceCents)})`}
      </button>
      {error && <p className="message error">{error}</p>}
      {run && (
        <div className="stack">
          {run.results.map((t) => (
            <TransactionResult key={t.id} txn={t} />
          ))}
          <p className="muted small">
            Started at {formatCents(run.before)} · approved {formatCents(approvedTotal ?? 0)} · ended at{' '}
            {formatCents(run.before - (approvedTotal ?? 0))}
          </p>
        </div>
      )}
    </section>
  )
}
