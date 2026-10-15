import type { Level } from './types'

/** The four alert colours of the SRS, each with a non-colour cue (icon + label) for accessibility. */
export interface LevelMeta {
  key: Level
  label: string
  short: string
  description: string
  rank: number
}

export const LEVELS: Record<Level, LevelMeta> = {
  green: { key: 'green', label: 'Normal', short: 'OK', description: 'Operating normally', rank: 0 },
  yellow: { key: 'yellow', label: 'ML caution', short: 'CAUTION', description: 'Isolation Forest anomaly score above 85 %', rank: 1 },
  orange: { key: 'orange', label: 'Projected fault', short: 'PROJECTED', description: 'Temperature trend will cross the hard limit within 60 s', rank: 2 },
  red: { key: 'red', label: 'Hard fault', short: 'FAULT', description: 'Rule-based hard threshold breached or machine down', rank: 3 },
}

export const LEVEL_ORDER: Level[] = ['red', 'orange', 'yellow', 'green']

export const STATUS_LABEL: Record<string, string> = {
  RUNNING: 'Running',
  IDLE: 'Idle',
  STOPPED: 'Stopped',
  UNKNOWN: 'No data',
}
