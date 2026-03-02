import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, RefreshCw, TrendingUp, Clock, Database, Globe } from 'lucide-react'
import api from '../api/client'
import StatsCards from '../components/StatsCards'
import TenderCard from '../components/TenderCard'

const sourceColors = {
  GEM: 'bg-green-500', CPPP: 'bg-blue-500', UP: 'bg-orange-500',
  MAHARASHTRA: 'bg-purple-500', UTTARAKHAND: 'bg-teal-500', HARYANA: 'bg-red-500', MP: 'bg-yellow-500',
}

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

  const totalBySource = stats?.tenders_by_source || {}
  const totalTenders = Object.values(totalBySource).reduce((a, b) => a + b, 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">
            Live government tenders from 7 portals
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

      {/* Source Breakdown */}
      <div className="bg-white rounded-xl border p-5">
        <h2 className="flex items-center gap-2 font-semibold text-gray-900 mb-4">
          <Globe size={18} /> Tenders by Source
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {Object.entries(totalBySource)
            .sort((a, b) => b[1] - a[1])
            .map(([source, count]) => (
              <Link
                key={source}
                to={`/search?source=${source}`}
                className="text-center p-3 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className={`w-3 h-3 rounded-full ${sourceColors[source] || 'bg-gray-400'} mx-auto mb-2`} />
                <p className="text-xs text-gray-500 uppercase font-medium">{source}</p>
                <p className="text-lg font-bold text-gray-900">{count.toLocaleString()}</p>
              </Link>
            ))}
        </div>
        {/* Progress bar */}
        <div className="flex h-2 rounded-full overflow-hidden mt-4 bg-gray-100">
          {Object.entries(totalBySource)
            .sort((a, b) => b[1] - a[1])
            .map(([source, count]) => (
              <div
                key={source}
                className={`${sourceColors[source] || 'bg-gray-400'}`}
                style={{ width: `${(count / totalTenders) * 100}%` }}
                title={`${source}: ${count}`}
              />
            ))}
        </div>
      </div>

      {/* State breakdown */}
      {stats?.tenders_by_source && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Tenders by State</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
            {Object.entries(stats.tenders_by_state || {})
              .sort((a, b) => b[1] - a[1])
              .map(([state, count]) => (
                <Link
                  key={state}
                  to={`/search?state=${encodeURIComponent(state)}`}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <span className="text-xs text-gray-600 truncate mr-1">{state}</span>
                  <span className="text-sm font-bold text-gray-900">{count.toLocaleString()}</span>
                </Link>
              ))}
          </div>
        </div>
      )}

      {/* Top Departments */}
      {stats?.tenders_by_department && Object.keys(stats.tenders_by_department).length > 0 && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Top Departments</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {Object.entries(stats.tenders_by_department)
              .filter(([dept]) => dept)  // skip empty
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
