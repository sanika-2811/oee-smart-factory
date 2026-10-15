import { memo } from 'react'
import { fmtNum, fmtInt, scoreBand } from '../lib/format'
import { go } from '../lib/router'
import type { HistPoint } from '../lib/store'
import type { MachineLive, WindowKey } from '../lib/types'
import { AnimatedNumber, Icon, LevelBadge, Sparkline, StatusChip } from './ui'

interface Props {
  m: MachineLive
  hist: HistPoint[] | undefined
  window: WindowKey
  threshold: number
  compact?: boolean
}

function MachineTileImpl({ m, hist, window, threshold, compact }: Props) {
  const level = m.online ? m.level : 'green'
  const temps = (hist ?? []).slice(-120).map((p) => p.temp)
  const band = scoreBand(m.anomaly_score, threshold)
  const scoreColor = band === 'caution' ? 'var(--yellow)' : band === 'watch' ? 'var(--accent)' : 'var(--green)'
  const hot = m.temperature !== null && m.temperature > m.thresholds.temp_limit
  const oee = m.oee[window]
  return (
    <button
      type="button"
      className={`tile lv-${level} ${m.online ? '' : 'offline'}`}
      onClick={() => go(`/machines/${m.id}`)}
    >
      <span className="sr-only">Open details for {m.name}. </span>
      <div className="head">
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="name">{m.name}</div>
          <div className="id">{m.id}</div>
        </div>
        <div className="stack" style={{ alignItems: 'flex-end', gap: 6 }}>
          <LevelBadge level={level} />
          <StatusChip status={m.status} online={m.online} />
        </div>
      </div>
      <div className="metrics">
        <div className="metric">
          <div className="k">Temp</div>
          <div className={`v ${hot ? 'hot' : ''}`}><AnimatedNumber value={m.temperature} digits={1} /><small>°C</small></div>
        </div>
        <div className="metric">
          <div className="k">Vibration</div>
          <div className="v"><AnimatedNumber value={m.vibration} digits={2} /><small>mm/s</small></div>
        </div>
        <div className="metric">
          <div className="k">Cycles</div>
          <div className="v">{fmtInt(m.cycle_count)}</div>
        </div>
      </div>
      {!compact && <div className="spark"><Sparkline values={temps} threshold={m.thresholds.temp_limit} /></div>}
      <div className="reason" aria-live="polite">
        {m.reason ?? (m.online ? '' : m.age_ms !== null ? `No data for ${Math.round(m.age_ms / 1000)} s` : 'Waiting for telemetry…')}
        {m.whatif.projected && m.whatif.eta_s !== null && ` · hits ${m.thresholds.temp_limit.toFixed(0)} °C in ${Math.round(m.whatif.eta_s)} s`}
      </div>
      <div className="foot">
        <Icon name="cpu" size={14} />
        <span title="Isolation Forest anomaly score" style={{ whiteSpace: 'nowrap' }}>
          ML <b className="mono" style={{ color: 'var(--text)' }}>{fmtNum(m.anomaly_score, 0)}%</b>{!m.ml_ok && ' (held)'}
        </span>
        <div className="bar" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(m.anomaly_score)} aria-label="Anomaly score">
          <i style={{ width: `${m.anomaly_score}%`, ['--c' as string]: scoreColor }} />
          <span className="mark" style={{ left: `${threshold}%` }} />
        </div>
        <span title={`OEE (${window})`} style={{ whiteSpace: 'nowrap' }}>OEE <b className="mono" style={{ color: 'var(--text)' }}>{fmtNum(oee.oee, 1)}%</b></span>
      </div>
    </button>
  )
}

export const MachineTile = memo(MachineTileImpl)
