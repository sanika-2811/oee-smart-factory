import { Bar } from 'react-chartjs-2'
import type { ChartOptions } from 'chart.js'
import { MachineTile } from '../components/MachineTile'
import { TopBar } from '../components/Layout'
import { AnimatedNumber, CardHeader, Empty, Icon, LEVEL_ICON, RingGauge, Segmented, Skeleton } from '../components/ui'
import { palette } from '../lib/chartSetup'
import { fmtNum, oeeGrade, timeAgo } from '../lib/format'
import { LEVELS, LEVEL_ORDER } from '../lib/levels'
import { go } from '../lib/router'
import { store, useStore } from '../lib/store'
import { useNow } from '../hooks/hooks'
import type { OEEBlock, WindowKey } from '../lib/types'

const GRADE_COLOR = { excellent: 'var(--green)', good: 'var(--accent)', fair: 'var(--orange)', poor: 'var(--red)' }
const GRADE_TEXT = { excellent: 'World-class', good: 'Good', fair: 'Needs attention', poor: 'Poor' }

export function OeeHero({ oee, window }: { oee: OEEBlock; window: WindowKey }) {
  const grade = oeeGrade(oee.oee)
  return (
    <div className="stack" style={{ gap: 18 }}>
      <div className="row" style={{ gap: 28, justifyContent: 'center', alignItems: 'center' }}>
        <div style={{ width: 'min(240px, 58vw)' }}>
          <RingGauge value={oee.oee} size={240} stroke={18} color={GRADE_COLOR[grade]} label={`Overall equipment effectiveness ${oee.oee.toFixed(1)} percent`}>
            <div className="big" style={{ fontSize: 52 }}><AnimatedNumber value={oee.oee} digits={1} /><span style={{ fontSize: 22, color: 'var(--muted)' }}>%</span></div>
            <div className="cap">OEE · {window}</div>
            <div className="cap" style={{ color: GRADE_COLOR[grade], marginTop: 2 }}>{GRADE_TEXT[grade]}</div>
          </RingGauge>
        </div>
        <div className="apq" style={{ flex: '1 1 280px', maxWidth: 420 }}>
          {([
            ['Availability', oee.availability, 'var(--accent)', 'run time ÷ planned time'],
            ['Performance', oee.performance, 'var(--accent-2)', 'ideal cycle time × cycles ÷ run time'],
            ['Quality', oee.quality, 'var(--green)', 'good cycles ÷ total cycles'],
          ] as const).map(([name, v, color, hint]) => (
            <div className="ring" key={name} title={hint}>
              <RingGauge value={v} size={92} stroke={9} color={color} label={`${name} ${v.toFixed(1)} percent`}>
                <div className="big" style={{ fontSize: 19 }}><AnimatedNumber value={v} digits={1} /></div>
              </RingGauge>
              <b>{name}</b>
              <small>%</small>
            </div>
          ))}
        </div>
      </div>
      <div className="formula" aria-label="OEE formula with current values">
        <span>OEE</span><span className="op">=</span>
        <span>A <b>{fmtNum(oee.availability)}</b></span><span className="op">×</span>
        <span>P <b>{fmtNum(oee.performance)}</b></span><span className="op">×</span>
        <span>Q <b>{fmtNum(oee.quality)}</b></span><span className="op">=</span>
        <b style={{ color: GRADE_COLOR[grade] }}>{fmtNum(oee.oee)} %</b>
      </div>
    </div>
  )
}

