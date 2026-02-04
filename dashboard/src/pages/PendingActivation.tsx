import { useState, useEffect } from 'react'
import { Clock, ExternalLink, RefreshCw, XCircle } from 'lucide-react'
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
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Clock className="text-yellow-500" />
            Pending Activation
          </h2>
          <p className="text-gray-500 mt-1">
            Agents waiting for user activation
          </p>
        </div>
        <button
          onClick={fetchPending}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {agents.length > 0 && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 mb-6">
          <p className="text-yellow-800 dark:text-yellow-200">
            <strong>{agents.length}</strong> agent(s) waiting for activation.
            Click the activation link to approve each agent.
          </p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6">
          <p className="text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {loading && agents.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="animate-spin mx-auto mb-4 text-gray-400" size={32} />
          <p className="text-gray-500">Loading...</p>
        </div>
      ) : agents.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-lg shadow">
          <Clock className="mx-auto mb-4 text-gray-400" size={48} />
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">No Pending Agents</h3>
          <p className="text-gray-500 mt-2">All agents have been activated or there are no pending registrations.</p>
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

      <div className="mt-6 text-sm text-gray-500">
        Auto-refresh: 30 seconds | Pending timeout: 12 hours
      </div>
    </div>
  )
}
