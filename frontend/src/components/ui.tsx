import { useEffect, useRef, useState, type ReactNode } from 'react'
import { LEVELS } from '../lib/levels'
import type { Level, MachineStatus } from '../lib/types'
import { clamp } from '../lib/format'

/* ------------------------------------------------------------------ icons (stroke, 24px grid) */
const P: Record<string, ReactNode> = {
  overview: <><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></>,
  machines: <><path d="M3 21V10l6 3V9l6 3V5l6 3v13z" /><path d="M7 21v-3M12 21v-3M17 21v-3" /></>,
  bell: <><path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8" /><path d="M10.3 20a2 2 0 0 0 3.4 0" /></>,
  wrench: <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.6 2.6-2.4-.6-.6-2.4z" />,
  chart: <><path d="M3 3v18h18" /><path d="m7 15 4-5 3 3 5-7" /></>,
  sliders: <><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></>,
  check: <><circle cx="12" cy="12" r="9" /><path d="m8 12.5 3 3 5-6" /></>,
  triangle: <><path d="M12 3 2.5 20h19z" /><path d="M12 10v4.5M12 17.5h.01" /></>,
  trend: <><path d="M3 17 9 11l4 4 8-9" /><path d="M15 6h6v6" /></>,
  octagon: <><path d="M8.3 2.5h7.4l5.8 5.8v7.4l-5.8 5.8H8.3l-5.8-5.8V8.3z" /><path d="M9 9l6 6M15 9l-6 6" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  moon: <path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z" />,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21c1-4 4-6 8-6s7 2 8 6" /></>,
  play: <path d="M7 4.5v15l12-7.5z" />,
  stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
  activity: <path d="M3 12h4l3-8 4 16 3-8h4" />,
  gauge: <><path d="M4 18a9 9 0 1 1 16 0" /><path d="m12 13 4-5" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  zap: <path d="M13 2 4 14h7l-1 8 9-12h-7z" />,
  thermo: <><path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0z" /></>,
  vibe: <path d="M2 12h3l2-5 3 10 3-14 3 12 2-3h4" />,
  box: <><path d="M21 8 12 3 3 8v8l9 5 9-5z" /><path d="m3 8 9 5 9-5M12 13v8" /></>,
  link: <><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  trash: <><path d="M4 7h16M10 11v6M14 11v6" /><path d="M6 7l1 13h10l1-13M9 7V4h6v3" /></>,
  thumbup: <path d="M7 11v9H3v-9zM7 11l4-8c2 0 3 1 3 3v3h5.5a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 18.3 20H7" />,
  thumbdown: <path d="M17 13V4h4v9zM17 13l-4 8c-2 0-3-1-3-3v-3H4.5a2 2 0 0 1-2-2.3l1.2-7A2 2 0 0 1 5.7 4H17" />,
  logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" /></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>,
  cpu: <><rect x="6" y="6" width="12" height="12" rx="2" /><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" /></>,
  inbox: <><path d="M3 13h5l1.5 3h5L16 13h5" /><path d="M5.5 5h13L21 13v6H3v-6z" /></>,
}

export function Icon({ name, className, size }: { name: string; className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      style={size ? { width: size, height: size } : undefined}
    >
      {P[name] ?? null}
    </svg>
  )
}

export const LEVEL_ICON: Record<Level, string> = { green: 'check', yellow: 'triangle', orange: 'trend', red: 'octagon' }

export function LevelBadge({ level, large, label }: { level: Level; large?: boolean; label?: string }) {
  const m = LEVELS[level]
  return (
    <span className={`badge lv-${level} ${large ? 'lg' : ''}`} title={m.description}>
      <Icon name={LEVEL_ICON[level]} />
      {label ?? m.short}
    </span>
  )
}

export function StatusChip({ status, online = true }: { status: MachineStatus; online?: boolean }) {
  if (!online || status === 'UNKNOWN') return <span className="chip none"><i className="dot" />No data</span>
  const cls = status === 'RUNNING' ? 'run' : status === 'IDLE' ? 'idle' : 'stop'
  const label = status === 'RUNNING' ? 'Running' : status === 'IDLE' ? 'Idle' : 'Stopped'
  return <span className={`chip ${cls}`}><i className="dot" />{label}</span>
}

