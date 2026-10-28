import { useState, type FormEvent } from 'react'
import { api, type MerchantCategory, type Transaction } from '../api'
import { formatCents, parseDollarsToCents } from '../money'
import { TransactionResult } from './TransactionResult'

interface Props {
  cardId: string | null
  categories: MerchantCategory[]
  onChange: () => void
}

type Payload = Parameters<typeof api.purchase>[0]

export function PurchaseForm({ cardId, categories, onChange }: Props) {
  const [merchant, setMerchant] = useState('CVS Pharmacy')
  const [category, setCategory] = useState('pharmacy')
  const [amount, setAmount] = useState('25.00')
  const [result, setResult] = useState<{ txn: Transaction; replay: boolean } | null>(null)
  const [last, setLast] = useState<Payload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const selected = categories.find((c) => c.value === category)

  async function send(payload: Payload) {
    setBusy(true)
    setError(null)
    // Remember the request before sending it. If the network drops after the
    // server processed it, the user can still retry with the same key and
    // get the original result instead of being charged twice.
    setLast(payload)
    try {
      const { txn, replayed } = await api.purchase(payload)
      setResult({ txn, replay: replayed })
      onChange()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!cardId) return
    const cents = parseDollarsToCents(amount)
    if (cents === null) {
      setError('Enter a positive dollar amount, like 25 or 19.99')
      return
    }
    send({
      card_id: cardId,
      merchant_name: merchant,
      merchant_category: category,
      amount_cents: cents,
      // A fresh key per purchase; "Retry" below reuses it on purpose.
      idempotency_key: crypto.randomUUID(),
    })
  }

  if (!cardId) {
    return (
      <section className="panel">
        <h2>Simulate a purchase</h2>
        <p className="muted">Issue a card to start simulating purchases.</p>
      </section>
    )
  }

  return (
    <section className="panel">
      <h2>Simulate a purchase</h2>
      <form className="stack" onSubmit={submit}>
        <div className="row">
          <label>
            Merchant
            <input value={merchant} onChange={(e) => setMerchant(e.target.value)} required />
          </label>
          <label>
            Amount (USD)
            <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </label>
        </div>
        <label>
          Merchant category
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <optgroup label="Qualified medical expense">
              {categories.filter((c) => c.qualified).map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </optgroup>
            <optgroup label="Not qualified">
              {categories.filter((c) => !c.qualified).map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </optgroup>
          </select>
        </label>
        {selected && (
          <p className={`hint ${selected.qualified ? 'good' : 'bad'}`}>
            {selected.label} {selected.qualified ? 'is' : 'is not'} a qualified medical expense
          </p>
        )}
        <div className="row buttons">
          <button type="submit" disabled={busy}>
            Authorize purchase
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy || !last}
            title="Re-send the last request with the same idempotency key"
            onClick={() => last && send(last)}
          >
            Retry last request
          </button>
        </div>
      </form>
      {error && <p className="message error">{error}</p>}
      {result && (
        <>
          <TransactionResult txn={result.txn} />
          {result.replay && (
            <p className="muted small">
              Same idempotency key → the original {formatCents(result.txn.amount_cents)} result was
              returned; the card was not charged again.
            </p>
          )}
        </>
      )}
    </section>
  )
}
