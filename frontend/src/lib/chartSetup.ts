import {
  BarElement, CategoryScale, Chart as ChartJS, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip,
  type ChartOptions,
} from 'chart.js'
import { clockTime } from './format'

ChartJS.register(BarElement, CategoryScale, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip)

export function cssVar(name: string, fallback = '#888'): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

export function palette() {
  return {
    text: cssVar('--muted'),
    grid: cssVar('--grid'),
    accent: cssVar('--accent'),
    accent2: cssVar('--accent-2'),
    green: cssVar('--green'),
    yellow: cssVar('--yellow'),
    orange: cssVar('--orange'),
    red: cssVar('--red'),
    solid: cssVar('--solid'),
    textStrong: cssVar('--text'),
  }
}

type Axis = Record<string, unknown>

/** Shared options for the live time-series charts (linear x axis in epoch seconds, no animation). */
export function timeOptions(opts: { xMin: number; xMax: number; y?: Axis; y2?: Axis; legend?: boolean }): ChartOptions<'line'> {
  const c = palette()
  const base = { grid: { color: c.grid }, ticks: { color: c.text, font: { family: 'JetBrains Mono', size: 10.5 } }, border: { display: false } }
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    normalized: true,
    parsing: false,
    interaction: { mode: 'nearest', axis: 'x', intersect: false },
    plugins: {
      legend: { display: opts.legend ?? false, labels: { color: c.text, boxWidth: 12, usePointStyle: true } },
      tooltip: {
        backgroundColor: c.solid, titleColor: c.textStrong, bodyColor: c.text, borderColor: c.grid, borderWidth: 1, padding: 10,
        callbacks: { title: (items) => (items[0] ? clockTime(items[0].parsed.x ?? 0) : '') },
      },
    },
    scales: {
      x: {
        type: 'linear', min: opts.xMin, max: opts.xMax, ...base,
        ticks: { ...base.ticks, maxTicksLimit: 6, callback: (v) => clockTime(Number(v), true) },
      },
      y: { ...base, position: 'left', ...(opts.y ?? {}) } as never,
      ...(opts.y2 ? { y2: { ...base, position: 'right', grid: { drawOnChartArea: false, color: c.grid }, ...opts.y2 } as never } : {}),
    },
  }
}

export { ChartJS }
