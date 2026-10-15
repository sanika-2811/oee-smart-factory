import { useEffect, useState } from 'react'

/** Minimal hash router: "#/machines/CNC-01" -> ['machines', 'CNC-01'] */
function parse(): string[] {
  const h = window.location.hash.replace(/^#\/?/, '')
  return h.split('?')[0].split('/').filter(Boolean).map(decodeURIComponent)
}

export function useRoute(): string[] {
  const [route, setRoute] = useState<string[]>(parse)
  useEffect(() => {
    const on = () => setRoute(parse())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}

export function go(path: string) {
  window.location.hash = path.startsWith('#') ? path : `#${path}`
}

export function hashParams(): URLSearchParams {
  const q = window.location.hash.split('?')[1] ?? ''
  return new URLSearchParams(q)
}
