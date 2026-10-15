import { memo, useState } from 'react'
import { api, ApiError } from '../lib/api'
import { dateTime, fmtDuration, timeAgo } from '../lib/format'
import { LEVELS } from '../lib/levels'
import { go } from '../lib/router'
import { store, useStore, EMPTY } from '../lib/store'
import type { Alert } from '../lib/types'
import { Icon, LEVEL_ICON } from './ui'

function useAct() {
  const [busy, setBusy] = useState(false)
  async function run<T>(fn: () => Promise<T>, ok?: string): Promise<T | undefined> {
    setBusy(true)
    try {
      const r = await fn()
      if (ok) store.toast({ kind: 'success', title: ok, message: '' }, 2500)
      return r
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) {
        store.toast({ kind: 'error', title: 'That did not work', message: e instanceof Error ? e.message : 'Unknown error' }, 7000)
      }
    } finally {
      setBusy(false)
    }
  }
  return { busy, run }
}

function AlertCardImpl({ a, technicians, now }: { a: Alert; technicians: string[]; now: number }) {
  const { busy, run } = useAct()
  const [resolving, setResolving] = useState(false)
  const [notes, setNotes] = useState('')
  const live = a.active
  const upd = (next: Alert) => store.upsertAlert(next)

  const ack = () => run(async () => upd(await api.post<Alert>(`/alerts/${a.id}/ack`)), 'Alarm acknowledged')
  const assign = (tech: string) => tech && run(async () => upd(await api.post<Alert>(`/alerts/${a.id}/assign`, { technician: tech })), `Assigned to ${tech}`)
  const resolve = () =>
    run(async () => { upd(await api.post<Alert>(`/alerts/${a.id}/resolve`, { notes })); setResolving(false); setNotes('') }, 'Issue closed')
  const feedback = (verdict: 'true_positive' | 'false_positive') =>
    run(async () => upd(await api.post<Alert>(`/alerts/${a.id}/feedback`, { verdict, comment: '' })), 'Thanks - feedback recorded')

  const statusText = a.status === 'cleared' ? 'Auto-cleared' : a.status === 'acknowledged' ? `Acknowledged by ${a.acked_by}` : a.status === 'resolved' ? `Resolved by ${a.resolved_by ?? '—'}` : 'Open'

  return (
    <article className={`alert-item lv-${a.level} ${live ? '' : 'cleared'}`} aria-label={`${LEVELS[a.level].label} alert on ${a.machine_id}`}>
      <div className="alert-ico"><Icon name={LEVEL_ICON[a.level]} /></div>
      <div style={{ minWidth: 0 }}>
        <h4>
          {a.title}
          <a className="chip" href={`#/machines/${a.machine_id}`} style={{ textDecoration: 'none' }}>{a.machine_id}</a>
          <span className="chip" style={{ color: 'var(--lv-ink)' }}>{LEVELS[a.level].short}</span>
          {live && <span className="chip run"><i className="dot" />Active</span>}
        </h4>
        <p>{a.message}{a.eta_s !== null && a.level === 'orange' ? ` · ETA ${Math.round(a.eta_s)} s` : ''}{a.score !== null && a.level === 'yellow' ? ` · peak score ${a.score.toFixed(0)} %` : ''}</p>
        <div className="alert-meta">
          <span title={dateTime(a.opened_at)}>{timeAgo(a.opened_at, now)}</span>
          <span>·</span><span>{live ? `lasting ${fmtDuration(a.duration_s)}` : `lasted ${fmtDuration(a.duration_s)}`}</span>
          <span>·</span><span>{statusText}</span>
          {a.technician && <><span>·</span><span>Tech: {a.technician}</span></>}
          {a.feedback && <><span>·</span><span className={a.feedback.verdict === 'true_positive' ? 'tag-ok' : 'tag-bad'}>{a.feedback.verdict === 'true_positive' ? 'Marked true positive' : 'Marked false positive'}</span></>}
        </div>
        {a.resolution_notes && <p style={{ marginTop: 6 }}><b style={{ color: 'var(--text)' }}>Resolution:</b> {a.resolution_notes}</p>}
        <div className="alert-actions">
          {a.status === 'open' && <button className="btn sm primary" disabled={busy} onClick={ack}><Icon name="check" />Acknowledge</button>}
          {a.status !== 'resolved' && (
            <select className="input" style={{ width: 'auto', minHeight: 32, padding: '4px 8px', fontSize: 12 }} aria-label="Assign technician" value={a.technician ?? ''} disabled={busy} onChange={(e) => assign(e.target.value)}>
              <option value="">Assign technician…</option>
              {technicians.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          )}
          {a.status !== 'resolved' && <button className="btn sm" disabled={busy} onClick={() => setResolving((v) => !v)}>Resolve…</button>}
          <button className="btn sm ghost" onClick={() => go(`/maintenance?alert=${a.id}&machine=${a.machine_id}`)}><Icon name="wrench" />Log maintenance</button>
          <span style={{ marginLeft: 'auto' }} className="row">
            <span className="faint" style={{ fontSize: 12 }}>{a.level === 'yellow' ? 'Was this caution correct?' : 'Feedback'}</span>
            <button className="btn sm ok" disabled={busy} aria-pressed={a.feedback?.verdict === 'true_positive'} onClick={() => feedback('true_positive')} title="True positive: real issue"><Icon name="thumbup" /></button>
            <button className="btn sm danger" disabled={busy} aria-pressed={a.feedback?.verdict === 'false_positive'} onClick={() => feedback('false_positive')} title="False positive: nothing wrong"><Icon name="thumbdown" /></button>
          </span>
        </div>
        {resolving && (
          <form className="inline-form" onSubmit={(e) => { e.preventDefault(); resolve() }}>
            <div className="field">
              <label htmlFor={`n${a.id}`}>Root cause / resolution notes</label>
              <textarea id={`n${a.id}`} className="input" autoFocus value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. Coolant pump strainer cleared, temperature back to normal" />
            </div>
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button type="button" className="btn sm ghost" onClick={() => setResolving(false)}>Cancel</button>
              <button type="submit" className="btn sm primary" disabled={busy}>Close issue</button>
            </div>
          </form>
        )}
      </div>
      <div />
    </article>
  )
}

export const AlertCard = memo(AlertCardImpl)

export function useTechnicians(): string[] {
  return useStore((s) => s.config?.technicians ?? EMPTY)
}
