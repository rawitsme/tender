import { useState, useEffect } from 'react'
import { RefreshCw } from 'lucide-react'
import api from '../api/client'

const SOURCES = ['cppp', 'gem', 'up', 'maharashtra', 'uttarakhand', 'haryana', 'mp']

export default function Admin() {
  const [dashboard, setDashboard] = useState(null)
  const [triggering, setTriggering] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/admin/dashboard')
      .then(r => setDashboard(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const triggerIngestion = async (source) => {
    setTriggering(s => ({ ...s, [source]: true }))
    try {
      await api.post(`/admin/ingestion/trigger/${source}`)
      alert(`Ingestion triggered for ${source}`)
    } catch (err) {
      alert(`Failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setTriggering(s => ({ ...s, [source]: false }))
    }
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
        <p className="text-gray-500 mt-1">System management and ingestion controls</p>
      </div>

      {/* Stats */}
      {dashboard && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white rounded-xl border p-5">
            <p className="text-3xl font-bold text-gray-900">{dashboard.total_tenders}</p>
            <p className="text-sm text-gray-500">Total Tenders</p>
          </div>
          <div className="bg-white rounded-xl border p-5">
            <p className="text-3xl font-bold text-gray-900">{dashboard.total_users}</p>
            <p className="text-sm text-gray-500">Total Users</p>
          </div>
          <div className="bg-white rounded-xl border p-5">
            <p className="text-3xl font-bold text-orange-600">{dashboard.unverified_tenders}</p>
            <p className="text-sm text-gray-500">Unverified Tenders</p>
          </div>
        </div>
      )}

      {/* Ingestion triggers */}
      <div className="bg-white rounded-xl border p-5">
        <h2 className="font-semibold text-gray-900 mb-4">Trigger Ingestion</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {SOURCES.map(source => (
            <button key={source}
              onClick={() => triggerIngestion(source)}
              disabled={triggering[source]}
              className="flex items-center justify-center gap-2 px-4 py-3 border rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              <RefreshCw size={14} className={triggering[source] ? 'animate-spin' : ''} />
              {source.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Per-source counts */}
      {dashboard?.tenders_by_source && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Tenders by Source</h2>
          <div className="space-y-2">
            {Object.entries(dashboard.tenders_by_source).map(([src, count]) => (
              <div key={src} className="flex justify-between items-center py-2 border-b last:border-0">
                <span className="uppercase text-sm font-medium">{src}</span>
                <span className="text-sm text-gray-600">{count} tenders</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
