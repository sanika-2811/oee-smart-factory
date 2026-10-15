import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import type { SeriesPoint } from '../lib/types'

/** Fetch now and then every `ms` (0 = once). Keeps the previous data while refreshing. */
export function usePoll<T>(fn: () => Promise<T>, ms: number, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const load = useCallback(async () => {
    try {
      setData(await fnRef.current())
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    load()
    if (!ms) return
    const t = window.setInterval(load, ms)
    return () => window.clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, ms, ...deps])

  return { data, error, loading, reload: load }
}

/** History from REST (older part) + every live snapshot appended on top. */
export function useMachineSeries(id: string, windowSec: number) {
  const [pts, setPts] = useState<SeriesPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const seq = useStore((s) => s.snapshot?.seq)
  const machine = useStore((s) => s.snapshot?.machines.find((m) => m.id === id))

  useEffect(() => {
    let alive = true
    setLoading(true)
    setPts([])
    const now = Date.now() / 1000
    api
      .get<{ points: SeriesPoint[] }>(`/machines/${encodeURIComponent(id)}/telemetry?from=${now - windowSec}&to=${now + 5}&max_points=1100`)
      .then((r) => { if (alive) { setPts(r.points); setError('') } })
      .catch((e) => alive && setError(e instanceof Error ? e.message : 'Could not load history.'))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [id, windowSec])

  useEffect(() => {
    if (!machine || machine.temperature === null || machine.ts === null) return
    const ts = machine.ts
    setPts((prev) => {
      const last = prev[prev.length - 1]
      if (last && last.ts >= ts) return prev
      const cutoff = ts - windowSec
      const start = prev.findIndex((p) => p.ts >= cutoff)
      const base = start > 0 ? prev.slice(start) : prev
      return [...base, { ts, temperature: machine.temperature, vibration: machine.vibration, anomaly_score: machine.anomaly_score }]
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seq])

  return { pts, loading, error }
}

/** Re-render every second (for "x s ago" labels). */
export function useNow(ms = 1000): number {
  const [now, setNow] = useState(Date.now() / 1000)
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now() / 1000), ms)
    return () => window.clearInterval(t)
  }, [ms])
  return now
}
