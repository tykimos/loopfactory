import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
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
    <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 min-h-screen p-4">
      <h1 className="text-xl font-bold mb-8 text-indigo-600">LoopFactory</h1>
      <nav className="space-y-2">
        {links.map(({ to, icon: Icon, label }) => (
          <Link
            key={to}
            to={to}
            className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <Icon size={20} />
            <span>{label}</span>
          </Link>
        ))}
      </nav>
    </aside>
  )
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold">{title}</h2>
      <p className="text-gray-500 mt-4">Coming soon...</p>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 bg-gray-50 dark:bg-gray-900">
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
