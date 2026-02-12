import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RefreshCw } from 'lucide-react'

const PROMETHEUS_URL = 'https://prometheus.aifactory.space/api/v1/query'
const CELL_SIZE = 36
const CELL_GAP = 2
const HISTORY_POINTS = 10
const QUERY_TIMEOUT_MS = 8000

const QUERY_DEFS = [
  { key: 'info', expr: 'nvidia_smi_gpu_info' },
  { key: 'usage', expr: 'nvidia_smi_utilization_gpu_ratio' },
  { key: 'memoryUtilization', expr: 'nvidia_smi_utilization_memory_ratio' },
  { key: 'temperature', expr: 'nvidia_smi_temperature_gpu' },
] as const

type QueryKey = (typeof QUERY_DEFS)[number]['key']

interface PrometheusValue {
  metric: Record<string, string>
  value: [number, string]
}

interface PrometheusResponse {
  status: 'success' | 'error'
  data: {
    resultType: string
    result: PrometheusValue[]
  }
  error?: string
}

interface GridGpuData {
  uuid: string
  server: string
  name: string
  index?: string
  usage?: number
  memory?: number
  temperature?: number
}

interface MetricHistory {
  usage: number[]
  memory: number[]
  temperature: number[]
}

type HistoryMap = Record<string, MetricHistory>

