import { useState, useEffect, useMemo, useRef, useCallback } from 'react'

interface Agent {
  id: string
  name: string
  display_name: string
  status: string
  activity_status: string
  bucks: number
  followers: number
  last_heartbeat: string | null
  activation_url?: string
  bio?: string
  created_at?: string
  model?: string | null
  site_id?: string | null
  node_id?: string | null
  site_name?: string | null
  node_name?: string | null
  is_running?: boolean
}

interface LoopNode {
  id: string
  name: string
  description?: string | null
}

interface LoopSite {
  id: string
  name: string
  description?: string | null
  nodes: LoopNode[]
}

interface SystemStatus {
  cpu_percent: number
  memory_percent: number
  memory_mb: number
  available_memory_mb: number
  disk_percent: number
  disk_used_gb: number
  disk_total_gb: number
  token_percent: number
  token_used: number
  token_limit: number
  running_processes: number
  max_concurrent: number
  can_run_agent: boolean
  // Claude Code usage
  claude_five_hour_percent: number
  claude_seven_day_percent: number
  claude_five_hour_resets_at: string | null
  claude_seven_day_resets_at: string | null
}

interface BottleneckCheck {
  name: string
  label: string
  current: number
  threshold?: number
  unit?: string
  status: 'ok' | 'warning' | 'blocked'
  detail?: string
}

interface BottleneckStage {
  name: string
  label: string
  count: number
  checks: BottleneckCheck[]
  has_bottleneck: boolean
  blocked_count: number
}

interface BottleneckData {
  stages: BottleneckStage[]
  scheduler: { running: boolean; active_agents: number; job_count: number; inflight: number }
}

const COLORS = {
  RUNNING: { base: '#39d353', light: '#6ee87a', glow: '#39d353' },
  ACTIVE: { base: '#2ea043', light: '#3fb950' },
  IDLE: { base: '#1a472a', light: '#1f5c35' },
  STARVING: { base: '#7c2d12', light: '#9a3412' },  // Dark orange-red for starving
  WAITING: { base: '#ffd33d', light: '#ffe066' }, // Human auth wait
  PENDING: { base: '#f97316', light: '#fb923c' }, // Active wait
  PROBATION: { base: '#fb7185', light: '#fda4af' },
  DESIGN: { base: '#1f6feb', light: '#58a6ff' },
  RETIRED: { base: '#21262d', light: '#30363d' },
  VACANT: { base: '#161b22', light: '#21262d' },
}

const RESOURCE_COLORS = {
  CPU: '#39d353',
  Memory: '#58a6ff',
  Disk: '#f97316',
  Token: '#a371f7',
  Human: '#ffd33d',
}

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toString()
}

function isRunning(agent: Agent): boolean {
  if (typeof agent.is_running === 'boolean') return agent.is_running
  if (!agent.last_heartbeat) return false
  const lastBeat = new Date(agent.last_heartbeat).getTime()
  return Date.now() - lastBeat < 5 * 60 * 1000
}

function isStarving(agent: Agent): boolean {
  if (agent.status !== 'ACTIVE') return false
  if (isRunning(agent)) return false
  if (!agent.last_heartbeat) return true  // Never had a heartbeat
  const lastBeat = new Date(agent.last_heartbeat).getTime()
  return Date.now() - lastBeat > 60 * 60 * 1000  // >60 min since last heartbeat
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString()
}

