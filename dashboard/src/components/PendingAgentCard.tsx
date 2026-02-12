import { ExternalLink, RefreshCw, XCircle, Clock } from 'lucide-react'

interface PendingAgent {
  agent_id: string
  display_name: string
  bio: string
  activation_url: string
  created_at: string
  check_count: number
}

interface Props {
  agent: PendingAgent
  onCheck: () => void
  onCancel: () => void
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins} min ago`

  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`

  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
}

export default function PendingAgentCard({ agent, onCheck, onCancel }: Props) {
  return (
    <div className="crt-panel rounded-lg p-6 border-l-4 border-[#ffd166]">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <h3 className="text-lg font-semibold text-[#b6ffe4]">
              {agent.display_name}
            </h3>
            <span className="px-2 py-0.5 bg-[#2b2412] text-[#ffd166] text-xs rounded-full border border-[#ffd166]/30">
              PENDING
            </span>
          </div>

          <p className="text-[#9ce8d5] mt-2 line-clamp-2">
            {agent.bio || 'No description provided'}
          </p>

          <div className="flex items-center gap-4 mt-4 text-sm crt-muted">
            <span className="flex items-center gap-1">
              <Clock size={14} />
              Created {formatTimeAgo(agent.created_at)}
            </span>
            <span>
              Checks: {agent.check_count}
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-2 ml-4">
          <a
            href={agent.activation_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 terminal-btn rounded-lg transition-colors"
          >
            <ExternalLink size={16} />
            Activate
          </a>

          <button
            onClick={onCheck}
            className="flex items-center gap-2 px-4 py-2 terminal-chip rounded-lg hover:bg-[#162b34] transition-colors"
          >
            <RefreshCw size={16} />
            Check Status
          </button>

          <button
            onClick={onCancel}
            className="flex items-center gap-2 px-4 py-2 text-[#ff9f9f] hover:bg-[#2d1a1a] rounded-lg transition-colors"
          >
            <XCircle size={16} />
            Cancel
          </button>
        </div>
      </div>

      <div className="mt-4 p-3 bg-[#091219] border border-[#19313b] rounded-lg">
        <p className="text-xs crt-muted mb-1">Activation URL:</p>
        <code className="text-sm text-[#66f0c0] break-all">
          {agent.activation_url}
        </code>
      </div>
    </div>
  )
}
