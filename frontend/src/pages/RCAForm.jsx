import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ChevronLeft, CheckCircle, AlertCircle } from 'lucide-react'
import { submitRCA } from '../api/client'

const CATEGORIES = [
  'HARDWARE_FAILURE', 'SOFTWARE_BUG', 'CONFIGURATION_ERROR',
  'CAPACITY_EXHAUSTION', 'NETWORK_ISSUE', 'HUMAN_ERROR',
  'THIRD_PARTY_DEPENDENCY', 'UNKNOWN',
]

function toLocalDatetimeValue(dt) {
  const d = dt || new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function RCAForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const now = new Date()
  const twoHoursAgo = new Date(now - 2 * 3600 * 1000)

  const [form, setForm] = useState({
    incident_start: toLocalDatetimeValue(twoHoursAgo),
    incident_end: toLocalDatetimeValue(now),
    root_cause_category: 'SOFTWARE_BUG',
    root_cause_description: '',
    fix_applied: '',
    prevention_steps: '',
    submitted_by: 'engineer',
  })
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await submitRCA(id, {
        ...form,
        incident_start: new Date(form.incident_start).toISOString(),
        incident_end: new Date(form.incident_end).toISOString(),
      })
      setSuccess(true)
      setTimeout(() => navigate(`/incident/${id}`), 1500)
    } catch (e) {
      setError(e.response?.data?.detail || JSON.stringify(e.response?.data) || 'Submission failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (success) {
    return (
      <div className="p-12 flex flex-col items-center gap-4 text-green-400">
        <CheckCircle size={48} />
        <p className="text-lg font-semibold">RCA submitted successfully!</p>
        <p className="text-sm text-gray-400">Redirecting to incident…</p>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <Link to={`/incident/${id}`} className="flex items-center gap-1 text-gray-400 hover:text-gray-200 text-sm mb-5">
        <ChevronLeft size={16} /> Back to Incident
      </Link>

      <h1 className="text-xl font-bold mb-1">Root Cause Analysis</h1>
      <p className="text-sm text-gray-400 mb-6">
        Complete RCA is required before closing this incident.
      </p>

      {error && (
        <div className="flex items-start gap-2 bg-red-900/40 border border-red-700 rounded p-3 mb-5 text-red-300 text-sm">
          <AlertCircle size={14} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="space-y-5">
        {/* Dates */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Incident Start *</label>
            <input
              type="datetime-local"
              value={form.incident_start}
              onChange={e => set('incident_start', e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Incident End *</label>
            <input
              type="datetime-local"
              value={form.incident_end}
              onChange={e => set('incident_end', e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {/* Category */}
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Root Cause Category *</label>
          <select
            value={form.root_cause_category}
            onChange={e => set('root_cause_category', e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
          >
            {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
          </select>
        </div>

        {/* Submitted by */}
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Submitted By</label>
          <input
            type="text"
            value={form.submitted_by}
            onChange={e => set('submitted_by', e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Textareas */}
        {[
          ['root_cause_description', 'Root Cause Description *', 'Describe the technical root cause in detail…'],
          ['fix_applied', 'Fix Applied *', 'Describe what was done to resolve the incident…'],
          ['prevention_steps', 'Prevention Steps *', 'How will we prevent this from happening again?'],
        ].map(([key, label, placeholder]) => (
          <div key={key}>
            <label className="block text-xs text-gray-400 mb-1.5">{label}</label>
            <textarea
              rows={4}
              value={form[key]}
              onChange={e => set(key, e.target.value)}
              placeholder={placeholder}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500 resize-none"
            />
          </div>
        ))}

        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded text-sm transition-colors"
        >
          {submitting ? 'Submitting…' : 'Submit RCA'}
        </button>
      </div>
    </div>
  )
}
