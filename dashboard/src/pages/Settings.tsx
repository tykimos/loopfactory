import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Save, RefreshCw } from 'lucide-react'

interface Config {
  system: {
    max_concurrent_agents: string
    cpu_threshold_high: number
    cpu_threshold_low: number
    memory_limit_per_agent_mb: number
  }
  scheduling: {
    base_interval_minutes: number
    jitter_minutes: number
  }
  activity_monitoring: {
    check_interval_minutes: number
    idle_threshold_minutes: number
    warning_threshold_hours: number
    critical_threshold_hours: number
    auto_retire_inactive_hours: number
  }
  lifecycle: {
    probation_trigger_days: number
    probation_duration_hours: number
    auto_retire: boolean
    auto_create_replacement: boolean
  }
}

export default function SettingsPage() {
  const [config, setConfig] = useState<Config | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const fetchConfig = async () => {
    try {
      const response = await fetch('/api/system/config')
      if (response.ok) {
        setConfig(await response.json())
      }
    } catch (err) {
      console.error('Failed to fetch config:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchConfig()
  }, [])

  const handleSave = async () => {
    if (!config) return

    setSaving(true)
    setMessage(null)

    try {
      const response = await fetch('/api/system/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })

      if (response.ok) {
        setMessage('Configuration saved successfully!')
      } else {
        setMessage('Failed to save configuration')
      }
    } catch (err) {
      setMessage('Error saving configuration')
    } finally {
      setSaving(false)
    }
  }

  const updateConfig = (section: string, key: string, value: any) => {
    if (!config) return
    setConfig({
      ...config,
      [section]: {
        ...config[section as keyof Config],
        [key]: value
      }
    })
  }

  if (loading) return <div className="p-8 text-center">Loading...</div>

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <SettingsIcon />
          Settings
        </h2>
        <div className="flex gap-2">
          <button
            onClick={fetchConfig}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            <RefreshCw size={16} />
            Reload
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            <Save size={16} />
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>

      {message && (
        <div className={`mb-4 p-4 rounded-lg ${message.includes('success') ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
          {message}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4">System</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-500 mb-1">CPU Threshold (High)</label>
              <input
                type="number"
                value={config?.system.cpu_threshold_high ?? 85}
                onChange={e => updateConfig('system', 'cpu_threshold_high', Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-500 mb-1">Memory per Agent (MB)</label>
              <input
                type="number"
                value={config?.system.memory_limit_per_agent_mb ?? 256}
                onChange={e => updateConfig('system', 'memory_limit_per_agent_mb', Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
          </div>
        </div>

        {/* Scheduling Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4">Scheduling</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-500 mb-1">Base Interval (minutes)</label>
              <input
                type="number"
                value={config?.scheduling.base_interval_minutes ?? 60}
                onChange={e => updateConfig('scheduling', 'base_interval_minutes', Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-500 mb-1">Jitter (minutes)</label>
              <input
                type="number"
                value={config?.scheduling.jitter_minutes ?? 8}
                onChange={e => updateConfig('scheduling', 'jitter_minutes', Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
          </div>
        </div>

        {/* Activity Monitoring */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4">Activity Monitoring</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-500 mb-1">Idle Threshold (minutes)</label>
              <input
                type="number"
                value={config?.activity_monitoring.idle_threshold_minutes ?? 90}
                onChange={e => updateConfig('activity_monitoring', 'idle_threshold_minutes', Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-500 mb-1">Auto-Retire (hours)</label>
              <input
                type="number"
                value={config?.activity_monitoring.auto_retire_inactive_hours ?? 18}
                onChange={e => updateConfig('activity_monitoring', 'auto_retire_inactive_hours', Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
          </div>
        </div>

        {/* Lifecycle */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4">Lifecycle</h3>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={config?.lifecycle.auto_retire ?? true}
                onChange={e => updateConfig('lifecycle', 'auto_retire', e.target.checked)}
                className="w-4 h-4"
              />
              <label className="text-sm">Enable Auto-Retire</label>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={config?.lifecycle.auto_create_replacement ?? true}
                onChange={e => updateConfig('lifecycle', 'auto_create_replacement', e.target.checked)}
                className="w-4 h-4"
              />
              <label className="text-sm">Auto-Create Replacement Agent</label>
            </div>
            <div>
              <label className="block text-sm text-gray-500 mb-1">Probation Duration (hours)</label>
              <input
                type="number"
                value={config?.lifecycle.probation_duration_hours ?? 48}
                onChange={e => updateConfig('lifecycle', 'probation_duration_hours', Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
