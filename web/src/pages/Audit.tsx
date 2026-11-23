import { Fragment, useCallback, useState } from 'react'
import { api } from '../lib/api'
import type { TraceStep } from '../lib/types'
import { PageHead, Tag, Trace } from '../components/Bits'
import { fmtDateTime } from '../lib/format'
import { useLoad } from '../lib/hooks'

interface Event {
  created_at?: string
  user_email?: string
  role_level?: number | null
  query?: string
  outcome: string
  top_score?: number | null
  latency_ms?: number | null
  rewritten_query?: string | null
  trace?: TraceStep[]
}

export default function Audit() {
  const [rows, setRows] = useState<Event[]>([])
  const [message, setMessage] = useState('')
  const [open, setOpen] = useState<number | null>(null)

  const load = useCallback(async () => {
    setMessage('')
    try {
      const res = await api('/audit/events')
      if (!res.ok) { setRows([]); setMessage(res.status === 403 ? 'Only partners can view the audit log.' : 'Could not load audit log.'); return }
      const data = await res.json()
      const list: Event[] = Array.isArray(data) ? data : data.events || data.items || []
      setRows(list)
      if (!list.length) setMessage('No events yet.')
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Could not load audit log.') }
  }, [])
  useLoad(load)

  return (
    <div className="page">
      <PageHead title="Audit log" hint="Every question, who asked it, how it ended and which agents ran. Select a row to see the pipeline timeline.">
        <button type="button" onClick={() => void load()}>Refresh</button>
      </PageHead>
      {message && <p className="muted gap">{message}</p>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>When</th><th>Who</th><th>Level</th><th>Question</th><th>Outcome</th><th>Score</th><th>ms</th><th>Rewritten as</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <Fragment key={i}>
                  <tr className="clickable" onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}>
                    <td>{fmtDateTime(r.created_at)}</td>
                    <td>{r.user_email}</td>
                    <td>{r.role_level != null ? 'L' + r.role_level : ''}</td>
                    <td className="q">{r.query}</td>
                    <td><Tag outcome={r.outcome} /></td>
                    <td>{typeof r.top_score === 'number' ? r.top_score.toFixed(3) : ''}</td>
                    <td>{r.latency_ms ?? ''}</td>
                    <td className="q">{r.rewritten_query}</td>
                  </tr>
                  {open === i && (
                    <tr className="trace-row">
                      <td colSpan={8}>{r.trace && r.trace.length ? <Trace steps={r.trace} detail /> : <span className="muted small">No pipeline steps were recorded for this event.</span>}</td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
