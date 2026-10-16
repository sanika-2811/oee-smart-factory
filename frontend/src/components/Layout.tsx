import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { ApiError, auth, loginDialog, useAuth } from '../lib/api'
import { LEVELS } from '../lib/levels'
import { go } from '../lib/router'
import { store, useStore, EMPTY } from '../lib/store'
import { Icon, LEVEL_ICON } from './ui'

const NAV = [
  { path: 'overview', label: 'Overview', icon: 'overview' },
  { path: 'machines', label: 'Machines', icon: 'machines' },
  { path: 'alerts', label: 'Alerts', icon: 'bell' },
  { path: 'maintenance', label: 'Maintenance', icon: 'wrench' },
  { path: 'reports', label: 'Reports', icon: 'chart' },
  { path: 'control', label: 'Control', icon: 'sliders' },
]

function useOpenAlerts(): number {
  return useStore((s) => s.snapshot?.plant.open_alerts ?? 0)
}

export function Sidebar({ current }: { current: string }) {
  const open = useOpenAlerts()
  const config = useStore((s) => s.config)
  return (
    <aside className="sidebar" aria-label="Main navigation">
      <div className="brand">
        <img src="/logo.svg" alt="" />
        <div><b>OEE Control Room</b><small>Smart factory</small></div>
      </div>
      <nav className="nav">
        {NAV.map((n) => (
          <a key={n.path} href={`#/${n.path}`} aria-current={current === n.path ? 'page' : undefined}>
            <Icon name={n.icon} />
            {n.label}
            {n.path === 'alerts' && open > 0 && <span className="count" aria-label={`${open} open alerts`}>{open}</span>}
          </a>
        ))}
      </nav>
      <div className="sidebar-foot">
        <div>{config ? `${config.machines.length} machines · ${config.ingest_mode.toUpperCase()}` : 'Connecting…'}</div>
        <div>Storage: {config?.storage_mode ?? '…'}</div>
        <div style={{ marginTop: 6 }}>NMIMS Shirpur · Software Engineering</div>
      </div>
    </aside>
  )
}

export function TabBar({ current }: { current: string }) {
  const open = useOpenAlerts()
  return (
    <nav className="tabbar" aria-label="Main navigation">
      {NAV.map((n) => (
        <a key={n.path} href={`#/${n.path}`} aria-current={current === n.path ? 'page' : undefined}>
          <Icon name={n.icon} />
          {n.label}
          {n.path === 'alerts' && open > 0 && <span className="count">{open}</span>}
        </a>
      ))}
    </nav>
  )
}

function ConnBadge() {
  const conn = useStore((s) => s.conn)
  const lat = useStore((s) => s.clientLatencyMs)
  const label = conn === 'live' ? `Live${lat !== null ? ` · ${Math.round(lat)} ms` : ''}` : conn === 'connecting' ? 'Connecting…' : 'Reconnecting…'
  return (
    <span className={`conn ${conn}`} role="status" aria-live="polite" title="WebSocket connection to the backend">
      <i />{label}
    </span>
  )
}

