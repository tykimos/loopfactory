import { useState, useEffect } from 'react'
import { Clock, RefreshCw } from 'lucide-react'
import PendingAgentCard from '../components/PendingAgentCard'

interface PendingAgent {
  agent_id: string
  display_name: string
  bio: string
  activation_url: string
  created_at: string
  check_count: number
}

export default function PendingActivation() {
  const [agents, setAgents] = useState<PendingAgent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchPending = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/pending')
      if (!response.ok) throw new Error('Failed to fetch pending agents')
      const data = await response.json()
      setAgents(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPending()
    const interval = setInterval(fetchPending, 30000) // Auto-refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const handleCheck = async (agentId: string) => {
    try {
      const response = await fetch(`/api/pending/${agentId}/check`, { method: 'POST' })
      const result = await response.json()
      if (result.status === 'ACTIVE') {
        // Refresh the list
        fetchPending()
      }
    } catch (err) {
      console.error('Check failed:', err)
    }
  }

  const handleCancel = async (agentId: string) => {
    if (!confirm('Cancel this pending activation?')) return
    try {
      await fetch(`/api/pending/${agentId}`, { method: 'DELETE' })
      fetchPending()
    } catch (err) {
      console.error('Cancel failed:', err)
    }
  }

  return (
    <div className="p-8 crt-screen">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2 crt-title">
            <Clock className="text-[#ffd166]" />
            Pending Activation
          </h2>
          <p className="crt-muted mt-1">
            Agents waiting for user activation
          </p>
        </div>
        <button
          onClick={fetchPending}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 terminal-btn rounded-lg disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {agents.length > 0 && (
        <div className="bg-[#2b2412]/60 border border-[#ffd166]/30 rounded-lg p-4 mb-6">
          <p className="text-[#ffd166]">
            <strong>{agents.length}</strong> agent(s) waiting for activation.
            Click the activation link to approve each agent.
          </p>
        </div>
      )}

      {error && (
        <div className="bg-[#2d1a1a]/60 border border-[#ff6b6b]/30 rounded-lg p-4 mb-6">
          <p className="text-[#ff9f9f]">{error}</p>
        </div>
      )}

      {loading && agents.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="animate-spin mx-auto mb-4 text-[#5c8f86]" size={32} />
          <p className="crt-muted">Loading...</p>
        </div>
      ) : agents.length === 0 ? (
        <div className="text-center py-12 crt-panel rounded-lg">
          <Clock className="mx-auto mb-4 text-[#5c8f86]" size={48} />
          <h3 className="text-lg font-medium text-[#b6ffe4]">No Pending Agents</h3>
          <p className="crt-muted mt-2">All agents have been activated or there are no pending registrations.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {agents.map(agent => (
            <PendingAgentCard
              key={agent.agent_id}
              agent={agent}
              onCheck={() => handleCheck(agent.agent_id)}
              onCancel={() => handleCancel(agent.agent_id)}
            />
          ))}
        </div>
      )}

      <div className="mt-6 text-sm crt-muted">
        Auto-refresh: 30 seconds | Pending timeout: 12 hours
      </div>
    </div>
  )
}
