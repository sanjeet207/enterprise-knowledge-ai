import { useCallback, useState } from 'react'
import { getJson } from '../lib/api'
import { PageHead } from '../components/Bits'
import { fmtDateTime } from '../lib/format'
import { useLoad } from '../lib/hooks'

export interface AccessRequest {
  id: string; user_email: string; question: string; reason: string; status: string
  decided_by: string | null; decided_at: string | null; decision_note: string | null; created_at: string
}

export function StatusTag({ status }: { status: string }) {
  const cls = status === 'approved' ? 'answered' : status === 'denied' ? 'refused' : 'general'
  return <span className={'tag ' + cls}>{status === 'pending' ? 'Waiting' : status === 'approved' ? 'Approved' : 'Denied'}</span>
}

export default function Requests() {
  const [rows, setRows] = useState<AccessRequest[] | null>(null)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    try { setRows((await getJson<{ requests: AccessRequest[] }>('/access-requests/mine')).requests) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load your requests.') }
  }, [])
  useLoad(load)

  return (
    <div className="page">
      <PageHead title="Access requests" hint="Ask for access from a refused answer in Ask. An administrator decides, and the decision shows here." />
      {error && <p className="small bad-text" role="alert">{error}</p>}
      <section className="card gap">
        {rows === null ? <p className="muted">Loading…</p> : rows.length === 0
          ? <p className="muted">You have not asked for access to anything.</p>
          : <ul className="reqs">{rows.map((r) => (
              <li key={r.id} className="req">
                <StatusTag status={r.status} />
                <strong>{r.question}</strong>
                <span className="muted">Sent {fmtDateTime(r.created_at)}. Your reason: {r.reason}</span>
                {r.decided_at && <span className="muted">Decided by {r.decided_by} on {fmtDateTime(r.decided_at)}{r.decision_note ? `: ${r.decision_note}` : '.'}</span>}
              </li>))}</ul>}
      </section>
    </div>
  )
}
