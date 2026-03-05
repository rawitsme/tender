import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Globe, MapPin, Building2, Tag, Shield, ChevronDown, ChevronRight } from 'lucide-react'
import api from '../api/client'

const sourceInfo = {
  GEM: { label: 'GeM', color: 'from-green-500 to-green-600', icon: '\ud83d\uded2' },
  CPPP: { label: 'CPPP (Central)', color: 'from-blue-500 to-blue-600', icon: '\ud83c\udfdb' },
  UP: { label: 'Uttar Pradesh', color: 'from-orange-500 to-orange-600', icon: '\ud83c\udfd7' },
  MAHARASHTRA: { label: 'Maharashtra', color: 'from-purple-500 to-purple-600', icon: '\ud83c\udfd7' },
  UTTARAKHAND: { label: 'Uttarakhand', color: 'from-teal-500 to-teal-600', icon: '\ud83c\udfd4' },
  HARYANA: { label: 'Haryana', color: 'from-red-500 to-red-600', icon: '\ud83c\udfd7' },
  MP: { label: 'Madhya Pradesh', color: 'from-yellow-500 to-yellow-600', icon: '\ud83c\udfd7' },
}

const keywordIcons = {
  'Construction': '\ud83c\udfd7', 'Road': '\ud83d\udee3', 'Water': '\ud83d\udca7', 'IT & Software': '\ud83d\udcbb',
  'Medical': '\ud83c\udfe5', 'Railway': '\ud83d\ude82', 'Electrical': '\u26a1', 'Education': '\ud83d\udcda',
  'Agriculture': '\ud83c\udf3e', 'Security': '\ud83d\udee1', 'Transport': '\ud83d\ude9b', 'Printing': '\ud83d\udda8',
}

