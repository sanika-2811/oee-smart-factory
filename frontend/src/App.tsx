import { useEffect } from 'react'
import { ErrorBoundary } from './components/ErrorBoundary'
import { LoginModal, OfflineBanner, Sidebar, TabBar, Toasts } from './components/Layout'
import { go, useRoute } from './lib/router'
import { startLive, useStore } from './lib/store'
import Alerts from './pages/Alerts'
import Control from './pages/Control'
import MachineDetail from './pages/MachineDetail'
import Machines from './pages/Machines'
import Maintenance from './pages/Maintenance'
import Overview from './pages/Overview'
import Reports from './pages/Reports'

export default function App() {
  const route = useRoute()
  useEffect(() => { startLive() }, [])
  const openAlerts = useStore((st) => st.snapshot?.plant.open_alerts ?? 0)
  useEffect(() => { document.title = openAlerts > 0 ? `(${openAlerts}) OEE Control Room` : 'OEE Control Room' }, [openAlerts])
  useEffect(() => { if (route.length === 0) go('/overview') }, [route.length])

  const section = route[0] ?? 'overview'
  let page
  switch (section) {
    case 'machines': page = route[1] ? <MachineDetail key={route[1]} id={route[1]} /> : <Machines />; break
    case 'alerts': page = <Alerts />; break
    case 'maintenance': page = <Maintenance />; break
    case 'reports': page = <Reports />; break
    case 'control': page = <Control />; break
    default: page = <Overview />
  }

  return (
    <div className="app">
      <a className="skip" href="#main" onClick={(e) => { e.preventDefault(); document.getElementById("main")?.focus() }}>Skip to main content</a>
      <Sidebar current={section} />
      <main className="main" id="main" tabIndex={-1} aria-label="Dashboard content"><OfflineBanner /><ErrorBoundary key={section + (route[1] ?? '')}>{page}</ErrorBoundary></main>
      <TabBar current={section} />
      <Toasts />
      <LoginModal />
    </div>
  )
}
