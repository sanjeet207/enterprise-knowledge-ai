import { useState, type FormEvent } from 'react'
import { errText, send } from '../lib/api'

/** Shown under a refused answer. The refusal never says whether a restricted document exists, so the person
 *  describes what they need and why, and an administrator decides. */
export default function RequestAccess({ question }: { question: string }) {
  const [open, setOpen] = useState(false)
  const [need, setNeed] = useState(question)
  const [reason, setReason] = useState('')
  const [state, setState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const [error, setError] = useState('')

  async function submit(e: FormEvent) {
    e.preventDefault()
    setState('sending'); setError('')
    try {
      const res = await send('/access-requests', 'POST', { question: need, reason })
      if (!res.ok) { setError(await errText(res)); setState('idle'); return }
      setState('sent')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error.')
      setState('idle')
    }
  }

  if (state === 'sent') return <div className="request"><span className="thanks">Request sent. An administrator will review it, and the decision appears under Access requests.</span></div>
  if (!open) return <div className="request"><button type="button" className="link" onClick={() => setOpen(true)}>Request access</button></div>
  return (
    <form className="request" onSubmit={submit}>
      <label htmlFor="ra-need">What do you need access to?</label>
      <textarea id="ra-need" rows={2} required maxLength={1000} value={need} onChange={(e) => setNeed(e.target.value)} />
      <label htmlFor="ra-why">Why do you need it?</label>
      <textarea id="ra-why" rows={2} required minLength={10} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="For example: I am staffed on the review starting next week." />
      {error && <span className="note" role="alert">{error}</span>}
      <span className="actions">
        <button type="submit" className="primary" disabled={state === 'sending'}>{state === 'sending' ? 'Sending…' : 'Send request'}</button>
        <button type="button" className="link" onClick={() => setOpen(false)}>Cancel</button>
      </span>
    </form>
  )
}
