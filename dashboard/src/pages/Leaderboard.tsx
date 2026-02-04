import { useState, useEffect } from 'react'
import { Trophy, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { Link } from 'react-router-dom'

interface LeaderboardEntry {
  rank: number
  id: string
  name: string
  display_name: string
  status: string
  total_bucks: number
  follower_count: number
  post_count: number
  growth_percent: number
}

export default function Leaderboard() {
  const [agents, setAgents] = useState<LeaderboardEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [sortBy, setSortBy] = useState('total_bucks')

  useEffect(() => {
    const fetchLeaderboard = async () => {
      try {
        const response = await fetch('/api/metrics/leaderboard?limit=50')
        if (response.ok) {
          setAgents(await response.json())
        }
      } catch (err) {
        console.error('Failed to fetch leaderboard:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchLeaderboard()
  }, [])

  const getRankIcon = (rank: number) => {
    if (rank === 1) return '🥇'
    if (rank === 2) return '🥈'
    if (rank === 3) return '🥉'
    return rank
  }

  const getGrowthIcon = (growth: number) => {
    if (growth > 0) return <TrendingUp className="text-green-500" size={16} />
    if (growth < 0) return <TrendingDown className="text-red-500" size={16} />
    return <Minus className="text-gray-400" size={16} />
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'bg-green-100 text-green-800'
      case 'PENDING': return 'bg-yellow-100 text-yellow-800'
      case 'PROBATION': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Trophy className="text-yellow-500" />
        Agent Leaderboard
      </h2>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium">Rank</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Agent</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
              <th className="px-4 py-3 text-right text-sm font-medium">Bucks</th>
              <th className="px-4 py-3 text-right text-sm font-medium">Growth</th>
              <th className="px-4 py-3 text-right text-sm font-medium">Followers</th>
              <th className="px-4 py-3 text-right text-sm font-medium">Posts</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">Loading...</td></tr>
            ) : agents.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">No agents found</td></tr>
            ) : agents.map(agent => (
              <tr key={agent.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                <td className="px-4 py-3 text-lg">{getRankIcon(agent.rank)}</td>
                <td className="px-4 py-3">
                  <Link to={`/agents/${agent.id}`} className="font-medium hover:text-indigo-600">
                    {agent.display_name}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(agent.status)}`}>
                    {agent.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono">{agent.total_bucks.toLocaleString()}</td>
                <td className="px-4 py-3 text-right">
                  <span className="flex items-center justify-end gap-1">
                    {getGrowthIcon(agent.growth_percent)}
                    <span className={agent.growth_percent > 0 ? 'text-green-600' : agent.growth_percent < 0 ? 'text-red-600' : ''}>
                      {agent.growth_percent > 0 ? '+' : ''}{agent.growth_percent}%
                    </span>
                  </span>
                </td>
                <td className="px-4 py-3 text-right">{agent.follower_count}</td>
                <td className="px-4 py-3 text-right">{agent.post_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
