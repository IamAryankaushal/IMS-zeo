import { useState } from 'react'
import { CheckCircle, Send, Zap } from 'lucide-react'
import { ingestSignal } from '../api/client'

const PRESETS = [
  {
    label: 'RDBMS Outage (P0)',
    payload: {
      component_id: 'RDBMS_PRIMARY_01',
      component_type: 'RDBMS',
      error_type: 'CONNECTION_REFUSED',
      message: 'Primary PostgreSQL instance is unreachable. Connection pool exhausted.',
      latency_ms: 5000,
    },
  },
  {
    label: 'Cache Degradation (P2)',
    payload: {
      component_id: 'CACHE_CLUSTER_01',
      component_type: 'CACHE',
      error_type: 'CACHE_MISS_STORM',
      message: 'Redis cluster reporting 90% cache miss rate. Possible node failure.',
      latency_ms: 250,
    },
  },
  {
    label: 'Kafka Queue Failure (P1)',
    payload: {
      component_id: 'KAFKA_BROKER_01',
      component_type: 'QUEUE',
      error_type: 'PARTITION_OFFLINE',
      message: 'Kafka broker 01 partition 3 is offline. Consumer lag: 450k messages.',
      latency_ms: null,
    },
  },
  {
    label: 'MCP Host Failure (P1)',
    payload: {
      component_id: 'MCP_HOST_PROD',
      component_type: 'MCP',
      error_type: 'HEALTH_CHECK_FAILED',
      message: 'MCP host failed 3 consecutive health checks. Removing from pool.',
      latency_ms: 2000,
    },
  },
]

export default function IngestTest() {
  const [results, setResults] = useState([])
  const [custom, setCustom] = useState(JSON.stringify(PRESETS[0].payload, null, 2))
  const [sending, setSending] = useState(false)

  const send = async (payload) => {
    setSending(true)
    try {
      const res = await ingestSignal(payload)
      setResults(r => [{ ...res, ts: new Date().toISOString(), payload }, ...r.slice(0, 19)])
    } catch (e) {
      setResults(r => [
        { accepted: false, error: e.response?.data?.detail || 'Error', ts: new Date().toISOString() },
        ...r.slice(0, 19),
      ])
    } finally {
      setSending(false)
    }
  }

  const sendBurst = async () => {
    setSending(true)
    const preset = PRESETS[1].payload
    const promises = Array.from({ length: 20 }, () => ingestSignal(preset))
    const results = await Promise.allSettled(promises)
    const accepted = results.filter(r => r.status === 'fulfilled' && r.value.accepted).length
    setResults(r => [{
      accepted: true,
      burst: true,
      accepted_count: accepted,
      ts: new Date().toISOString(),
    }, ...r.slice(0, 19)])
    setSending(false)
  }

  const sendCustom = async () => {
    try {
      const payload = JSON.parse(custom)
      await send(payload)
    } catch {
      setResults(r => [{ accepted: false, error: 'Invalid JSON', ts: new Date().toISOString() }, ...r])
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold mb-1">Signal Ingestion Test</h1>
      <p className="text-sm text-gray-400 mb-6">Simulate failure events across the stack</p>

      {/* Presets */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
        {PRESETS.map(p => (
          <button
            key={p.label}
            onClick={() => send(p.payload)}
            disabled={sending}
            className="flex items-center gap-2 px-4 py-3 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-sm text-left disabled:opacity-50 transition-colors"
          >
            <Send size={14} className="shrink-0 text-blue-400" />
            <div>
              <p className="font-medium text-gray-200">{p.label}</p>
              <p className="text-xs text-gray-500 font-mono mt-0.5">{p.payload.component_id}</p>
            </div>
          </button>
        ))}
        <button
          onClick={sendBurst}
          disabled={sending}
          className="flex items-center gap-2 px-4 py-3 bg-amber-900/40 hover:bg-amber-900/60 border border-amber-700 rounded-lg text-sm text-left disabled:opacity-50 transition-colors"
        >
          <Zap size={14} className="shrink-0 text-amber-400" />
          <div>
            <p className="font-medium text-amber-300">Burst Test (20 signals)</p>
            <p className="text-xs text-amber-500 mt-0.5">Trigger debounce on CACHE_CLUSTER_01</p>
          </div>
        </button>
      </div>

      {/* Custom payload */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6">
        <h2 className="text-sm font-medium mb-3">Custom Signal</h2>
        <textarea
          rows={8}
          value={custom}
          onChange={e => setCustom(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-xs font-mono text-gray-200 focus:outline-none focus:border-blue-500 resize-none mb-3"
        />
        <button
          onClick={sendCustom}
          disabled={sending}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm font-medium disabled:opacity-50"
        >
          Send Custom Signal
        </button>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800 text-sm font-medium">Response Log</div>
          <div className="divide-y divide-gray-800/60 max-h-64 overflow-y-auto">
            {results.map((r, i) => (
              <div key={i} className="px-4 py-2.5 flex items-start gap-3 text-xs">
                <CheckCircle size={13} className={r.accepted ? 'text-green-400 mt-0.5' : 'text-red-400 mt-0.5'} />
                <div className="flex-1 min-w-0">
                  <span className="text-gray-400">{new Date(r.ts).toLocaleTimeString()}</span>
                  {' · '}
                  {r.burst ? (
                    <span className="text-amber-300">Burst: {r.accepted_count}/20 accepted</span>
                  ) : r.error ? (
                    <span className="text-red-400">{r.error}</span>
                  ) : (
                    <>
                      <span className={r.accepted ? 'text-green-400' : 'text-red-400'}>
                        {r.accepted ? 'accepted' : 'rejected'}
                      </span>
                      {r.signal_id && <span className="text-gray-500 font-mono ml-2">{r.signal_id.slice(0, 8)}…</span>}
                      <span className="text-gray-500 ml-2">queue: {r.queue_size}</span>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
