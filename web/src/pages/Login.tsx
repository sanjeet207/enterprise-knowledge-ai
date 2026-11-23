import { useEffect, useState, type FormEvent } from 'react'
import { login, setToken } from '../lib/api'

const DEMO_PASSWORD = 'DemoPass2026x'
const DEMO: [string, string][] = [
  ['analyst@acme.test', 'Analyst (level 1)'],
  ['manager@acme.test', 'Manager (level 2)'],
  ['director@acme.test', 'Director (level 3)'],
  ['manager_titan@acme.test', 'Manager, Project Titan team'],
  ['director_titan@acme.test', 'Director, Project Titan team'],
  ['partner_titan@acme.test', 'Partner, Project Titan team'],
  ['partner_outsider@acme.test', 'Partner, not on Titan'],
  ['admin@acme.test', 'Administrator (knowledge team), uploads and manages'],
  ['globex_analyst@globex.test', 'Other company: Globex analyst'],
]

export default function Login({ onSignedIn, ssoFailed }: { onSignedIn: () => Promise<void>; ssoFailed: boolean }) {
  const [cfg, setCfg] = useState({ sso: false, password: true })
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(
    ssoFailed ? 'Single sign-on failed. Ask your administrator to check that your account exists.' : '',
  )
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    fetch('/auth/config').then((r) => (r.ok ? r.json() : null)).then((c) => { if (c) setCfg(c) }).catch(() => {})
  }, [])

  async function go(e: string, p: string) {
    setError('')
    setBusy(true)
    try {
      setToken(await login(e, p))
      await onSignedIn()
    } catch (err) {
      setToken(null)
      setError(err instanceof Error ? err.message : 'Sign-in failed.')
    } finally {
      setBusy(false)
    }
  }

  const submit = (e: FormEvent) => { e.preventDefault(); void go(email.trim(), password) }

  return (
    <div className="login">
      <div className="login-card card">
        <h1>Enterprise Knowledge</h1>
        <p className="muted">Ask questions in plain language. Answers come only from your company's documents that you are allowed to read, with the source for every statement.</p>
        {cfg.sso
          ? <a className="sso-button" href="/auth/sso/login">Sign in with company SSO</a>
          : <button type="button" className="sso-button off" disabled aria-describedby="sso-help">Sign in with company SSO</button>}
        {!cfg.sso && <p id="sso-help" className="muted small center">SSO is not configured on this server. Set OIDC_ISSUER and OIDC_CLIENT_ID in .env to turn it on (see docs/SSO.md).</p>}
        {cfg.password && <p className="muted small center">{cfg.sso ? 'or use a password' : 'Password sign-in is available below.'}</p>}
        {cfg.password && (
          <form onSubmit={submit}>
            <label htmlFor="email">Work email</label>
            <input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            <label htmlFor="password">Password</label>
            <input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            <button className="primary" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
          </form>
        )}
        {error && <p className="error" role="alert">{error}</p>}
        {cfg.password && (
          <details className="demo">
            <summary>Try a demo account</summary>
            <p className="muted small">Each account sees different documents. Ask the same question as two of them to see access control at work.</p>
            <div className="demo-list">
              {DEMO.map(([em, label]) => (
                <button key={em} type="button" disabled={busy} onClick={() => void go(em, DEMO_PASSWORD)}>
                  <span>{label}</span><span className="lvl">{em}</span>
                </button>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  )
}
