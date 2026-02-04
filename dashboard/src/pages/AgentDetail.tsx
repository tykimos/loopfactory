import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { User, Edit, Pause, Trash2, Activity, TrendingUp } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface Agent {
  id: string
  name: string
  display_name: string
  bio: string
  status: string
  activation_url?: string
  created_at: string
  last_heartbeat?: string
  total_bucks: number
  is_protected: boolean
}

export default function AgentDetail() {
  const { id } = useParams<{ id: string }>()
  const [agent, setAgent] = useState<Agent | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchAgent = async () => {
      try {
        const response = await fetch(`/api/agents/${id}`)
        if (!response.ok) throw new Error('Agent not found')
        setAgent(await response.json())
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load agent')
      } finally {
        setLoading(false)
      }
    }
    if (id) fetchAgent()
  }, [id])

  if (loading) return <div className="p-8 text-center">Loading...</div>
  if (error) return <div className="p-8 text-center text-red-500">{error}</div>
  if (!agent) return <div className="p-8 text-center">Agent not found</div>

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'bg-green-100 text-green-800'
      case 'PENDING': return 'bg-yellow-100 text-yellow-800'
      case 'PROBATION': return 'bg-red-100 text-red-800'
      case 'RETIRED': return 'bg-gray-100 text-gray-800'
      default: return 'bg-blue-100 text-blue-800'
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center">
            <User size={32} className="text-indigo-600" />
          </div>
          <div>
            <h2 className="text-2xl font-bold">{agent.display_name}</h2>
            <p className="text-gray-500">@{agent.name}</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm ${getStatusColor(agent.status)}`}>
            {agent.status}
          </span>
          {agent.is_protected && (
            <span className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm">
              Protected
            </span>
          )}
        </div>

        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200">
            <Edit size={16} /> Edit
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-yellow-100 text-yellow-800 rounded-lg hover:bg-yellow-200">
            <Pause size={16} /> Pause
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-red-100 text-red-800 rounded-lg hover:bg-red-200">
            <Trash2 size={16} /> Retire
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4">Profile</h3>
          <p className="text-gray-600 dark:text-gray-400">{agent.bio}</p>
          <div className="mt-4 space-y-2 text-sm">
            <p><span className="text-gray-500">Created:</span> {new Date(agent.created_at).toLocaleDateString()}</p>
            {agent.last_heartbeat && (
              <p><span className="text-gray-500">Last Active:</span> {new Date(agent.last_heartbeat).toLocaleString()}</p>
            )}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4">Statistics</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-gray-500 text-sm">Total Bucks</p>
              <p className="text-2xl font-bold text-indigo-600">{agent.total_bucks.toLocaleString()}</p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4">Performance (7 Days)</h3>
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={[]}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="bucks" stroke="#6366f1" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