export function Skeleton({ h = 20, w = '100%', r }: { h?: number; w?: number | string; r?: number }) {
  return <div className="skeleton" style={{ height: h, width: w, borderRadius: r }} aria-hidden="true" />
}

export function Empty({ icon = 'inbox', title, children }: { icon?: string; title: string; children?: ReactNode }) {
  return (
    <div className="empty" role="status">
      <Icon name={icon} />
      <b>{title}</b>
      {children && <span>{children}</span>}
    </div>
  )
}

/* ------------------------------------------------------------------ animated number */
export function useTween(target: number | null | undefined, ms = 450): number {
  const [v, setV] = useState<number>(target ?? 0)
  const from = useRef(target ?? 0)
  const raf = useRef(0)
  useEffect(() => {
    if (target === null || target === undefined || Number.isNaN(target)) return
    const start = performance.now()
    const a = from.current
    cancelAnimationFrame(raf.current)
    const step = (now: number) => {
      const t = clamp((now - start) / ms, 0, 1)
      const e = 1 - Math.pow(1 - t, 3)
      const cur = a + (target - a) * e
      from.current = cur
      setV(cur)
      if (t < 1) raf.current = requestAnimationFrame(step)
    }
    raf.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf.current)
  }, [target, ms])
  return v
}

export function AnimatedNumber({ value, digits = 1, suffix = '' }: { value: number | null | undefined; digits?: number; suffix?: string }) {
  const v = useTween(value)
  if (value === null || value === undefined) return <>—</>
  return <>{v.toFixed(digits)}{suffix}</>
}

/* ------------------------------------------------------------------ ring gauge */
export function RingGauge({
  value, max = 100, size = 200, stroke = 14, color = 'var(--accent)', children, label,
}: { value: number; max?: number; size?: number; stroke?: number; color?: string; children?: ReactNode; label?: string }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const frac = clamp(value / max, 0, 1)
  return (
    <div className="gauge" role="img" aria-label={label ?? `${value.toFixed(1)} of ${max}`}>
      <svg viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <circle className="track" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} />
        <circle
          className="arc" cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={c} strokeDashoffset={c * (1 - frac)} transform={`rotate(-90 ${size / 2} ${size / 2})`}
          filter="url(#glow)"
        />
      </svg>
      <div className="center">{children}</div>
    </div>
  )
}

/* ------------------------------------------------------------------ SVG sparkline */
export function Sparkline({
  values, min, max, threshold, color = 'var(--lv, var(--accent))', height = 46,
}: { values: number[]; min?: number; max?: number; threshold?: number; color?: string; height?: number }) {
  const W = 220
  const H = height
  if (values.length < 2) return <div className="skeleton" style={{ height: H }} aria-hidden="true" />
  let lo = min ?? Math.min(...values)
  let hi = max ?? Math.max(...values)
  if (hi - lo < 6) { const mid = (hi + lo) / 2; hi = mid + 3; lo = mid - 3 }
  // only draw the limit when it is close enough not to flatten the live trace
  const showLimit = threshold !== undefined && threshold - hi < Math.max(10, (hi - lo) * 1.2)
  if (showLimit) hi = Math.max(hi, (threshold as number) + 1)
  const x = (i: number) => (i / (values.length - 1)) * W
  const y = (v: number) => H - 3 - ((v - lo) / (hi - lo)) * (H - 8)
  const line = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')
  const area = `${line} L${W} ${H} L0 ${H} Z`
  const id = useRef(`sg${Math.random().toString(36).slice(2, 8)}`).current
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height={H} aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.35" /><stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {showLimit && threshold !== undefined && <line x1="0" x2={W} y1={y(threshold)} y2={y(threshold)} stroke="var(--red)" strokeWidth="1" strokeDasharray="3 3" opacity="0.7" />}
      <path d={area} fill={`url(#${id})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      <circle cx={x(values.length - 1)} cy={y(values[values.length - 1])} r="3" fill={color} />
    </svg>
  )
}

export function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  )
}

export function CardHeader({ title, children, icon }: { title: string; children?: ReactNode; icon?: string }) {
  return (
    <div className="card-h">
      {icon && <Icon name={icon} size={16} />}
      <h2>{title}</h2>
      {children && <div className="right">{children}</div>}
    </div>
  )
}
