export function PriorityBadge({ priority }) {
  const styles = {
    P0: 'bg-red-600 text-white',
    P1: 'bg-orange-600 text-white',
    P2: 'bg-amber-500 text-black',
    P3: 'bg-green-600 text-white',
  }
  return (
    <span className={`priority-badge ${styles[priority] || 'bg-gray-600 text-white'}`}>
      {priority}
    </span>
  )
}

export function StatusBadge({ status }) {
  const styles = {
    OPEN: 'bg-red-900/60 text-red-300 border border-red-700',
    INVESTIGATING: 'bg-amber-900/60 text-amber-300 border border-amber-700',
    RESOLVED: 'bg-blue-900/60 text-blue-300 border border-blue-700',
    CLOSED: 'bg-gray-800 text-gray-400 border border-gray-600',
  }
  return (
    <span className={`status-badge ${styles[status] || 'bg-gray-800 text-gray-400'}`}>
      {status}
    </span>
  )
}