// Agent Detail Panel with Resizable and Embedded Activation
function AgentDetailPanel({
  agent,
  onClose,
  onActivate,
}: {
  agent: Agent
  onClose: () => void
  onActivate?: (updatedAgent: Agent) => void
}) {
  const [width, setWidth] = useState(280)
  const [isResizing, setIsResizing] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const [logLines, setLogLines] = useState<string[]>([])
  const [logStatus, setLogStatus] = useState<'connecting' | 'connected' | 'error'>('connecting')

  const running = isRunning(agent)
  const colorSet = COLORS[agent.status as keyof typeof COLORS] || COLORS.IDLE
  const needsActivation = agent.status === 'WAITING' && agent.activation_url

  useEffect(() => {
    setLogLines([])
    setLogStatus('connecting')
    const source = new EventSource(`/api/agents/${agent.id}/logs/stream`)

    source.onmessage = (event) => {
      if (!event.data) return
      setLogStatus('connected')
      setLogLines(prev => {
        const next = [...prev, event.data]
        if (next.length > 500) {
          return next.slice(next.length - 500)
        }
        return next
      })
    }

    source.onerror = () => {
      setLogStatus('error')
    }

    return () => {
      source.close()
    }
  }, [agent.id])

  useEffect(() => {
    if (!logRef.current) return
    logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logLines])

  // Handle resize
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return
      const newWidth = e.clientX
      setWidth(Math.max(240, Math.min(500, newWidth)))
    }
    const handleMouseUp = () => setIsResizing(false)

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
    }
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isResizing])

  return (
    <div
      ref={panelRef}
      className="bg-gray-900/95 border-r border-gray-800 flex flex-col shrink-0 relative"
      style={{ width }}
    >
      {/* Resize Handle */}
      <div
        className="absolute right-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-blue-500/50 transition-colors"
        onMouseDown={() => setIsResizing(true)}
      />

      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-800">
        <h2 className="font-bold text-sm truncate flex-1">{agent.display_name || agent.name}</h2>
        <button onClick={onClose} className="text-gray-500 hover:text-white text-lg ml-2">&times;</button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-3">
        <div className="space-y-3 text-xs">
          {/* Status */}
          <div className="flex items-center gap-2">
            <span
              className={`w-3 h-3 rounded-sm ${running ? 'glow-pulse' : ''}`}
              style={{
                backgroundColor: colorSet.base,
                '--color-base': colorSet.base,
                '--color-light': colorSet.light,
                '--color-glow': 'glow' in colorSet ? (colorSet as typeof COLORS.RUNNING).glow : colorSet.light,
              } as React.CSSProperties}
            />
            <span style={{ color: colorSet.base }}>{agent.status}</span>
            {running && <span className="text-green-400 text-[10px]">(running)</span>}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-2 py-2 border-y border-gray-800">
            <div>
              <div className="opacity-50 text-[10px]">Bucks</div>
              <div className="text-green-400 font-medium">{formatNumber(agent.bucks || 0)}</div>
            </div>
            <div>
              <div className="opacity-50 text-[10px]">Followers</div>
              <div className="font-medium">{agent.followers || 0}</div>
            </div>
          </div>

          {/* Info */}
          <div className="space-y-2">
            <div>
              <div className="opacity-50 text-[10px]">ID</div>
              <div className="font-mono text-[10px] opacity-70">{agent.id}</div>
            </div>
            <div>
              <div className="opacity-50 text-[10px]">Created</div>
              <div>{formatDate(agent.created_at)}</div>
            </div>
            {agent.last_heartbeat && (
              <div>
                <div className="opacity-50 text-[10px]">Last Heartbeat</div>
                <div>{new Date(agent.last_heartbeat).toLocaleString()}</div>
              </div>
            )}
          </div>

          {/* Bio */}
          {agent.bio && (
            <div className="pt-2 border-t border-gray-800">
              <div className="opacity-50 text-[10px] mb-1">Bio</div>
              <div className="text-[11px] opacity-80 leading-relaxed">{agent.bio}</div>
            </div>
          )}

          {/* Live Logs */}
          <div className="pt-2 border-t border-gray-800">
            <div className="flex items-center justify-between mb-1">
              <div className="opacity-50 text-[10px]">Live Log</div>
              <div className="text-[9px] opacity-60">
                {logStatus === 'connected' ? 'streaming' : logStatus}
              </div>
            </div>
            <div
              ref={logRef}
              className="font-mono text-[10px] leading-relaxed bg-black/30 border border-gray-800 rounded p-2 h-40 overflow-auto"
            >
              {logLines.length === 0 ? (
                <div className="opacity-50">No log output yet.</div>
              ) : (
                logLines.map((line, i) => (
                  <div key={i} className="whitespace-pre-wrap break-words">{line}</div>
                ))
              )}
            </div>
          </div>

          {/* View Full Details Link */}
          <a
            href={`/agents/${agent.id}`}
            className="block w-full py-2 px-3 bg-gray-800 text-gray-300 rounded text-center text-xs hover:bg-gray-700 mt-2"
          >
            View Full Details
          </a>
        </div>
      </div>

      {/* Activation Buttons - for WAITING agents */}
      {needsActivation && (
        <div className="border-t border-yellow-500/30 bg-yellow-500/5 p-3">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
            <span className="text-[10px] font-medium text-yellow-400">Activation Required</span>
          </div>
          <div className="space-y-2">
            <a
              href={agent.activation_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full py-2 px-3 bg-yellow-500 text-black rounded text-center text-xs font-medium hover:bg-yellow-400 transition-colors"
            >
              Open Activation Link
            </a>
            <button
              onClick={async () => {
                try {
                  const res = await fetch(`/api/agents/${agent.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'ACTIVE' })
                  })
                  if (res.ok) {
                    const updated = await res.json()
                    onActivate?.(updated)
                  }
                } catch (err) {
                  console.error('Failed to activate:', err)
                }
              }}
              className="block w-full py-2 px-3 bg-green-600 text-white rounded text-center text-xs font-medium hover:bg-green-500 transition-colors"
            >
              Activation Complete
            </button>
          </div>
          <p className="text-[9px] text-gray-500 mt-2">
            1. Click "Open Activation Link" and complete activation
            <br />
            2. Return here and click "Activation Complete"
          </p>
        </div>
      )}
    </div>
  )
}

// Agent Tile
function AgentTile({
  agent,
  isSelected,
  onClick,
}: {
  agent: Agent | null
  isSelected: boolean
  onClick?: () => void
}) {
  if (!agent) {
    return <div className="w-full h-full rounded-sm" style={{ backgroundColor: COLORS.VACANT.base }} />
  }

  const isWaiting = agent.status === 'WAITING'
  const isPending = agent.status === 'PENDING'
  const running = isRunning(agent)
  const starving = isStarving(agent)

  let colorSet = COLORS.IDLE
  if (agent.status === 'WAITING') colorSet = COLORS.WAITING
  else if (agent.status === 'PENDING') colorSet = COLORS.PENDING
  else if (agent.status === 'PROBATION') colorSet = COLORS.PROBATION
  else if (agent.status === 'DESIGN') colorSet = COLORS.DESIGN
  else if (agent.status === 'RETIRED') colorSet = COLORS.RETIRED
  else if (running) colorSet = COLORS.RUNNING
  else if (starving) colorSet = COLORS.STARVING

  // Running uses glow animation, WAITING (auth) uses gradient animation
  const animationClass = running ? 'glow-pulse' : isWaiting ? 'gradient-pulse' : ''

  return (
    <div
      className={`w-full h-full rounded-sm cursor-pointer transition-all hover:scale-125 hover:z-10 flex items-center justify-center ${
        animationClass
      } ${isSelected ? 'ring-2 ring-white ring-offset-1 ring-offset-gray-900' : ''}`}
      style={{
        backgroundColor: colorSet.base,
        '--color-light': colorSet.light,
        '--color-base': colorSet.base,
        '--color-glow': 'glow' in colorSet ? colorSet.glow : colorSet.light,
      } as React.CSSProperties}
      onClick={onClick}
      title={agent.display_name || agent.name}
    >
      <span className="text-[6px] font-bold text-white/80">{formatNumber(agent.bucks || 0)}</span>
    </div>
  )
}

// Time-series Resource Graph
function ResourceGraph({
  label,
  history,
  color,
  limit,
  currentValue,
  subValue,
}: {
  label: string
  history: number[]
  color: string
  limit: number
  currentValue?: string
  subValue?: string
}) {
  const current = history[history.length - 1] || 0
  const isWarning = current >= limit * 0.7
  const isCritical = current >= limit * 0.85
  const barColor = isCritical ? '#ef4444' : isWarning ? '#f97316' : color

  const paddedHistory = [...Array(30 - history.length).fill(0), ...history]

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-[9px]">
        <span className="opacity-70">{label}</span>
        <div className="text-right">
          <span style={{ color: barColor }}>{currentValue || `${current.toFixed(0)}%`}</span>
          {subValue && <span className="opacity-40 ml-1 text-[8px]">{subValue}</span>}
        </div>
      </div>
      <div className="flex items-end gap-px h-5 bg-gray-900/50 rounded">
        {paddedHistory.map((value, i) => (
          <div
            key={i}
            className="flex-1 transition-all duration-300"
            style={{
              height: `${Math.max((value / 100) * 20, 1)}px`,
              backgroundColor: i === paddedHistory.length - 1 ? barColor : `${color}40`,
              opacity: 0.4 + (i / paddedHistory.length) * 0.6,
            }}
          />
        ))}
      </div>
    </div>
  )
}

// Minimap
function Minimap({
  agents,
  gridCols,
  viewportRef,
  containerRef,
}: {
  agents: Agent[]
  gridCols: number
  viewportRef: React.RefObject<HTMLDivElement>
  containerRef: React.RefObject<HTMLDivElement>
}) {
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, width: 100, height: 100 })
  const minimapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const updateViewBox = () => {
      if (!viewportRef.current || !containerRef.current) return
      const vp = viewportRef.current
      const ct = containerRef.current
      setViewBox({
        x: (vp.scrollLeft / ct.scrollWidth) * 100,
        y: (vp.scrollTop / ct.scrollHeight) * 100,
        width: (vp.clientWidth / ct.scrollWidth) * 100,
        height: (vp.clientHeight / ct.scrollHeight) * 100,
      })
    }
    const vp = viewportRef.current
    if (vp) {
      vp.addEventListener('scroll', updateViewBox)
      window.addEventListener('resize', updateViewBox)
      updateViewBox()
    }
    return () => {
      if (vp) {
        vp.removeEventListener('scroll', updateViewBox)
        window.removeEventListener('resize', updateViewBox)
      }
    }
  }, [viewportRef, containerRef])

  const handleClick = (e: React.MouseEvent) => {
    if (!minimapRef.current || !viewportRef.current || !containerRef.current) return
    const rect = minimapRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top) / rect.height
    viewportRef.current.scrollTo({
      left: x * containerRef.current.scrollWidth - viewportRef.current.clientWidth / 2,
      top: y * containerRef.current.scrollHeight - viewportRef.current.clientHeight / 2,
      behavior: 'smooth',
    })
  }

  const rows = Math.ceil(agents.length / gridCols)
  const minimapCols = Math.min(gridCols, 40)
  const minimapRows = Math.min(rows, 30)
  const step = Math.max(1, Math.ceil(agents.length / (minimapCols * minimapRows)))

  return (
    <div
      ref={minimapRef}
      className="relative bg-gray-900/90 border border-gray-700 rounded p-1 cursor-pointer"
      style={{ width: '100%', height: '50px' }}
      onClick={handleClick}
    >
      <div className="w-full h-full grid gap-px" style={{ gridTemplateColumns: `repeat(${minimapCols}, 1fr)` }}>
        {Array.from({ length: minimapCols * minimapRows }).map((_, i) => {
          const agent = agents[i * step]
          let color = COLORS.VACANT.base
          if (agent) {
            if (agent.status === 'WAITING') color = COLORS.WAITING.base
            else if (agent.status === 'PENDING') color = COLORS.PENDING.base
            else if (agent.status === 'PROBATION') color = COLORS.PROBATION.base
            else if (agent.status === 'DESIGN') color = COLORS.DESIGN.base
            else if (agent.status === 'RETIRED') color = COLORS.RETIRED.base
            else if (isRunning(agent)) color = COLORS.RUNNING.base
            else if (isStarving(agent)) color = COLORS.STARVING.base
            else color = COLORS.IDLE.base
          }
          return <div key={i} style={{ backgroundColor: color }} />
        })}
      </div>
      <div
        className="absolute border border-white/60 bg-white/10 pointer-events-none"
        style={{
          left: `${viewBox.x}%`,
          top: `${viewBox.y}%`,
          width: `${Math.max(viewBox.width, 5)}%`,
          height: `${Math.max(viewBox.height, 5)}%`,
        }}
      />
    </div>
  )
}

const BN_COLORS: Record<string, string> = {
  ok: '#39d353',
  warning: '#f97316',
  blocked: '#ef4444',
}

function BottleneckPanel({ data }: { data: BottleneckData | null }) {
  if (!data) {
    return (
      <div className="flex flex-col gap-1 py-2">
        <div className="text-[9px] font-bold tracking-widest opacity-50">BOTTLENECK</div>
        <div className="text-[8px] opacity-30">Waiting for data...</div>
      </div>
    )
  }

  const anyBlocked = data.stages.some(s => s.has_bottleneck)

  return (
    <div className="flex flex-col gap-2">
      {/* Pipeline header */}
      <div className="flex items-center gap-1.5">
        {anyBlocked ? (
          <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: '#ef4444' }} />
        ) : (
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#39d353' }} />
        )}
        <span className="text-[9px] font-bold tracking-widest opacity-50">PIPELINE</span>
      </div>

      {/* Pipeline stages */}
      {data.stages.map((stage, idx) => (
        <div key={stage.name} className="flex flex-col gap-0.5">
          {/* Stage header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              {stage.has_bottleneck ? (
                <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: '#ef4444' }} />
              ) : (
                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#39d353' }} />
              )}
              <span className="text-[9px] font-bold opacity-70">{stage.label}</span>
            </div>
            <span className="text-[9px] opacity-40">{stage.count}</span>
          </div>

          {/* Checks per stage */}
          <div className="ml-3 flex flex-col gap-0.5">
            {stage.checks.map((check) => {
              const color = BN_COLORS[check.status]
              const hasPct = check.threshold != null && check.threshold > 0
              const barPct = hasPct ? Math.min((check.current / check.threshold!) * 100, 100) : 0

              return (
                <div key={check.name}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1">
                      <span className="w-1 h-1 rounded-full" style={{ backgroundColor: color }} />
                      <span className="text-[8px] opacity-60">{check.label}</span>
                      {check.status === 'blocked' && (
                        <span className="text-[7px] font-bold" style={{ color }}>BLOCKED</span>
                      )}
                    </div>
                    <span className="text-[8px] font-medium" style={{ color }}>
                      {check.current}{check.unit === '%' ? '%' : ''}
                      {check.threshold != null ? ` / ${check.threshold}${check.unit === '%' ? '%' : ''}` : ''}
                    </span>
                  </div>
                  {hasPct && (
                    <div className="h-0.5 bg-gray-800 rounded-full mt-0.5 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${check.status === 'blocked' ? 'bottleneck-pulse' : ''}`}
                        style={{ width: `${barPct}%`, backgroundColor: color }}
                      />
                    </div>
                  )}
                  {check.detail && (
                    <div className="text-[7px] opacity-30 ml-2">{check.detail}</div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Pipeline arrow between stages */}
          {idx < data.stages.length - 1 && (
            <div className="text-[8px] opacity-20 ml-1 leading-none">↓</div>
          )}
        </div>
      ))}

      {/* Scheduler */}
      <div className="text-[8px] opacity-30 pt-0.5 border-t border-gray-800/30">
        {data.scheduler.inflight} running, {data.scheduler.job_count} scheduled
      </div>
    </div>
  )
}

export default function Overview() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [sites, setSites] = useState<LoopSite[]>([])
  const [selectedSite, setSelectedSite] = useState('all')
  const [selectedNode, setSelectedNode] = useState('all')
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [bottleneckData, setBottleneckData] = useState<BottleneckData | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [resourceHistory, setResourceHistory] = useState({
    cpu: [] as number[],
    mem: [] as number[],
    hdd: [] as number[],
    claude5h: [] as number[],
    human: [] as number[],
  })
  const [needsMinimap, setNeedsMinimap] = useState(false)
  const [gridCols, setGridCols] = useState(20)
  const viewportRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const MAX_HISTORY = 30
  const TILE_SIZE = 18
  const GAP_SIZE = 2

  useEffect(() => {
    const fetchTopology = async () => {
      try {
        const res = await fetch('/api/topology/sites')
        if (res.ok) {
          const data = await res.json()
          setSites(data || [])
        }
      } catch (err) {
        console.error('Topology fetch error:', err)
      }
    }
    fetchTopology()
  }, [])

  useEffect(() => {
    const currentSite = sites.find(s => s.id === selectedSite)
    if (selectedNode !== 'all' && (!currentSite || !currentSite.nodes.some(n => n.id === selectedNode))) {
      setSelectedNode('all')
    }
  }, [selectedSite, selectedNode, sites])

  useEffect(() => {
    const fetchData = async () => {
      try {
        const params = new URLSearchParams()
        if (selectedSite !== 'all') params.set('site_id', selectedSite)
        if (selectedNode !== 'all') params.set('node_id', selectedNode)
        const agentsUrl = params.toString() ? `/api/agents?${params.toString()}` : '/api/agents'

        const [agentsRes, statusRes, bottleneckRes] = await Promise.all([
          fetch(agentsUrl),
          fetch('/api/system/status'),
          fetch('/api/system/bottleneck'),
        ])
        if (agentsRes.ok) {
          const agentData = await agentsRes.json()
          setAgents(agentData)
          const waitingCount = agentData.filter((a: Agent) => a.status === 'WAITING').length
          const humanPercent = Math.min((waitingCount / 100) * 100, 100)

          if (statusRes.ok) {
            const statusData = await statusRes.json()
            setStatus(statusData)
            setResourceHistory(prev => ({
              cpu: [...prev.cpu.slice(-(MAX_HISTORY - 1)), statusData.cpu_percent || 0],
              mem: [...prev.mem.slice(-(MAX_HISTORY - 1)), statusData.memory_percent || 0],
              hdd: [...prev.hdd.slice(-(MAX_HISTORY - 1)), statusData.disk_percent || 0],
              claude5h: [...prev.claude5h.slice(-(MAX_HISTORY - 1)), statusData.claude_five_hour_percent || 0],
              human: [...prev.human.slice(-(MAX_HISTORY - 1)), humanPercent],
            }))
          }
          if (bottleneckRes.ok) {
            setBottleneckData(await bottleneckRes.json())
          }
        }
      } catch (err) {
        console.error('Fetch error:', err)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [selectedSite, selectedNode])

  // Calculate grid columns based on viewport width
  useEffect(() => {
    const calculateCols = () => {
      if (viewportRef.current) {
        const width = viewportRef.current.clientWidth - 32
        const cols = Math.floor(width / (TILE_SIZE + GAP_SIZE))
        setGridCols(Math.max(10, Math.min(cols, 50)))
      }
    }
    calculateCols()
    window.addEventListener('resize', calculateCols)
    return () => window.removeEventListener('resize', calculateCols)
  }, [selectedAgent]) // recalculate when sidebar opens/closes

  // Check if minimap is needed
  useEffect(() => {
    const checkOverflow = () => {
      if (viewportRef.current && containerRef.current) {
        const vp = viewportRef.current
        const ct = containerRef.current
        setNeedsMinimap(ct.scrollHeight > vp.clientHeight)
      }
    }
    const timer = setTimeout(checkOverflow, 100)
    window.addEventListener('resize', checkOverflow)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('resize', checkOverflow)
    }
  }, [agents, gridCols])

  const sortedAgents = useMemo(() => [...agents].sort((a, b) => (b.bucks || 0) - (a.bucks || 0)), [agents])

  useEffect(() => {
    if (selectedAgent && !agents.some(a => a.id === selectedAgent.id)) {
      setSelectedAgent(null)
    }
  }, [agents, selectedAgent])

  // Track viewport dimensions for grid fill calculation
  const [viewportSize, setViewportSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const updateSize = () => {
      if (viewportRef.current) {
        setViewportSize({
          width: viewportRef.current.clientWidth,
          height: viewportRef.current.clientHeight
        })
      }
    }
    updateSize()
    window.addEventListener('resize', updateSize)
    return () => window.removeEventListener('resize', updateSize)
  }, [selectedAgent])

  // Calculate grid with empty placeholders to fill viewport
  const gridWithPlaceholders = useMemo(() => {
    const viewportWidth = viewportSize.width - 32
    const viewportHeight = viewportSize.height - 32
    if (viewportWidth <= 0 || viewportHeight <= 0) {
      return sortedAgents.map(a => ({ agent: a }))
    }

    const cols = Math.floor(viewportWidth / (TILE_SIZE + GAP_SIZE))
    const rows = Math.ceil(viewportHeight / (TILE_SIZE + GAP_SIZE)) + 1
    const totalCells = Math.max(cols * rows, sortedAgents.length)

    const result: { agent: Agent | null }[] = sortedAgents.map(a => ({ agent: a }))
    for (let i = sortedAgents.length; i < totalCells; i++) {
      result.push({ agent: null })
    }
    return result
  }, [sortedAgents, viewportSize])

  const handleAgentClick = useCallback((agent: Agent) => {
    setSelectedAgent(prev => prev?.id === agent.id ? null : agent)
  }, [])

  const waitingCount = agents.filter(a => a.status === 'WAITING').length
  const pendingCount = agents.filter(a => a.status === 'PENDING').length
  const activeCount = agents.filter(a => a.status === 'ACTIVE').length
  const runningCount = agents.filter(isRunning).length
  const starvingCount = agents.filter(isStarving).length
  const selectedSiteObj = sites.find(s => s.id === selectedSite)
  const availableNodes = selectedSiteObj?.nodes || []

  return (
    <div className="h-screen w-screen flex flex-col bg-[#0d1117] text-white overflow-hidden relative">
      <style>{`
        @keyframes gradientPulse {
          0%, 100% { background-color: var(--color-base); }
          50% { background-color: var(--color-light); }
        }
        @keyframes glowPulse {
          0%, 100% {
            background-color: var(--color-base);
            box-shadow: 0 0 2px var(--color-glow), 0 0 4px var(--color-glow);
            opacity: 0.85;
          }
          50% {
            background-color: var(--color-light);
            box-shadow: 0 0 6px var(--color-glow), 0 0 12px var(--color-glow), 0 0 18px var(--color-glow);
            opacity: 1;
          }
        }
        .gradient-pulse { animation: gradientPulse 2s ease-in-out infinite; }
        .glow-pulse { animation: glowPulse 1.5s ease-in-out infinite; }
        @keyframes bottleneckPulse {
          0%, 100% { opacity: 0.7; }
          50% { opacity: 1; }
        }
        .bottleneck-pulse { animation: bottleneckPulse 1.5s ease-in-out infinite; }
        .hide-scrollbar::-webkit-scrollbar { display: none; }
        .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>

      {/* Header */}
      <header className="px-4 py-2 flex items-center justify-between border-b border-gray-800/50 shrink-0">
        <span className="text-sm font-bold tracking-wider" style={{ color: '#39d353' }}>Loop Factory</span>
        <div className="flex items-center gap-4 text-[10px]">
          <div className="flex items-center gap-1.5">
            <span className="opacity-50">SITE</span>
            <select
              value={selectedSite}
              onChange={(e) => setSelectedSite(e.target.value)}
              className="bg-gray-900 border border-gray-700 text-[10px] px-1 py-0.5 rounded"
            >
              <option value="all">All Sites</option>
              {sites.map(site => (
                <option key={site.id} value={site.id}>{site.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="opacity-50">NODE</span>
            <select
              value={selectedNode}
              onChange={(e) => setSelectedNode(e.target.value)}
              className="bg-gray-900 border border-gray-700 text-[10px] px-1 py-0.5 rounded"
            >
              <option value="all">All Nodes</option>
              {availableNodes.map(node => (
                <option key={node.id} value={node.id}>{node.name}</option>
              ))}
            </select>
          </div>
          <span className="opacity-30">|</span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm glow-pulse" style={{ '--color-base': COLORS.RUNNING.base, '--color-light': COLORS.RUNNING.light, '--color-glow': COLORS.RUNNING.glow } as React.CSSProperties} />
            <span style={{ color: COLORS.RUNNING.base }} className="font-medium">{runningCount}</span>
            <span className="opacity-40">RUNNING</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: COLORS.IDLE.base }} />
            <span style={{ color: COLORS.IDLE.base }} className="font-medium">{activeCount - runningCount - starvingCount}</span>
            <span className="opacity-40">IDLE</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: COLORS.STARVING.base }} />
            <span style={{ color: COLORS.STARVING.base }} className="font-medium">{starvingCount}</span>
            <span className="opacity-40">STARVING</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: COLORS.ACTIVE.base }} />
            <span style={{ color: COLORS.ACTIVE.base }} className="font-medium">{activeCount}</span>
            <span className="opacity-40">ACTIVE</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm gradient-pulse" style={{ '--color-base': COLORS.WAITING.base, '--color-light': COLORS.WAITING.light } as React.CSSProperties} />
            <span style={{ color: COLORS.WAITING.base }} className="font-medium">{waitingCount}</span>
            <span className="opacity-40">WAITING</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm gradient-pulse" style={{ '--color-base': COLORS.PENDING.base, '--color-light': COLORS.PENDING.light } as React.CSSProperties} />
            <span style={{ color: COLORS.PENDING.base }} className="font-medium">{pendingCount}</span>
            <span className="opacity-40">PENDING</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: COLORS.DESIGN.base }} />
            <span style={{ color: COLORS.DESIGN.base }} className="font-medium">{agents.filter(a => a.status === 'DESIGN').length}</span>
            <span className="opacity-40">DESIGN</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: COLORS.PROBATION.base }} />
            <span style={{ color: COLORS.PROBATION.base }} className="font-medium">{agents.filter(a => a.status === 'PROBATION').length}</span>
            <span className="opacity-40">PROBATION</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: COLORS.RETIRED.base }} />
            <span style={{ color: COLORS.RETIRED.light }} className="font-medium">{agents.filter(a => a.status === 'RETIRED').length}</span>
            <span className="opacity-40">RETIRED</span>
          </span>
          <span className="opacity-30">|</span>
          <span className="opacity-50">{agents.length} in view</span>
          <span className="opacity-30">|</span>
          <a href="/settings/agents" className="opacity-70 hover:opacity-100">Agent Settings</a>
          <a href="/settings/system" className="opacity-70 hover:opacity-100">System Settings</a>
        </div>
        <img src="/img/logo.webp" alt="AI Factory" className="h-6" />
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Agent Detail Panel (Resizable) */}
        {selectedAgent && (
          <AgentDetailPanel
            agent={selectedAgent}
            onClose={() => setSelectedAgent(null)}
            onActivate={(updatedAgent) => {
              setAgents(prev => prev.map(a => a.id === updatedAgent.id ? updatedAgent : a))
              setSelectedAgent(updatedAgent)
            }}
          />
        )}

        {/* Center: Grid */}
        <main ref={viewportRef} className="flex-1 overflow-auto p-4 hide-scrollbar">
          <div
            ref={containerRef}
            className="grid"
            style={{
              gridTemplateColumns: `repeat(auto-fill, ${TILE_SIZE}px)`,
              gap: `${GAP_SIZE}px`,
              gridAutoRows: `${TILE_SIZE}px`,
              width: '100%',
            }}
          >
            {gridWithPlaceholders.map((item, i) => (
              <AgentTile
                key={item.agent?.id || `empty-${i}`}
                agent={item.agent}
                isSelected={selectedAgent?.id === item.agent?.id}
                onClick={item.agent ? () => handleAgentClick(item.agent!) : undefined}
              />
            ))}
          </div>
        </main>

        {/* Right: Resource Panel */}
        <aside className="w-56 border-l border-gray-800/50 p-3 flex flex-col shrink-0 overflow-y-auto hide-scrollbar">
          {/* Resource Graphs */}
          <div className="flex flex-col gap-3">
            <ResourceGraph
              label="CPU"
              history={resourceHistory.cpu}
              color={RESOURCE_COLORS.CPU}
              limit={60}
              currentValue={`${(status?.cpu_percent || 0).toFixed(1)}%`}
            />
            <ResourceGraph
              label="Memory"
              history={resourceHistory.mem}
              color={RESOURCE_COLORS.Memory}
              limit={70}
              currentValue={`${((status?.memory_mb || 0) / 1024).toFixed(1)}/${(((status?.memory_mb || 0) + (status?.available_memory_mb || 0)) / 1024).toFixed(0)}GB`}
            />
            <ResourceGraph
              label="Disk"
              history={resourceHistory.hdd}
              color={RESOURCE_COLORS.Disk}
              limit={90}
              currentValue={`${(status?.disk_used_gb || 0).toFixed(0)}/${(status?.disk_total_gb || 0).toFixed(0)}GB`}
            />
            <ResourceGraph
              label="Claude (5h)"
              history={resourceHistory.claude5h}
              color={RESOURCE_COLORS.Token}
              limit={80}
              currentValue={`${(status?.claude_five_hour_percent || 0).toFixed(1)}%`}
              subValue={`${(100 - (status?.claude_five_hour_percent || 0)).toFixed(0)}% left`}
            />
            <ResourceGraph
              label="Human"
              history={resourceHistory.human}
              color={RESOURCE_COLORS.Human}
              limit={100}
              currentValue={`${pendingCount}/100`}
              subValue="pending"
            />
          </div>

          {/* Bottleneck Diagnosis Panel */}
          <div className="border-y border-gray-800/50 my-2 py-2">
            <BottleneckPanel data={bottleneckData} />
          </div>

          {/* Minimap - bottom right */}
          {needsMinimap && (
            <Minimap agents={sortedAgents} gridCols={gridCols} viewportRef={viewportRef} containerRef={containerRef} />
          )}
        </aside>
      </div>
    </div>
  )
}
