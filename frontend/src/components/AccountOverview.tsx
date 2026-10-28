import { useState, type FormEvent } from 'react'
import { api, type AccountDetail } from '../api'
import { formatCents, parseDollarsToCents } from '../money'

interface Props {
  account: AccountDetail
  onChange: () => void
}

export function AccountOverview({ account, onChange }: Props) {
  const [amount, setAmount] = useState('')
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const used = account.contributions_this_year_cents
  const limit = account.annual_limit_cents
  const pct = Math.min(100, (used / limit) * 100)

  async function run(action: () => Promise<string>) {
    setBusy(true)
    setMessage(null)
    try {
      setMessage({ kind: 'ok', text: await action() })
      onChange()
    } catch (e) {
      setMessage({ kind: 'error', text: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  function deposit(event: FormEvent) {
    event.preventDefault()
    const cents = parseDollarsToCents(amount)
    if (cents === null) {
      setMessage({ kind: 'error', text: 'Enter a positive dollar amount, like 250 or 19.99' })
      return
    }
    run(async () => {
      await api.deposit(account.id, cents)
      setAmount('')
      return `Deposited ${formatCents(cents)}`
    })
  }

  const card = account.card

  return (
    <section className="panel overview">
      <div className="balance-block">
        <span className="eyebrow">Available balance</span>
        <span className="balance">{formatCents(account.balance_cents)}</span>
        <span className="muted">
          {account.holder_name} · {account.email} ·{' '}
          {account.coverage_type === 'family' ? 'Family' : 'Self-only'} coverage
        </span>
      </div>

      <div className="limit">
        <div className="limit-labels">
          <span>2026 contributions</span>
          <span>
            {formatCents(used)} of {formatCents(limit)}
          </span>
        </div>
        <div className="meter" role="meter" aria-valuenow={used} aria-valuemin={0} aria-valuemax={limit}>
          <div className="meter-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="overview-grid">
        <form className="stack" onSubmit={deposit}>
          <h3>Deposit funds</h3>
          <label>
            Amount (USD)
            <input
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="100.00"
            />
          </label>
          <button type="submit" disabled={busy}>
            Deposit
          </button>
        </form>

        <div className="stack">
          <h3>Debit card</h3>
          {card ? (
            <>
              <div className={`card-visual ${card.status}`}>
                <span className="card-brand">HSA Debit</span>
                <span className="card-number">•••• •••• •••• {card.last4}</span>
                <span className="card-meta">
                  <span>{account.holder_name}</span>
                  <span>
                    {String(card.expiry_month).padStart(2, '0')}/{String(card.expiry_year).slice(-2)}
                  </span>
                </span>
                {card.status === 'frozen' && <span className="card-badge">Frozen</span>}
              </div>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const next = card.status === 'active' ? 'frozen' : 'active'
                    await api.setCardStatus(card.id, next)
                    return next === 'frozen' ? 'Card frozen' : 'Card unfrozen'
                  })
                }
              >
                {card.status === 'active' ? 'Freeze card' : 'Unfreeze card'}
              </button>
            </>
          ) : (
            <>
              <p className="muted">No card issued yet.</p>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const issued = await api.issueCard(account.id)
                    return `Issued card ending in ${issued.last4}`
                  })
                }
              >
                Issue virtual card
              </button>
            </>
          )}
        </div>
      </div>

      {message && <p className={`message ${message.kind}`}>{message.text}</p>}
    </section>
  )
}
