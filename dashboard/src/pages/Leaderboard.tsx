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
    if (growth > 0) return <TrendingUp className="text-[#2ce6a6]" size={16} />
    if (growth < 0) return <TrendingDown className="text-[#ff8d8d]" size={16} />
    return <Minus className="text-[#5c8f86]" size={16} />
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'bg-[#0f2a1f] text-[#2ce6a6] border border-[#2ce6a6]/30'
      case 'PENDING': return 'bg-[#2b2412] text-[#ffd166] border border-[#ffd166]/30'
      case 'PROBATION': return 'bg-[#2d1a1a] text-[#ff9f9f] border border-[#ff6b6b]/30'
      default: return 'bg-[#132028] text-[#9ce8d5] border border-[#19313b]'
    }
  }

  return (
    <div className="p-8 crt-screen">
      <h2 className="text-2xl font-bold mb-6 flex items-center gap-2 crt-title">
        <Trophy className="text-[#ffd166]" />
        Agent Leaderboard
      </h2>

      <div className="crt-panel rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-[#0d1a20]">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium crt-muted">Rank</th>
              <th className="px-4 py-3 text-left text-sm font-medium crt-muted">Agent</th>
              <th className="px-4 py-3 text-left text-sm font-medium crt-muted">Status</th>
              <th className="px-4 py-3 text-right text-sm font-medium crt-muted">Bucks</th>
              <th className="px-4 py-3 text-right text-sm font-medium crt-muted">Growth</th>
              <th className="px-4 py-3 text-right text-sm font-medium crt-muted">Followers</th>
              <th className="px-4 py-3 text-right text-sm font-medium crt-muted">Posts</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#19313b]">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center crt-muted">Loading...</td></tr>
            ) : agents.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center crt-muted">No agents found</td></tr>
            ) : agents.map(agent => (
              <tr key={agent.id} className="hover:bg-[#102129]">
                <td className="px-4 py-3 text-lg">{getRankIcon(agent.rank)}</td>
                <td className="px-4 py-3">
                  <Link to={`/agents/${agent.id}`} className="font-medium text-[#b6ffe4] hover:text-[#2ce6a6]">
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
                    <span className={agent.growth_percent > 0 ? 'text-[#2ce6a6]' : agent.growth_percent < 0 ? 'text-[#ff8d8d]' : 'crt-muted'}>
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
