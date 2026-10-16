import { useMemo, useState } from 'react'
import { AlertCard, useTechnicians } from '../components/AlertCard'
import { TopBar } from '../components/Layout'
import { Empty, Skeleton } from '../components/ui'
import { LEVELS } from '../lib/levels'
import { useStore, EMPTY } from '../lib/store'
import { downloadCsv } from '../lib/csv'
import { dateTime } from '../lib/format'
import { Icon } from '../components/ui'
import { useNow } from '../hooks/hooks'
import type { AlertLevel } from '../lib/types'

type StatusFilter = 'all' | 'active' | 'open' | 'acknowledged' | 'history'

export default function Alerts() {
  const alerts = useStore((s) => s.alerts)
  const loaded = useStore((s) => s.alertsLoaded)
  const machines = useStore((s) => s.config?.machines ?? EMPTY)
  const technicians = useTechnicians()
  const now = useNow(1000)
  const [level, setLevel] = useState<AlertLevel | 'all'>('all')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [machine, setMachine] = useState('all')
  const [limit, setLimit] = useState(25)

  const counts = useMemo(() => {
    const c = { red: 0, orange: 0, yellow: 0 }
    alerts.forEach((a) => { if (a.active) c[a.level]++ })
    return c
  }, [alerts])

  const filtered = useMemo(() => alerts.filter((a) => {
    if (level !== 'all' && a.level !== level) return false
    if (machine !== 'all' && a.machine_id !== machine) return false
    if (status === 'active') return a.active
    if (status === 'open') return a.status === 'open'
    if (status === 'acknowledged') return a.status === 'acknowledged'
    if (status === 'history') return !a.active
    return true
  }), [alerts, level, machine, status])

  const levels: (AlertLevel | 'all')[] = ['all', 'red', 'orange', 'yellow']

  return (
    <div className="page">
      <TopBar title="Alert centre" sub="Live feed · acknowledge, assign, resolve and give the ML model feedback" />
      <div className="card">
        <div className="filters" role="group" aria-label="Filter alerts">
          {levels.map((l) => (
            <button key={l} className={`pill ${l !== 'all' ? `lv-${l}` : ''}`} aria-pressed={level === l} onClick={() => setLevel(l)}>
              {l === 'all' ? 'All levels' : LEVELS[l].label}
              {l !== 'all' && <span className="n">{counts[l]} active</span>}
            </button>
          ))}
          <span style={{ flex: 1 }} />
          <button
            className="btn sm" disabled={filtered.length === 0} title="Download the filtered alerts as a CSV file"
            onClick={() => downloadCsv('alerts.csv', [
              ['id', 'level', 'machine', 'title', 'message', 'opened', 'status', 'active', 'acknowledged_by', 'technician', 'resolution_notes', 'feedback'],
              ...filtered.map((a) => [a.id, a.level, a.machine_id, a.title, a.message, dateTime(a.opened_at), a.status, a.active ? 'yes' : 'no', a.acked_by, a.technician, a.resolution_notes, a.feedback?.verdict]),
            ])}
          ><Icon name="inbox" />Export CSV</button>
          <label className="sr-only" htmlFor="st">Status</label>
          <select id="st" className="input" style={{ width: 'auto' }} value={status} onChange={(e) => setStatus(e.target.value as StatusFilter)}>
            <option value="all">Any status</option>
            <option value="active">Active now</option>
            <option value="open">Unacknowledged</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="history">History (cleared / resolved)</option>
          </select>
          <label className="sr-only" htmlFor="mc">Machine</label>
          <select id="mc" className="input" style={{ width: 'auto' }} value={machine} onChange={(e) => setMachine(e.target.value)}>
            <option value="all">All machines</option>
            {machines.map((m) => <option key={m.id} value={m.id}>{m.id}</option>)}
          </select>
        </div>
      </div>

      {!loaded ? (
        <div className="stack">{[0, 1, 2].map((i) => <div className="card" key={i}><Skeleton h={64} /></div>)}</div>
      ) : filtered.length === 0 ? (
        <div className="card"><Empty icon="check" title={alerts.length ? 'No alerts match these filters' : 'No alerts yet'}>
          {alerts.length ? 'Try clearing a filter.' : 'The factory is calm. Use the Control page to inject a fault and watch the feed react in real time.'}
        </Empty></div>
      ) : (
        <div className="stack" aria-live="polite">
          {filtered.slice(0, limit).map((a) => <AlertCard key={a.id} a={a} technicians={technicians} now={now} />)}
          {filtered.length > limit && <button className="btn" onClick={() => setLimit((n) => n + 25)}>Show {Math.min(25, filtered.length - limit)} more</button>}
        </div>
      )}
    </div>
  )
}
