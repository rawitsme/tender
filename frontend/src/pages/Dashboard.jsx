import { useState, useEffect } from 'react'
import api from '../api/client'
import StatsCards from '../components/StatsCards'
import TenderCard from '../components/TenderCard'

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [recent, setRecent] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get('/tenders/stats').then(r => setStats(r.data)),
      api.post('/tenders/search', { page: 1, page_size: 10, sort_by: 'created_at', sort_order: 'desc' })
        .then(r => setRecent(r.data.tenders)),
    ]).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Loading dashboard...</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">Overview of tender activity across all sources</p>
      </div>

      <StatsCards stats={stats} />

      {/* Source breakdown */}
      {stats?.tenders_by_source && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Tenders by Source</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
            {Object.entries(stats.tenders_by_source).map(([source, count]) => (
              <div key={source} className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-lg font-bold text-gray-900">{count}</p>
                <p className="text-xs text-gray-500 uppercase">{source}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* State breakdown */}
      {stats?.tenders_by_state && Object.keys(stats.tenders_by_state).length > 0 && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Tenders by State</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {Object.entries(stats.tenders_by_state).map(([state, count]) => (
              <div key={state} className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-lg font-bold text-gray-900">{count}</p>
                <p className="text-xs text-gray-500">{state}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent tenders */}
      <div>
        <h2 className="font-semibold text-gray-900 mb-3">Recently Added</h2>
        <div className="space-y-3">
          {recent.map(t => <TenderCard key={t.id} tender={t} />)}
          {recent.length === 0 && (
            <p className="text-gray-400 text-center py-8">No tenders yet. Run ingestion to populate.</p>
          )}
        </div>
      </div>
    </div>
  )
}
