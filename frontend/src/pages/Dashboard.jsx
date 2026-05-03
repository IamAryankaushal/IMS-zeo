import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { RefreshCw, AlertCircle, Filter } from 'lucide-react'
import { fetchWorkItems } from '../api/client'
import { PriorityBadge, StatusBadge } from '../components/Badges'

const STATUS_OPTS = ['', 'OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED']
const PRIORITY_OPTS = ['', 'P0', 'P1', 'P2', 'P3']

export default function Dashboard() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)

  const load = useCallback(async () => {
    try {
      const data = await fetchWorkItems({
        status_filter: statusFilter || undefined,
        priority_filter: priorityFilter || undefined,
      })
      setItems(data.items)
      setTotal(data.total)
      setError(null)
    } catch (e) {
      setError('Failed to load incidents. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, priorityFilter])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [load, autoRefresh])

  const priorityOrder = { P0: 0, P1: 1, P2: 2, P3: 3 }
  const sorted = [...items].sort((a, b) => {
    const pd = priorityOrder[a.priority] - priorityOrder[b.priority]
    if (pd !== 0) return pd
    return new Date(b.created_at) - new Date(a.created_at)
  })

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Incident Dashboard</h1>
          <p className="text-gray-400 text-sm mt-0.5">{total} total incidents</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            Auto-refresh (5s)
          </label>
          <button
            onClick={load}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded text-sm"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-gray-500" />
          <span className="text-sm text-gray-400">Filter:</span>
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200"
        >
          {STATUS_OPTS.map(s => <option key={s} value={s}>{s || 'All statuses'}</option>)}
        </select>
        <select
          value={priorityFilter}
          onChange={e => setPriorityFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200"
        >
          {PRIORITY_OPTS.map(p => <option key={p} value={p}>{p || 'All priorities'}</option>)}
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 bg-red-900/40 border border-red-700 rounded p-4 mb-4 text-red-300">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-gray-400 text-left">
              <th className="px-4 py-3 font-medium">Priority</th>
              <th className="px-4 py-3 font-medium">Component</th>
              <th className="px-4 py-3 font-medium">Title</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Signals</th>
              <th className="px-4 py-3 font-medium">MTTR</th>
              <th className="px-4 py-3 font-medium">Age</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">Loading…</td></tr>
            )}
            {!loading && sorted.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">No incidents found</td></tr>
            )}
            {sorted.map(item => (
              <tr
                key={item.id}
                className="border-b border-gray-800/60 hover:bg-gray-800/40 transition-colors"
              >
                <td className="px-4 py-3">
                  <PriorityBadge priority={item.priority} />
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-300">
                  {item.component_id}
                </td>
                <td className="px-4 py-3">
                  <Link
                    to={`/incident/${item.id}`}
                    className="text-blue-400 hover:text-blue-300 hover:underline"
                  >
                    {item.title}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={item.status} />
                </td>
                <td className="px-4 py-3 text-gray-300">{item.signal_count.toLocaleString()}</td>
                <td className="px-4 py-3 text-gray-300">
                  {item.mttr_seconds != null
                    ? `${Math.round(item.mttr_seconds / 60)}m`
                    : '—'}
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs">
                  {formatDistanceToNow(new Date(item.created_at), { addSuffix: true })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
