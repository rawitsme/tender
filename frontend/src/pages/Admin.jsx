import { useState, useEffect } from 'react'
import { RefreshCw, Database, Users, CheckCircle, AlertTriangle } from 'lucide-react'
import api from '../api/client'

export default function Admin() {
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ingesting, setIngesting] = useState(null)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    api.get('/admin/dashboard')
      .then(r => setDashboard(r.data))
      .catch(() => setMessage({ type: 'error', text: 'Failed to load admin dashboard. Login as admin first.' }))
      .finally(() => setLoading(false))
  }, [])

  const triggerIngestion = async (source) => {
    setIngesting(source)
    setMessage(null)
    try {
      const res = await api.post(`/admin/ingestion/trigger/${source}`)
      setMessage({ type: 'success', text: `Ingestion triggered for ${source.toUpperCase()}. Task ID: ${res.data.task_id}` })
    } catch (err) {
      setMessage({ type: 'error', text: `Failed: ${err.response?.data?.detail || err.message}` })
    } finally {
      setIngesting(null)
    }
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
        <p className="text-gray-500 mt-1">Manage ingestion, users, and system health</p>
      </div>

      {message && (
        <div className={`p-4 rounded-xl flex items-center gap-2 text-sm ${
          message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
        }`}>
          {message.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          {message.text}
        </div>
      )}

      {dashboard && (
        <>
          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-blue-50 text-blue-600"><Database size={20} /></div>
                <div>
                  <p className="text-2xl font-bold">{dashboard.total_tenders?.toLocaleString()}</p>
                  <p className="text-sm text-gray-500">Total Tenders</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-xl border p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-green-50 text-green-600"><Users size={20} /></div>
                <div>
                  <p className="text-2xl font-bold">{dashboard.total_users}</p>
                  <p className="text-sm text-gray-500">Registered Users</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-xl border p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-orange-50 text-orange-600"><AlertTriangle size={20} /></div>
                <div>
                  <p className="text-2xl font-bold">{dashboard.unverified_tenders?.toLocaleString()}</p>
                  <p className="text-sm text-gray-500">Unverified Tenders</p>
                </div>
              </div>
            </div>
          </div>

          {/* Ingestion Controls */}
          <div className="bg-white rounded-xl border p-5">
            <h2 className="font-semibold text-gray-900 mb-4">Ingestion Controls</h2>
            <p className="text-sm text-gray-500 mb-4">
              Celery worker runs auto-ingestion every 30 minutes. Use buttons below for manual triggers.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                { key: 'gem', label: 'GeM (Government eMarketplace)', status: 'active', count: dashboard.tenders_by_source?.gem },
              ].map(({ key, label, status, count }) => (
                <div key={key} className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <p className="font-medium text-gray-900">{label}</p>
                    <p className="text-sm text-gray-500">
                      {count?.toLocaleString() || 0} tenders
                      <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${
                        status === 'active' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        {status === 'active' ? '● Live' : '⚠ CAPTCHA'}
                      </span>
                    </p>
                  </div>
                  <button
                    onClick={() => triggerIngestion(key)}
                    disabled={ingesting === key}
                    className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700 disabled:opacity-50"
                  >
                    <RefreshCw size={14} className={ingesting === key ? 'animate-spin' : ''} />
                    {ingesting === key ? 'Running...' : 'Ingest'}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Source Breakdown */}
          {dashboard.tenders_by_source && Object.keys(dashboard.tenders_by_source).length > 0 && (
            <div className="bg-white rounded-xl border p-5">
              <h2 className="font-semibold text-gray-900 mb-3">Tenders by Source</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(dashboard.tenders_by_source).map(([source, count]) => (
                  <div key={source} className="text-center p-3 bg-gray-50 rounded-lg">
                    <p className="text-lg font-bold text-gray-900">{count?.toLocaleString()}</p>
                    <p className="text-xs text-gray-500 uppercase">{source}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
