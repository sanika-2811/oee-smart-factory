import { useSyncExternalStore } from 'react'

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/* ---------------------------------------------------------------- auth (HTTP Basic, kept in sessionStorage) */
export interface AuthUser {
  username: string
  role: string
  token: string
}

const AUTH_KEY = 'oee.auth'
let authUser: AuthUser | null = null
try {
  const raw = sessionStorage.getItem(AUTH_KEY)
  if (raw) authUser = JSON.parse(raw)
} catch {
  /* storage unavailable: stay signed out */
}
const authListeners = new Set<() => void>()
let loginRequested = false

function emitAuth() {
  authListeners.forEach((l) => l())
}

export const auth = {
  get: () => authUser,
  subscribe(l: () => void) {
    authListeners.add(l)
    return () => { authListeners.delete(l) }
  },
  async login(username: string, password: string): Promise<AuthUser> {
    const token = btoa(`${username}:${password}`)
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { Authorization: `Basic ${token}`, 'X-Requested-With': 'fetch' },
    })
    if (!res.ok) throw new ApiError(res.status, 'That username or password is not right. Please check and try again.')
    const data = await res.json()
    authUser = { username: data.username, role: data.role, token }
    try {
      sessionStorage.setItem(AUTH_KEY, JSON.stringify(authUser))
    } catch {
      /* ignore */
    }
    emitAuth()
    return authUser
  },
  logout() {
    authUser = null
    try {
      sessionStorage.removeItem(AUTH_KEY)
    } catch {
      /* ignore */
    }
    emitAuth()
  },
}

export function useAuth(): AuthUser | null {
  return useSyncExternalStore(auth.subscribe, auth.get)
}

/** The login dialog subscribes to this; any write without credentials asks for it. */
const loginListeners = new Set<(open: boolean) => void>()
export const loginDialog = {
  subscribe(l: (open: boolean) => void) {
    loginListeners.add(l)
    return () => { loginListeners.delete(l) }
  },
  request() {
    loginRequested = true
    loginListeners.forEach((l) => l(true))
  },
  close() {
    loginRequested = false
    loginListeners.forEach((l) => l(false))
  },
  isOpen: () => loginRequested,
}

/* ---------------------------------------------------------------- requests */
async function request<T>(method: string, path: string, body?: unknown, needsAuth = false): Promise<T> {
  const headers: Record<string, string> = { 'X-Requested-With': 'fetch' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (needsAuth || authUser) {
    if (!authUser && needsAuth) {
      loginDialog.request()
      throw new ApiError(401, 'Please sign in to make changes.')
    }
    if (authUser) headers.Authorization = `Basic ${authUser.token}`
  }
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check that the backend is running, then try again.')
  }
  if (res.status === 401) {
    auth.logout()
    loginDialog.request()
    throw new ApiError(401, 'Your session is not valid. Please sign in again.')
  }
  if (!res.ok) {
    let msg = `The server said no (HTTP ${res.status}).`
    try {
      const j = await res.json()
      if (typeof j.detail === 'string') msg = j.detail
      else if (Array.isArray(j.detail)) msg = j.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      /* keep default */
    }
    throw new ApiError(res.status, msg)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}, true),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body, true),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body ?? {}, true),
  del: <T = void>(path: string) => request<T>('DELETE', path, undefined, true),
}

export function wsUrl(): string {
  const base = API_BASE.startsWith('http') ? API_BASE.replace(/^http/, 'ws') : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${API_BASE}`
  return `${base}/ws/live`
}