function AuthorityBrowser() {
  const [hierarchy, setHierarchy] = useState(null)
  const [expanded, setExpanded] = useState(null)
  const [stateDepts, setStateDepts] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/tenders/authorities/hierarchy')
      .then(r => setHierarchy(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const toggleExpand = async (name) => {
    if (expanded === name) { setExpanded(null); return }
    setExpanded(name)
    if (!stateDepts[name]) {
      try {
        const res = await api.get('/tenders/authorities/departments?state=' + encodeURIComponent(name))
        setStateDepts(prev => ({ ...prev, [name]: res.data }))
      } catch (e) { console.error(e) }
    }
  }

  if (loading) return <div className="text-sm text-gray-400 py-4">Loading authorities...</div>
  if (!hierarchy) return null

  const renderDepts = (name) => {
    const data = stateDepts[name]
    if (!data) return <div className="p-4 text-sm text-gray-400">Loading...</div>
    return (
      <div className="border-t px-4 py-3 bg-gray-50 space-y-3">
        {data.departments.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase mb-2">Departments</p>
            <div className="grid grid-cols-1 gap-1">
              {data.departments.map(d => (
                <Link key={d.name} to={'/search?department=' + encodeURIComponent(d.name)}
                  className="flex items-center justify-between py-2 px-3 bg-white rounded-lg hover:bg-primary-50 text-sm">
                  <span className="text-gray-700 truncate mr-2">{d.name}</span>
                  <span className="text-xs font-medium text-primary-600 shrink-0">{d.count.toLocaleString()}</span>
                </Link>
              ))}
            </div>
          </div>
        )}
        {data.organizations.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase mb-2">Organizations</p>
            <div className="grid grid-cols-1 gap-1">
              {data.organizations.slice(0, 10).map(o => (
                <Link key={o.name} to={'/search?department=' + encodeURIComponent(o.name)}
                  className="flex items-center justify-between py-2 px-3 bg-white rounded-lg hover:bg-primary-50 text-sm">
                  <span className="text-gray-700 truncate mr-2">{o.name}</span>
                  <span className="text-xs font-medium text-primary-600 shrink-0">{o.count.toLocaleString()}</span>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="bg-white rounded-xl border overflow-hidden">
        <button onClick={() => toggleExpand('Central')}
          className="w-full flex items-center justify-between p-4 hover:bg-gray-50">
          <div className="flex items-center gap-3">
            <span className="text-xl">{'\ud83c\udfdb'}</span>
            <div className="text-left">
              <p className="font-semibold text-gray-900">Central Government</p>
              <p className="text-xs text-gray-500">Ministries & central departments</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold text-primary-700">{hierarchy.central_count.toLocaleString()}</span>
            {expanded === 'Central' ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </div>
        </button>
        {expanded === 'Central' && renderDepts('Central')}
      </div>

      <div className="bg-white rounded-xl border overflow-hidden">
        <div className="p-4 border-b bg-gray-50 flex items-center gap-3">
          <span className="text-xl">{'\ud83c\udfe2'}</span>
          <div>
            <p className="font-semibold text-gray-900">State Governments</p>
            <p className="text-xs text-gray-500">{hierarchy.states.length} states</p>
          </div>
        </div>
        <div className="divide-y">
          {hierarchy.states.map(s => (
            <div key={s.name}>
              <button onClick={() => toggleExpand(s.name)}
                className="w-full flex items-center justify-between p-4 hover:bg-gray-50">
                <span className="font-medium text-gray-900">{s.name}</span>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold text-primary-700">{s.count.toLocaleString()}</span>
                  {expanded === s.name ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </div>
              </button>
              {expanded === s.name && renderDepts(s.name)}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function Browse() {
  const [facets, setFacets] = useState(null)
  const [keywords, setKeywords] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get('/tenders/browse/facets').then(r => setFacets(r.data)),
      api.get('/tenders/keywords/popular').then(r => setKeywords(r.data)).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Browse Tenders</h1>
        <p className="text-gray-500 mt-1">Explore by keyword, authority, source, or state</p>
      </div>

      {keywords.length > 0 && (
        <section>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
            <Tag size={20} /> Explore by Keywords
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {keywords.map(kw => (
              <Link key={kw.name} to={'/search?q=' + encodeURIComponent(kw.keywords)}
                className="flex items-center gap-3 p-4 bg-white rounded-xl border hover:border-primary-300 hover:shadow-sm transition-all">
                <span className="text-2xl">{keywordIcons[kw.name] || '\ud83d\udccb'}</span>
                <div>
                  <p className="font-medium text-gray-900">{kw.name}</p>
                  <p className="text-sm text-primary-600 font-bold">{kw.count.toLocaleString()} tenders</p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Shield size={20} /> Explore by Authorities
        </h2>
        <AuthorityBrowser />
      </section>

      <section>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Globe size={20} /> By Source Portal
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Object.entries(facets?.by_source || {}).map(([source, count]) => {
            const info = sourceInfo[source.toUpperCase()] || { label: source, color: 'from-gray-500 to-gray-600', icon: '\ud83d\udccb' }
            return (
              <Link key={source} to={'/search?source=' + source}
                className="rounded-xl overflow-hidden hover:shadow-lg transition-shadow">
                <div className={'bg-gradient-to-r ' + info.color + ' p-5 text-white'}>
                  <div className="text-2xl mb-2">{info.icon}</div>
                  <h3 className="font-bold text-lg">{info.label}</h3>
                  <p className="text-white/80 text-sm mt-1">{count.toLocaleString()} tenders</p>
                </div>
              </Link>
            )
          })}
        </div>
      </section>

      <section>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <MapPin size={20} /> By State
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {Object.entries(facets?.by_state || {}).map(([state, count]) => (
            <Link key={state} to={'/search?state=' + encodeURIComponent(state)}
              className="flex items-center justify-between p-4 bg-white rounded-xl border hover:border-primary-300 hover:shadow-sm transition-all">
              <span className="text-sm font-medium text-gray-700">{state}</span>
              <span className="text-sm font-bold text-primary-700">{count.toLocaleString()}</span>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Building2 size={20} /> Top Departments
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(facets?.by_department || {}).slice(0, 12).map(([dept, count]) => (
            <Link key={dept} to={'/search?department=' + encodeURIComponent(dept)}
              className="flex items-center justify-between p-4 bg-white rounded-xl border hover:border-primary-300 hover:shadow-sm transition-all">
              <span className="text-sm text-gray-700 truncate mr-3">{dept}</span>
              <span className="text-sm font-bold text-primary-700 shrink-0">{count.toLocaleString()}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
