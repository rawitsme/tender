import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Plus, Trash2, Check, CheckCheck, Play, Clock, AlertTriangle, FileText, Award } from 'lucide-react'
import api from '../api/client'

const TRIGGER_INFO = {
  new_tender: { label: 'New Tender', icon: FileText, color: 'text-green-600 bg-green-50' },
  corrigendum: { label: 'Corrigendum', icon: AlertTriangle, color: 'text-orange-600 bg-orange-50' },
  deadline_approaching: { label: 'Deadline Soon', icon: Clock, color: 'text-red-600 bg-red-50' },
  award_result: { label: 'Award Result', icon: Award, color: 'text-purple-600 bg-purple-50' },
  extension: { label: 'Extension', icon: Clock, color: 'text-blue-600 bg-blue-50' },
}

const STATES = ['Uttarakhand', 'Uttar Pradesh', 'Maharashtra', 'Haryana', 'Madhya Pradesh', 'Central']
const SOURCES = ['GEM', 'CPPP', 'UTTARAKHAND', 'UP', 'MAHARASHTRA', 'HARYANA', 'MP']

function formatValue(v) {
  if (!v) return ''
  if (v >= 10000000) return `₹${(v / 10000000).toFixed(1)}Cr`
  if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L`
  return `₹${v.toLocaleString()}`
}

export default function Alerts() {
  const [searches, setSearches] = useState([])
  const [alerts, setAlerts] = useState([])
  const [showCreate, setShowCreate] = useState(false)
  const [running, setRunning] = useState(false)
  const [form, setForm] = useState({
    name: '', keywords: '', states: [], sources: [], channels: ['email'],
    frequency: 'instant', min_value: '', max_value: '',
  })

  const load = () => {
    api.get('/alerts/searches').then(r => setSearches(r.data)).catch(console.error)
    api.get('/alerts').then(r => setAlerts(r.data)).catch(console.error)
  }

  useEffect(load, [])

  const createSearch = async () => {
    if (!form.name.trim()) return alert('Name is required')
    try {
      await api.post('/alerts/searches', {
        name: form.name,
        criteria: {
          keywords: form.keywords || undefined,
          states: form.states.length ? form.states : undefined,
          sources: form.sources.length ? form.sources : undefined,
          min_value: form.min_value ? Number(form.min_value) : undefined,
          max_value: form.max_value ? Number(form.max_value) : undefined,
        },
        alert_channels: form.channels,
        alert_frequency: form.frequency,
      })
      setShowCreate(false)
      setForm({ name: '', keywords: '', states: [], sources: [], channels: ['email'], frequency: 'instant', min_value: '', max_value: '' })
      load()
    } catch (err) {
      alert('Failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  const deleteSearch = async (id) => {
    if (!confirm('Delete this saved search and all its alerts?')) return
    await api.delete(`/alerts/searches/${id}`)
    load()
  }

  const markAllRead = async () => {
    await api.post('/alerts/mark-all-read')
    setAlerts(prev => prev.map(a => ({ ...a, is_read: true })))
  }

  const runMatcher = async () => {
    setRunning(true)
    try {
      const res = await api.post('/alerts/run-matcher?since_minutes=10080') // 7 days
      alert(`Matcher complete!\n\nSearches checked: ${res.data.searches_checked}\nNew tenders scanned: ${res.data.new_tenders_scanned}\nAlerts created: ${res.data.alerts_created}`)
      load()
    } catch (err) {
      alert('Matcher failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setRunning(false)
    }
  }

  const toggleArrayField = (field, value) => {
    setForm(prev => ({
      ...prev,
      [field]: prev[field].includes(value)
        ? prev[field].filter(v => v !== value)
        : [...prev[field], value],
    }))
  }

  const unreadCount = alerts.filter(a => !a.is_read).length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alerts & Saved Searches</h1>
          <p className="text-gray-500 mt-1">Get notified when new tenders match your criteria</p>
        </div>
        <div className="flex gap-2">
          <button onClick={runMatcher} disabled={running}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 disabled:opacity-50">
            <Play size={16} className={running ? 'animate-spin' : ''} />
            {running ? 'Scanning...' : 'Scan Now'}
          </button>
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700">
            <Plus size={16} /> New Alert
          </button>
        </div>
      </div>

      {/* How it works */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800">
        <p className="font-semibold mb-1">How Alerts Work</p>
        <ul className="list-disc ml-5 space-y-0.5 text-blue-700">
          <li><strong>New Tender</strong> — triggers when a tender matching your keywords/filters is added</li>
          <li><strong>Corrigendum</strong> — triggers when a matching tender gets updated (date change, amendment)</li>
          <li><strong>Deadline Approaching</strong> — triggers when a matching tender's bid close date is within 24 hours</li>
          <li>Alerts are scanned automatically during each sync cycle and can also be triggered manually with "Scan Now"</li>
        </ul>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="bg-white rounded-xl border p-5 space-y-4">
          <h2 className="font-semibold text-gray-900">Create Alert</h2>

          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Alert Name *</label>
            <input placeholder="e.g. Road Construction Uttarakhand"
              value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
              className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Keywords</label>
            <input placeholder="e.g. road construction bridge"
              value={form.keywords} onChange={e => setForm({ ...form, keywords: e.target.value })}
              className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
            <p className="text-xs text-gray-400 mt-1">Any of these words will trigger a match</p>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">States</label>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {STATES.map(s => (
                <button key={s} onClick={() => toggleArrayField('states', s)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    form.states.includes(s) ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}>{s}</button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Sources</label>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {SOURCES.map(s => (
                <button key={s} onClick={() => toggleArrayField('sources', s)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    form.sources.includes(s) ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}>{s}</button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-500 uppercase">Min Value (₹)</label>
              <input type="number" placeholder="e.g. 100000"
                value={form.min_value} onChange={e => setForm({ ...form, min_value: e.target.value })}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 uppercase">Max Value (₹)</label>
              <input type="number" placeholder="e.g. 10000000"
                value={form.max_value} onChange={e => setForm({ ...form, max_value: e.target.value })}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Notify via</label>
            <div className="flex gap-2 mt-1.5">
              {[
                { key: 'email', label: '📧 Email' },
                { key: 'whatsapp', label: '📱 WhatsApp' },
                { key: 'in_app', label: '🔔 In-App' },
              ].map(ch => (
                <button key={ch.key} onClick={() => toggleArrayField('channels', ch.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    form.channels.includes(ch.key) ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}>{ch.label}</button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Frequency</label>
            <select value={form.frequency} onChange={e => setForm({ ...form, frequency: e.target.value })}
              className="w-full mt-1 px-3 py-2 border rounded-lg text-sm">
              <option value="instant">Instant — notify as soon as found</option>
              <option value="daily_digest">Daily Digest — once a day summary</option>
              <option value="weekly_digest">Weekly Summary — once a week</option>
            </select>
          </div>

          <div className="flex gap-2 pt-2">
            <button onClick={createSearch}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700">
              Create Alert
            </button>
            <button onClick={() => setShowCreate(false)}
              className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50">Cancel</button>
          </div>
        </div>
      )}

      {/* Saved searches */}
      <div className="space-y-3">
        <h2 className="font-semibold text-gray-900">Your Saved Searches ({searches.length})</h2>
        {searches.map(s => (
          <div key={s.id} className="bg-white rounded-xl border p-4 flex items-center justify-between">
            <div className="min-w-0">
              <p className="font-medium text-gray-900">{s.name}</p>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {s.criteria?.keywords && (
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">🔍 {s.criteria.keywords}</span>
                )}
                {s.criteria?.states?.map(st => (
                  <span key={st} className="px-2 py-0.5 bg-green-50 text-green-700 rounded text-xs">📍 {st}</span>
                ))}
                {s.criteria?.sources?.map(src => (
                  <span key={src} className="px-2 py-0.5 bg-purple-50 text-purple-700 rounded text-xs">🏛 {src}</span>
                ))}
                {s.criteria?.min_value && (
                  <span className="px-2 py-0.5 bg-yellow-50 text-yellow-700 rounded text-xs">💰 ≥ {formatValue(s.criteria.min_value)}</span>
                )}
              </div>
              <p className="text-xs text-gray-400 mt-1.5">
                {s.match_count || 0} matches · {(s.alert_channels || []).join(', ')} · {s.alert_frequency || 'instant'}
              </p>
            </div>
            <button onClick={() => deleteSearch(s.id)} className="p-2 text-red-500 hover:bg-red-50 rounded-lg shrink-0">
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        {searches.length === 0 && (
          <div className="text-center py-8 text-gray-400">
            <Bell size={32} className="mx-auto mb-2 opacity-50" />
            <p>No saved searches yet. Create one to start getting alerts!</p>
          </div>
        )}
      </div>

      {/* Recent alerts */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">
            Recent Alerts
            {unreadCount > 0 && (
              <span className="ml-2 px-2 py-0.5 bg-red-500 text-white text-xs rounded-full">{unreadCount} new</span>
            )}
          </h2>
          {unreadCount > 0 && (
            <button onClick={markAllRead}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700">
              <CheckCheck size={14} /> Mark all read
            </button>
          )}
        </div>

        {alerts.map(a => {
          const info = TRIGGER_INFO[a.trigger] || TRIGGER_INFO.new_tender
          const Icon = info.icon
          return (
            <Link key={a.id} to={a.tender_id ? `/tenders/${a.tender_id}` : '#'}
              className={`block bg-white rounded-xl border p-4 hover:border-primary-300 transition-colors ${
                !a.is_read ? 'border-l-4 border-l-primary-500' : ''
              }`}>
              <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg shrink-0 ${info.color}`}>
                  <Icon size={16} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'inherit' }}>
                      {info.label}
                    </span>
                    <span className="text-xs text-gray-400">
                      {new Date(a.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  {a.tender_title && (
                    <p className="text-sm font-medium text-gray-900 mt-1 line-clamp-2">{a.tender_title}</p>
                  )}
                  <div className="flex flex-wrap gap-3 mt-1.5 text-xs text-gray-500">
                    {a.tender_source && <span>📋 {a.tender_source}</span>}
                    {a.tender_state && <span>📍 {a.tender_state}</span>}
                    {a.tender_value && <span>💰 {formatValue(a.tender_value)}</span>}
                    {a.tender_bid_close && <span>⏰ Close: {new Date(a.tender_bid_close).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</span>}
                  </div>
                </div>
              </div>
            </Link>
          )
        })}
        {alerts.length === 0 && (
          <div className="text-center py-8 text-gray-400">
            <Bell size={32} className="mx-auto mb-2 opacity-50" />
            <p>No alerts yet. Create a saved search and click "Scan Now" to find matches!</p>
          </div>
        )}
      </div>
    </div>
  )
}
