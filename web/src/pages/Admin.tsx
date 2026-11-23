import { useCallback, useState, type FormEvent } from 'react'
import { api, errText, send } from '../lib/api'
import { LEVELS, type Me } from '../lib/types'
import { Note, PageHead } from '../components/Bits'
import { fmtDateTime } from '../lib/format'
import { useLoad } from '../lib/hooks'
import { StatusTag, type AccessRequest } from './Requests'

interface User { id: string; email: string; level: number; is_admin: boolean; is_active: boolean; locked?: boolean }
interface Team { id: string; name: string; members: { user_id: string; email: string }[] }
interface AdminEvent { created_at: string; actor_email: string; action: string; target: string }
interface Insights {
  total: number; reviews_overdue?: number; answered_rate: number | null; outcomes: Record<string, number>
  median_latency_ms: number | null; feedback: { helpful: number; not_helpful: number }
  unhelpful_questions: { question: string; times: number }[]; content_gaps: { question: string; times: number }[]
}

function Stat({ value, label }: { value: string | number; label: string }) {
  return <div className="stat"><b>{value}</b><span>{label}</span></div>
}

function PasswordReset({ onSet }: { onSet: (pw: string) => void }) {
  const [pw, setPw] = useState('')
  return (
    <>
      <input type="password" autoComplete="new-password" placeholder="Set new password" aria-label="New password" value={pw} onChange={(e) => setPw(e.target.value)} />{' '}
      <button type="button" className="secondary" onClick={() => { if (pw) { onSet(pw); setPw('') } }}>Reset</button>
    </>
  )
}

function AddMember({ users, taken, onAdd }: { users: User[]; taken: Set<string>; onAdd: (id: string) => void }) {
  const choices = users.filter((u) => !taken.has(u.id) && u.is_active)
  const [id, setId] = useState('')
  const value = choices.some((u) => u.id === id) ? id : choices[0]?.id ?? ''
  return (
    <div className="team-add">
      <select aria-label="Person to add" value={value} onChange={(e) => setId(e.target.value)}>
        {choices.map((u) => <option key={u.id} value={u.id}>{u.email}</option>)}
      </select>
      <button type="button" className="secondary" onClick={() => value && onAdd(value)}>Add member</button>
    </div>
  )
}

