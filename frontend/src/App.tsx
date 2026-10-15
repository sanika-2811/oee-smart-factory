import { useEffect } from 'react'
import { LoginModal, Sidebar, TabBar, Toasts } from './components/Layout'
import { go, useRoute } from './lib/router'
import { startLive } from './lib/store'
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
      <Sidebar current={section} />
      <main className="main" id="main">{page}</main>
      <TabBar current={section} />
      <Toasts />
      <LoginModal />
    </div>
  )
}
