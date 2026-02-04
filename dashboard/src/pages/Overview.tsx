import { useState, useEffect } from 'react'
import { LayoutDashboard, Users, TrendingUp, Cpu, AlertTriangle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface SystemStatus {
  cpu_percent: number
  memory_mb: number
  active_agents: number
  pending_agents: number
}

interface MetricsOverview {
  total_bucks: number
  agent_count: number
  active_agents: number
  pending_agents: number
}

export default function Overview() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statusRes, metricsRes] = await Promise.all([
          fetch('/api/system/status'),
          fetch('/api/metrics/overview')
        ])

        if (statusRes.ok) setStatus(await statusRes.json())
        if (metricsRes.ok) setMetrics(await metricsRes.json())
      } catch (err) {
        console.error('Failed to fetch data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  const cards = [
    { title: 'Active Agents', value: metrics?.active_agents ?? '--', icon: Users, color: 'text-green-500' },
    { title: 'Pending', value: metrics?.pending_agents ?? '--', icon: AlertTriangle, color: 'text-yellow-500' },
    { title: 'Total Bucks', value: metrics?.total_bucks?.toLocaleString() ?? '--', icon: TrendingUp, color: 'text-indigo-500' },
    { title: 'CPU Usage', value: status ? `${status.cpu_percent.toFixed(1)}%` : '--', icon: Cpu, color: 'text-blue-500' }
  ]

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <LayoutDashboard />
        Dashboard Overview
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {cards.map(({ title, value, icon: Icon, color }) => (
          <div key={title} className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500 dark:text-gray-400">{title}</p>
              <Icon className={color} size={20} />
            </div>
            <p className="text-3xl font-bold mt-2">{value}</p>
          </div>
        ))}
      </div>

      {(metrics?.pending_agents ?? 0) > 0 && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between">
            <p className="text-yellow-800 dark:text-yellow-200">
              <AlertTriangle className="inline mr-2" size={16} />
              <strong>{metrics?.pending_agents}</strong> agent(s) waiting for activation
            </p>
            <Link to="/pending" className="text-yellow-800 dark:text-yellow-200 underline">
              Go to Pending →
            </Link>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4">Bucks Trend (2 Days)</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={[]}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="bucks" stroke="#6366f1" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4">Top Performers</h3>
          <p className="text-gray-500 text-sm">Loading...</p>
        </div>
      </div>
    </div>
  )
}
