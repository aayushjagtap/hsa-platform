import type { Transaction } from '../api'
import { DECLINE_LABELS } from '../labels'
import { formatCents } from '../money'

export function TransactionResult({ txn }: { txn: Transaction }) {
  const approved = txn.status === 'approved'
  return (
    <div className={`result ${txn.status}`}>
      <div className="result-head">
        <span className={`pill ${txn.status}`}>{approved ? 'Approved' : 'Declined'}</span>
        <strong>
          {txn.merchant_name} · {formatCents(txn.amount_cents)}
        </strong>
      </div>
      <span className="muted small">
        {approved
          ? `Balance after: ${formatCents(txn.balance_after_cents ?? 0)}`
          : DECLINE_LABELS[txn.decline_reason ?? ''] ?? txn.decline_reason}
      </span>
    </div>
  )
}
