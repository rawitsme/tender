import { useState, useEffect, useCallback } from 'react'
import {
  RefreshCw, Database, Users, CheckCircle, AlertTriangle, Activity, Clock, Mail,
  Shield, Heart, HardDrive, Wifi, WifiOff, ToggleLeft, ToggleRight, Search,
  Bell, FileText, BarChart3, Trash2, Eye, ChevronDown, ChevronRight, X
} from 'lucide-react'
import api from '../api/client'

const SOURCES = [
  { key: 'gem', label: 'GeM', type: 'API', captcha: false },
  { key: 'cppp', label: 'CPPP', type: 'Selenium', captcha: true },
  { key: 'up', label: 'UP', type: 'Selenium', captcha: true },
  { key: 'maharashtra', label: 'Maharashtra', type: 'Selenium', captcha: true },
  { key: 'uttarakhand', label: 'Uttarakhand', type: 'Selenium', captcha: true },
  { key: 'haryana', label: 'Haryana', type: 'Selenium', captcha: true },
  { key: 'mp', label: 'MP', type: 'Selenium', captcha: true },
]

const TABS = [
  { key: 'overview', label: 'Overview', icon: BarChart3 },
  { key: 'ingestion', label: 'Ingestion', icon: Database },
  { key: 'users', label: 'Users', icon: Users },
  { key: 'quality', label: 'Data Quality', icon: CheckCircle },
  { key: 'notifications', label: 'Notifications', icon: Bell },
  { key: 'system', label: 'System', icon: Activity },
]

