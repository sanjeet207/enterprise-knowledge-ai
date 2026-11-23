import { useCallback, useState, type FormEvent } from 'react'
import { api, errText, send } from '../lib/api'
import { Note, PageHead, Tag } from '../components/Bits'
import { fmtDate, fmtDateTime } from '../lib/format'
import { useLoad } from '../lib/hooks'

interface Report {
  id: string
  title: string
  summary?: string
  sections?: { question: string; answer: string }[]
  gaps?: { question: string; reason: string }[]
  inconsistencies?: { topic?: string; statement_a: string; statement_b: string }[]
  limitations?: string[]
  sources?: { number: number; title: string }[]
  reviewed_at?: string | null
  elapsed_s?: number
}
interface PastReport { id: string; created_at: string; request: string; reviewed?: boolean }

function Block({ title, items }: { title: string; items?: string[] }) {
  if (!items || !items.length) return null
  return (
    <div className="box">
      <b>{title}</b>
      <ul>{items.map((t, i) => <li key={i}>{t}</li>)}</ul>
    </div>
  )
}

export default function Research() {
  const [request, setRequest] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [bad, setBad] = useState(false)
  const [report, setReport] = useState<Report | null>(null)
  const [past, setPast] = useState<PastReport[]>([])
  const [selected, setSelected] = useState('')

  const loadPast = useCallback(async () => {
    const res = await api('/research')
    if (res.ok) setPast((await res.json()).reports as PastReport[])
  }, [])
  useLoad(loadPast)

  async function make(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setBad(false); setReport(null)
    setMsg('Researching… this takes a minute or two. Please keep this page open.')
    try {
      const res = await send('/research', 'POST', { request })
      if (!res.ok) { setMsg(await errText(res)); setBad(true); return }
      const r = (await res.json()) as Report
      setMsg(''); setReport(r); setSelected(r.id); void loadPast()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Network error.'); setBad(true)
    } finally { setBusy(false) }
  }

  async function open(id: string) {
    setSelected(id)
    if (!id) { setReport(null); return }
    const r = await api('/research/' + id)
    if (r.ok) setReport((await r.json()) as Report)
  }

  async function review() {
    if (!report) return
    const r = await api(`/research/${report.id}/review`, { method: 'POST' })
    if (r.ok) setReport({ ...report, reviewed_at: new Date().toISOString() })
  }

  async function remove() {
    if (!report || !window.confirm('Delete this report?')) return
    await api('/research/' + report.id, { method: 'DELETE' })
    setReport(null); setSelected(''); void loadPast()
  }

  return (
    <div className="page">
      <PageHead title="Research assistant" hint="Describe a topic. The assistant plans the questions, answers each from your documents, flags gaps and contradictions, and writes a draft report with sources." />
      <form className="card gap" onSubmit={make}>
        <label htmlFor="research-request">What should be researched?</label>
        <textarea id="research-request" rows={3} maxLength={1000} required value={request} onChange={(e) => setRequest(e.target.value)}
          placeholder="For example: Summarise our rules on remote work, travel approval and data handling for a new joiner." />
        <div className="research-actions">
          <button className="primary" type="submit" disabled={busy || !request.trim()}>{busy ? 'Researching…' : 'Prepare report'}</button>
          <select aria-label="Earlier reports" value={selected} onChange={(e) => void open(e.target.value)}>
            <option value="">Earlier reports ({past.length})</option>
            {past.map((p) => <option key={p.id} value={p.id}>{fmtDate(p.created_at)}: {p.request}{p.reviewed ? ' (reviewed)' : ''}</option>)}
          </select>
        </div>
        <Note text={msg} ok={!bad} />
      </form>
      {report && (
        <article className="card gap report">
          <h2>{report.title}</h2>
          <div className="actions">
            <Tag outcome={report.gaps && report.gaps.length ? 'report_partial' : 'report'} label="Draft: review before relying on it" />
            {report.reviewed_at
              ? <span className="muted small">Reviewed {fmtDateTime(report.reviewed_at)}</span>
              : <button type="button" className="secondary" onClick={() => void review()}>Mark as reviewed</button>}
            <button type="button" className="danger" onClick={() => void remove()}>Delete</button>
          </div>
          {report.summary && <div className="box"><b>Executive summary</b><p>{report.summary}</p></div>}
          {(report.sections ?? []).map((s, i) => <div key={i}><h3>{s.question}</h3><p>{s.answer}</p></div>)}
          <Block title="Evidence gaps" items={report.gaps?.map((g) => `${g.question} — ${g.reason}`)} />
          <Block title="Possible inconsistencies (flagged by a model; check the sources)"
            items={report.inconsistencies?.map((c) => `${c.topic ? c.topic + ': ' : ''}"${c.statement_a}" versus "${c.statement_b}"`)} />
          <Block title="Limitations" items={report.limitations} />
          <Block title="Sources" items={report.sources?.map((s) => `[${s.number}] ${s.title}`)} />
          {report.elapsed_s !== undefined && (
            <p className="muted small">Prepared in {report.elapsed_s} s. Every research question was answered and checked under your own access rights.</p>
          )}
        </article>
      )}
    </div>
  )
}