export default function Admin({ me }: { me: Me }) {
  const [users, setUsers] = useState<User[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [events, setEvents] = useState<AdminEvent[]>([])
  const [insights, setInsights] = useState<Insights | null>(null)
  const [msg, setMsg] = useState('')
  const [ok, setOk] = useState(true)
  const [nu, setNu] = useState({ email: '', password: '', level: '1', admin: 'no' })
  const [teamName, setTeamName] = useState('')
  const [requests, setRequests] = useState<AccessRequest[]>([])
  const [notes, setNotes] = useState<Record<string, string>>({})

  const say = (text: string, good: boolean) => { setMsg(text); setOk(good) }

  const load = useCallback(async () => {
    const [u, t, e, i, q] = await Promise.all([api('/admin/users'), api('/admin/teams'), api('/admin/events'), api('/admin/insights'), api('/admin/access-requests?status=all')])
    if (q.ok) setRequests((await q.json()).requests as AccessRequest[])
    if (i.ok) setInsights((await i.json()) as Insights)
    if (!u.ok) { say(await errText(u), false); return }
    setUsers((await u.json()).users as User[])
    if (t.ok) setTeams((await t.json()).teams as Team[])
    if (e.ok) setEvents((await e.json()).events as AdminEvent[])
  }, [])
  useLoad(load)

  async function decide(id: string, decision: 'approved' | 'denied') {
    const res = await send(`/admin/access-requests/${id}/decision`, 'POST', { decision, note: notes[id] ?? '' })
    if (!res.ok) { say(await errText(res), false); return }
    say(decision === 'approved' ? 'Approved. Now grant the level or team in People or Engagement teams below.' : 'Denied.', true)
    await load()
  }

  async function patch(id: string, change: Partial<User> & { password?: string }) {
    const r = await send('/admin/users/' + id, 'PATCH', change)
    say(r.ok ? 'Saved.' : await errText(r), r.ok)
    void load()
  }

  async function addUser(e: FormEvent) {
    e.preventDefault()
    const r = await send('/admin/users', 'POST', { email: nu.email, password: nu.password, level: Number(nu.level), is_admin: nu.admin === 'yes' })
    if (r.ok) { setNu({ email: '', password: '', level: '1', admin: 'no' }); say('Person added.', true); void load() } else say(await errText(r), false)
  }

  async function addTeam(e: FormEvent) {
    e.preventDefault()
    const r = await send('/admin/teams', 'POST', { name: teamName })
    if (r.ok) { setTeamName(''); void load() } else say(await errText(r), false)
  }

  const pct = (n: number | null) => (n === null ? 'n/a' : Math.round(n * 100) + '%')

  return (
    <div className="page">
      <PageHead title="Administration" hint="People, engagement teams, usage and the record of every change." />

      {insights && (
        <section className="card gap">
          <h2>How the assistant is doing</h2>
          <div className="stats">
            <Stat value={insights.total} label="questions" />
            <Stat value={insights.reviews_overdue || 0} label="documents past their review date" />
            <Stat value={pct(insights.answered_rate)} label="answered from documents" />
            <Stat value={insights.outcomes.refused || 0} label="not available to the asker" />
            <Stat value={insights.outcomes.no_answer || 0} label="not in the documents" />
            <Stat value={insights.median_latency_ms === null ? 'n/a' : (insights.median_latency_ms / 1000).toFixed(1) + ' s'} label="median answer time" />
            <Stat value={`${insights.feedback.helpful} / ${insights.feedback.not_helpful}`} label="helpful / not helpful ratings" />
          </div>
          <div className="two-col">
            <div>
              <h3>Questions the documents could not answer</h3>
              {insights.content_gaps.length === 0 ? <p className="muted small">None yet.</p> : (
                <div className="table-wrap"><table><thead><tr><th>Question</th><th>Times</th></tr></thead>
                  <tbody>{insights.content_gaps.map((g, i) => <tr key={i}><td className="q">{g.question}</td><td>{g.times}</td></tr>)}</tbody></table></div>
              )}
            </div>
            <div>
              <h3>Answers rated not helpful</h3>
              {insights.unhelpful_questions.length === 0 ? <p className="muted small">None yet.</p> : (
                <div className="table-wrap"><table><thead><tr><th>Question</th><th>Times</th></tr></thead>
                  <tbody>{insights.unhelpful_questions.map((g, i) => <tr key={i}><td className="q">{g.question}</td><td>{g.times}</td></tr>)}</tbody></table></div>
              )}
            </div>
          </div>
        </section>
      )}

      <section className="card gap">
        <h2>Access requests</h2>
        {requests.length === 0 ? <p className="muted">No one has asked for access yet.</p> : (
          <ul className="reqs">{requests.map((r) => (
            <li key={r.id} className="req">
              <StatusTag status={r.status} />
              <strong>{r.user_email}</strong>
              <span>{r.question}</span>
              <span className="muted">Reason: {r.reason} ({fmtDateTime(r.created_at)})</span>
              {r.status === 'pending' ? (
                <span className="actions">
                  <input aria-label={`Note for ${r.user_email}`} placeholder="Note (required to deny)" maxLength={500} value={notes[r.id] ?? ''} onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })} />
                  <button type="button" className="primary" onClick={() => void decide(r.id, 'approved')}>Approve</button>
                  <button type="button" onClick={() => void decide(r.id, 'denied')}>Deny</button>
                </span>
              ) : <span className="muted">Decided by {r.decided_by}{r.decision_note ? `: ${r.decision_note}` : ''}</span>}
            </li>))}</ul>
        )}
        <p className="muted small">Approving records the decision. Changing someone's level or team is a separate step below, so a request alone never widens what anyone can read.</p>
      </section>

      <section className="card gap">
        <h2>People</h2>
        <form onSubmit={addUser}>
          <div className="grid-form">
            <div><label htmlFor="nu-email">Email</label><input id="nu-email" type="email" required value={nu.email} onChange={(e) => setNu({ ...nu, email: e.target.value })} /></div>
            <div><label htmlFor="nu-pass">Starting password</label><input id="nu-pass" type="password" autoComplete="new-password" required value={nu.password} onChange={(e) => setNu({ ...nu, password: e.target.value })} /></div>
            <div><label htmlFor="nu-level">Reading level</label>
              <select id="nu-level" value={nu.level} onChange={(e) => setNu({ ...nu, level: e.target.value })}>
                {[1, 2, 3, 4].map((l) => <option key={l} value={l}>L{l} {LEVELS[l]}</option>)}
              </select></div>
            <div><label htmlFor="nu-admin">Administrator</label>
              <select id="nu-admin" value={nu.admin} onChange={(e) => setNu({ ...nu, admin: e.target.value })}><option value="no">No</option><option value="yes">Yes</option></select></div>
          </div>
          <div className="form-actions"><button className="primary" type="submit">Add person</button></div>
        </form>
        <Note text={msg} ok={ok} />
        <div className="table-wrap">
          <table>
            <thead><tr><th>Email</th><th>Level</th><th>Admin</th><th>Active</th><th>Password</th></tr></thead>
            <tbody>
              {users.map((u) => {
                const self = u.email.toLowerCase() === me.email.toLowerCase()
                return (
                  <tr key={u.id}>
                    <td>{u.email}{u.locked ? ' (locked after failed sign-ins: reset the password to unlock)' : ''}</td>
                    <td>{self ? 'L' + u.level : (
                      <select aria-label={'Level for ' + u.email} value={u.level} onChange={(e) => void patch(u.id, { level: Number(e.target.value) })}>
                        {[1, 2, 3, 4].map((l) => <option key={l} value={l}>L{l} {LEVELS[l]}</option>)}
                      </select>)}</td>
                    <td>{self ? (u.is_admin ? 'Yes' : 'No') : <input type="checkbox" aria-label={'Administrator: ' + u.email} checked={u.is_admin} onChange={(e) => void patch(u.id, { is_admin: e.target.checked })} />}</td>
                    <td>{self ? 'Yes (you)' : <input type="checkbox" aria-label={'Active: ' + u.email} checked={u.is_active} onChange={(e) => void patch(u.id, { is_active: e.target.checked })} />}</td>
                    <td><PasswordReset onSet={(pw) => void patch(u.id, { password: pw })} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card gap">
        <h2>Engagement teams</h2>
        <p className="muted small">Sensitive documents tied to a team are visible only to its members who also have the required level.</p>
        <form className="team-add" onSubmit={addTeam}>
          <input aria-label="New team name" placeholder="New team name" required value={teamName} onChange={(e) => setTeamName(e.target.value)} />
          <button className="secondary" type="submit">Create team</button>
        </form>
        <div className="teams">
          {teams.map((t) => (
            <div key={t.id} className="team">
              <h3>{t.name}</h3>
              <div className="chips">
                {t.members.length === 0 && <span className="muted small">No members yet.</span>}
                {t.members.map((m) => (
                  <span key={m.user_id} className="chip">{m.email}
                    <button type="button" title={'Remove ' + m.email} aria-label={'Remove ' + m.email}
                      onClick={async () => { await send(`/admin/teams/${t.id}/members/${m.user_id}`, 'DELETE'); void load() }}>×</button>
                  </span>
                ))}
              </div>
              <AddMember users={users} taken={new Set(t.members.map((m) => m.user_id))}
                onAdd={async (id) => { await send(`/admin/teams/${t.id}/members`, 'POST', { user_id: id }); void load() }} />
            </div>
          ))}
        </div>
      </section>

      <section className="card gap">
        <h2>Change history</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Target</th></tr></thead>
            <tbody>{events.map((ev, i) => <tr key={i}><td>{fmtDateTime(ev.created_at)}</td><td>{ev.actor_email}</td><td>{ev.action}</td><td className="q">{ev.target}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
