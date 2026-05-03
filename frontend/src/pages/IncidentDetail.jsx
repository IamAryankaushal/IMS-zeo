import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { formatDistanceToNow, format } from 'date-fns'
import { ChevronLeft, AlertCircle, ArrowRight, FileText } from 'lucide-react'
import {
  fetchWorkItem, fetchWorkItemSignals, transitionWorkItem
} from '../api/client'
import { PriorityBadge, StatusBadge } from '../components/Badges'

const TRANSITIONS = {
  OPEN: ['INVESTIGATING'],
  INVESTIGATING: ['RESOLVED', 'OPEN'],
  RESOLVED: ['CLOSED', 'INVESTIGATING'],
  CLOSED: [],
}

export default function IncidentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [item, setItem] = useState(null)
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [transitioning, setTransitioning] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const [wi, sigs] = await Promise.all([
          fetchWorkItem(id),
          fetchWorkItemSignals(id),
        ])
        setItem(wi)
        setSignals(sigs)
      } catch (e) {
        setError(e.response?.data?.detail || 'Failed to load incident')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  const handleTransition = async (status) => {
    if (status === 'CLOSED' && !item.rca) {
      navigate(`/incident/${id}/rca`)
      return
    }
    setTransitioning(true)
    try {
      const updated = await transitionWorkItem(id, status)
      setItem(updated)
    } catch (e) {
      setError(e.response?.data?.detail || 'Transition failed')
    } finally {
      setTransitioning(false)
    }
  }

  if (loading) return <div className="p-8 text-gray-400">Loading…</div>
  if (!item) return <div className="p-8 text-red-400">{error}</div>

  const allowed = TRANSITIONS[item.status] || []

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Back */}
      <Link to="/" className="flex items-center gap-1 text-gray-400 hover:text-gray-200 text-sm mb-5">
        <ChevronLeft size={16} /> Back to Dashboard
      </Link>

      {error && (
        <div className="flex items-center gap-2 bg-red-900/40 border border-red-700 rounded p-3 mb-4 text-red-300 text-sm">
          <AlertCircle size={14} /> {error}
        </div>
      )}

      {/* Header card */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <PriorityBadge priority={item.priority} />
              <StatusBadge status={item.status} />
            </div>
            <h1 className="text-xl font-bold text-gray-100 mb-1">{item.title}</h1>
            <p className="text-gray-400 text-sm font-mono">{item.component_id}</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            {item.status !== 'CLOSED' && (
              <Link
                to={`/incident/${id}/rca`}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-800 hover:bg-blue-700 rounded text-sm text-blue-200"
              >
                <FileText size={14} />
                {item.rca ? 'View RCA' : 'Submit RCA'}
              </Link>
            )}
            {allowed.map(s => (
              <button
                key={s}
                onClick={() => handleTransition(s)}
                disabled={transitioning}
                className="flex items-center gap-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm disabled:opacity-50"
              >
                <ArrowRight size={14} />
                → {s}
              </button>
            ))}
          </div>
        </div>

        {/* Metadata grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5 pt-4 border-t border-gray-800">
          {[
            ['Signals', item.signal_count.toLocaleString()],
            ['MTTR', item.mttr_seconds != null ? `${Math.round(item.mttr_seconds / 60)}m` : '—'],
            ['First signal', format(new Date(item.first_signal_at), 'MMM d, HH:mm')],
            ['Age', formatDistanceToNow(new Date(item.created_at), { addSuffix: true })],
          ].map(([label, val]) => (
            <div key={label}>
              <p className="text-xs text-gray-500 mb-0.5">{label}</p>
              <p className="text-sm font-medium text-gray-200">{val}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Signals from MongoDB */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
          <h2 className="font-semibold text-sm">Raw Signals ({signals.length})</h2>
          <span className="text-xs text-gray-500">from MongoDB audit log</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-left">
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-4 py-2 font-medium">Error Type</th>
                <th className="px-4 py-2 font-medium">Message</th>
                <th className="px-4 py-2 font-medium">Latency</th>
              </tr>
            </thead>
            <tbody>
              {signals.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-6 text-center text-gray-500">No signals yet</td></tr>
              )}
              {signals.map(sig => (
                <tr key={sig.id} className="border-b border-gray-800/40 hover:bg-gray-800/30">
                  <td className="px-4 py-2 text-gray-400 whitespace-nowrap">
                    {format(new Date(sig.timestamp), 'HH:mm:ss.SSS')}
                  </td>
                  <td className="px-4 py-2 font-mono text-amber-400">{sig.error_type}</td>
                  <td className="px-4 py-2 text-gray-300 max-w-xs truncate">{sig.message}</td>
                  <td className="px-4 py-2 text-gray-400">
                    {sig.latency_ms != null ? `${sig.latency_ms}ms` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* RCA summary if present */}
      {item.rca && (
        <div className="mt-5 bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h2 className="font-semibold mb-3 text-sm flex items-center gap-2">
            <FileText size={14} className="text-blue-400" />
            Root Cause Analysis
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-gray-500 text-xs mb-1">Category</p>
              <p className="text-gray-200">{item.rca.root_cause_category}</p>
            </div>
            <div>
              <p className="text-gray-500 text-xs mb-1">Submitted by</p>
              <p className="text-gray-200">{item.rca.submitted_by}</p>
            </div>
            <div className="sm:col-span-2">
              <p className="text-gray-500 text-xs mb-1">Root cause</p>
              <p className="text-gray-300">{item.rca.root_cause_description}</p>
            </div>
            <div className="sm:col-span-2">
              <p className="text-gray-500 text-xs mb-1">Fix applied</p>
              <p className="text-gray-300">{item.rca.fix_applied}</p>
            </div>
            <div className="sm:col-span-2">
              <p className="text-gray-500 text-xs mb-1">Prevention steps</p>
              <p className="text-gray-300">{item.rca.prevention_steps}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
