import { useEffect, useState, type FormEvent } from 'react'
import { TopBar } from '../components/Layout'
import { CardHeader, Empty, Icon, Skeleton } from '../components/ui'
import { api, ApiError } from '../lib/api'
import { dateTime, timeAgo } from '../lib/format'
import { hashParams } from '../lib/router'
import { store, useStore, EMPTY } from '../lib/store'
import { useNow } from '../hooks/hooks'
import type { Maintenance as Rec } from '../lib/types'

const STATUS_LABEL = { open: 'Open', in_progress: 'In progress', closed: 'Closed' } as const

export default function Maintenance() {
  const machines = useStore((s) => s.config?.machines ?? EMPTY)
  const technicians = useStore((s) => s.config?.technicians ?? EMPTY)
  const alerts = useStore((s) => s.alerts)
  const records = useStore((s) => s.maintenance)
  const now = useNow(1000)
  const params = hashParams()
  const [machine, setMachine] = useState(params.get('machine') ?? '')
  const [alertId, setAlertId] = useState(params.get('alert') ?? '')
  const [action, setAction] = useState('')
  const [notes, setNotes] = useState('')
  const [tech, setTech] = useState('')
  const [status, setStatus] = useState<Rec['status']>('open')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { if (!machine && machines.length) setMachine(machines[0].id) }, [machines, machine])
  useEffect(() => { store.refreshMaintenance() }, [])

  const linkable = alerts.filter((a) => a.machine_id === machine).slice(0, 30)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const rec = await api.post<Rec>('/maintenance', {
        machine_id: machine, alert_id: alertId ? Number(alertId) : null, action, notes, technician: tech, status,
      })
      store.upsertMaintenance(rec)
      store.toast({ kind: 'success', title: 'Maintenance logged', message: `${rec.machine_id}: ${rec.action}` }, 3500)
      setAction(''); setNotes(''); setAlertId('')
      history.replaceState(null, '', '#/maintenance')
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) setError(err instanceof Error ? err.message : 'Could not save the record.')
    } finally { setBusy(false) }
  }

  async function patch(r: Rec, status: Rec['status']) {
    try { store.upsertMaintenance(await api.patch<Rec>(`/maintenance/${r.id}`, { status })) }
    catch (err) { if (!(err instanceof ApiError && err.status === 401)) store.toast({ kind: 'error', title: 'Could not update', message: err instanceof Error ? err.message : '' }) }
  }
  async function remove(r: Rec) {
    if (!window.confirm(`Delete maintenance record #${r.id}? This cannot be undone.`)) return
    try { await api.del(`/maintenance/${r.id}`); store.removeMaintenance(r.id) }
    catch (err) { if (!(err instanceof ApiError && err.status === 401)) store.toast({ kind: 'error', title: 'Could not delete', message: err instanceof Error ? err.message : '' }) }
  }

  return (
    <div className="page">
      <TopBar title="Maintenance" sub="Log interventions, link them to alerts and keep an audit trail" />
      <div className="grid g-detail" style={{ alignItems: 'start' }}>
        <section className="card" aria-label="Maintenance timeline">
          <CardHeader title={`Timeline · ${records.length} record${records.length === 1 ? '' : 's'}`} icon="wrench" />
          {records.length === 0 ? (
            <Empty icon="wrench" title="No maintenance logged yet">Use the form to record an action — optionally linked to an alert.</Empty>
          ) : (
            <div className="timeline">
              {records.map((r) => {
                const a = r.alert_id ? alerts.find((x) => x.id === r.alert_id) : undefined
                return (
                  <article key={r.id} className={`tl-item ${r.status}`}>
                    <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <b style={{ fontSize: 14.5 }}>{r.action}</b>
                        <div className="alert-meta" style={{ marginTop: 4 }}>
                          <a className="chip" href={`#/machines/${r.machine_id}`} style={{ textDecoration: 'none' }}>{r.machine_id}</a>
                          <span className="chip">{STATUS_LABEL[r.status]}</span>
                          {a && <span className={`badge lv-${a.level}`}><Icon name="link" />Alert #{a.id}</span>}
                          {r.alert_id && !a && <span className="chip"><Icon name="link" size={12} />Alert #{r.alert_id}</span>}
                          {r.technician && <span>Tech: {r.technician}</span>}
                        </div>
                      </div>
                      <span className="faint" style={{ fontSize: 12 }} title={dateTime(r.created_at)}>{timeAgo(r.created_at, now)}</span>
                    </div>
                    {r.notes && <p className="muted" style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{r.notes}</p>}
                    <div className="alert-actions">
                      <span className="faint" style={{ fontSize: 12 }}>by {r.created_by}</span>
                      <span style={{ marginLeft: 'auto' }} className="row">
                        {r.status !== 'in_progress' && r.status !== 'closed' && <button className="btn sm" onClick={() => patch(r, 'in_progress')}>Start work</button>}
                        {r.status !== 'closed' && <button className="btn sm ok" onClick={() => patch(r, 'closed')}><Icon name="check" />Close</button>}
                        <button className="btn sm ghost" aria-label={`Delete record ${r.id}`} onClick={() => remove(r)}><Icon name="trash" /></button>
                      </span>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </section>

        <form className="card" onSubmit={submit} aria-label="Log maintenance action">
          <CardHeader title="Log an action" icon="plus" />
          {machines.length === 0 ? <Skeleton h={220} /> : (
            <div className="form-grid">
              <div className="field">
                <label htmlFor="m-machine">Machine</label>
                <select id="m-machine" className="input" value={machine} onChange={(e) => { setMachine(e.target.value); setAlertId('') }} required>
                  {machines.map((m) => <option key={m.id} value={m.id}>{m.id} — {m.name}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor="m-alert">Linked alert (optional)</label>
                <select id="m-alert" className="input" value={alertId} onChange={(e) => setAlertId(e.target.value)}>
                  <option value="">— none —</option>
                  {linkable.map((a) => <option key={a.id} value={a.id}>#{a.id} {a.level.toUpperCase()} · {a.title}{a.active ? ' (active)' : ''}</option>)}
                </select>
              </div>
              <div className="field full">
                <label htmlFor="m-action">What was done?</label>
                <input id="m-action" className="input" value={action} onChange={(e) => setAction(e.target.value)} placeholder="e.g. Replaced coolant filter" required minLength={2} maxLength={200} />
              </div>
              <div className="field">
                <label htmlFor="m-tech">Technician</label>
                <select id="m-tech" className="input" value={tech} onChange={(e) => setTech(e.target.value)}>
                  <option value="">— unassigned —</option>
                  {technicians.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor="m-status">Status</label>
                <select id="m-status" className="input" value={status} onChange={(e) => setStatus(e.target.value as Rec['status'])}>
                  <option value="open">Open</option><option value="in_progress">In progress</option><option value="closed">Closed</option>
                </select>
              </div>
              <div className="field full">
                <label htmlFor="m-notes">Root cause / notes</label>
                <textarea id="m-notes" className="input" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Findings, parts used, follow-ups…" maxLength={2000} />
              </div>
              {error && <div className="err full" role="alert">{error}</div>}
              <div className="full row" style={{ justifyContent: 'flex-end' }}>
                <button className="btn primary" type="submit" disabled={busy || !machine}><Icon name="plus" />{busy ? 'Saving…' : 'Save record'}</button>
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