function ThemeToggle() {
  const theme = useStore((s) => s.theme)
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button className="btn icon-btn" onClick={() => store.setTheme(next)} aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`}>
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
    </button>
  )
}

function UserChip() {
  const user = useAuth()
  if (!user) {
    return <button className="btn sm" onClick={() => loginDialog.request()}><Icon name="user" />Sign in</button>
  }
  return (
    <button className="btn sm" onClick={() => auth.logout()} title="Sign out" aria-label={`Signed in as ${user.username}. Sign out`}>
      <Icon name="logout" />{user.username}
    </button>
  )
}

export function TopBar({ title, sub, children }: { title: string; sub?: ReactNode; children?: ReactNode }) {
  return (
    <header className="topbar">
      <div>
        <h1>{title}</h1>
        {sub && <div className="sub">{sub}</div>}
      </div>
      <div className="spacer" />
      {children}
      <ConnBadge />
      <ThemeToggle />
      <UserChip />
    </header>
  )
}

/* ------------------------------------------------------------------ offline banner */
export function OfflineBanner() {
  const conn = useStore((s) => s.conn)
  const last = useStore((s) => s.lastMessageAt)
  const [, force] = useState(0)
  useEffect(() => { const t = window.setInterval(() => force((n) => n + 1), 1000); return () => window.clearInterval(t) }, [])
  if (conn === 'live' || (conn === 'connecting' && !last)) return null
  const secs = last ? Math.round((Date.now() - last) / 1000) : null
  return (
    <div className="err" role="alert" style={{ marginBottom: 12, display: 'flex', gap: 10, alignItems: 'center' }}>
      <Icon name="octagon" size={18} />
      <span><b>Live data paused.</b> The dashboard cannot reach the backend{secs !== null ? ` (last update ${secs} s ago)` : ''}. It reconnects automatically — figures on screen may be out of date.</span>
    </div>
  )
}

/* ------------------------------------------------------------------ toasts */
export function Toasts() {
  const toasts = useStore((s) => s.toasts)
  return (
    <div className="toasts" aria-live="assertive" aria-atomic="false">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`toast ${t.level ? `lv-${t.level}` : ''}`}
          role="alert"
          tabIndex={0}
          onClick={() => { store.dismissToast(t.id); if (t.kind === 'alert') go('/alerts') }}
          onKeyDown={(e) => { if (e.key === 'Enter') { store.dismissToast(t.id); if (t.kind === 'alert') go('/alerts') } }}
        >
          <div className="alert-ico" style={t.level ? undefined : { background: 'var(--surface-2)', color: 'var(--accent)' }}>
            <Icon name={t.level ? LEVEL_ICON[t.level] : t.kind === 'error' ? 'octagon' : 'check'} />
          </div>
          <div><b>{t.level ? `${LEVELS[t.level].label} · ` : ''}{t.title}</b><span>{t.message}</span></div>
          <button className="btn sm ghost" style={{ padding: '2px 8px' }} aria-label="Dismiss" onClick={(e) => { e.stopPropagation(); store.dismissToast(t.id) }}>×</button>
        </div>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ login */
export function LoginModal() {
  const [open, setOpen] = useState(loginDialog.isOpen())
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const demo = useStore((s) => s.config?.demo_logins ?? EMPTY)

  useEffect(() => loginDialog.subscribe(setOpen), [])
  useEffect(() => {
    if (!open) return
    const prev = document.activeElement as HTMLElement | null
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') return loginDialog.close()
      if (e.key !== 'Tab') return
      const nodes = Array.from(document.querySelectorAll<HTMLElement>('.modal input, .modal button, .modal select')).filter((n) => !n.hasAttribute('disabled'))
      if (!nodes.length) return
      const first = nodes[0], last = nodes[nodes.length - 1]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    window.addEventListener('keydown', onKey)
    return () => { window.removeEventListener('keydown', onKey); prev?.focus() }
  }, [open])
  if (!open) return null

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const u = await auth.login(username.trim(), password)
      store.toast({ kind: 'success', title: 'Signed in', message: `Welcome, ${u.username} (${u.role.replace(/_/g, ' ')}).` }, 3500)
      setPassword('')
      loginDialog.close()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not sign in. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && loginDialog.close()}>
      <form className="modal stack" onSubmit={submit} role="dialog" aria-modal="true" aria-labelledby="login-title">
        <div>
          <h2 id="login-title">Sign in to make changes</h2>
          <p className="muted">Viewing is open to everyone. Acknowledging alarms, logging maintenance and running scenarios needs a login.</p>
        </div>
        <div className="field">
          <label htmlFor="u">Username</label>
          <input id="u" className="input" autoFocus autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="p">Password</label>
          <input id="p" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {error && <div className="err" role="alert">{error}</div>}
        {demo.length > 0 && (
          <div>
            <div className="lbl" style={{ marginBottom: 6 }}>Demo accounts</div>
            <div className="demo-logins">
              {demo.map((d) => (
                <button type="button" key={d.username} className="pill" onClick={() => { setUsername(d.username); setPassword(d.password) }}>
                  {d.username}<span className="n">{d.role.replace(/_/g, ' ')}</span>
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="btn ghost" onClick={() => loginDialog.close()}>Cancel</button>
          <button type="submit" className="btn primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        </div>
      </form>
    </div>
  )
}
