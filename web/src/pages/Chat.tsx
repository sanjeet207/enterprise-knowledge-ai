import { Fragment, useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { api, errText, send } from '../lib/api'
import { LEVELS, type ChatMessage, type ChatReply, type Me, type Source } from '../lib/types'
import { Tag, Trace } from '../components/Bits'
import { useLoad } from '../lib/hooks'

const SUGGESTIONS = [
  'How many days of annual leave do I get?',
  'Do I need approval to travel to an international conference?',
  'How quickly must I report a security incident?',
  'What is the compensation band for a manager?',
  'What is the weather in Delhi today?',
]

interface Conversation { id: string; title: string }
interface StoredMessage { id: string; role: string; content: string; outcome: string; sources: Source[]; rating?: number | null }

function failureText(status: number): string {
  if (status === 503) return 'The language model is not reachable right now. Please try again shortly.'
  if (status === 429) return 'You are asking too quickly. Please wait a moment.'
  if (status === 422) return 'That question could not be processed. Keep it under 1000 characters.'
  return `Something went wrong (${status}).`
}

function AnswerText({ text, sources, onCite }: { text: string; sources: Source[]; onCite: (n: number) => void }) {
  const valid = new Set(sources.map((s) => s.number))
  return (
    <>
      {String(text).split(/(\[\d+\])/g).map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part)
        if (m && valid.has(Number(m[1]))) {
          const n = Number(m[1])
          return <button key={i} type="button" className="cite" title={'Show source ' + n} onClick={() => onCite(n)}>{n}</button>
        }
        return <Fragment key={i}>{part}</Fragment>
      })}
    </>
  )
}

function Feedback({ messageId, current }: { messageId: string; current?: number | null }) {
  const [state, setState] = useState<'idle' | 'comment' | 'done' | 'failed'>('idle')
  const [comment, setComment] = useState('')
  const [rating, setRating] = useState<number | null | undefined>(current)

  async function submit(value: number, text?: string) {
    const r = await send(`/chat/messages/${messageId}/feedback`, 'POST', { rating: value, comment: text || null })
    setRating(value)
    setState(r.ok ? 'done' : 'failed')
  }

  if (state === 'done') return <div className="feedback"><span className="thanks">Thanks, your feedback was recorded.</span></div>
  if (state === 'failed') return <div className="feedback"><span className="thanks">Could not save feedback.</span></div>
  if (state === 'comment') {
    return (
      <div className="feedback">
        <input type="text" maxLength={500} autoFocus placeholder="What was wrong? (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
        <button type="button" onClick={() => void submit(-1, comment)}>Send</button>
      </div>
    )
  }
  return (
    <div className="feedback">
      <button type="button" className={rating === 1 ? 'on' : ''} onClick={() => void submit(1)}>Helpful</button>
      <button type="button" className={rating === -1 ? 'on' : ''} onClick={() => setState('comment')}>Not helpful</button>
    </div>
  )
}

function Bot({ m, onCite }: { m: ChatMessage; onCite: (key: number, n: number) => void }) {
  const [showTrace, setShowTrace] = useState(false)
  if (m.pending) return <div className="msg bot thinking" role="status">Searching the documents you are allowed to see…</div>
  const r = m.reply
  if (!r) return null
  const feedbackOn = r.message_id && ['answered', 'general', 'no_answer'].includes(r.outcome)
  return (
    <div className="msg bot" data-outcome={r.outcome}>
      <Tag outcome={r.outcome} />
      {r.corrected_query ? <span className="note">Searched for: {r.corrected_query}</span> : null}
      <span className="body">
        {r.outcome === 'answered'
          ? <AnswerText text={r.answer} sources={r.sources ?? []} onCite={(n) => onCite(m.key, n)} />
          : r.answer}
      </span>
      {r.outcome === 'general' && <span className="note">General knowledge, not from company documents. Check it before relying on it.</span>}
      {r.trace && r.trace.length > 0 && (
        <div className="how">
          <button type="button" className="link" aria-expanded={showTrace} onClick={() => setShowTrace(!showTrace)}>
            {showTrace ? 'Hide how this was answered' : 'How this was answered'}
          </button>
          {showTrace && <Trace steps={r.trace} />}
        </div>
      )}
      {feedbackOn ? <Feedback messageId={r.message_id as string} current={r.rating} /> : null}
    </div>
  )
}

