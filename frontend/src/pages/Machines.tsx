import { useState } from 'react'
import { MachineTile } from '../components/MachineTile'
import { TopBar } from '../components/Layout'
import { Empty, Segmented, Skeleton } from '../components/ui'
import { LEVELS, LEVEL_ORDER } from '../lib/levels'
import { store, useStore } from '../lib/store'
import type { Level, WindowKey } from '../lib/types'

export default function Machines() {
  const snap = useStore((s) => s.snapshot)
  const win = useStore((s) => s.window)
  const history = useStore((s) => s.history)
  const threshold = useStore((s) => s.config?.anomaly_threshold ?? 85)
  const [filter, setFilter] = useState<Level | 'all'>('all')

  const toggle = (
    <Segmented<WindowKey> label="OEE window" value={win} onChange={store.setWindow}
      options={[{ value: '1h', label: '1 h' }, { value: '8h', label: '8 h' }]} />
  )

  if (!snap) {
    return (
      <div className="page">
        <TopBar title="Machines" sub="Waiting for telemetry…">{toggle}</TopBar>
        <div className="grid g-tiles">{[0, 1, 2, 3, 4].map((i) => <div className="card" key={i}><Skeleton h={190} /></div>)}</div>
      </div>
    )
  }
  const list = snap.machines.filter((m) => filter === 'all' || m.level === filter)

  return (
    <div className="page">
      <TopBar title="Machines" sub="Click a tile for live charts, the What-If projection and per-machine OEE">{toggle}</TopBar>
      <div className="filters" role="group" aria-label="Filter by state">
        <button className="pill" aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>All <span className="n">{snap.machines.length}</span></button>
        {LEVEL_ORDER.map((l) => (
          <button key={l} className={`pill lv-${l}`} aria-pressed={filter === l} onClick={() => setFilter(l)}>
            {LEVELS[l].label} <span className="n">{snap.plant.levels[l]}</span>
          </button>
        ))}
      </div>
      {list.length === 0 ? (
        <div className="card"><Empty icon="check" title="No machines in this state">Pick another filter to see the rest of the floor.</Empty></div>
      ) : (
        <div className="grid g-tiles">
          {list.map((m) => <MachineTile key={m.id} m={m} hist={history[m.id]} window={win} threshold={threshold} />)}
        </div>
      )}
    </div>
  )
}
