import { Link, useLocation } from 'react-router-dom'
import { AlertTriangle, Activity, Plus } from 'lucide-react'

export default function Navbar({ health }) {
  const loc = useLocation()

  return (
    <nav className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <AlertTriangle className="text-red-500" size={22} />
        <span className="font-bold text-lg tracking-tight">IMS</span>
        <span className="text-gray-500 text-sm hidden sm:inline">Incident Management System</span>
      </div>
      <div className="flex items-center gap-6">
        <Link
          to="/"
          className={`text-sm ${loc.pathname === '/' ? 'text-white font-medium' : 'text-gray-400 hover:text-gray-200'}`}
        >
          Dashboard
        </Link>
        <Link
          to="/ingest"
          className={`text-sm ${loc.pathname === '/ingest' ? 'text-white font-medium' : 'text-gray-400 hover:text-gray-200'}`}
        >
          Test Ingest
        </Link>
        {health && (
          <div className="flex items-center gap-1.5">
            <Activity size={14} className={health.status === 'healthy' ? 'text-green-400' : 'text-amber-400'} />
            <span className={`text-xs ${health.status === 'healthy' ? 'text-green-400' : 'text-amber-400'}`}>
              {health.status}
            </span>
          </div>
        )}
      </div>
    </nav>
  )
}
