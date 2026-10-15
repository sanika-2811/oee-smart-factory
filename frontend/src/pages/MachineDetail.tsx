import { useEffect, useMemo, useState } from 'react'
import { Line } from 'react-chartjs-2'
import type { ChartData } from 'chart.js'
import { AlertCard, useTechnicians } from '../components/AlertCard'
import { TopBar } from '../components/Layout'
import { AnimatedNumber, CardHeader, Empty, Icon, LEVEL_ICON, LevelBadge, RingGauge, Segmented, Skeleton, StatusChip } from '../components/ui'
import { palette, timeOptions } from '../lib/chartSetup'
import { api, ApiError } from '../lib/api'
import { fmtInt, scoreBand } from '../lib/format'
import { LEVELS } from '../lib/levels'
import { store, useStore } from '../lib/store'
import { useMachineSeries, useNow, usePoll } from '../hooks/hooks'
import type { WhatIfDetail, WindowKey } from '../lib/types'
import { OeeHero } from './Overview'

const WINDOWS = [
  { value: '120', label: '2 min' },
  { value: '300', label: '5 min' },
  { value: '900', label: '15 min' },
]

export default function MachineDetail({ id }: { id: string }) {
  const m = useStore((s) => s.snapshot?.machines.find((x) => x.id === id))
  const snapTs = useStore((s) => s.snapshot?.ts)
  const win = useStore((s) => s.window)
  const config = useStore((s) => s.config)
  const alerts = useStore((s) => s.alerts)
  const technicians = useTechnicians()
  const [range, setRange] = useState('300')
  const windowSec = Number(range)
  const { pts, loading, error } = useMachineSeries(id, windowSec)
  const now = useNow(1000)
  const threshold = config?.anomaly_threshold ?? 85

  if (!m) {
    return (
      <div className="page">
        <TopBar title={id} sub={<a href="#/machines">← All machines</a>} />
        {store.get().snapshot ? <div className="card"><Empty icon="machines" title="Machine not found">There is no machine called “{id}”. <a href="#/machines">Back to the list</a>.</Empty></div>
          : <div className="card"><Skeleton h={300} /></div>}
      </div>
    )
  }

  const c = palette()
  const xMax = pts.length ? pts[pts.length - 1].ts : (snapTs ?? now)
  const xMin = xMax - windowSec
  const lvl = m.online ? m.level : 'green'
  const tl = m.thresholds.temp_limit
  const vl = m.thresholds.vib_limit

  const tempData: ChartData<'line'> = {
    datasets: [
      { label: 'Temperature (°C)', data: pts.map((p) => ({ x: p.ts, y: p.temperature as number })), borderColor: c.accent, backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0.25, yAxisID: 'y' },
      { label: 'Vibration (mm/s)', data: pts.map((p) => ({ x: p.ts, y: p.vibration as number })), borderColor: c.accent2, backgroundColor: 'transparent', borderWidth: 1.6, pointRadius: 0, tension: 0.25, yAxisID: 'y2' },
      { label: `Temp limit ${tl} °C`, data: [{ x: xMin, y: tl }, { x: xMax, y: tl }], borderColor: c.red, borderDash: [6, 5], borderWidth: 1.4, pointRadius: 0, yAxisID: 'y' },
      { label: `Vibration limit ${vl} mm/s`, data: [{ x: xMin, y: vl }, { x: xMax, y: vl }], borderColor: c.orange, borderDash: [2, 4], borderWidth: 1.2, pointRadius: 0, yAxisID: 'y2' },
    ],
  }
  const tempOpts = timeOptions({
    xMin, xMax, legend: true,
    y: { suggestedMin: Math.floor((m.temperature ?? 40) - 12), suggestedMax: tl + 6, title: { display: true, text: '°C', color: c.text } },
    y2: { suggestedMin: 0, suggestedMax: vl * 1.15, title: { display: true, text: 'mm/s', color: c.text } },
  })

  const scoreData: ChartData<'line'> = {
    datasets: [
      { label: 'Anomaly score (%)', data: pts.map((p) => ({ x: p.ts, y: p.anomaly_score as number })), borderColor: c.yellow, backgroundColor: 'rgba(250, 204, 21, .12)', fill: true, borderWidth: 2, pointRadius: 0, tension: 0.2, spanGaps: false },
      { label: `Caution threshold ${threshold}%`, data: [{ x: xMin, y: threshold }, { x: xMax, y: threshold }], borderColor: c.red, borderDash: [6, 5], borderWidth: 1.3, pointRadius: 0 },
    ],
  }
  const scoreOpts = timeOptions({ xMin, xMax, legend: true, y: { min: 0, max: 100, ticks: { callback: (v: number | string) => `${v}%`, color: c.text } as never } })
  const band = scoreBand(m.anomaly_score, threshold)

  const mine = alerts.filter((a) => a.machine_id === id).slice(0, 8)

  return (
    <div className="page">
      <TopBar
        title={m.name}
        sub={<><a href="#/machines">← All machines</a> · <span className="mono">{m.id}</span> · {m.kind}</>}
      >
        <Segmented label="Chart range" value={range} onChange={setRange} options={WINDOWS} />
      </TopBar>

      <section className={`card lv-${lvl}`} style={{ borderLeft: '4px solid var(--lv)' }} aria-label="Current state">
        <div className="row" style={{ gap: 18, justifyContent: 'space-between' }}>
          <div className="row" style={{ gap: 12 }}>
            <LevelBadge level={lvl} large />
            <StatusChip status={m.status} online={m.online} />
            <span className="muted">{m.reason ?? LEVELS[lvl].description}</span>
          </div>
          <div className="row" style={{ gap: 28 }}>
            <div className="metric"><div className="k">Temperature</div><div className="v" style={{ fontSize: 30 }}><AnimatedNumber value={m.temperature} digits={1} /><small>°C</small></div></div>
            <div className="metric"><div className="k">Vibration</div><div className="v" style={{ fontSize: 30 }}><AnimatedNumber value={m.vibration} digits={2} /><small>mm/s</small></div></div>
            <div className="metric"><div className="k">Cycle count</div><div className="v" style={{ fontSize: 30 }}>{fmtInt(m.cycle_count)}</div></div>
            <div className="metric"><div className="k">Good / total</div><div className="v" style={{ fontSize: 30 }}>{m.cycle_count ? ((m.good_count ?? 0) / m.cycle_count * 100).toFixed(1) : '—'}<small>%</small></div></div>
          </div>
        </div>
      </section>

      <div className="grid g-detail">
        <section className="card" aria-label="Telemetry chart">
          <CardHeader title="Live temperature & vibration" icon="thermo" />
          <div className="chart lg">
            {loading && !pts.length ? <Skeleton h={320} /> : error ? <div className="err">{error}</div> : <Line data={tempData} options={tempOpts} aria-label="Temperature and vibration over time" role="img" />}
          </div>
        </section>
        <section className="card" aria-label="ML anomaly score">
          <CardHeader title="Anomaly score (Isolation Forest)" icon="cpu" />
          <div className="row" style={{ gap: 18, alignItems: 'center', marginBottom: 6 }}>
            <div style={{ width: 120 }}>
              <RingGauge value={m.anomaly_score} size={120} stroke={11} color={band === 'caution' ? 'var(--yellow)' : band === 'watch' ? 'var(--accent)' : 'var(--green)'} label={`Anomaly score ${m.anomaly_score.toFixed(0)} percent`}>
                <div className="big" style={{ fontSize: 28 }}><AnimatedNumber value={m.anomaly_score} digits={0} /><span style={{ fontSize: 13, color: 'var(--muted)' }}>%</span></div>
              </RingGauge>
            </div>
            <div className="muted" style={{ fontSize: 12.5, flex: 1, minWidth: 140 }}>
              {band === 'caution' ? <b style={{ color: 'var(--yellow-ink)' }}>Above the {threshold}% caution threshold</b> : band === 'watch' ? 'Elevated but below the caution threshold' : 'Behaving like the healthy training data'}
              {!m.ml_ok && <div style={{ color: 'var(--orange-ink)', marginTop: 4 }}>ML service unavailable - showing the last known score. Rule-based alerts still work.</div>}
            </div>
          </div>
          <div className="chart sm"><Line data={scoreData} options={scoreOpts} aria-label="Anomaly score over time" role="img" /></div>
        </section>
      </div>

      <WhatIfPanel id={id} />

      <div className="grid g-2">
        <section className="card" aria-label="Machine OEE">
          <CardHeader title={`OEE · ${win}`} icon="gauge">
            <Segmented<WindowKey> label="OEE window" value={win} onChange={store.setWindow} options={[{ value: '1h', label: '1 h' }, { value: '8h', label: '8 h' }]} />
          </CardHeader>
          <OeeHero oee={m.oee[win]} window={win} />
        </section>
        <div className="stack" style={{ gap: 'var(--gap)' }}>
          <LimitsCard id={id} tl={tl} vl={vl} />
          <FaultCard id={id} />
        </div>
      </div>

      <section aria-label="Alerts for this machine">
        <div className="card-h"><h2 style={{ fontSize: 13, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--muted)' }}>Alerts on {m.id}</h2></div>
        {mine.length === 0 ? <div className="card"><Empty icon="check" title="No alerts for this machine yet" /></div>
          : <div className="stack">{mine.map((a) => <AlertCard key={a.id} a={a} technicians={technicians} now={now} />)}</div>}
      </section>
    </div>
  )
}

/* ------------------------------------------------------------------ What-If panel */
function WhatIfPanel({ id }: { id: string }) {
  const m = useStore((s) => s.snapshot?.machines.find((x) => x.id === id))
  const { data, error } = usePoll<WhatIfDetail>(() => api.get(`/whatif/${encodeURIComponent(id)}`), 1000, [id])
  const [busy, setBusy] = useState(false)
  const c = palette()
  const horizon = data?.horizon_s ?? 60
  const p = data?.projection
  const limit = m?.thresholds.temp_limit ?? data?.threshold ?? 85

  const chart = useMemo(() => {
    if (!data || !data.points.length) return null
    const nowTs = data.points[data.points.length - 1].ts
    const x0 = data.points[0].ts
    const x1 = nowTs + horizon
    const ys = data.points.map((q) => q.temperature)
    const yMin = Math.min(...ys, ...(data.line.map((l) => l.y))) - 2
    const yMax = Math.max(limit + 4, ...ys)
    const d: ChartData<'line'> = {
      datasets: [
        { label: 'Temperature (last 3 min)', data: data.points.map((q) => ({ x: q.ts, y: q.temperature })), borderColor: c.accent, backgroundColor: c.accent, borderWidth: 1.6, pointRadius: 1.6, showLine: true, tension: 0.2 },
        { label: 'Regression  y = m·x + c', data: data.line.map((l) => ({ x: l.ts, y: l.y })), borderColor: c.orange, borderWidth: 2.4, borderDash: [8, 5], pointRadius: 0 },
        { label: `Hard limit ${limit} °C`, data: [{ x: x0, y: limit }, { x: x1, y: limit }], borderColor: c.red, borderWidth: 1.5, borderDash: [5, 5], pointRadius: 0 },
        { label: 'Now', data: [{ x: nowTs, y: yMin }, { x: nowTs, y: yMax }], borderColor: c.text, borderWidth: 1, pointRadius: 0 },
      ],
    }
    return { d, opts: timeOptions({ xMin: x0, xMax: x1, legend: true, y: { suggestedMin: yMin, suggestedMax: yMax } }) }
  }, [data, horizon, limit, c.accent, c.orange, c.red, c.text])

  async function run() {
    setBusy(true)
    try {
      await api.post(`/whatif/${encodeURIComponent(id)}/run`)
      store.toast({ kind: 'info', title: 'What-If scenario started', message: `Controlled temperature rise on ${id} over ~3 minutes. Watch for the Orange warning.` }, 6000)
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) store.toast({ kind: 'error', title: 'Could not start the scenario', message: e instanceof Error ? e.message : '' })
    } finally { setBusy(false) }
  }
  async function clear() {
    try { await api.post('/simulator/clear', { machine_id: id }); store.toast({ kind: 'success', title: 'Scenario cleared', message: '' }, 2500) }
    catch (e) { if (!(e instanceof ApiError && e.status === 401)) store.toast({ kind: 'error', title: 'Could not clear', message: e instanceof Error ? e.message : '' }) }
  }

  let callout: { level: 'green' | 'orange' | 'red' | 'yellow'; title: string; body: string } | null = null
  if (m && m.temperature !== null && m.temperature > limit) callout = { level: 'red', title: `Already above ${limit} °C`, body: 'The hard limit is breached — the rule engine has raised a Red alert.' }
  else if (p?.projected) callout = { level: 'orange', title: `Projected to hit ${limit} °C in ${Math.round(p.eta_s ?? 0)} s`, body: `Temperature is rising ${p.slope_c_per_min >= 0 ? '+' : ''}${p.slope_c_per_min.toFixed(1)} °C/min (R² ${p.r2.toFixed(2)}). Orange appears when the crossing is ≤ ${horizon} s away.` }
  else if (p?.ready) callout = { level: 'green', title: 'No threshold crossing predicted', body: `Trend ${p.slope_c_per_min >= 0 ? '+' : ''}${p.slope_c_per_min.toFixed(2)} °C/min${p.eta_s ? ` — would reach ${limit} °C in ${Math.round(p.eta_s)} s, beyond the ${horizon} s horizon` : ''}.` }
  else callout = { level: 'yellow', title: 'Collecting data…', body: `Need ${data ? Math.max(0, 30 - (p?.n ?? 0)) : 30} more seconds of running telemetry before a trend line can be fitted.` }

  return (
    <section className="card" aria-label="What-If degradation projection">
      <CardHeader title="What-If degradation simulator" icon="trend">
        <button className="btn sm warn" disabled={busy} onClick={run}><Icon name="play" />Start 3-min degradation</button>
        <button className="btn sm ghost" onClick={clear}>Clear</button>
      </CardHeader>
      <div className="grid g-detail" style={{ alignItems: 'start' }}>
        <div className="chart lg">
          {error && !data ? <div className="err">{error}</div> : chart ? <Line data={chart.d} options={chart.opts} role="img" aria-label="Temperature, fitted regression line and hard limit" /> : <Skeleton h={320} />}
        </div>
        <div className="stack">
          {callout && (
            <div className={`whatif-callout lv-${callout.level}`} role="status">
              <Icon name={LEVEL_ICON[callout.level]} />
              <div><b>{callout.title}</b><span style={{ fontSize: 12.5 }}>{callout.body}</span></div>
            </div>
          )}
          <dl className="kv card" style={{ margin: 0, background: 'var(--surface-2)' }}>
            <dt>Equation</dt><dd>y = {p?.ready ? `${p.slope_c_per_s.toFixed(4)}·x + ${p.intercept.toFixed(2)}` : 'm·x + c'}</dd>
            <dt>Slope m</dt><dd>{p?.ready ? `${p.slope_c_per_min >= 0 ? '+' : ''}${p.slope_c_per_min.toFixed(2)} °C/min` : '—'}</dd>
            <dt>Fit quality R²</dt><dd>{p?.ready ? p.r2.toFixed(3) : '—'}</dd>
            <dt>Window</dt><dd>{data ? `${data.window_s} s · ${p?.n ?? 0} pts` : '—'}</dd>
            <dt>Time to {limit} °C</dt><dd>{p?.eta_s != null ? `${Math.round(p.eta_s)} s` : '—'}</dd>
          </dl>
          <p className="faint" style={{ fontSize: 12 }}>
            A least-squares line is fitted through the last 3 minutes of temperature. When it will cross the hard threshold within {horizon} s, the machine turns <b style={{ color: 'var(--orange-ink)' }}>Orange</b> with a countdown.
          </p>
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ small cards */
function LimitsCard({ id, tl, vl }: { id: string; tl: number; vl: number }) {
  const [t, setT] = useState(String(tl))
  const [v, setV] = useState(String(vl))
  const [busy, setBusy] = useState(false)
  useEffect(() => { setT(String(tl)); setV(String(vl)) }, [tl, vl])
  async function save() {
    setBusy(true)
    try {
      await api.put(`/machines/${encodeURIComponent(id)}/thresholds?temp_limit=${encodeURIComponent(t)}&vib_limit=${encodeURIComponent(v)}`)
      store.toast({ kind: 'success', title: 'Limits saved', message: `${id}: ${t} °C, ${v} mm/s` }, 3000)
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) store.toast({ kind: 'error', title: 'Could not save limits', message: e instanceof Error ? e.message : '' })
    } finally { setBusy(false) }
  }
  return (
    <section className="card">
      <CardHeader title="Hard limits (Red rules)" icon="shield" />
      <div className="form-grid">
        <div className="field"><label htmlFor="tl">Temperature °C</label><input id="tl" className="input mono" inputMode="decimal" value={t} onChange={(e) => setT(e.target.value)} /></div>
        <div className="field"><label htmlFor="vl">Vibration mm/s</label><input id="vl" className="input mono" inputMode="decimal" value={v} onChange={(e) => setV(e.target.value)} /></div>
        <div className="full row" style={{ justifyContent: 'space-between' }}>
          <span className="faint" style={{ fontSize: 12 }}>Red if temperature or vibration exceeds its limit, or the machine stops.</span>
          <button className="btn sm primary" disabled={busy} onClick={save}>Save limits</button>
        </div>
      </div>
    </section>
  )
}

export function FaultButtons({ id, compact }: { id: string; compact?: boolean }) {
  const [busy, setBusy] = useState('')
  async function inject(kind: string, label: string) {
    setBusy(kind)
    try {
      await api.post('/simulator/inject-fault', { machine_id: id, kind })
      store.toast({ kind: 'info', title: `${label} injected`, message: `${id} — watch the alert colours change.` }, 4500)
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) store.toast({ kind: 'error', title: 'Injection failed', message: e instanceof Error ? e.message : '' })
    } finally { setBusy('') }
  }
  async function clear() {
    try { await api.post('/simulator/clear', { machine_id: id }); store.toast({ kind: 'success', title: `Faults cleared on ${id}`, message: '' }, 2500) }
    catch (e) { if (!(e instanceof ApiError && e.status === 401)) store.toast({ kind: 'error', title: 'Could not clear', message: e instanceof Error ? e.message : '' }) }
  }
  return (
    <div className="row" style={{ gap: 8 }}>
      <button className="btn sm warn" disabled={!!busy} onClick={() => inject('temp_ramp', 'Temperature ramp')} title="Temperature rises over 3 minutes: Orange, then Red"><Icon name="thermo" />{compact ? 'Ramp' : 'Temperature ramp'}</button>
      <button className="btn sm danger" disabled={!!busy} onClick={() => inject('vib_spike', 'Vibration spike')} title="Vibration jumps above the limit: Red"><Icon name="vibe" />{compact ? 'Spike' : 'Vibration spike'}</button>
      <button className="btn sm danger" disabled={!!busy} onClick={() => inject('stop', 'Machine stop')} title="Machine stops: Red"><Icon name="stop" />{compact ? 'Stop' : 'Machine stop'}</button>
      <button className="btn sm amber" disabled={!!busy} onClick={() => inject('anomaly', 'ML anomaly')} title="Subtle bearing-wear signature, below hard limits: Yellow"><Icon name="cpu" />{compact ? 'Anomaly' : 'ML anomaly'}</button>
      <button className="btn sm ghost" onClick={clear}>Clear</button>
    </div>
  )
}

function FaultCard({ id }: { id: string }) {
  return (
    <section className="card">
      <CardHeader title="Demo: inject a fault" icon="zap" />
      <FaultButtons id={id} />
      <p className="faint" style={{ fontSize: 12, marginTop: 10 }}>Requires sign-in. Orange → Red takes about 3 minutes for the ramp; use the Control page to compress time.</p>
    </section>
  )
}

