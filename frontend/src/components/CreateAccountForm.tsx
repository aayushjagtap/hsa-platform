import { useState, type FormEvent } from 'react'
import { api, type Account, type CoverageType } from '../api'

interface Props {
  onCreated: (account: Account) => void
}

export function CreateAccountForm({ onCreated }: Props) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [coverage, setCoverage] = useState<CoverageType>('self_only')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const account = await api.createAccount({
        holder_name: name,
        email,
        coverage_type: coverage,
      })
      setName('')
      setEmail('')
      onCreated(account)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <label>
        Account holder
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Jordan Rivera" required />
      </label>
      <label>
        Email
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="jordan@example.com"
          required
        />
      </label>
      <label>
        HDHP coverage
        <select value={coverage} onChange={(e) => setCoverage(e.target.value as CoverageType)}>
          <option value="self_only">Self-only ($4,400 / yr limit)</option>
          <option value="family">Family ($8,750 / yr limit)</option>
        </select>
      </label>
      <button type="submit" disabled={busy}>
        {busy ? 'Creating…' : 'Create account'}
      </button>
      {error && <p className="message error">{error}</p>}
    </form>
  )
}
