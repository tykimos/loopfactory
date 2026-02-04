import { useState, useEffect } from 'react'
import { Factory, TrendingUp, Lightbulb, Plus, RefreshCw } from 'lucide-react'

interface TrendTopic {
  topic: string
  percentage: number
  post_count: number
}

interface Niche {
  niche: string
  competition: string
  opportunity_score: number
}

interface Trends {
  hot_topics: TrendTopic[]
  underserved_niches: Niche[]
  our_gaps: string[]
}

interface AgentSuggestion {
  name: string
  display_name: string
  bio: string
  topic: string
  confidence: number
}

export default function FactoryPage() {
  const [trends, setTrends] = useState<Trends | null>(null)
  const [suggestions, setSuggestions] = useState<AgentSuggestion[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [trendsRes, suggestionsRes] = await Promise.all([
        fetch('/api/factory/trends'),
        fetch('/api/factory/suggestions?count=3')
      ])

      if (trendsRes.ok) setTrends(await trendsRes.json())
      if (suggestionsRes.ok) setSuggestions(await suggestionsRes.json())
    } catch (err) {
      console.error('Failed to fetch factory data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleDesign = async () => {
    setCreating(true)
    try {
      const response = await fetch('/api/factory/design', { method: 'POST' })
      if (response.ok) {
        const result = await response.json()
        alert(`Agent created: ${result.agent_id}`)
        fetchData()
      }
    } catch (err) {
      console.error('Failed to design agent:', err)
    } finally {
      setCreating(false)
    }
  }

  const getCompetitionColor = (competition: string) => {
    switch (competition) {
      case 'low': return 'text-green-600 bg-green-100'
      case 'medium': return 'text-yellow-600 bg-yellow-100'
      case 'high': return 'text-red-600 bg-red-100'
      default: return 'text-gray-600 bg-gray-100'
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Factory className="text-indigo-600" />
          Agent Factory
        </h2>
        <div className="flex gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={handleDesign}
            disabled={creating}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            <Plus size={16} />
            {creating ? 'Creating...' : 'Design New Agent'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Trends Panel */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="text-green-500" />
            Trend Analysis (Last 2 Days)
          </h3>

          {loading ? (
            <p className="text-gray-500">Loading trends...</p>
          ) : (
            <>
              <h4 className="text-sm font-medium text-gray-500 mb-2">Hot Topics</h4>
              <div className="space-y-2 mb-4">
                {trends?.hot_topics?.slice(0, 5).map((topic, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <span>{topic.topic}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-indigo-600 h-2 rounded-full"
                          style={{ width: `${topic.percentage}%` }}
                        />
                      </div>
                      <span className="text-sm text-gray-500">{topic.percentage}%</span>
                    </div>
                  </div>
                ))}
              </div>

              <h4 className="text-sm font-medium text-gray-500 mb-2">Underserved Niches</h4>
              <div className="space-y-2">
                {trends?.underserved_niches?.map((niche, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <span>{niche.niche}</span>
                    <span className={`px-2 py-1 rounded-full text-xs ${getCompetitionColor(niche.competition)}`}>
                      {niche.competition}
                    </span>
                  </div>
                ))}
              </div>

              {trends?.our_gaps && trends.our_gaps.length > 0 && (
                <>
                  <h4 className="text-sm font-medium text-gray-500 mt-4 mb-2">Our Gaps</h4>
                  <ul className="list-disc list-inside text-sm text-orange-600">
                    {trends.our_gaps.map((gap, i) => (
                      <li key={i}>{gap}</li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </div>

        {/* Suggestions Panel */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <Lightbulb className="text-yellow-500" />
            AI-Suggested Agents
          </h3>

          {loading ? (
            <p className="text-gray-500">Loading suggestions...</p>
          ) : (
            <div className="space-y-4">
              {suggestions.map((suggestion, i) => (
                <div key={i} className="border dark:border-gray-700 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-medium">{suggestion.display_name}</h4>
                    <span className="text-sm text-gray-500">
                      Confidence: {Math.round(suggestion.confidence * 100)}%
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                    {suggestion.bio}
                  </p>
                  <div className="flex items-center justify-between">
                    <span className="text-xs bg-indigo-100 text-indigo-800 px-2 py-1 rounded">
                      {suggestion.topic}
                    </span>
                    <button className="text-sm text-indigo-600 hover:underline">
                      Use This Concept →
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
