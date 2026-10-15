/** Live data store: one WebSocket (auto-reconnect), a short rolling history per machine for sparklines,
 *  the alert list (REST load + live events) and a toast queue. Components read it via useSyncExternalStore. */
import { useSyncExternalStore } from 'react'
import { api, wsUrl } from './api'
import type { Alert, AppConfig, ConnState, Maintenance, Snapshot, WindowKey } from './types'

export interface HistPoint {
  t: number
  temp: number
  vib: number
  score: number
}

export interface Toast {
  id: number
  kind: 'alert' | 'info' | 'error' | 'success'
  level?: Alert['level']
  title: string
  message: string
}

interface State {
  conn: ConnState
  snapshot: Snapshot | null
  history: Record<string, HistPoint[]>
  alerts: Alert[]
  alertsLoaded: boolean
  maintenance: Maintenance[]
  config: AppConfig | null
  window: WindowKey
  toasts: Toast[]
  lastMessageAt: number
  clientLatencyMs: number | null
  theme: 'dark' | 'light'
}

/** Stable empty array for selector fallbacks (a fresh [] each call would loop useSyncExternalStore). */
export const EMPTY: never[] = []

const HISTORY_MAX = 240 // 2 minutes at 500 ms

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}
function write(key: string, v: string) {
  try {
    localStorage.setItem(key, v)
  } catch {
    /* ignore */
  }
}

let state: State = {
  conn: 'connecting',
  snapshot: null,
  history: {},
  alerts: [],
  alertsLoaded: false,
  maintenance: [],
  config: null,
  window: read('oee.window') === '8h' ? '8h' : '1h',
  toasts: [],
  lastMessageAt: 0,
  clientLatencyMs: null,
  theme: document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark',
}
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())
function set(patch: Partial<State>) {
  state = { ...state, ...patch }
  emit()
}

export const store = {
  get: () => state,
  subscribe(l: () => void) {
    listeners.add(l)
    return () => { listeners.delete(l) }
  },
  setWindow(w: WindowKey) {
    write('oee.window', w)
    set({ window: w })
  },
  setTheme(t: 'dark' | 'light') {
    document.documentElement.setAttribute('data-theme', t)
    write('oee.theme', t)
    set({ theme: t })
  },
  toast(t: Omit<Toast, 'id'>, ttl = 6500) {
    const id = Date.now() + Math.random()
    set({ toasts: [...state.toasts.slice(-3), { ...t, id }] })
    setTimeout(() => store.dismissToast(id), ttl)
  },
  dismissToast(id: number) {
    set({ toasts: state.toasts.filter((t) => t.id !== id) })
  },
  upsertAlert(a: Alert) {
    const i = state.alerts.findIndex((x) => x.id === a.id)
    const alerts = i >= 0 ? state.alerts.map((x) => (x.id === a.id ? a : x)) : [a, ...state.alerts]
    alerts.sort((x, y) => y.id - x.id)
    set({ alerts: alerts.slice(0, 500) })
  },
  upsertMaintenance(m: Maintenance) {
    const i = state.maintenance.findIndex((x) => x.id === m.id)
    const list = i >= 0 ? state.maintenance.map((x) => (x.id === m.id ? m : x)) : [m, ...state.maintenance]
    list.sort((x, y) => y.id - x.id)
    set({ maintenance: list })
  },
  removeMaintenance(id: number) {
    set({ maintenance: state.maintenance.filter((m) => m.id !== id) })
  },
  async refreshAlerts() {
    try {
      set({ alerts: await api.get<Alert[]>('/alerts?limit=400'), alertsLoaded: true })
    } catch {
      /* the next reconnect will retry */
    }
  },
  async refreshMaintenance() {
    try {
      set({ maintenance: await api.get<Maintenance[]>('/maintenance') })
    } catch {
      /* ignore */
    }
  },
}

export function useStore<T>(selector: (s: State) => T): T {
  return useSyncExternalStore(store.subscribe, () => selector(state))
}

/* ------------------------------------------------------------------ WebSocket with auto-reconnect */
let ws: WebSocket | null = null
let retry = 0
let started = false
let watchdog: number | undefined

function onSnapshot(s: Snapshot) {
  const history = { ...state.history }
  for (const m of s.machines) {
    if (m.temperature === null || m.temperature === undefined) continue
    const arr = history[m.id] ? history[m.id].slice(-(HISTORY_MAX - 1)) : []
    arr.push({ t: s.ts, temp: m.temperature, vib: m.vibration ?? 0, score: m.anomaly_score })
    history[m.id] = arr
  }
  set({
    snapshot: s,
    history,
    conn: 'live',
    lastMessageAt: Date.now(),
    clientLatencyMs: Math.max(0, Date.now() - s.ts * 1000),
  })
}

function connect() {
  set({ conn: retry === 0 && !state.snapshot ? 'connecting' : 'reconnecting' })
  try {
    ws = new WebSocket(wsUrl())
  } catch {
    scheduleRetry()
    return
  }
  ws.onopen = () => {
    retry = 0
    store.refreshAlerts()
    store.refreshMaintenance()
  }
  ws.onmessage = (ev) => {
    let msg: { type: string; [k: string]: unknown }
    try {
      msg = JSON.parse(ev.data)
    } catch {
      return
    }
    if (msg.type === 'snapshot') onSnapshot(msg as unknown as Snapshot)
    else if (msg.type === 'alert_event') {
      const a = msg.alert as Alert
      store.upsertAlert(a)
      if (msg.event === 'opened') {
        store.toast({ kind: 'alert', level: a.level, title: `${a.title} · ${a.machine_id}`, message: a.message })
      }
    } else if (msg.type === 'maintenance_event') {
      const rec = msg.record as Maintenance
      if (msg.event === 'deleted') store.removeMaintenance(rec.id)
      else store.upsertMaintenance(rec)
    }
  }
  ws.onclose = () => scheduleRetry()
  ws.onerror = () => ws?.close()
}

function scheduleRetry() {
  set({ conn: 'reconnecting' })
  retry += 1
  const delay = Math.min(5000, 800 * retry)
  window.setTimeout(connect, delay)
}

export function startLive() {
  if (started) return
  started = true
  api.get<AppConfig>('/config').then((config) => set({ config })).catch(() => undefined)
  connect()
  // watchdog: if frames stop (laptop sleep, proxy hiccup) force a reconnect
  watchdog = window.setInterval(() => {
    if (state.conn === 'live' && Date.now() - state.lastMessageAt > 4000) {
      set({ conn: 'reconnecting' })
      ws?.close()
    }
    if (!state.config) api.get<AppConfig>('/config').then((config) => set({ config })).catch(() => undefined)
  }, 2000)
}

export function stopLive() {
  started = false
  window.clearInterval(watchdog)
  ws?.close()
}
