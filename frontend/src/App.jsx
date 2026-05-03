import { Routes, Route } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import IncidentDetail from './pages/IncidentDetail'
import RCAForm from './pages/RCAForm'
import IngestTest from './pages/IngestTest'
import { fetchHealth } from './api/client'

export default function App() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    const check = async () => {
      try { setHealth(await fetchHealth()) } catch {}
    }
    check()
    const t = setInterval(check, 30000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar health={health} />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/incident/:id" element={<IncidentDetail />} />
          <Route path="/incident/:id/rca" element={<RCAForm />} />
          <Route path="/ingest" element={<IngestTest />} />
        </Routes>
      </main>
    </div>
  )
}
