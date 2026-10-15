import { describe, expect, it } from 'vitest'
import { clamp, computeOee, fmtDuration, fmtInt, fmtNum, fmtPct, oeeGrade, scoreBand, timeAgo } from '../src/lib/format'

describe('number formatting', () => {
  it('formats numbers with fallbacks', () => {
    expect(fmtNum(62.345, 1)).toBe('62.3')
    expect(fmtNum(null)).toBe('—')
    expect(fmtNum(undefined)).toBe('—')
    expect(fmtNum(Number.NaN)).toBe('—')
    expect(fmtPct(88.04)).toBe('88.0%')
    expect(fmtInt(44249.4)).toBe('44,249')
  })
  it('formats durations', () => {
    expect(fmtDuration(42)).toBe('42 s')
    expect(fmtDuration(185)).toBe('3 min 05 s')
    expect(fmtDuration(7500)).toBe('2 h 05 min')
    expect(fmtDuration(null)).toBe('—')
  })
  it('formats relative time', () => {
    expect(timeAgo(100, 102)).toBe('just now')
    expect(timeAgo(100, 130)).toBe('30 s ago')
    expect(timeAgo(100, 400)).toBe('5 min ago')
    expect(timeAgo(0, 7200)).toBe('2 h ago')
  })
  it('clamps', () => {
    expect(clamp(5, 0, 3)).toBe(3)
    expect(clamp(-1, 0, 3)).toBe(0)
  })
})

describe('OEE helpers', () => {
  it('OEE = A x P x Q', () => {
    expect(computeOee(90, 80, 95)).toBeCloseTo(68.4, 5)
    expect(computeOee(100, 100, 100)).toBe(100)
    expect(computeOee(0, 100, 100)).toBe(0)
  })
  it('grades OEE', () => {
    expect(oeeGrade(90)).toBe('excellent')
    expect(oeeGrade(75)).toBe('good')
    expect(oeeGrade(60)).toBe('fair')
    expect(oeeGrade(30)).toBe('poor')
  })
  it('bands anomaly scores around the 85 % threshold', () => {
    expect(scoreBand(10)).toBe('normal')
    expect(scoreBand(60)).toBe('watch')
    expect(scoreBand(85)).toBe('watch')
    expect(scoreBand(85.1)).toBe('caution')
  })
})
