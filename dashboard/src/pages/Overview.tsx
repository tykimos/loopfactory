import { useCallback, useEffect, useMemo, useState } from 'react'

const PROMETHEUS_URL = 'https://prometheus.aifactory.space/api/v1/query'

const QUERY_DEFS = [
  { key: 'info', expr: 'nvidia_smi_gpu_info' },
  { key: 'usage', expr: 'nvidia_smi_utilization_gpu_ratio' },
  { key: 'memoryUtilization', expr: 'nvidia_smi_utilization_memory_ratio' },
  { key: 'memoryUsed', expr: 'nvidia_smi_memory_used_megabytes' },
  { key: 'memoryTotal', expr: 'nvidia_smi_memory_total_megabytes' },
  { key: 'temperature', expr: 'nvidia_smi_temperature_gpu' },
  { key: 'power', expr: 'nvidia_smi_power_usage_watts' },
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
  errorType?: string
  error?: string
}

interface GpuCardData {
  uuid: string
  site: string
  server: string
  name: string
  index?: string
  model?: string
  utilization?: number
  memoryUtilization?: number
  temperature?: number
  power?: number
  memoryUsed?: number
  memoryTotal?: number
  lastUpdated?: number
}

interface GpuMetricHistory {
  usage: number[]
  memory: number[]
  temperature: number[]
}

type GpuHistoryMap = Record<string, GpuMetricHistory>

const HISTORY_POINTS = 18

async function fetchPrometheus(query: string): Promise<PrometheusValue[]> {
  const params = new URLSearchParams({ query })
  const response = await fetch(`${PROMETHEUS_URL}?${params.toString()}`, {
    cache: 'no-store',
  })
  if (!response.ok) {
    throw new Error(`Prometheus responded with ${response.status}`)
  }
  const body: PrometheusResponse = await response.json()
  if (body.status !== 'success') {
    throw new Error(body.error || 'Prometheus query failed')
  }
  return body.data?.result || []
}