export default function Chat({ me }: { me: Me }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [convId, setConvId] = useState<string | null>(null)
  const [convs, setConvs] = useState<Conversation[]>([])
  const [activeKey, setActiveKey] = useState<number | null>(null)
  const [highlight, setHighlight] = useState<number | null>(null)
  const counter = useRef(0)
  const endRef = useRef<HTMLDivElement>(null)
  const sourceRefs = useRef<Record<number, HTMLLIElement | null>>({})

  const loadConversations = useCallback(async () => {
    const res = await api('/chat/conversations')
    if (res.ok) setConvs((await res.json()).conversations as Conversation[])
  }, [])

  useLoad(loadConversations)
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }) }, [messages])
  useEffect(() => {
    if (highlight !== null) sourceRefs.current[highlight]?.scrollIntoView({ block: 'nearest' })
  }, [highlight, activeKey])

  const active = messages.find((m) => m.key === activeKey)
  const sources = active?.reply?.outcome === 'answered' ? active.reply.sources ?? [] : []

  function reset() {
    setConvId(null)
    setMessages([])
    setActiveKey(null)
    setHighlight(null)
  }

  async function ask(text: string) {
    const q = text.trim()
    if (busy || !q) return
    setBusy(true)
    const userKey = ++counter.current
    const botKey = ++counter.current
    setMessages((prev) => [...prev, { key: userKey, role: 'user', text: q }, { key: botKey, role: 'bot', text: '', pending: true }])
    const finish = (reply: ChatReply) =>
      setMessages((prev) => prev.map((m) => (m.key === botKey ? { ...m, pending: false, reply } : m)))
    try {
      const res = await send('/chat/query', 'POST', { query: q, top_k: 3, conversation_id: convId })
      if (!res.ok) {
        finish({ outcome: 'error', answer: failureText(res.status) })
      } else {
        const data = (await res.json()) as ChatReply
        if (data.conversation_id) setConvId(data.conversation_id)
        finish(data)
        setActiveKey(botKey)
        setHighlight(null)
        void loadConversations()
      }
    } catch (e) {
      finish({ outcome: 'error', answer: e instanceof Error ? e.message : 'Network error.' })
    } finally {
      setBusy(false)
    }
  }

  async function openConversation(id: string) {
    if (!id) { reset(); return }
    const res = await api('/chat/conversations/' + id)
    if (!res.ok) { reset(); return }
    const stored = (await res.json()).messages as StoredMessage[]
    setConvId(id)
    setActiveKey(null)
    setMessages(stored.map((m) => {
      const key = ++counter.current
      if (m.role === 'user') return { key, role: 'user', text: m.content }
      return {
        key, role: 'bot', text: '',
        reply: { outcome: m.outcome, answer: m.content, sources: m.sources, message_id: m.id, rating: m.rating },
      }
    }))
  }

  async function removeConversation() {
    if (!convId || !window.confirm('Delete this conversation?')) return
    const r = await api('/chat/conversations/' + convId, { method: 'DELETE' })
    if (!r.ok) { window.alert(await errText(r)); return }
    reset()
    void loadConversations()
  }

  const submit = (e: FormEvent) => { e.preventDefault(); const q = question; setQuestion(''); void ask(q) }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); const q = question; setQuestion(''); void ask(q) }
  }

  return (
    <div className="layout">
      <section className="chat" aria-label="Conversation">
        <div className="convbar">
          <select aria-label="Saved conversations" value={convId ?? ''} onChange={(e) => void openConversation(e.target.value)}>
            <option value="">New conversation</option>
            {convs.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
          <button type="button" onClick={() => { reset(); void loadConversations() }}>New</button>
          {convId && <button type="button" className="danger" onClick={() => void removeConversation()}>Delete</button>}
        </div>
        <div className="messages" aria-live="polite">
          {messages.length === 0 && (
            <div className="empty">
              <h2>What do you need to know?</h2>
              <p className="muted">
                You are reading as {LEVELS[me.level] ?? 'level ' + me.level}. Answers use only documents that level
                (and your teams) may see, and every statement links to its source.
              </p>
              <div className="suggestions">
                {SUGGESTIONS.map((s, i) => (
                  <button key={s} type="button" className={i === SUGGESTIONS.length - 1 ? 'try' : ''} onClick={() => void ask(s)}>{s}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) =>
            m.role === 'user'
              ? <div key={m.key} className="msg user">{m.text}</div>
              : <Bot key={m.key} m={m} onCite={(key, n) => { setActiveKey(key); setHighlight(n) }} />)}
          <div ref={endRef} />
        </div>
        <form className="composer" onSubmit={submit}>
          <label className="sr-only" htmlFor="question">Your question</label>
          <textarea
            id="question" rows={1} maxLength={1000} autoFocus
            placeholder="Ask about a policy, a process or a document…"
            value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={onKey}
          />
          <button className="primary" type="submit" disabled={busy || !question.trim()}>Ask</button>
        </form>
      </section>
      <aside className="sources card" aria-label="Sources">
        <h2>Sources</h2>
        {sources.length === 0
          ? <p className="muted small">Documents cited by the latest answer appear here. Select a numbered citation in an answer to jump to its source.</p>
          : (
            <ul className="sources-list">
              {sources.map((s) => (
                <li
                  key={s.number}
                  ref={(el) => { sourceRefs.current[s.number] = el }}
                  className={'source' + (highlight === s.number ? ' hl' : '')}
                >
                  <div><span className="n">{s.number}</span><span className="t">{s.title}</span></div>
                  <div className="bar"><span style={{ width: Math.max(2, Math.min(100, Math.round((s.score || 0) * 100))) + '%' }} /></div>
                  <div className="s">Relevance {(s.score || 0).toFixed(2)}</div>
                </li>
              ))}
            </ul>
          )}
      </aside>
    </div>
  )
}
