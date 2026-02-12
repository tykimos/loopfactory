import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, Users, Activity, Factory, Settings, Clock, Trophy } from 'lucide-react'
import PendingActivation from './pages/PendingActivation'
import Overview from './pages/Overview'
import Leaderboard from './pages/Leaderboard'
import AgentDetail from './pages/AgentDetail'
import FactoryPage from './pages/Factory'
import SettingsPage from './pages/Settings'

function Sidebar() {
  const links = [
    { to: '/', icon: LayoutDashboard, label: 'Overview' },
    { to: '/agents', icon: Users, label: 'Agents' },
    { to: '/leaderboard', icon: Trophy, label: 'Leaderboard' },
    { to: '/pending', icon: Clock, label: 'Pending' },
    { to: '/activity', icon: Activity, label: 'Activity' },
    { to: '/factory', icon: Factory, label: 'Factory' },
    { to: '/settings', icon: Settings, label: 'Settings' }
  ]

  return (
    <aside className="w-64 min-h-screen p-4 border-r border-[#19313b] bg-[#060d12]">
      <h1 className="text-xl font-bold mb-8 crt-title crt-glow">LoopFactory</h1>
      <nav className="space-y-2">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md border transition-colors ${
                isActive
                  ? 'border-[#2ce6a6]/60 bg-[#102129] text-[#2ce6a6]'
                  : 'border-transparent text-[#78b7a8] hover:border-[#19313b] hover:bg-[#0d1a20]'
              }`
            }
          >
            <Icon size={20} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="p-8 h-full crt-screen">
      <div className="crt-panel rounded-lg p-6">
        <h2 className="text-2xl font-bold crt-title">{title}</h2>
        <p className="crt-muted mt-4">Coming soon...</p>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-[#050a0d] text-[#9ce8d5]">
        <Sidebar />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/agents" element={<Placeholder title="Agents" />} />
            <Route path="/agents/:id" element={<AgentDetail />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
            <Route path="/pending" element={<PendingActivation />} />
            <Route path="/activity" element={<Placeholder title="Activity Monitor" />} />
            <Route path="/factory" element={<FactoryPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
