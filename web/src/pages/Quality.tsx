import { PageHead } from '../components/Bits'
import { SCALE, SUITES } from '../data/quality'

export default function Quality() {
  return (
    <div className="page">
      <PageHead title="Quality" hint="How well the assistant answers, measured on fixed question sets. Misses are listed, not hidden." />
      <div className="quality-grid">
        {SUITES.map((s) => (
          <section key={s.title} className="card gap">
            <h2>{s.title} <span className="muted small">({s.questions} questions)</span></h2>
            <dl className="metrics">
              {s.rows.map((r) => (
                <div key={r.label} className={r.leak ? 'metric leak' : 'metric'}>
                  <dt>{r.label}</dt>
                  <dd>{r.value}{r.note ? <span className="muted small"> ({r.note})</span> : null}</dd>
                </div>
              ))}
            </dl>
            {s.failures && (
              <>
                <h3>Questions it got wrong</h3>
                <ul className="plain">{s.failures.map((f) => <li key={f}>{f}</li>)}</ul>
              </>
            )}
          </section>
        ))}
        <section className="card gap">
          <h2>Scale and isolation</h2>
          <dl className="metrics">
            {SCALE.map((r) => <div key={r.label} className="metric"><dt>{r.label}</dt><dd>{r.value}</dd></div>)}
          </dl>
        </section>
      </div>
      <p className="muted small gap">
        Results come from the evaluation reports in the repository, run on a local model. The check script recomputes these numbers from the raw result files in CI.
      </p>
    </div>
  )
}