const toPercent = (raw: number): number | undefined => {
  if (Number.isNaN(raw)) return undefined
  const scaled = raw <= 1 ? raw * 100 : raw
  return Math.max(0, Math.min(100, scaled))
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

const formatPercent = (value?: number): string => {
  if (value == null || Number.isNaN(value)) return '--'
  return `${value.toFixed(0)}%`
}

const formatMegabytes = (value?: number): string => {
  if (value == null || Number.isNaN(value)) return '--'
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} GB`
  }
  return `${value.toFixed(0)} MB`
}

const relativeTime = (timestamp?: number | null): string => {
  if (!timestamp) return '—'
  const diff = Date.now() - timestamp
  if (diff < 10_000) return 'just now'
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

const compareIndex = (a?: string, b?: string): number => {
  const parse = (value?: string) => {
    if (!value) return Number.POSITIVE_INFINITY
    const parsed = parseInt(value, 10)
    return Number.isNaN(parsed) ? Number.POSITIVE_INFINITY : parsed
  }
  const parsedA = parse(a)
  const parsedB = parse(b)
  return parsedA - parsedB
}

const getServerLabel = (labels: Record<string, string>): string => {
  return (
    labels.server ||
    labels.hostname ||
    labels.instance?.split(':')[0] ||
    labels.node ||
    'Unknown node'
  )
}

const getGpuName = (labels: Record<string, string>): string => {
  return labels.name || labels.model || labels.product_name || 'GPU'
}

const getSiteLabel = (labels: Record<string, string>, server: string): string => {
  const direct =
    labels.site ||
    labels.site_name ||
    labels.site_id ||
    labels.region ||
    labels.dc
  if (direct) return direct
  const token = server.split(/[-_.]/).filter(Boolean)[0]
  return token || 'Unknown site'
}

export default function Overview() {
  const [gpus, setGpus] = useState<GpuCardData[]>([])
  const [gpuHistory, setGpuHistory] = useState<GpuHistoryMap>({})
  const [selectedGpu, setSelectedGpu] = useState<GpuCardData | null>(null)
  const [selectedSite, setSelectedSite] = useState<string>('all')
  const [selectedNode, setSelectedNode] = useState<string>('all')
  const [error, setError] = useState<string | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<number | null>(null)

  const fetchGpuData = useCallback(async () => {
    setIsRefreshing(true)
    try {
      const responses = await Promise.allSettled(
        QUERY_DEFS.map((def) => fetchPrometheus(def.expr))
      )

      const dataset: Partial<Record<QueryKey, PrometheusValue[]>> = {}
      responses.forEach((result, idx) => {
        const key = QUERY_DEFS[idx].key
        if (result.status === 'fulfilled') {
          dataset[key] = result.value
        } else {
          console.error(`Prometheus query failed for ${key}`, result.reason)
        }
      })

      const gpuMap: Record<string, GpuCardData> = {}
      let newestTimestamp = 0

      const ensureGpu = (entry: PrometheusValue): GpuCardData | null => {
        const labels = entry.metric || {}
        const uuid =
          labels.uuid || labels.UUID || labels.gpu_uuid || labels.device_uuid
        const fallbackId = uuid || `${labels.server || labels.instance || 'gpu'}-${labels.index || labels.gpu || labels.minor_number || '0'}`
        const id = fallbackId
        if (!id) return null

        const timestamp = entry.value?.[0] ? entry.value[0] * 1000 : undefined
        if (timestamp) {
          newestTimestamp = Math.max(newestTimestamp, timestamp)
        }

        let gpu = gpuMap[id]
        if (!gpu) {
          const server = getServerLabel(labels)
          gpu = {
            uuid: id,
            site: getSiteLabel(labels, server),
            server,
            name: getGpuName(labels),
            index: labels.index || labels.gpu || labels.minor_number || undefined,
            model: labels.model || labels.product_name || undefined,
            lastUpdated: timestamp,
          }
          gpuMap[id] = gpu
        } else if (timestamp) {
          gpu.lastUpdated = Math.max(gpu.lastUpdated ?? 0, timestamp)
        }

        if (!gpu.server || gpu.server === 'Unknown node') {
          gpu.server = getServerLabel(labels)
        }
        if (!gpu.site || gpu.site === 'Unknown site') {
          gpu.site = getSiteLabel(labels, gpu.server)
        }
        if ((!gpu.name || gpu.name === 'GPU') && getGpuName(labels)) {
          gpu.name = getGpuName(labels)
        }
        if (!gpu.index && (labels.index || labels.gpu || labels.minor_number)) {
          gpu.index = labels.index || labels.gpu || labels.minor_number
        }
        if (!gpu.model && (labels.model || labels.product_name)) {
          gpu.model = labels.model || labels.product_name
        }

        return gpu
      }

      ;(dataset.info ?? []).forEach((entry) => {
        ensureGpu(entry)
      })

      ;(dataset.usage ?? []).forEach((entry) => {
        const gpu = ensureGpu(entry)
        if (!gpu) return
        const raw = parseFloat(entry.value?.[1] ?? '')
        const percent = toPercent(raw)
        if (percent != null) {
          gpu.utilization = percent
        }
      })

      ;(dataset.memoryUtilization ?? []).forEach((entry) => {
        const gpu = ensureGpu(entry)
        if (!gpu) return
        const raw = parseFloat(entry.value?.[1] ?? '')
        const percent = toPercent(raw)
        if (percent != null) {
          gpu.memoryUtilization = percent
        }
      })

      ;(dataset.memoryUsed ?? []).forEach((entry) => {
        const gpu = ensureGpu(entry)
        if (!gpu) return
        const raw = parseFloat(entry.value?.[1] ?? '')
        if (!Number.isNaN(raw)) {
          gpu.memoryUsed = raw
        }
      })

      ;(dataset.memoryTotal ?? []).forEach((entry) => {
        const gpu = ensureGpu(entry)
        if (!gpu) return
        const raw = parseFloat(entry.value?.[1] ?? '')
        if (!Number.isNaN(raw)) {
          gpu.memoryTotal = raw
        }
      })

      ;(dataset.temperature ?? []).forEach((entry) => {
        const gpu = ensureGpu(entry)
        if (!gpu) return
        const raw = parseFloat(entry.value?.[1] ?? '')
        if (!Number.isNaN(raw)) {
          gpu.temperature = raw
        }
      })

      ;(dataset.power ?? []).forEach((entry) => {
        const gpu = ensureGpu(entry)
        if (!gpu) return
        const raw = parseFloat(entry.value?.[1] ?? '')
        if (!Number.isNaN(raw)) {
          gpu.power = raw
        }
      })

      const nextGpus = Object.values(gpuMap)
        .map((gpu) => {
          if (
            gpu.memoryUtilization == null &&
            gpu.memoryUsed != null &&
            gpu.memoryTotal
          ) {
            gpu.memoryUtilization = Math.max(
              0,
              Math.min(100, (gpu.memoryUsed / gpu.memoryTotal) * 100)
            )
          }
          return gpu
        })
        .sort((a, b) => {
          if (a.server === b.server) {
            return compareIndex(a.index, b.index)
          }
          return a.server.localeCompare(b.server)
        })

      setGpus(nextGpus)
      setGpuHistory((prev) => {
        const next: GpuHistoryMap = {}
        nextGpus.forEach((gpu) => {
          const previous = prev[gpu.uuid] ?? { usage: [], memory: [], temperature: [] }
          const usage = gpu.utilization ?? 0
          const memory = gpu.memoryUtilization ?? 0
          const temperature = Math.max(0, Math.min(100, gpu.temperature ?? 0))
          next[gpu.uuid] = {
            usage: [...previous.usage.slice(-(HISTORY_POINTS - 1)), usage],
            memory: [...previous.memory.slice(-(HISTORY_POINTS - 1)), memory],
            temperature: [...previous.temperature.slice(-(HISTORY_POINTS - 1)), temperature],
          }
        })
        return next
      })
      setSelectedGpu((prev) => {
        if (!prev) return null
        return nextGpus.find((gpu) => gpu.uuid === prev.uuid) || null
      })
      setLastUpdated(newestTimestamp || Date.now())
      setError(null)
    } catch (err) {
      console.error('Failed to load GPU metrics', err)
      setError((err as Error).message)
    } finally {
      setIsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchGpuData()
    const interval = setInterval(fetchGpuData, 10_000)
    return () => clearInterval(interval)
  }, [fetchGpuData])

  const nodeGroups = useMemo(() => {
    const groups: Record<string, { site: string; gpus: GpuCardData[] }> = {}
    gpus.forEach((gpu) => {
      const key = gpu.server || 'Unknown node'
      if (!groups[key]) {
        groups[key] = { site: gpu.site || 'Unknown site', gpus: [] }
      }
      groups[key].gpus.push(gpu)
    })
    return Object.entries(groups)
      .map(([server, entry]) => ({ server, site: entry.site, gpus: entry.gpus }))
      .sort((a, b) => a.server.localeCompare(b.server))
  }, [gpus])

  useEffect(() => {
    if (selectedSite === 'all') return
    const exists = nodeGroups.some((group) => group.site === selectedSite)
    if (!exists) {
      setSelectedSite('all')
    }
  }, [nodeGroups, selectedSite])

  useEffect(() => {
    if (selectedNode === 'all') return
    const exists = nodeGroups.some(
      (group) =>
        group.server === selectedNode &&
        (selectedSite === 'all' || group.site === selectedSite)
    )
    if (!exists) {
      setSelectedNode('all')
    }
  }, [nodeGroups, selectedNode, selectedSite])

  const filteredBySite = selectedSite === 'all'
    ? nodeGroups
    : nodeGroups.filter((group) => group.site === selectedSite)

  const filteredGroups = selectedNode === 'all'
    ? filteredBySite
    : filteredBySite.filter((group) => group.server === selectedNode)

  const summary = useMemo(() => {
    const total = gpus.length
    const avg =
      total === 0
        ? 0
        : gpus.reduce((sum, gpu) => sum + (gpu.utilization ?? 0), 0) / total
    const busy = gpus.filter((gpu) => (gpu.utilization ?? 0) >= 80).length
    const idle = gpus.filter(
      (gpu) => gpu.utilization != null && gpu.utilization < 15
    ).length
    const offline = gpus.filter((gpu) => gpu.utilization == null).length
    return { total, avg, busy, idle, offline }
  }, [gpus])

  const siteOptions = useMemo(
    () => Array.from(new Set(nodeGroups.map((group) => group.site))).sort((a, b) => a.localeCompare(b)),
    [nodeGroups]
  )

  const nodeOptions = useMemo(
    () => filteredBySite.map((group) => group.server),
    [filteredBySite]
  )

  const showInitialSpinner = isRefreshing && gpus.length === 0

  return (
    <div className="relative min-h-screen crt-screen crt-grid-bg">
      <div className={selectedGpu ? 'lg:pr-[320px]' : undefined}>
        <header className="border-b border-[#19313b] px-6 py-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between bg-[#071117]/90 backdrop-blur">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#2ce6a6] crt-glow">
              LoopFactory
            </p>
            <h1 className="text-2xl font-semibold text-[#b6ffe4]">GPU Control Tower</h1>
            <p className="text-sm crt-muted">
              Metrics directly from Prometheus (
              <a
                className="text-[#66f0c0] underline-offset-2 hover:underline"
                href="https://prometheus.aifactory.space/query"
                target="_blank"
                rel="noreferrer"
              >
                https
              </a>
              )
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
            <label className="text-xs font-medium text-[#9ce8d5]">
              Site
              <select
                value={selectedSite}
                onChange={(event) => {
                  setSelectedSite(event.target.value)
                  setSelectedNode('all')
                }}
                className="ml-2 rounded-md border border-[#19313b] bg-[#0b1419]/90 px-2 py-1 text-sm focus:border-[#2ce6a6] focus:outline-none"
              >
                <option value="all">All Sites</option>
                {siteOptions.map((site) => (
                  <option key={site} value={site}>
                    {site}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-medium text-[#9ce8d5]">
              Node
              <select
                value={selectedNode}
                onChange={(event) => setSelectedNode(event.target.value)}
                className="ml-2 rounded-md border border-[#19313b] bg-[#0b1419]/90 px-2 py-1 text-sm focus:border-[#2ce6a6] focus:outline-none"
              >
                <option value="all">All Nodes</option>
                {nodeOptions.map((node) => (
                  <option key={node} value={node}>
                    {node}
                  </option>
                ))}
              </select>
            </label>
            <div className="text-right text-xs crt-muted">
              <p>Last updated: {relativeTime(lastUpdated)}</p>
              <p className="text-[#4d786f]">Auto refresh 10s</p>
            </div>
            <button
              onClick={fetchGpuData}
              className="rounded-md border border-[#2ce6a6]/60 px-3 py-1 text-sm font-semibold text-[#9ce8d5] transition hover:bg-[#133429] hover:text-[#d8ffee] disabled:opacity-60"
              disabled={isRefreshing}
            >
              {isRefreshing ? 'Refreshing…' : 'Refresh now'}
            </button>
          </div>
        </header>

        <section className="grid gap-4 border-b border-[#19313b] bg-[#071117]/70 px-6 py-4 text-sm text-[#9ce8d5] sm:grid-cols-2 lg:grid-cols-4">
          <SummaryCard
            label="GPUs online"
            value={summary.total}
            sub={`${nodeGroups.length} nodes connected`}
          />
          <SummaryCard
            label="Average utilization"
            value={formatPercent(summary.avg)}
            sub="Across all GPUs"
          />
          <SummaryCard
            label="High load GPUs"
            value={summary.busy}
            sub=">= 80% usage"
          />
          <SummaryCard
            label="Idle / Offline"
            value={`${summary.idle} idle`}
            sub={`${summary.offline} offline`}
          />
        </section>

        <div className="flex flex-col gap-3 border-b border-[#19313b] px-6 py-3 text-xs crt-muted lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-6">
            <Legend color="#22c55e" label="< 55% Utilization" />
            <Legend color="#eab308" label="55-75% Utilization" />
            <Legend color="#f97316" label="75-90% Utilization" />
            <Legend color="#ef4444" label="> 90% Utilization" />
            <Legend color="#475569" label="No signal" />
          </div>
          {error && (
            <p className="text-[#ff8d8d]">Prometheus error: {error}</p>
          )}
        </div>

        <main className="max-h-[calc(100vh-220px)] overflow-y-auto px-6 pb-6 pt-4 hide-scrollbar">
          {showInitialSpinner && (
            <div className="flex h-64 items-center justify-center crt-muted">
              Loading GPU metrics…
            </div>
          )}
          {!showInitialSpinner && filteredGroups.length === 0 && (
            <div className="flex h-64 flex-col items-center justify-center gap-2 crt-muted">
              <p className="text-lg font-semibold text-[#b6ffe4]">No GPU metrics found</p>
              <p className="text-sm">
                Check Prometheus exporter status for the selected filter.
              </p>
            </div>
          )}
          <div className="flex flex-col gap-6">
            {filteredGroups.map((group) => (
              <section
                key={group.server}
                className="rounded-xl crt-panel p-4"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-wide crt-muted">
                      Node
                    </p>
                    <h2 className="text-xl font-semibold text-[#b6ffe4]">{group.server}</h2>
                  </div>
                  <p className="text-xs crt-muted">
                    {group.gpus.length} GPU
                    {group.gpus.length > 1 ? 's' : ''}
                  </p>
                </div>

                <div
                  className="mt-4 grid gap-3"
                  style={{
                    gridTemplateColumns:
                      'repeat(auto-fill, minmax(220px, 1fr))',
                  }}
                >
                  {group.gpus.map((gpu) => (
                    <GpuCard
                      key={gpu.uuid}
                      gpu={gpu}
                      history={gpuHistory[gpu.uuid] ?? { usage: [], memory: [], temperature: [] }}
                      isSelected={selectedGpu?.uuid === gpu.uuid}
                      onSelect={() => setSelectedGpu(gpu)}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </main>
      </div>

      {selectedGpu && (
        <aside className="fixed right-0 top-0 z-20 h-screen w-full max-w-sm border-l border-[#19313b] bg-[#081218]/95 px-5 py-6 backdrop-blur lg:w-[320px]">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide crt-muted">
                GPU Detail
              </p>
              <h3 className="text-lg font-semibold text-[#b6ffe4]">{selectedGpu.name}</h3>
              <p className="text-xs crt-muted">{selectedGpu.server}</p>
            </div>
            <button
              onClick={() => setSelectedGpu(null)}
              className="rounded-full border border-[#24505d] px-2 py-1 text-xs text-[#9ce8d5] transition hover:border-[#2ce6a6] hover:text-[#b6ffe4]"
            >
              Close
            </button>
          </div>
          <div className="mt-4 space-y-4 text-sm">
            <DetailRow label="Utilization" value={formatPercent(selectedGpu.utilization)} accent={usageColor(selectedGpu.utilization)} />
            <DetailRow label="Memory" value={`${formatPercent(selectedGpu.memoryUtilization)} (${formatMegabytes(selectedGpu.memoryUsed)} / ${formatMegabytes(selectedGpu.memoryTotal)})`} />
            <DetailRow label="Temperature" value={selectedGpu.temperature != null ? `${selectedGpu.temperature.toFixed(0)} °C` : '--'} />
            <DetailRow label="Power draw" value={selectedGpu.power != null ? `${selectedGpu.power.toFixed(0)} W` : '--'} />
            <DetailRow label="GPU UUID" value={selectedGpu.uuid} wrap />
            <DetailRow label="Model" value={selectedGpu.model || '—'} />
            <DetailRow label="Slot / Index" value={selectedGpu.index || '—'} />
            <DetailRow label="Last metric" value={relativeTime(selectedGpu.lastUpdated)} />
          </div>
        </aside>
      )}
    </div>
  )
}

function SummaryCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg crt-panel px-4 py-3">
      <p className="text-xs uppercase tracking-wide crt-muted">{label}</p>
      <p className="text-2xl font-semibold text-[#b6ffe4]">{value}</p>
      {sub && <p className="text-xs text-[#4d786f]">{sub}</p>}
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-2 text-xs">
      <span
        className="h-2.5 w-2.5 rounded-sm"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  )
}

function GpuCard({
  gpu,
  history,
  onSelect,
  isSelected,
}: {
  gpu: GpuCardData
  history: GpuMetricHistory
  onSelect: () => void
  isSelected: boolean
}) {
  const usageCurrent = gpu.utilization ?? 0
  const memoryCurrent = gpu.memoryUtilization ?? 0
  const temperatureCurrent = gpu.temperature ?? 0
  const usageSeries = [...Array(Math.max(HISTORY_POINTS - history.usage.length, 0)).fill(0), ...history.usage].slice(-HISTORY_POINTS)
  const memorySeries = [...Array(Math.max(HISTORY_POINTS - history.memory.length, 0)).fill(0), ...history.memory].slice(-HISTORY_POINTS)
  const temperatureSeries = [...Array(Math.max(HISTORY_POINTS - history.temperature.length, 0)).fill(0), ...history.temperature].slice(-HISTORY_POINTS)

  return (
    <button
      onClick={onSelect}
      className={`relative aspect-square rounded-lg border p-3 text-left transition hover:border-[#2ce6a6]/70 ${
        isSelected ? 'border-[#2ce6a6] shadow-[0_0_18px_rgba(44,230,166,0.35)]' : 'border-[#19313b]'
      }`}
      title={`${gpu.name} - ${gpu.server}`}
    >
      <div
        className="pointer-events-none absolute inset-0 rounded-lg"
        style={{
          background: `linear-gradient(140deg, rgba(8,17,23,0.96) 25%, ${usageColor(gpu.utilization)}20 100%)`,
        }}
      />
      <div className="relative z-10 flex h-full flex-col justify-between">
        <div className="flex items-center justify-between text-[11px] text-[#9ce8d5]">
          <span className="line-clamp-1 font-semibold">{gpu.name}</span>
          {gpu.index && (
            <span className="text-[#5c8f86]">
              #{gpu.index}
            </span>
          )}
        </div>
        <div className="mt-2 space-y-1.5">
          <MetricBarSeries
            label="USE"
            values={usageSeries}
            color={usageColor(usageCurrent)}
            suffix="%"
            displayValue={usageCurrent.toFixed(0)}
            keyPrefix={`${gpu.uuid}-usage`}
          />
          <MetricBarSeries
            label="MEM"
            values={memorySeries}
            color="#58a6ff"
            suffix="%"
            displayValue={memoryCurrent.toFixed(0)}
            keyPrefix={`${gpu.uuid}-memory`}
          />
          <MetricBarSeries
            label="TMP"
            values={temperatureSeries}
            color={temperatureColor(temperatureCurrent)}
            suffix="C"
            displayValue={temperatureCurrent.toFixed(0)}
            keyPrefix={`${gpu.uuid}-temperature`}
          />
        </div>
      </div>
    </button>
  )
}

function MetricBarSeries({
  label,
  values,
  color,
  suffix,
  displayValue,
  keyPrefix,
}: {
  label: string
  values: number[]
  color: string
  suffix: string
  displayValue: string
  keyPrefix: string
}) {
  return (
    <div className="rounded bg-[#071117]/70 px-1.5 py-1 border border-[#19313b]">
      <div className="mb-1 flex items-center justify-between text-[9px]">
        <span className="text-[#5c8f86]">{label}</span>
        <span style={{ color }}>{displayValue}{suffix}</span>
      </div>
      <div className="h-7 flex items-end gap-[2px]">
        {values.map((value, idx) => (
          <div
            key={`${keyPrefix}-${idx}`}
            className="flex-1 rounded-[1px]"
            style={{
              height: `${Math.max(value, 6)}%`,
              backgroundColor: idx === values.length - 1 ? color : `${color}66`,
              opacity: 0.35 + (idx / values.length) * 0.65,
            }}
          />
        ))}
      </div>
    </div>
  )
}

function DetailRow({
  label,
  value,
  accent,
  wrap,
}: {
  label: string
  value: string
  accent?: string
  wrap?: boolean
}) {
  return (
    <div className="rounded-lg border border-[#19313b] bg-[#0b1419]/70 p-3">
      <p className="text-xs uppercase tracking-wide text-[#5c8f86]">{label}</p>
      <p
        className={`text-base font-semibold ${wrap ? 'break-words text-sm' : ''}`}
        style={{ color: accent || '#b6ffe4' }}
      >
        {value}
      </p>
    </div>
  )
}
