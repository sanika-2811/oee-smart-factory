import { useState } from 'react'
import { FaultButtons } from './MachineDetail'
import { TopBar } from '../components/Layout'
import { CardHeader, Icon } from '../components/ui'
import { api, ApiError } from '../lib/api'
import { fmtDuration, fmtNum } from '../lib/format'
import { store, useStore, EMPTY } from '../lib/store'
import { usePoll } from '../hooks/hooks'
import type { Metrics } from '../lib/types'

function Target({ label, value, limit, unit, hint }: { label: string; value: number | null; limit: number; unit: string; hint: string }) {
  const ok = value !== null && value <= limit
  const pct = value === null ? 0 : Math.min(100, (value / limit) * 100)
  return (
    <div className="target" title={hint}>
      <span>{label}</span>
      <span className="mono"><b className={value === null ? '' : ok ? 'pass' : 'fail'}>{value === null ? '—' : `${fmtNum(value, 0)} ${unit}`}</b> <span className="faint">/ ≤ {limit} {unit}</span></span>
      <div className="bar"><i style={{ width: `${pct}%`, ['--c' as string]: ok ? 'var(--green)' : 'var(--red)' }} /></div>
    </div>
  )
}

export default function Control() {
  const machines = useStore((s) => s.config?.machines ?? EMPTY)
  const [machine, setMachine] = useState('')
  const [speed, setSpeed] = useState(1)
  const metrics = usePoll<Metrics>(() => api.get('/metrics'), 2000)
  const m = metrics.data
  const target = machine || machines[0]?.id || ''
  const clientLat = useStore((s) => s.clientLatencyMs)

  async function act(fn: () => Promise<unknown>, ok: string) {
    try { await fn(); store.toast({ kind: 'success', title: ok, message: '' }, 2800); metrics.reload() }
    catch (e) { if (!(e instanceof ApiError && e.status === 401)) store.toast({ kind: 'error', title: 'That did not work', message: e instanceof Error ? e.message : '' }) }
  }

  const steps = [
    ['Sign in', 'Use the Sign in button (top right). Demo accounts are listed in the dialog.'],
    ['Yellow', 'Click ML anomaly on a machine → a subtle bearing-wear signature that stays below every hard limit. Within ~3 s the machine turns Yellow.'],
    ['Orange → Red', 'Click Temperature ramp. The regression line steepens, Orange appears with an ETA countdown, then Red when the limit is crossed. Raise the speed to compress the 3 minutes.'],
    ['Red (instant)', 'Vibration spike or Machine stop trips the rule engine immediately.'],
    ['Respond', 'Open the Alert centre: acknowledge, assign a technician, resolve with notes, and mark the ML caution true/false positive. Log maintenance linked to the alert.'],
    ['Resilience', 'Toggle “ML outage” — the last score is held and Red rules keep working.'],
  ]

  return (
    <div className="page">
      <TopBar title="Demo & control" sub="Fault injection, simulator speed and live system health" />
      <div className="grid g-2">
        <section className="card" aria-label="Fault injection">
          <CardHeader title="Fault injection" icon="zap" />
          <div className="stack" style={{ gap: 14 }}>
            <div className="field" style={{ maxWidth: 320 }}>
              <label htmlFor="target">Target machine</label>
              <select id="target" className="input" value={target} onChange={(e) => setMachine(e.target.value)}>
                {machines.map((x) => <option key={x.id} value={x.id}>{x.id} — {x.name}</option>)}
              </select>
            </div>
            {target && <FaultButtons id={target} />}
            <div className="field" style={{ maxWidth: 420 }}>
              <label htmlFor="speed">Demo speed (compresses fault duration) · ×{speed}</label>
              <div className="row" style={{ flexWrap: 'nowrap' }}>
                <input id="speed" type="range" min={1} max={6} step={1} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} style={{ flex: 1, accentColor: 'var(--accent)' }} />
                <button className="btn sm" onClick={() => act(() => api.post('/simulator/speed', { factor: speed }), `Faults now play at ×${speed}`)}>Apply</button>
              </div>
              <span className="faint" style={{ fontSize: 12 }}>The 3-minute temperature ramp takes {fmtDuration(180 / speed)} at ×{speed}. Currently ×{m?.simulator.time_scale ?? 1}.</span>
            </div>
            <div className="row">
              <button className="btn sm ghost" onClick={() => act(() => api.post('/simulator/clear', {}), 'All faults cleared')}>Clear faults on all machines</button>
              <button className={`btn sm ${m?.ml.outage ? 'warn' : ''}`} onClick={() => act(() => api.post('/ml/outage', { enabled: !m?.ml.outage }), m?.ml.outage ? 'ML service restored' : 'ML outage simulated')}>
                <Icon name="cpu" />{m?.ml.outage ? 'Restore ML service' : 'Simulate ML outage'}
              </button>
            </div>
          </div>
        </section>

        <section className="card" aria-label="Demo script">
          <CardHeader title="Demo script" icon="play" />
          <ol className="steps">
            {steps.map(([t, d]) => <li key={t}><span><b>{t}.</b> {d}</span></li>)}
          </ol>
        </section>
      </div>

      <div className="grid g-2">
        <section className="card" aria-label="Non-functional targets">
          <CardHeader title="Non-functional targets (live)" icon="activity" />
          {!m ? <span className="muted">Loading…</span> : (
            <div className="targets">
              <Target label="Emission → broadcast latency (p95)" value={m.latency_ms.p95} limit={m.targets.update_latency_ms} unit="ms" hint="NFR-P1: dashboard updates within 1 s" />
              <Target label="ML inference (p95)" value={m.inference_ms.p95} limit={m.targets.inference_ms} unit="ms" hint="NFR-P2: anomaly score within 200 ms" />
              <Target label="Browser round-trip (this tab)" value={clientLat} limit={m.targets.update_latency_ms} unit="ms" hint="Server timestamp → received in this browser" />
              <div className="target"><span>WebSocket clients</span><span className="mono"><b>{m.ws.clients}</b> <span className="faint">peak {m.ws.peak} · target ≥ {m.targets.ws_clients}</span></span></div>
              <div className="target"><span>MQTT reconnect</span><span className="mono"><b>{m.mqtt.enabled ? (m.mqtt.connected ? 'connected' : 'DISCONNECTED') : 'n/a (direct mode)'}</b> <span className="faint">{m.mqtt.enabled ? `${m.mqtt.reconnects ?? 0} reconnects · target ≤ ${m.targets.mqtt_reconnect_s} s` : ''}</span></span></div>
            </div>
          )}
        </section>

        <section className="card" aria-label="System health">
          <CardHeader title="System health" icon="database" />
          {!m ? <span className="muted">Loading…</span> : (
            <dl className="kv">
              <dt>Uptime</dt><dd>{fmtDuration(m.uptime_s)}</dd>
              <dt>Ingest</dt><dd>{m.simulator.mode ?? '—'} · {m.simulator.machines ?? '—'} machines</dd>
              <dt>Samples received</dt><dd>{m.ingest.rx.toLocaleString()} ({m.ingest.invalid} invalid)</dd>
              <dt>Engine tick (p95)</dt><dd>{fmtNum(m.tick_ms.p95, 1)} ms</dd>
              <dt>Inference (last / max)</dt><dd>{fmtNum(m.inference_ms.last, 1)} / {fmtNum(m.inference_ms.max, 1)} ms</dd>
              <dt>ML model</dt><dd className={m.ml.outage ? 'fail' : m.ml.ready ? 'pass' : 'fail'}>{m.ml.outage ? 'OUTAGE (simulated)' : m.ml.ready ? 'ready' : 'not loaded'}</dd>
              <dt>Storage mode</dt><dd>{m.storage.storage_mode}</dd>
              <dt>InfluxDB</dt><dd className={m.storage.influx === 'ok' ? 'pass' : ''}>{m.storage.influx}</dd>
              <dt>PostgreSQL</dt><dd className={m.storage.postgres === 'ok' ? 'pass' : ''}>{m.storage.postgres}</dd>
              <dt>Write queue</dt><dd>{m.storage.queue}</dd>
              <dt>Retention</dt><dd>30 d raw · 1 y aggregated</dd>
            </dl>
          )}
        </section>
      </div>
    </div>
  )
}
