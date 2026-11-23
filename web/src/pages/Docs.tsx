import { useCallback, useState, type FormEvent } from 'react'
import { api, errText, send } from '../lib/api'
import { LEVELS, type Me } from '../lib/types'
import { Note, PageHead, Tag } from '../components/Bits'
import { fmtDate } from '../lib/format'
import { useLoad } from '../lib/hooks'

interface Options { can_upload: boolean; company_wide?: boolean; max_level: number; teams: { id: string; name: string }[] }
interface Doc {
  document_id: string; title: string; status: string; version: number; level: number; team?: string | null
  review_by?: string | null; sections: number; uploaded_by?: string | null; created_at?: string; note?: string | null; supersedes?: string | null
}
interface Comparison {
  old: { title: string; version: number }; new: { version: number }
  total_changes: number; unchanged: number; summary?: string; note?: string
  changes: { type: string; before?: string; after?: string }[]
}

const STATUS_LABEL: Record<string, string> = { pending: 'Waiting for approval', archived: 'Replaced', published: 'Live' }

export default function Docs({ me }: { me: Me }) {
  const [opts, setOpts] = useState<Options>({ can_upload: false, max_level: 0, teams: [] })
  const [docs, setDocs] = useState<Doc[]>([])
  const [loaded, setLoaded] = useState(false)
  const [msg, setMsg] = useState('')
  const [ok, setOk] = useState(true)
  const [busy, setBusy] = useState(false)
  const [cmp, setCmp] = useState<Comparison | null>(null)
  const [cmpState, setCmpState] = useState('')

  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [level, setLevel] = useState('1')
  const [team, setTeam] = useState('')
  const [review, setReview] = useState('')
  const [replaces, setReplaces] = useState('')

  const say = (text: string, good: boolean) => { setMsg(text); setOk(good) }

  const load = useCallback(async () => {
    const o = await api('/documents/options')
    const options: Options = o.ok ? await o.json() : { can_upload: false, teams: [], max_level: 0 }
    setOpts(options)
    setTeam((t) => (t || options.company_wide ? t : options.teams[0]?.id ?? ''))
    const res = await api('/documents')
    if (res.ok) setDocs((await res.json()).documents as Doc[])
    setLoaded(true)
  }, [])
  useLoad(load)

  async function watchJob(jobId: string, name: string) {
    for (let i = 0; i < 150; i++) {
      await new Promise((r) => setTimeout(r, i < 5 ? 800 : 2000))
      const res = await api('/documents/jobs/' + jobId)
      if (!res.ok) return
      const j = await res.json()
      if (j.status === 'done') {
        say(j.publish_status === 'pending'
          ? `"${name}" was received and waits for an administrator to approve it before anyone can search it.${j.review_note ? ' ' + j.review_note : ''}`
          : `"${name}" is now searchable (${j.parents_created} sections).`, true)
        void load()
        return
      }
      if (j.status === 'failed') { say(`"${name}" could not be added: ${j.error || 'unknown error'}`, false); return }
      say(`"${name}" is ${j.status === 'processing' ? 'being indexed' : 'waiting in the queue'}${j.attempts > 1 ? ` (try ${j.attempts})` : ''}…`, true)
    }
  }

  async function upload(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    form.append('title', title)
    form.append('classification_level', level)
    form.append('engagement_id', team)
    form.append('review_by', review)
    form.append('new_version_of', replaces)
    setBusy(true)
    say(`Reading and indexing ${file.name}…`, true)
    try {
      const res = await api('/documents/upload', { method: 'POST', body: form })
      if (!res.ok) { say(await errText(res), false); return }
      const d = await res.json()
      setFile(null); setTitle(''); setReview(''); setReplaces('')
      ;(document.getElementById('up-file') as HTMLInputElement | null)?.form?.reset()
      if (d.status === 'queued') {
        say(`"${d.title}" was received and is being indexed in the background. You can keep working.`, true)
        void watchJob(d.job_id, d.title)
        return
      }
      say(d.status === 'pending'
        ? `"${d.title}" was received and waits for an administrator to approve it before anyone can search it.`
        : `"${d.title}" is now searchable (${d.parents_created} sections).`, true)
      void load()
    } catch (err) { say(err instanceof Error ? err.message : 'Upload failed.', false) } finally { setBusy(false) }
  }

  async function remove(d: Doc) {
    if (!window.confirm(`Delete "${d.title}" and remove it from search?`)) return
    const r = await api('/documents/' + d.document_id, { method: 'DELETE' })
    if (!r.ok) say(await errText(r), false)
    else { say(`Deleted "${d.title}".`, true); void load() }
  }

  async function approve(d: Doc) {
    const r = await api(`/admin/documents/${d.document_id}/approve`, { method: 'POST' })
    say(r.ok ? `"${d.title}" is now searchable.` : await errText(r), r.ok)
    void load()
  }

  async function compare(oldId: string, newId: string) {
    setCmp(null); setCmpState('Comparing…')
    const r = await send('/documents/compare', 'POST', { document_a: oldId, document_b: newId })
    if (!r.ok) { setCmpState(await errText(r)); return }
    setCmp((await r.json()) as Comparison); setCmpState('')
  }

  const levels = Array.from({ length: opts.max_level }, (_, i) => i + 1)
  const teamChoices = [...(opts.company_wide ? [{ id: '', name: 'Company-wide (no team restriction)' }] : []), ...opts.teams]
  const replacing = replaces !== ''
  const today = new Date().toISOString().slice(0, 10)

  return (
    <div className="page">
      <PageHead title={me.is_admin ? 'All company documents' : 'Documents you added'}
        hint={me.is_admin ? "You see titles and settings, not the content. Reading follows each person's own level." : undefined}>
        <button type="button" onClick={() => void load()}>Refresh</button>
      </PageHead>

      {opts.can_upload && (
        <form className="card gap" onSubmit={upload}>
          <h2>Add a document</h2>
          <p className="muted small">
            {opts.company_wide
              ? 'You publish documents for the whole company. Choose who may read the document; a team adds a second restriction.'
              : 'You can add documents to the engagement teams you belong to, up to your own level. Company-wide documents are published by the administrators.'}
          </p>
          <div className="grid-form">
            <div><label htmlFor="up-file">File (PDF, Word, text)</label><input id="up-file" type="file" required onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></div>
            <div><label htmlFor="up-title">Title</label><input id="up-title" type="text" maxLength={200} placeholder="Defaults to the file name" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
            <div><label htmlFor="up-version">Replaces an existing document?</label>
              <select id="up-version" value={replaces} onChange={(e) => setReplaces(e.target.value)}>
                <option value="">No, a new document</option>
                {docs.filter((d) => d.status === 'published').map((d) => <option key={d.document_id} value={d.document_id}>Yes, replaces: {d.title} (v{d.version})</option>)}
              </select></div>
            <div><label htmlFor="up-level">Who may read it</label>
              <select id="up-level" disabled={replacing} value={level} onChange={(e) => setLevel(e.target.value)}>
                {levels.map((l) => <option key={l} value={l}>Level {l} and above ({LEVELS[l]})</option>)}
              </select></div>
            <div><label htmlFor="up-team">Team</label>
              <select id="up-team" disabled={replacing} value={team} onChange={(e) => setTeam(e.target.value)}>
                {teamChoices.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select></div>
            <div><label htmlFor="up-review">Review by (optional)</label><input id="up-review" type="date" value={review} onChange={(e) => setReview(e.target.value)} /></div>
          </div>
          <div className="form-actions"><button className="primary" type="submit" disabled={busy || !file || !teamChoices.length}>Upload</button></div>
          {!teamChoices.length && <p className="bad-text small">You are not a member of any engagement team yet. Ask an administrator to add you.</p>}
        </form>
      )}
      <Note text={msg} ok={ok} />

      {(cmp || cmpState) && (
        <section className="card gap">
          <div className="audit-head">
            <h2>{cmp ? `${cmp.old.title}: v${cmp.old.version} to v${cmp.new.version}` : cmpState}</h2>
            <button type="button" onClick={() => { setCmp(null); setCmpState('') }}>Close</button>
          </div>
          {cmp && (
            <>
              <p className="muted small">{cmp.total_changes} change(s), {cmp.unchanged} sentence(s) unchanged.{cmp.total_changes > cmp.changes.length ? ` Showing the first ${cmp.changes.length}.` : ''}</p>
              {cmp.summary && <p className="compare-summary">{cmp.summary}</p>}
              {cmp.note && <p className="muted small">{cmp.note}</p>}
              <div className="changes">
                {cmp.changes.map((c, i) => (
                  <div key={i} className={'change ' + c.type}>
                    <b>{c.type}</b>
                    {c.before && <div className={c.type === 'changed' ? 'before' : undefined}>{c.before}</div>}
                    {c.after && <div>{c.after}</div>}
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {loaded && docs.length === 0 ? <p className="muted gap">No documents yet.</p> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Title</th><th>Status</th><th>Level</th><th>Team</th><th>Review by</th><th>Sections</th><th>Added by</th><th>Added</th><th>Actions</th></tr></thead>
            <tbody>
              {docs.map((d) => {
                const overdue = !!d.review_by && d.review_by < today
                return (
                  <tr key={d.document_id}>
                    <td className="q">{d.title}{d.version > 1 ? `  (v${d.version})` : ''}</td>
                    <td><Tag outcome={d.status} label={STATUS_LABEL[d.status] ?? d.status} />{d.note && <div className="muted small">{d.note}</div>}</td>
                    <td>L{d.level}</td>
                    <td>{d.team || 'Company-wide'}</td>
                    <td>{d.review_by ? <span className={overdue ? 'bad-text' : undefined}>{d.review_by}{overdue ? ' (overdue)' : ''}</span> : '-'}</td>
                    <td>{d.sections}</td>
                    <td>{d.uploaded_by || '(seeded)'}</td>
                    <td>{fmtDate(d.created_at)}</td>
                    <td className="actions-cell">
                      {me.is_admin && d.status === 'pending' && <button type="button" className="primary" onClick={() => void approve(d)}>Approve</button>}
                      <button type="button" className="danger" onClick={() => void remove(d)}>{me.is_admin && d.status === 'pending' ? 'Reject' : 'Delete'}</button>
                      {d.supersedes && <button type="button" className="secondary" onClick={() => void compare(d.supersedes as string, d.document_id)}>What changed?</button>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
