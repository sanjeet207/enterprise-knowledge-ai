// All network access lives here. The server contract is unchanged from the previous interface.
const KEY = 'eka_token'
let token: string | null = null
let onExpired: (() => void) | null = null

export function loadToken(): string | null {
  try { token = sessionStorage.getItem(KEY) } catch { token = null }
  return token
}
export function setToken(value: string | null): void {
  token = value
  try { if (value) sessionStorage.setItem(KEY, value); else sessionStorage.removeItem(KEY) } catch { /* storage may be blocked */ }
}
export function setExpiredHandler(fn: () => void): void { onExpired = fn }

export async function api(path: string, opts: RequestInit = {}): Promise<Response> {
  const headers = new Headers(opts.headers)
  if (token) headers.set('Authorization', 'Bearer ' + token)
  const res = await fetch(path, { ...opts, headers })
  if (res.status === 401 && token) {
    onExpired?.()
    throw new Error('Session expired. Please sign in again.')
  }
  return res
}

export function send(path: string, method: string, payload?: unknown): Promise<Response> {
  return api(path, {
    method,
    headers: payload === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  })
}

export async function errText(res: Response): Promise<string> {
  try {
    const j = await res.json()
    return typeof j.detail === 'string' ? j.detail : `Request failed (${res.status}).`
  } catch {
    return `Request failed (${res.status}).`
  }
}

export async function getJson<T>(path: string): Promise<T> {
  const res = await api(path)
  if (!res.ok) throw new Error(await errText(res))
  return (await res.json()) as T
}

export async function login(email: string, password: string): Promise<string> {
  const res = await fetch('/auth/login', { method: 'POST', body: new URLSearchParams({ username: email, password }) })
  if (!res.ok) throw new Error(res.status === 401 ? 'Incorrect email or password.' : `Sign-in failed (${res.status}).`)
  return (await res.json()).access_token as string
}
