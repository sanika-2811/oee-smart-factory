export type Level = 'green' | 'yellow' | 'orange' | 'red'
export type AlertLevel = Exclude<Level, 'green'>
export type MachineStatus = 'RUNNING' | 'IDLE' | 'STOPPED' | 'UNKNOWN'
export type WindowKey = '1h' | '8h'
export type FaultKind = 'temp_ramp' | 'vib_spike' | 'stop' | 'anomaly'

export interface OEEBlock {
  availability: number
  performance: number
  quality: number
  oee: number
  planned_s: number
  run_s: number
  cycles: number
  good: number
}

export interface WhatIfLite {
  ready: boolean
  projected: boolean
  eta_s: number | null
  slope_c_per_min: number
  r2: number
  fit_now: number | null
}

export interface MachineLive {
  id: string
  name: string
  kind: string
  online: boolean
  status: MachineStatus
  temperature: number | null
  vibration: number | null
  cycle_count: number | null
  good_count: number | null
  ts: number | null
  age_ms: number | null
  anomaly_score: number
  ml_ok: boolean
  level: Level
  reason: string | null
  alert_id: number | null
  alert_status: string | null
  whatif: WhatIfLite
  thresholds: { temp_limit: number; vib_limit: number }
  oee: Record<WindowKey, OEEBlock>
}

export interface PlantLive {
  oee: Record<WindowKey, OEEBlock>
  machines_total: number
  active_machines: number
  online_machines: number
  open_alerts: number
  avg_anomaly: number
  throughput_per_min: number
  levels: Record<Level, number>
}

export interface Snapshot {
  type: 'snapshot'
  seq: number
  ts: number
  machines: MachineLive[]
  plant: PlantLive
  ml_ok: boolean
  ws_clients?: number
}

export interface Alert {
  id: number
  machine_id: string
  level: AlertLevel
  kind: string
  title: string
  message: string
  opened_at: number
  value: number | null
  threshold: number | null
  eta_s: number | null
  score: number | null
  peak: number | null
  status: 'open' | 'acknowledged' | 'cleared' | 'resolved'
  active: boolean
  last_seen: number
  cleared_at: number | null
  clear_reason: string | null
  acked_by: string | null
  acked_at: number | null
  technician: string | null
  resolved_by: string | null
  resolved_at: number | null
  resolution_notes: string | null
  feedback: { verdict: 'true_positive' | 'false_positive'; by: string; at: number; comment: string } | null
  duration_s: number
}

export interface Maintenance {
  id: number
  machine_id: string
  alert_id: number | null
  action: string
  notes: string
  technician: string
  status: 'open' | 'in_progress' | 'closed'
  created_by: string
  created_at: number
  updated_at: number
}

export interface MachineInfo {
  id: string
  name: string
  kind: string
  ideal_cycle_s: number
  temp_limit: number
  vib_limit: number
  base_temp: number
  base_vib: number
  reject_rate: number
}

export interface AppConfig {
  ingest_mode: string
  storage_mode: string
  machines: MachineInfo[]
  anomaly_threshold: number
  whatif_horizon_s: number
  whatif_window_s: number
  tick_ms: number
  technicians: string[]
  demo_logins: { username: string; password: string; role: string }[]
  backfill: { days?: number; note?: string }
}

export interface SeriesPoint {
  ts: number
  temperature: number | null
  vibration: number | null
  anomaly_score: number | null
  status?: string | null
}

export interface WhatIfDetail {
  machine_id: string
  window_s: number
  threshold: number
  horizon_s: number
  level: Level
  line: { ts: number; y: number }[]
  points: { ts: number; temperature: number }[]
  projection: {
    ready: boolean
    projected: boolean
    n: number
    slope_c_per_s: number
    slope_c_per_min: number
    intercept: number
    r2: number
    eta_s: number | null
    fit_now: number | null
  }
}

export interface Metrics {
  uptime_s: number
  targets: { update_latency_ms: number; inference_ms: number; mqtt_reconnect_s: number; ws_clients: number }
  latency_ms: { p50: number | null; p95: number | null; max: number | null; samples: number }
  inference_ms: { last: number; p50: number | null; p95: number | null; max: number | null }
  tick_ms: { p50: number | null; p95: number | null; max: number | null }
  ingest: { rx: number; invalid: number; unknown_machine: number; ticks: number; ml_errors: number }
  ml: { ready: boolean; outage: boolean; model: string | null }
  mqtt: { enabled: boolean; connected: boolean | null; reconnects?: number; host?: string; port?: number; transport?: string; note?: string }
  simulator: { mode?: string; machines?: number; time_scale?: number; faults?: Record<string, string[]> }
  backfill: { days?: number; seconds?: number; samples?: number }
  storage: { storage_mode: string; influx: string; postgres: string; queue: number }
  ws: { clients: number; peak: number; total_connections: number }
}

export type ConnState = 'connecting' | 'live' | 'reconnecting'