async function fetchPrometheus(query: string): Promise<PrometheusValue[]> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), QUERY_TIMEOUT_MS)
  const params = new URLSearchParams({ query })
  try {
    const response = await fetch(`${PROMETHEUS_URL}?${params.toString()}`, {
      cache: 'no-store',
      signal: controller.signal,
    })
    if (!response.ok) {
      throw new Error(`Prometheus responded with ${response.status}`)
    }
    const body: PrometheusResponse = await response.json()
    if (body.status !== 'success') {
      throw new Error(body.error || 'Prometheus query failed')
    }
    return body.data?.result || []
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('Prometheus request timed out')
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

const toPercent = (raw: number): number | undefined => {
  if (Number.isNaN(raw)) return undefined
  const scaled = raw <= 1 ? raw * 100 : raw
  return Math.max(0, Math.min(100, scaled))
}

const normalizeTemperature = (value?: number): number => {
  if (value == null || Number.isNaN(value)) return 0
  return Math.max(0, Math.min(100, value))
}

const usageColor = (value?: number): string => {
  if (value == null) return '#475569'
  if (value >= 90) return '#ef4444'
  if (value >= 75) return '#f97316'
  if (value >= 55) return '#eab308'
  return '#22c55e'
}

const temperatureColor = (value?: number): string => {
  if (value == null) return '#475569'
  if (value >= 85) return '#ef4444'
  if (value >= 75) return '#f97316'
  if (value >= 65) return '#eab308'
  return '#22c55e'
}

const compareIndex = (a?: string, b?: string): number => {
  const toInt = (value?: string) => {
    if (!value) return Number.POSITIVE_INFINITY
    const parsed = parseInt(value, 10)
    return Number.isNaN(parsed) ? Number.POSITIVE_INFINITY : parsed
  }
  return toInt(a) - toInt(b)
}

function MetricMiniRow({
  values,
  color,
  keyPrefix,
}: {
  values: number[]
  color: string
  keyPrefix: string
}) {
  return (
    <div className="h-[4px] flex items-end gap-[1px]">
      {values.map((value, idx) => (
        <div
          key={`${keyPrefix}-${idx}`}
          className="flex-1 rounded-[1px]"
          style={{
            height: `${Math.max(value, 6)}%`,
            backgroundColor: idx === values.length - 1 ? color : `${color}66`,
            opacity: 0.3 + (idx / values.length) * 0.7,
          }}
        />
      ))}
    </div>
  )
}

function GridCell({ gpu, history }: { gpu: GridGpuData | null; history?: MetricHistory }) {
  if (!gpu) {
    return (
      <div className="border border-[#0f2129] bg-[#061017] rounded-[2px]" />
    )
  }

  const usageSeries = [...Array(Math.max(HISTORY_POINTS - (history?.usage.length ?? 0), 0)).fill(0), ...(history?.usage ?? [])].slice(-HISTORY_POINTS)
  const memorySeries = [...Array(Math.max(HISTORY_POINTS - (history?.memory.length ?? 0), 0)).fill(0), ...(history?.memory ?? [])].slice(-HISTORY_POINTS)
  const temperatureSeries = [...Array(Math.max(HISTORY_POINTS - (history?.temperature.length ?? 0), 0)).fill(0), ...(history?.temperature ?? [])].slice(-HISTORY_POINTS)

  const usage = gpu.usage ?? 0
  const temperature = gpu.temperature ?? 0

  return (
    <div
      className="rounded-[2px] border border-[#17313a] bg-[#08131a] p-[2px] overflow-hidden"
      title={`${gpu.server} / ${gpu.name}${gpu.index ? ` #${gpu.index}` : ''}`}
    >
      <div className="h-full flex flex-col gap-[1px]">
        <MetricMiniRow
          values={usageSeries}
          color={usageColor(usage)}
          keyPrefix={`${gpu.uuid}-use`}
        />
        <MetricMiniRow
          values={memorySeries}
          color="#58a6ff"
          keyPrefix={`${gpu.uuid}-mem`}
        />
        <MetricMiniRow
          values={temperatureSeries}
          color={temperatureColor(temperature)}
          keyPrefix={`${gpu.uuid}-tmp`}
        />
      </div>
    </div>
  )
}

export default function GridView() {
  const [gpus, setGpus] = useState<GridGpuData[]>([])
  const [history, setHistory] = useState<HistoryMap>({})
  const [lastUpdated, setLastUpdated] = useState<number | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const viewportRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const minimapRef = useRef<HTMLDivElement>(null)
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, width: 100, height: 100 })

  const fetchData = useCallback(async () => {
    setIsRefreshing(true)
    try {
      const responses = await Promise.allSettled(
        QUERY_DEFS.map((def) => fetchPrometheus(def.expr))
      )

      const dataset: Partial<Record<QueryKey, PrometheusValue[]>> = {}
      const failedQueries: string[] = []
      responses.forEach((result, idx) => {
        if (result.status === 'fulfilled') {
          dataset[QUERY_DEFS[idx].key] = result.value
        } else {
          failedQueries.push(QUERY_DEFS[idx].key)
        }
      })

      const gpuMap: Record<string, GridGpuData> = {}
      const ensureGpu = (entry: PrometheusValue): GridGpuData | null => {
        const labels = entry.metric || {}
        const uuid =
          labels.uuid || labels.UUID || labels.gpu_uuid || labels.device_uuid ||
          `${labels.server || labels.instance || 'gpu'}-${labels.index || labels.gpu || labels.minor_number || '0'}`
        if (!uuid) return null

        let gpu = gpuMap[uuid]
        if (!gpu) {
          gpu = {
            uuid,
            server: labels.server || labels.hostname || labels.instance?.split(':')[0] || 'Unknown node',
            name: labels.name || labels.model || labels.product_name || 'GPU',
            index: labels.index || labels.gpu || labels.minor_number || undefined,
          }
          gpuMap[uuid] = gpu
        }
        return gpu
      }

      ;(dataset.info ?? []).forEach((entry) => {
        ensureGpu(entry)
      })
      ;(dataset.usage ?? []).forEach((entry) => {
        const gpu = ensureGpu(entry)
        if (!gpu) return
        const value = toPercent(parseFloat(entry.value?.[1] ?? ''))
        if (value != null) gpu.usage = value
      })
      ;(dataset.memoryUtilization ?? []).forEach((entry) => {
        const gpu = ensureGpu(entry)
        if (!gpu) return
        const value = toPercent(parseFloat(entry.value?.[1] ?? ''))
        if (value != null) gpu.memory = value
      })
      ;(dataset.temperature ?? []).forEach((entry) => {
        const gpu = ensureGpu(entry)
        if (!gpu) return
        const value = parseFloat(entry.value?.[1] ?? '')
        if (!Number.isNaN(value)) gpu.temperature = value
      })

      const nextGpus = Object.values(gpuMap).sort((a, b) => {
        if (a.server === b.server) return compareIndex(a.index, b.index)
        return a.server.localeCompare(b.server)
      })

      setGpus(nextGpus)
      setHistory((prev) => {
        const next: HistoryMap = {}
        nextGpus.forEach((gpu) => {
          const old = prev[gpu.uuid] ?? { usage: [], memory: [], temperature: [] }
          next[gpu.uuid] = {
            usage: [...old.usage.slice(-(HISTORY_POINTS - 1)), gpu.usage ?? 0],
            memory: [...old.memory.slice(-(HISTORY_POINTS - 1)), gpu.memory ?? 0],
            temperature: [...old.temperature.slice(-(HISTORY_POINTS - 1)), normalizeTemperature(gpu.temperature)],
          }
        })
        return next
      })
      setLastUpdated(Date.now())
      setError(
        failedQueries.length > 0
          ? `Some metric queries failed: ${failedQueries.join(', ')}`
          : null
      )
    } catch (err) {
      console.error('Failed to fetch GridView metrics', err)
      setError((err as Error).message)
    } finally {
      setIsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10_000)
    return () => clearInterval(interval)
  }, [fetchData])

  const gridCols = useMemo(() => {
    if (gpus.length === 0) return 1
    return Math.max(8, Math.ceil(Math.sqrt(gpus.length)))
  }, [gpus.length])

  const gridRows = useMemo(() => {
    if (gpus.length === 0) return 1
    return Math.ceil(gpus.length / gridCols)
  }, [gpus.length, gridCols])

  const cells = useMemo(() => {
    const total = gridCols * gridRows
    const filled: (GridGpuData | null)[] = [...gpus]
    while (filled.length < total) filled.push(null)
    return filled
  }, [gpus, gridCols, gridRows])

  useEffect(() => {
    const updateViewBox = () => {
      if (!viewportRef.current || !contentRef.current) return
      const vp = viewportRef.current
      const ct = contentRef.current
      setViewBox({
        x: ct.scrollWidth > 0 ? (vp.scrollLeft / ct.scrollWidth) * 100 : 0,
        y: ct.scrollHeight > 0 ? (vp.scrollTop / ct.scrollHeight) * 100 : 0,
        width: ct.scrollWidth > 0 ? (vp.clientWidth / ct.scrollWidth) * 100 : 100,
        height: ct.scrollHeight > 0 ? (vp.clientHeight / ct.scrollHeight) * 100 : 100,
      })
    }
    const vp = viewportRef.current
    if (!vp) return
    vp.addEventListener('scroll', updateViewBox)
    window.addEventListener('resize', updateViewBox)
    const timer = setTimeout(updateViewBox, 50)
    return () => {
      clearTimeout(timer)
      vp.removeEventListener('scroll', updateViewBox)
      window.removeEventListener('resize', updateViewBox)
    }
  }, [gridCols, gridRows, cells.length])

  const handleMinimapClick = (e: React.MouseEvent) => {
    if (!minimapRef.current || !viewportRef.current || !contentRef.current) return
    const rect = minimapRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top) / rect.height
    viewportRef.current.scrollTo({
      left: x * contentRef.current.scrollWidth - viewportRef.current.clientWidth / 2,
      top: y * contentRef.current.scrollHeight - viewportRef.current.clientHeight / 2,
      behavior: 'smooth',
    })
  }

  return (
    <div className="h-screen flex flex-col crt-screen bg-[#050a0d]">
      <header className="shrink-0 px-4 py-3 border-b border-[#19313b] bg-[#071117]/90 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold crt-title crt-glow">GridView</h2>
          <p className="text-[11px] crt-muted">
            전체 GPU 동적 그리드 ({gridCols} x {gridRows}) | 셀당 USE/MEM/TMP 3단 시계열
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs crt-muted">
              Updated {new Date(lastUpdated).toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchData}
            disabled={isRefreshing}
            className="terminal-btn rounded-md px-3 py-1 text-xs flex items-center gap-2 disabled:opacity-60"
          >
            <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </header>

      {error && (
        <div className="shrink-0 px-4 py-2 text-xs text-[#ff8d8d] border-b border-[#3a1f25] bg-[#1d1115]">
          Prometheus error: {error}
        </div>
      )}

      <div ref={viewportRef} className="relative flex-1 overflow-auto p-3 hide-scrollbar">
        {!isRefreshing && gpus.length === 0 && (
          <div className="mb-3 rounded-md border border-[#3a1f25] bg-[#1d1115] px-3 py-2 text-xs text-[#ffb0b0]">
            GPU 메트릭이 0건입니다. Prometheus 접근/CORS/네트워크 상태를 확인해 주세요.
          </div>
        )}
        <div
          ref={contentRef}
          className="grid w-max"
          style={{
            gridTemplateColumns: `repeat(${gridCols}, ${CELL_SIZE}px)`,
            gridTemplateRows: `repeat(${gridRows}, ${CELL_SIZE}px)`,
            gap: `${CELL_GAP}px`,
          }}
        >
          {cells.map((gpu, idx) => (
            <GridCell
              key={gpu ? gpu.uuid : `empty-${idx}`}
              gpu={gpu}
              history={gpu ? history[gpu.uuid] : undefined}
            />
          ))}
        </div>

        <div className="fixed right-5 bottom-5 z-20 crt-panel rounded-md p-2">
          <div className="text-[10px] crt-muted mb-1">Minimap</div>
          <div
            ref={minimapRef}
            className="relative cursor-pointer border border-[#19313b] bg-[#061017]"
            style={{ width: 180, height: 180 }}
            onClick={handleMinimapClick}
          >
            <div
              className="grid w-full h-full"
              style={{ gridTemplateColumns: `repeat(${gridCols}, 1fr)` }}
            >
              {cells.map((gpu, idx) => (
                <div
                  key={gpu ? `${gpu.uuid}-minimap` : `empty-minimap-${idx}`}
                  style={{
                    backgroundColor: gpu ? usageColor(gpu.usage) : '#061017',
                    opacity: gpu ? 0.9 : 0.25,
                  }}
                />
              ))}
            </div>
            <div
              className="absolute border border-white/70 bg-white/10 pointer-events-none"
              style={{
                left: `${viewBox.x}%`,
                top: `${viewBox.y}%`,
                width: `${Math.max(viewBox.width, 4)}%`,
                height: `${Math.max(viewBox.height, 4)}%`,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

