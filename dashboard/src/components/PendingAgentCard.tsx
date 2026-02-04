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
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 border-l-4 border-yellow-500">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {agent.display_name}
            </h3>
            <span className="px-2 py-0.5 bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 text-xs rounded-full">
              PENDING
            </span>
          </div>

          <p className="text-gray-600 dark:text-gray-400 mt-2 line-clamp-2">
            {agent.bio || 'No description provided'}
          </p>

          <div className="flex items-center gap-4 mt-4 text-sm text-gray-500">
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
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <ExternalLink size={16} />
            Activate
          </a>

          <button
            onClick={onCheck}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            <RefreshCw size={16} />
            Check Status
          </button>

          <button
            onClick={onCancel}
            className="flex items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
          >
            <XCircle size={16} />
            Cancel
          </button>
        </div>
      </div>

      <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Activation URL:</p>
        <code className="text-sm text-indigo-600 dark:text-indigo-400 break-all">
          {agent.activation_url}
        </code>
      </div>
    </div>
  )
}
