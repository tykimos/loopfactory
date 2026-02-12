import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { User, Edit, Pause, Trash2 } from 'lucide-react'
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
      case 'ACTIVE': return 'bg-[#0f2a1f] text-[#2ce6a6] border border-[#2ce6a6]/30'
      case 'PENDING': return 'bg-[#2b2412] text-[#ffd166] border border-[#ffd166]/30'
      case 'PROBATION': return 'bg-[#2d1a1a] text-[#ff9f9f] border border-[#ff6b6b]/30'
      case 'RETIRED': return 'bg-[#1a2128] text-[#7ca39b] border border-[#19313b]'
      default: return 'bg-[#132028] text-[#9ce8d5] border border-[#19313b]'
    }
  }

  return (
    <div className="p-8 crt-screen">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-[#102129] border border-[#19313b] rounded-full flex items-center justify-center">
            <User size={32} className="text-[#2ce6a6]" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[#b6ffe4]">{agent.display_name}</h2>
            <p className="crt-muted">@{agent.name}</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm ${getStatusColor(agent.status)}`}>
            {agent.status}
          </span>
          {agent.is_protected && (
            <span className="px-3 py-1 bg-[#2e2442] text-[#d0b3ff] rounded-full text-sm border border-[#5e4c83]">
              Protected
            </span>
          )}
        </div>

        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-4 py-2 terminal-chip rounded-lg hover:bg-[#152830]">
            <Edit size={16} /> Edit
          </button>
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#2b2412] text-[#ffd166] border border-[#ffd166]/30 hover:bg-[#3a3119]">
            <Pause size={16} /> Pause
          </button>
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#2d1a1a] text-[#ff9f9f] border border-[#ff6b6b]/30 hover:bg-[#3a2020]">
            <Trash2 size={16} /> Retire
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="crt-panel rounded-lg p-6">
          <h3 className="font-semibold mb-4 crt-title text-sm">Profile</h3>
          <p className="text-[#9ce8d5]">{agent.bio}</p>
          <div className="mt-4 space-y-2 text-sm">
            <p><span className="crt-muted">Created:</span> {new Date(agent.created_at).toLocaleDateString()}</p>
            {agent.last_heartbeat && (
              <p><span className="crt-muted">Last Active:</span> {new Date(agent.last_heartbeat).toLocaleString()}</p>
            )}
          </div>
        </div>

        <div className="crt-panel rounded-lg p-6">
          <h3 className="font-semibold mb-4 crt-title text-sm">Statistics</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="crt-muted text-sm">Total Bucks</p>
              <p className="text-2xl font-bold text-[#2ce6a6]">{agent.total_bucks.toLocaleString()}</p>
            </div>
          </div>
        </div>

        <div className="crt-panel rounded-lg p-6">
          <h3 className="font-semibold mb-4 crt-title text-sm">Performance (7 Days)</h3>
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={[]}>
                <CartesianGrid strokeDasharray="3 3" stroke="#19313b" />
                <XAxis dataKey="date" stroke="#5c8f86" />
                <YAxis stroke="#5c8f86" />
                <Tooltip />
                <Line type="monotone" dataKey="bucks" stroke="#2ce6a6" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
