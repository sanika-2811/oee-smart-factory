/** Small, dependency-free formatting + OEE helpers (unit-tested in tests/). */

export function fmtNum(v: number | null | undefined, digits = 1, fallback = '—'): string {
  if (v === null || v === undefined || Number.isNaN(v)) return fallback
  return v.toFixed(digits)
}

export function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${v.toFixed(digits)}%`
}

export function fmtInt(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return Math.round(v).toLocaleString('en-US')
}

/** "42 s", "3 min 05 s", "2 h 10 min" */
export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return '—'
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s} s`
  if (s < 3600) return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s`
  return `${Math.floor(s / 3600)} h ${String(Math.floor((s % 3600) / 60)).padStart(2, '0')} min`
}

export function timeAgo(ts: number, now = Date.now() / 1000): string {
  const d = now - ts
  if (d < 5) return 'just now'
  if (d < 60) return `${Math.floor(d)} s ago`
  if (d < 3600) return `${Math.floor(d / 60)} min ago`
  if (d < 86400) return `${Math.floor(d / 3600)} h ago`
  return `${Math.floor(d / 86400)} d ago`
}

export function clockTime(ts: number, withSeconds = true): string {
  return new Date(ts * 1000).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    ...(withSeconds ? { second: '2-digit' } : {}),
  })
}

export function dateTime(ts: number): string {
  const d = new Date(ts * 1000)
  return `${d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} ${clockTime(ts)}`
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v))
}

/** OEE = Availability x Performance x Quality, all in percent. */
export function computeOee(availability: number, performance: number, quality: number): number {
  return (availability / 100) * (performance / 100) * (quality / 100) * 100
}

/** World-class OEE is 85 %; below 60 % is considered poor. */
export type OeeGrade = 'excellent' | 'good' | 'fair' | 'poor'
export function oeeGrade(oee: number): OeeGrade {
  if (oee >= 85) return 'excellent'
  if (oee >= 70) return 'good'
  if (oee >= 55) return 'fair'
  return 'poor'
}

/** Anomaly-score band used for the gauge colour. */
export function scoreBand(score: number, threshold = 85): 'normal' | 'watch' | 'caution' {
  if (score > threshold) return 'caution'
  if (score >= threshold * 0.6) return 'watch'
  return 'normal'
}
