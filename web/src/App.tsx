import { useCallback, useEffect, useState } from 'react'
import { useLoad } from './lib/hooks'
import { api, getJson, loadToken, setExpiredHandler, setToken } from './lib/api'
import { LEVELS, type Me } from './lib/types'
import { Clearance } from './components/Bits'
import Login from './pages/Login'
import Chat from './pages/Chat'
import Research from './pages/Research'
import Docs from './pages/Docs'
import Admin from './pages/Admin'
import Audit from './pages/Audit'
import Quality from './pages/Quality'

// Single sign-on returns here with a session token (or an error flag) in the address fragment.
// Read it once when the page loads, so React re-rendering can never lose it.
function readSso(): { token: string | null; failed: boolean } {
  const hash = new URLSearchParams(window.location.hash.slice(1))
  const token = hash.get('sso_token')
  const failed = hash.get('sso_error') !== null
  if (token || failed) history.replaceState(null, '', window.location.pathname)
  if (token) setToken(token)
  return { token: token ?? loadToken(), failed }
}
const START = readSso()

type Tab = 'chat' | 'research' | 'docs' | 'quality' | 'admin' | 'audit'

export default function App() {
  const [me, setMe] = useState<Me | null>(null)
  const [booting, setBooting] = useState(START.token !== null)
  const [tab, setTab] = useState<Tab>('chat')

  const signOut = useCallback(() => {
    setToken(null)
    setMe(null)
    setTab('chat')
  }, [])

  const enter = useCallback(async () => {
    setMe(await getJson<Me>('/auth/me'))
    setTab('chat')
  }, [])

  useEffect(() => { setExpiredHandler(signOut) }, [signOut])

  const boot = useCallback(async () => {
    if (START.token === null) return
    try { await enter() } catch { signOut() } finally { setBooting(false) }
  }, [enter, signOut])
  useLoad(boot)

  if (booting) return <div className="boot" aria-busy="true">Loading…</div>
  if (!me) return <Login onSignedIn={enter} ssoFailed={START.failed} />

  const tabs: { id: Tab; label: string; show: boolean }[] = [
    { id: 'chat', label: 'Ask', show: true },
    { id: 'research', label: 'Research', show: true },
    { id: 'docs', label: 'Documents', show: me.is_admin || me.level >= 2 },
    { id: 'quality', label: 'Quality', show: true },
    { id: 'admin', label: 'Administration', show: me.is_admin },
    { id: 'audit', label: 'Audit log', show: me.level >= 4 },
  ]

  const downloadMyData = async () => {
    const r = await api('/me/data')
    if (!r.ok) return
    const url = URL.createObjectURL(await r.blob())
    const a = document.createElement('a')
    a.href = url
    a.download = 'my-data.json'
    document.body.append(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">Enterprise Knowledge</div>
        <nav className="tabs" role="tablist" aria-label="Sections">
          {tabs.filter((t) => t.show).map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              className={'tab' + (tab === t.id ? ' active' : '')}
              onClick={() => setTab(t.id)}
            >{t.label}</button>
          ))}
        </nav>
        <div className="who">
          <span className="who-email">{me.email}</span>
          <span className="badge">{LEVELS[me.level] ?? 'Level ' + me.level} · L{me.level}{me.is_admin ? ' · Admin' : ''}</span>
          <Clearance level={me.level} />
          <span className="clearance-label">Reads documents up to level {me.level}</span>
          <button className="link" onClick={downloadMyData}>Download my data</button>
          <button className="link" onClick={signOut}>Sign out</button>
        </div>
      </header>
      <main className="main">
        {tab === 'chat' && <Chat me={me} />}
        {tab === 'research' && <Research />}
        {tab === 'docs' && <Docs me={me} />}
        {tab === 'quality' && <Quality />}
        {tab === 'admin' && <Admin me={me} />}
        {tab === 'audit' && <Audit />}
      </main>
    </div>
  )
}
