import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, RefreshCw } from 'lucide-react'
import api from '../api/client'
import StatsCards from '../components/StatsCards'
import TenderCard from '../components/TenderCard'

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [recent, setRecent] = useState([])
  const [closingSoon, setClosingSoon] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState(null)

  const loadData = () => {
    setLoading(true)
    Promise.all([
      api.get('/tenders/stats').then(r => setStats(r.data)),
      api.post('/tenders/search', {
        page: 1, page_size: 5,
        sort_by: 'created_at', sort_order: 'desc'
      }).then(r => setRecent(r.data.tenders)),
      api.post('/tenders/search', {
        page: 1, page_size: 5,
        closing_within: '3days',
        sort_by: 'bid_close_date', sort_order: 'asc'
      }).then(r => setClosingSoon(r.data.tenders)),
    ]).then(() => setLastUpdated(new Date()))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadData() }, [])

  if (loading && !stats) return <div className="text-center py-12 text-gray-500">Loading dashboard...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">
            Live government tenders from GeM
            {lastUpdated && (
              <span className="text-xs text-gray-400 ml-2">
                Updated {lastUpdated.toLocaleTimeString('en-IN')}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <StatsCards stats={stats} />

      {/* Top Departments */}
      {stats?.tenders_by_department && Object.keys(stats.tenders_by_department).length > 0 && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Top Departments</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {Object.entries(stats.tenders_by_department)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 9)
              .map(([dept, count]) => (
                <Link
                  key={dept}
                  to={`/search?department=${encodeURIComponent(dept)}`}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <span className="text-sm text-gray-700 truncate mr-2">{dept}</span>
                  <span className="text-sm font-bold text-gray-900 shrink-0">{count}</span>
                </Link>
              ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Closing Soon */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-900">⏰ Closing Soon</h2>
            <Link to="/search" className="text-sm text-primary-600 flex items-center gap-1 hover:underline">
              View all <ArrowRight size={14} />
            </Link>
          </div>
          <div className="space-y-3">
            {closingSoon.map(t => <TenderCard key={t.id} tender={t} />)}
            {closingSoon.length === 0 && (
              <p className="text-gray-400 text-center py-6 text-sm">No tenders closing in 3 days</p>
            )}
          </div>
        </div>

        {/* Recently Added */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-900">🆕 Recently Added</h2>
            <Link to="/search" className="text-sm text-primary-600 flex items-center gap-1 hover:underline">
              View all <ArrowRight size={14} />
            </Link>
          </div>
          <div className="space-y-3">
            {recent.map(t => <TenderCard key={t.id} tender={t} />)}
            {recent.length === 0 && (
              <p className="text-gray-400 text-center py-6 text-sm">No tenders yet</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