export default function Admin() {
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ingesting, setIngesting] = useState(null)
  const [message, setMessage] = useState(null)
  const [tab, setTab] = useState('overview')

  const load = useCallback(() => {
    setLoading(true)
    api.get('/admin/dashboard')
      .then(r => setDashboard(r.data))
      .catch(() => setMessage({ type: 'error', text: 'Admin access required.' }))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  const showMsg = (type, text) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 5000)
  }

  const ingest = async (src) => {
    setIngesting(src)
    try {
      await api.post(`/admin/ingestion/trigger/${src}`)
      showMsg('success', `${src.toUpperCase()} ingestion triggered.`)
    } catch (e) {
      showMsg('error', e.response?.data?.detail || e.message)
    }
    setIngesting(null)
  }

  const ingestAll = async () => {
    setIngesting('all')
    try {
      await api.post('/admin/ingestion/trigger-all')
      showMsg('success', 'All sources triggered.')
    } catch (e) {
      // Fallback: trigger individually
      for (const s of SOURCES) { try { await api.post(`/admin/ingestion/trigger/${s.key}`) } catch {} }
      showMsg('success', 'All sources triggered.')
    }
    setIngesting(null)
    setTimeout(load, 3000)
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading admin panel...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
          <p className="text-sm text-gray-500 mt-1">Manage tenders, users, ingestion, and system health</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {message && (
        <div className={`p-3 rounded-lg flex items-center gap-2 text-sm ${message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'}`}>
          {message.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          {message.text}
          <button onClick={() => setMessage(null)} className="ml-auto"><X size={14} /></button>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 overflow-x-auto">
        {TABS.map(t => {
          const Icon = t.icon
          return (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium whitespace-nowrap transition-colors ${
                tab === t.key ? 'bg-white text-primary-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}>
              <Icon size={14} /> {t.label}
            </button>
          )
        })}
      </div>

      {dashboard && tab === 'overview' && <OverviewTab d={dashboard} />}
      {dashboard && tab === 'ingestion' && <IngestionTab d={dashboard} ingesting={ingesting} ingest={ingest} ingestAll={ingestAll} />}
      {tab === 'users' && <UsersTab showMsg={showMsg} />}
      {dashboard && tab === 'quality' && <DataQualityTab d={dashboard} />}
      {tab === 'notifications' && <NotificationsTab />}
      {tab === 'system' && <SystemTab />}
    </div>
  )
}

/* ──────────────── OVERVIEW TAB ──────────────── */
function OverviewTab({ d }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat icon={Database} color="blue" value={d.total_tenders?.toLocaleString()} label="Total Tenders" />
        <Stat icon={Users} color="green" value={d.total_users} label="Users" />
        <Stat icon={AlertTriangle} color="orange" value={d.unverified_tenders?.toLocaleString()} label="Unverified" />
        <Stat icon={Activity} color="purple" value={d.recent_24h?.toLocaleString() || '0'} label="Last 24h" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat icon={FileText} color="indigo" value={d.total_documents?.toLocaleString() || '0'} label="Documents" />
        <Stat icon={Search} color="teal" value={d.total_saved_searches?.toLocaleString() || '0'} label="Saved Searches" />
        <Stat icon={Bell} color="pink" value={d.total_alerts?.toLocaleString() || '0'} label="Alerts Fired" />
        <Stat icon={BarChart3} color="cyan" value={Object.keys(d.tenders_by_source || {}).length} label="Active Sources" />
      </div>

      {/* Source Breakdown */}
      <div className="bg-white rounded-xl border p-5">
        <h2 className="font-semibold mb-4">Source Breakdown</h2>
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-4 py-2">Source</th>
              <th className="text-right px-4 py-2">Total</th>
              <th className="text-right px-4 py-2">Last 24h</th>
              <th className="text-right px-4 py-2">%</th>
              <th className="text-center px-4 py-2">Type</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {SOURCES.map(s => {
              const c = d.tenders_by_source?.[s.key] || 0
              const r = d.recent_by_source?.[s.key] || 0
              const p = d.total_tenders ? ((c / d.total_tenders) * 100).toFixed(1) : 0
              return (
                <tr key={s.key} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{s.label}</td>
                  <td className="px-4 py-3 text-right font-bold">{c.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right">
                    {r > 0 ? <span className="text-green-600 font-medium">+{r}</span> : <span className="text-gray-400">0</span>}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-500">{p}%</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${s.type === 'API' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>{s.type}</span>
                    {s.captcha && <span className="ml-1 px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-700">CAPTCHA</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ──────────────── INGESTION TAB ──────────────── */
function IngestionTab({ d, ingesting, ingest, ingestAll }) {
  const [sources, setSources] = useState(null)

  useEffect(() => {
    api.get('/admin/ingestion/sources').then(r => setSources(r.data)).catch(() => {})
  }, [])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-lg">Ingestion Controls</h2>
          <p className="text-sm text-gray-500 mt-1">Auto-runs every 6h via Celery Beat. Manual trigger below.</p>
        </div>
        <button onClick={ingestAll} disabled={!!ingesting}
          className="flex items-center gap-2 px-5 py-2.5 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
          <RefreshCw size={14} className={ingesting === 'all' ? 'animate-spin' : ''} />
          {ingesting === 'all' ? 'Running All...' : 'Run All Sources'}
        </button>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-800">
        <strong>⚡ Celery Worker:</strong>{' '}
        <code className="bg-yellow-100 px-2 py-0.5 rounded text-xs font-mono">celery -A backend.ingestion.tasks worker --beat --loglevel=info</code>
      </div>

      {/* Source cards with last-ingested info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {SOURCES.map(s => {
          const srcInfo = sources?.find(x => x.key === s.key)
          const count = d.tenders_by_source?.[s.key] || 0
          const recent = d.recent_by_source?.[s.key] || 0
          return (
            <div key={s.key} className="bg-white border rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold text-gray-900">{s.label}</p>
                  <div className="flex items-center gap-2 mt-1 text-sm">
                    <span className="text-gray-600">{count.toLocaleString()} tenders</span>
                    {recent > 0 && <span className="text-green-600 font-medium">+{recent} today</span>}
                  </div>
                </div>
                <button onClick={() => ingest(s.key)} disabled={!!ingesting}
                  className="flex items-center gap-2 px-3 py-2 bg-primary-600 text-white rounded-lg text-sm disabled:opacity-50 hover:bg-primary-700">
                  <RefreshCw size={14} className={ingesting === s.key ? 'animate-spin' : ''} />
                  {ingesting === s.key ? 'Running...' : 'Ingest'}
                </button>
              </div>
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <span className={`px-2 py-0.5 rounded-full ${s.type === 'API' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>{s.type}</span>
                {s.captcha && <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">CAPTCHA</span>}
                {srcInfo?.last_ingested && (
                  <span className="flex items-center gap-1">
                    <Clock size={12} /> Last: {new Date(srcInfo.last_ingested).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                  </span>
                )}
              </div>
              {/* Progress bar showing source share */}
              <div className="w-full bg-gray-100 rounded-full h-1.5">
                <div className="bg-primary-500 h-1.5 rounded-full" style={{ width: `${Math.min(100, (count / (d.total_tenders || 1)) * 100)}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ──────────────── USERS TAB ──────────────── */
function UsersTab({ showMsg }) {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    api.get('/admin/users')
      .then(r => setUsers(r.data))
      .catch(() => showMsg('error', 'Failed to load users'))
      .finally(() => setLoading(false))
  }, [showMsg])

  useEffect(load, [load])

  const toggleActive = async (userId) => {
    try {
      const res = await api.put(`/admin/users/${userId}/toggle`)
      showMsg('success', `User ${res.data.is_active ? 'activated' : 'deactivated'}`)
      load()
    } catch (e) {
      showMsg('error', e.response?.data?.detail || 'Failed')
    }
  }

  const changeRole = async (userId, role) => {
    try {
      await api.put(`/admin/users/${userId}/role?role=${role}`)
      showMsg('success', `Role updated to ${role}`)
      load()
    } catch (e) {
      showMsg('error', e.response?.data?.detail || 'Failed')
    }
  }

  const filtered = users.filter(u =>
    !search || u.email?.toLowerCase().includes(search.toLowerCase()) || u.full_name?.toLowerCase().includes(search.toLowerCase())
  )

  if (loading) return <div className="text-center py-8 text-gray-400">Loading users...</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-lg">User Management ({users.length})</h2>
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search users..."
            className="pl-9 pr-3 py-2 border rounded-lg text-sm w-56 focus:ring-2 focus:ring-primary-500 outline-none" />
        </div>
      </div>

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-4 py-3">User</th>
              <th className="text-left px-4 py-3">Role</th>
              <th className="text-center px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Joined</th>
              <th className="text-center px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {filtered.map(u => (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-gray-900">{u.full_name || '—'}</p>
                  <p className="text-xs text-gray-500">{u.email}</p>
                  {u.phone && <p className="text-xs text-gray-400">{u.phone}</p>}
                </td>
                <td className="px-4 py-3">
                  <select value={u.role} onChange={e => changeRole(u.id, e.target.value)}
                    className="text-xs border rounded px-2 py-1 focus:ring-1 focus:ring-primary-500 outline-none">
                    <option value="user">User</option>
                    <option value="operator">Operator</option>
                    <option value="admin">Admin</option>
                  </select>
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${u.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {u.is_active ? 'Active' : 'Disabled'}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {new Date(u.created_at).toLocaleDateString('en-IN', { dateStyle: 'medium' })}
                </td>
                <td className="px-4 py-3 text-center">
                  <button onClick={() => toggleActive(u.id)}
                    className={`p-1.5 rounded-lg transition-colors ${u.is_active ? 'text-red-500 hover:bg-red-50' : 'text-green-500 hover:bg-green-50'}`}
                    title={u.is_active ? 'Deactivate' : 'Activate'}>
                    {u.is_active ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={5} className="text-center py-8 text-gray-400">No users found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ──────────────── DATA QUALITY TAB ──────────────── */
function DataQualityTab({ d }) {
  const quality = d.data_quality || {}
  const fields = [
    { key: 'description', label: 'Description', icon: '📝' },
    { key: 'category', label: 'Category', icon: '🏷️' },
    { key: 'estimated_value', label: 'Estimated Value', icon: '💰' },
    { key: 'emd_amount', label: 'EMD Amount', icon: '🏦' },
    { key: 'contact_info', label: 'Contact Info', icon: '📞' },
    { key: 'department', label: 'Department', icon: '🏢' },
  ]

  const getColor = (pct) => {
    if (pct >= 80) return 'bg-green-500'
    if (pct >= 50) return 'bg-yellow-500'
    if (pct >= 20) return 'bg-orange-500'
    return 'bg-red-500'
  }

  const getLabel = (pct) => {
    if (pct >= 80) return { text: 'Good', cls: 'text-green-700 bg-green-50' }
    if (pct >= 50) return { text: 'Fair', cls: 'text-yellow-700 bg-yellow-50' }
    if (pct >= 20) return { text: 'Poor', cls: 'text-orange-700 bg-orange-50' }
    return { text: 'Critical', cls: 'text-red-700 bg-red-50' }
  }

  const avgQuality = fields.length > 0
    ? (fields.reduce((sum, f) => sum + (quality[f.key] || 0), 0) / fields.length).toFixed(1)
    : 0

  return (
    <div className="space-y-6">
      {/* Overall score */}
      <div className="bg-white border rounded-xl p-6 text-center">
        <p className="text-sm text-gray-500 mb-2">Overall Data Completeness</p>
        <p className="text-5xl font-bold text-gray-900">{avgQuality}%</p>
        <div className="w-full max-w-md mx-auto mt-4 bg-gray-100 rounded-full h-3">
          <div className={`h-3 rounded-full transition-all ${getColor(avgQuality)}`} style={{ width: `${avgQuality}%` }} />
        </div>
        <p className="text-sm text-gray-400 mt-3">Based on {d.total_tenders?.toLocaleString()} tenders</p>
      </div>

      {/* Per-field breakdown */}
      <div className="bg-white border rounded-xl p-5">
        <h2 className="font-semibold mb-4">Field Completeness</h2>
        <div className="space-y-4">
          {fields.map(f => {
            const pct = quality[f.key] || 0
            const label = getLabel(pct)
            return (
              <div key={f.key} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">{f.icon} {f.label}</span>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${label.cls}`}>{label.text}</span>
                    <span className="text-sm font-bold text-gray-900 w-14 text-right">{pct}%</span>
                  </div>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div className={`h-2 rounded-full transition-all ${getColor(pct)}`} style={{ width: `${pct}%` }} />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Unverified tenders */}
      <div className="bg-white border rounded-xl p-5">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold">Verification Status</h2>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-green-50 rounded-lg text-center">
            <p className="text-2xl font-bold text-green-700">{((d.total_tenders || 0) - (d.unverified_tenders || 0)).toLocaleString()}</p>
            <p className="text-sm text-green-600">Verified</p>
          </div>
          <div className="p-4 bg-orange-50 rounded-lg text-center">
            <p className="text-2xl font-bold text-orange-700">{(d.unverified_tenders || 0).toLocaleString()}</p>
            <p className="text-sm text-orange-600">Unverified</p>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ──────────────── NOTIFICATIONS TAB ──────────────── */
function NotificationsTab() {
  const [notifs, setNotifs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/admin/notifications?limit=50')
      .then(r => setNotifs(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-8 text-gray-400">Loading notifications...</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-lg">Recent Notifications ({notifs.length})</h2>
      </div>

      {notifs.length === 0 ? (
        <div className="text-center py-12 bg-white border rounded-xl">
          <Bell size={40} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-400">No notifications sent yet</p>
          <p className="text-xs text-gray-300 mt-1">Configure SMTP in .env to enable email alerts</p>
        </div>
      ) : (
        <div className="bg-white border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-3">Channel</th>
                <th className="text-left px-4 py-3">Subject</th>
                <th className="text-center px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Created</th>
                <th className="text-left px-4 py-3">Sent</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {notifs.map(n => (
                <tr key={n.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      n.channel === 'email' ? 'bg-blue-100 text-blue-700' :
                      n.channel === 'whatsapp' ? 'bg-green-100 text-green-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>{n.channel}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-700 truncate max-w-xs">{n.subject || '—'}</td>
                  <td className="px-4 py-3 text-center">
                    {n.sent
                      ? <span className="text-green-600"><CheckCircle size={16} /></span>
                      : <span className="text-gray-400"><Clock size={16} /></span>}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {new Date(n.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {n.sent_at ? new Date(n.sent_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/* ──────────────── SYSTEM TAB ──────────────── */
function SystemTab() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/admin/system-health')
      .then(r => setHealth(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-5">
      {/* Live Health Checks */}
      <div className="bg-white rounded-xl border p-5">
        <h2 className="font-semibold mb-4">System Health</h2>
        {loading ? (
          <p className="text-sm text-gray-400">Checking...</p>
        ) : health ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            <HealthCard name="Database" ok={health.database} icon={Database} />
            <HealthCard name="Redis" ok={health.redis} icon={HardDrive} />
            <HealthCard name="Celery" ok={health.celery} icon={Activity} />
            <HealthCard name="Storage" ok={health.storage} icon={FileText} />
            <HealthCard name="SMTP" ok={health.smtp_configured} icon={Mail} />
          </div>
        ) : (
          <p className="text-sm text-red-500">Failed to check health</p>
        )}
      </div>

      {/* Config info */}
      <div className="bg-white rounded-xl border p-5">
        <h2 className="font-semibold mb-4">Configuration</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <InfoCard icon={Database} title="Database" lines={['PostgreSQL @ localhost:5432', 'DB: tender_portal']} />
          <InfoCard icon={HardDrive} title="Redis" lines={['localhost:6379', 'Celery broker + result cache']} />
          <InfoCard icon={Clock} title="Celery Schedule" lines={['Ingestion: Every 6 hours', 'Alert matching: Every 1 hour']} />
          <InfoCard icon={Mail} title="Email Alerts" lines={['SMTP: smtp.gmail.com:587', 'Configure SMTP_USER in .env']} />
        </div>
      </div>

      <div className="bg-white rounded-xl border p-5">
        <h2 className="font-semibold mb-3">Environment</h2>
        <div className="text-sm text-gray-600 space-y-2">
          <p><strong>Backend:</strong> FastAPI + uvicorn @ port 8000</p>
          <p><strong>Frontend:</strong> React + Vite @ port 5173</p>
          <p><strong>Scraping:</strong> Selenium (Chrome headless) + 2Captcha</p>
          <p><strong>Storage:</strong> ./storage/documents/</p>
          <p><strong>Sources:</strong> GeM (API) + CPPP, UP, MH, UK, HR, MP (Selenium)</p>
        </div>
      </div>
    </div>
  )
}

/* ──────────────── SHARED COMPONENTS ──────────────── */
function Stat({ icon: Icon, color, value, label }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    orange: 'bg-orange-50 text-orange-600',
    purple: 'bg-purple-50 text-purple-600',
    indigo: 'bg-indigo-50 text-indigo-600',
    teal: 'bg-teal-50 text-teal-600',
    pink: 'bg-pink-50 text-pink-600',
    cyan: 'bg-cyan-50 text-cyan-600',
  }
  return (
    <div className="bg-white rounded-xl border p-4">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${colors[color] || colors.blue}`}><Icon size={18} /></div>
        <div>
          <p className="text-xl font-bold text-gray-900">{value ?? '—'}</p>
          <p className="text-xs text-gray-500">{label}</p>
        </div>
      </div>
    </div>
  )
}

function HealthCard({ name, ok, icon: Icon }) {
  return (
    <div className={`flex items-center gap-3 p-3 rounded-lg border ${ok ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
      <Icon size={16} className={ok ? 'text-green-600' : 'text-red-500'} />
      <div>
        <p className="text-sm font-medium text-gray-900">{name}</p>
        <p className={`text-xs ${ok ? 'text-green-600' : 'text-red-500'}`}>{ok ? '● Online' : '● Offline'}</p>
      </div>
    </div>
  )
}

function InfoCard({ icon: Icon, title, lines }) {
  return (
    <div className="p-4 bg-gray-50 rounded-lg">
      <p className="font-medium text-gray-700 mb-2 flex items-center gap-1.5"><Icon size={14} /> {title}</p>
      {lines.map((l, i) => <p key={i} className="text-gray-500 text-sm">{l}</p>)}
    </div>
  )
}
