import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Globe, MapPin, Building2, Layers } from 'lucide-react'
import api from '../api/client'

const sourceInfo = {
  GEM: { label: 'GeM (Government e-Marketplace)', color: 'from-green-500 to-green-600', icon: '🛒' },
  CPPP: { label: 'CPPP (Central Portal)', color: 'from-blue-500 to-blue-600', icon: '🏛️' },
  UP: { label: 'Uttar Pradesh', color: 'from-orange-500 to-orange-600', icon: '🏗️' },
  MAHARASHTRA: { label: 'Maharashtra', color: 'from-purple-500 to-purple-600', icon: '🏗️' },
  UTTARAKHAND: { label: 'Uttarakhand', color: 'from-teal-500 to-teal-600', icon: '🏔️' },
  HARYANA: { label: 'Haryana', color: 'from-red-500 to-red-600', icon: '🏗️' },
  MP: { label: 'Madhya Pradesh', color: 'from-yellow-500 to-yellow-600', icon: '🏗️' },
}

export default function Browse() {
  const [facets, setFacets] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/tenders/browse/facets')
      .then(r => setFacets(r.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Browse Tenders</h1>
        <p className="text-gray-500 mt-1">Explore tenders by source, state, or department</p>
      </div>

      {/* By Source */}
      <section>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Globe size={20} /> By Source Portal
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Object.entries(facets?.by_source || {}).map(([source, count]) => {
            const info = sourceInfo[source] || { label: source, color: 'from-gray-500 to-gray-600', icon: '📋' }
            return (
              <Link
                key={source}
                to={`/search?source=${source}`}
                className="rounded-xl overflow-hidden hover:shadow-lg transition-shadow"
              >
                <div className={`bg-gradient-to-r ${info.color} p-5 text-white`}>
                  <div className="text-2xl mb-2">{info.icon}</div>
                  <h3 className="font-bold text-lg">{info.label}</h3>
                  <p className="text-white/80 text-sm mt-1">{count.toLocaleString()} tenders</p>
                </div>
              </Link>
            )
          })}
        </div>
      </section>

      {/* By State */}
      <section>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <MapPin size={20} /> By State
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {Object.entries(facets?.by_state || {}).map(([state, count]) => (
            <Link
              key={state}
              to={`/search?state=${encodeURIComponent(state)}`}
              className="flex items-center justify-between p-4 bg-white rounded-xl border hover:border-primary-300 hover:shadow-sm transition-all"
            >
              <span className="text-sm font-medium text-gray-700">{state}</span>
              <span className="text-sm font-bold text-primary-700">{count.toLocaleString()}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* By Department */}
      <section>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Building2 size={20} /> Top Departments
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(facets?.by_department || {}).slice(0, 12).map(([dept, count]) => (
            <Link
              key={dept}
              to={`/search?department=${encodeURIComponent(dept)}`}
              className="flex items-center justify-between p-4 bg-white rounded-xl border hover:border-primary-300 hover:shadow-sm transition-all"
            >
              <span className="text-sm text-gray-700 truncate mr-3">{dept}</span>
              <span className="text-sm font-bold text-primary-700 shrink-0">{count.toLocaleString()}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* By Organization */}
      <section>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Layers size={20} /> Top Organizations
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(facets?.by_organization || {}).slice(0, 12).map(([org, count]) => (
            <Link
              key={org}
              to={`/search?department=${encodeURIComponent(org)}`}
              className="flex items-center justify-between p-4 bg-white rounded-xl border hover:border-primary-300 hover:shadow-sm transition-all"
            >
              <span className="text-sm text-gray-700 truncate mr-3">{org}</span>
              <span className="text-sm font-bold text-primary-700 shrink-0">{count.toLocaleString()}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