export default function Overview() {
  const snap = useStore((s) => s.snapshot)
  const win = useStore((s) => s.window)
  const history = useStore((s) => s.history)
  const alerts = useStore((s) => s.alerts)
  const config = useStore((s) => s.config)
  const now = useNow(1000)
  const threshold = config?.anomaly_threshold ?? 85

  const toggle = (
    <Segmented<WindowKey> label="OEE window" value={win} onChange={store.setWindow}
      options={[{ value: '1h', label: '1 hour' }, { value: '8h', label: '8 hours' }]} />
  )

  if (!snap) {
    return (
      <div className="page">
        <TopBar title="Plant overview" sub="Waiting for the first data snapshot…">{toggle}</TopBar>
        <div className="grid g-hero"><div className="card"><Skeleton h={300} /></div><div className="grid g-kpi">{[0, 1, 2, 3].map((i) => <div className="card" key={i}><Skeleton h={90} /></div>)}</div></div>
      </div>
    )
  }

  const plant = snap.plant
  const oee = plant.oee[win]
  const lv = plant.levels
  const sorted = [...snap.machines].sort((a, b) => LEVELS[b.level].rank - LEVELS[a.level].rank)
  const recent = alerts.slice(0, 6)
  const p = palette()
  const barOpts: ChartOptions<'bar'> = {
    indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: { duration: 400 },
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` OEE ${Number(c.parsed.x).toFixed(1)} %` } } },
    scales: {
      x: { min: 0, max: 100, grid: { color: p.grid }, ticks: { color: p.text, callback: (v) => `${v}%` }, border: { display: false } },
      y: { grid: { display: false }, ticks: { color: p.textStrong, font: { family: 'JetBrains Mono', size: 11 } }, border: { display: false }, afterFit: (axis) => { axis.width = Math.max(axis.width, 104) } },
    },
  }
  const colorFor = (v: number) => (v >= 85 ? p.green : v >= 70 ? p.accent : v >= 55 ? p.orange : p.red)
  const barData = {
    labels: snap.machines.map((m) => m.id),
    datasets: [{ data: snap.machines.map((m) => m.oee[win].oee), backgroundColor: snap.machines.map((m) => colorFor(m.oee[win].oee)), borderRadius: 6, barThickness: 16 }],
  }

  return (
    <div className="page">
      <TopBar title="Plant overview" sub={`${plant.online_machines}/${plant.machines_total} machines online · updated every ${config?.tick_ms ?? 500} ms`}>
        {toggle}
      </TopBar>

      <div className="grid g-hero">
        <section className="card" aria-label="Plant OEE">
          <CardHeader title="Plant OEE" icon="gauge" />
          <OeeHero oee={oee} window={win} />
          {config?.backfill?.days ? (
            <p className="faint" style={{ fontSize: 12, marginTop: 12, textAlign: 'center' }}>
              Windows include {config.backfill.days} days of simulated history so the 1 h / 8 h figures are meaningful from the first second.
            </p>
          ) : null}
        </section>

        <div className="grid g-kpi" style={{ alignContent: 'start' }}>
          <div className="card kpi">
            <div className="lbl"><Icon name="machines" />Active machines</div>
            <div className="val"><AnimatedNumber value={plant.active_machines} digits={0} /><small>/ {plant.machines_total}</small></div>
            <div className="hint">{plant.online_machines} reporting · {plant.machines_total - plant.active_machines} idle or stopped</div>
          </div>
          <div className="card kpi">
            <div className="lbl"><Icon name="bell" />Open alerts</div>
            <div className="val"><AnimatedNumber value={plant.open_alerts} digits={0} /></div>
            <div className="lvl-dots">
              {(['red', 'orange', 'yellow'] as const).map((l) => <span key={l} className={`lvl-dot lv-${l}`} title={LEVELS[l].label}>{lv[l]}</span>)}
              <span className="lvl-dot lv-green" title="Normal">{lv.green}</span>
            </div>
          </div>
          <div className="card kpi">
            <div className="lbl"><Icon name="cpu" />Avg anomaly score</div>
            <div className="val"><AnimatedNumber value={plant.avg_anomaly} digits={0} /><small>%</small></div>
            <div className="hint">Caution above {threshold}% {snap.ml_ok ? '' : '· ML unavailable, last scores held'}</div>
          </div>
          <div className="card kpi">
            <div className="lbl"><Icon name="box" />Throughput</div>
            <div className="val"><AnimatedNumber value={plant.throughput_per_min} digits={1} /><small>good/min</small></div>
            <div className="hint">{oee.good.toLocaleString()} good of {oee.cycles.toLocaleString()} cycles ({win})</div>
          </div>
        </div>
      </div>

      <section aria-label="Machines at a glance">
        <div className="card-h" style={{ marginBottom: 10 }}>
          <h2 style={{ fontSize: 13, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--muted)' }}>Machine health</h2>
          <div className="right"><a className="btn sm ghost" href="#/machines">All machines →</a></div>
        </div>
        <div className="grid g-tiles">
          {sorted.slice(0, 6).map((m) => <MachineTile key={m.id} m={m} hist={history[m.id]} window={win} threshold={threshold} />)}
        </div>
      </section>

      <div className="grid g-2">
        <section className="card">
          <CardHeader title={`OEE by machine · ${win}`} icon="chart" />
          <div className="chart" style={{ height: Math.max(180, snap.machines.length * 34 + 30) }}><Bar data={barData} options={barOpts} role="img" aria-label={`OEE by machine, ${win} window: ` + snap.machines.map((m) => `${m.id} ${m.oee[win].oee.toFixed(0)} percent`).join(', ')} /></div>
        </section>
        <section className="card">
          <CardHeader title="Latest alerts" icon="bell"><a className="btn sm ghost" href="#/alerts">Open alert centre →</a></CardHeader>
          {recent.length === 0 ? (
            <Empty icon="check" title="All quiet">No alerts yet. Inject a fault from the Control page to see Yellow, Orange and Red in action.</Empty>
          ) : (
            <div className="stack" style={{ gap: 8 }}>
              {recent.map((a) => (
                <button key={a.id} className={`alert-item lv-${a.level} ${a.active ? '' : 'cleared'}`} style={{ textAlign: 'left', gridTemplateColumns: 'auto 1fr', width: '100%' }} onClick={() => go('/alerts')}>
                  <div className="alert-ico"><Icon name={LEVEL_ICON[a.level]} /></div>
                  <div style={{ minWidth: 0 }}>
                    <h4>{a.title} <span className="chip">{a.machine_id}</span></h4>
                    <p style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.message}</p>
                    <div className="alert-meta"><span>{timeAgo(a.opened_at, now)}</span><span>·</span><span>{a.active ? 'active' : a.status}</span></div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="card" aria-label="Alert level legend">
        <CardHeader title="How machine states work" icon="shield" />
        <div className="grid g-kpi" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          {LEVEL_ORDER.slice().reverse().map((l) => (
            <div key={l} className={`lv-${l} stack`} style={{ gap: 6 }}>
              <span className={`badge lv-${l}`} style={{ alignSelf: 'flex-start' }}><Icon name={LEVEL_ICON[l]} />{LEVELS[l].label}</span>
              <span className="muted" style={{ fontSize: 12.5 }}>{LEVELS[l].description}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
