import type { ReactNode } from 'react'
import { LEVELS, OUTCOME_LABEL, type TraceStep } from '../lib/types'

export function Tag({ outcome, label }: { outcome: string; label?: string }) {
  return <span className={'tag ' + outcome}>{label ?? OUTCOME_LABEL[outcome] ?? outcome}</span>
}

export function Note({ text, ok }: { text: string; ok: boolean }) {
  if (!text) return null
  return <p className={'small ' + (ok ? 'ok-text' : 'bad-text')} role="status">{text}</p>
}

export function Clearance({ level }: { level: number }) {
  return (
    <div className="clearance" role="img" aria-label={`Reading level ${level} of 4, ${LEVELS[level] ?? ''}`}>
      {[1, 2, 3, 4].map((n) => <i key={n} className={n <= level ? 'on' : ''} />)}
    </div>
  )
}

export function PageHead({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="audit-head">
      <div>
        <h1>{title}</h1>
        {hint ? <p className="muted">{hint}</p> : null}
      </div>
      {children}
    </div>
  )
}

/** One segment per pipeline step; the width follows the time the step took. */
export function Trace({ steps, detail = false }: { steps: TraceStep[]; detail?: boolean }) {
  if (!steps.length) return null
  const total = steps.reduce((a, s) => a + Math.max(s.ms, 1), 0)
  return (
    <div className="trace" role="list" aria-label="Pipeline steps">
      {steps.map((s, i) => (
        <div
          key={i}
          role="listitem"
          className={'step ' + s.agent}
          style={{ flexGrow: Math.max(s.ms, 1) / total * 100 }}
          title={s.detail ? `${s.agent}: ${s.detail}` : s.agent}
        >
          <b>{s.agent}</b>
          <span>{s.ms >= 1000 ? (s.ms / 1000).toFixed(1) + ' s' : s.ms + ' ms'}</span>
          {detail && s.detail ? <em>{s.detail}</em> : null}
        </div>
      ))}
    </div>
  )
}
