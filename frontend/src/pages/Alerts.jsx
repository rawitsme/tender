import { useState, useEffect } from 'react'
import { Bell, Plus, Trash2 } from 'lucide-react'
import api from '../api/client'

export default function Alerts() {
  const [searches, setSearches] = useState([])
  const [alerts, setAlerts] = useState([])
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', keywords: '', states: [], channels: ['email'], frequency: 'instant' })

  useEffect(() => {
    api.get('/alerts/searches').then(r => setSearches(r.data)).catch(console.error)
    api.get('/alerts').then(r => setAlerts(r.data)).catch(console.error)
  }, [])

  const createSearch = async () => {
    try {
      await api.post('/alerts/searches', {
        name: form.name,
        criteria: { keywords: form.keywords, states: form.states.length ? form.states : undefined },
        alert_channels: form.channels,
      })
      setShowCreate(false)
      setForm({ name: '', keywords: '', states: [], channels: ['email'] })
      const res = await api.get('/alerts/searches')
      setSearches(res.data)
    } catch (err) {
      alert('Failed to create: ' + (err.response?.data?.detail || err.message))
    }
  }

  const deleteSearch = async (id) => {
    if (!confirm('Delete this saved search?')) return
    await api.delete(`/alerts/searches/${id}`)
    setSearches(s => s.filter(x => x.id !== id))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alerts & Saved Searches</h1>
          <p className="text-gray-500 mt-1">Get notified when new tenders match your criteria</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700">
          <Plus size={16} /> New Alert
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="bg-white rounded-xl border p-5 space-y-4">
          <h2 className="font-semibold">Create Saved Search</h2>
          <input placeholder="Alert name (e.g. Road Construction UP)"
            value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm" />
          <input placeholder="Keywords (e.g. road construction bridge)"
            value={form.keywords} onChange={e => setForm({ ...form, keywords: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm" />
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Notify via</label>
            <div className="flex gap-2 mt-1.5">
              {['email', 'whatsapp', 'sms'].map(ch => (
                <button key={ch}
                  onClick={() => {
                    const chs = form.channels.includes(ch) ? form.channels.filter(c => c !== ch) : [...form.channels, ch]
                    setForm({ ...form, channels: chs })
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                    form.channels.includes(ch) ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >{ch === 'whatsapp' ? '📱 WhatsApp' : ch === 'email' ? '📧 Email' : '💬 SMS'}</button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Frequency</label>
            <select value={form.frequency} onChange={e => setForm({ ...form, frequency: e.target.value })}
              className="w-full mt-1.5 px-3 py-2 border rounded-lg text-sm">
              <option value="instant">Instant</option>
              <option value="daily">Daily Digest</option>
              <option value="weekly">Weekly Summary</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button onClick={createSearch} className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm">Save</button>
            <button onClick={() => setShowCreate(false)} className="px-4 py-2 border rounded-lg text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Saved searches */}
      <div className="space-y-3">
        <h2 className="font-semibold text-gray-900">Your Saved Searches ({searches.length})</h2>
        {searches.map(s => (
          <div key={s.id} className="bg-white rounded-xl border p-4 flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-900">{s.name}</p>
              <p className="text-sm text-gray-500">
                {s.criteria?.keywords && `Keywords: ${s.criteria.keywords}`}
                {s.criteria?.states?.length > 0 && ` | States: ${s.criteria.states.join(', ')}`}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {s.match_count} matches | Channels: {(s.alert_channels || []).join(', ')}
              </p>
            </div>
            <button onClick={() => deleteSearch(s.id)} className="p-2 text-red-500 hover:bg-red-50 rounded-lg">
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        {searches.length === 0 && <p className="text-gray-400 text-center py-8">No saved searches yet.</p>}
      </div>

      {/* Recent alerts */}
      <div className="space-y-3">
        <h2 className="font-semibold text-gray-900">Recent Alerts ({alerts.length})</h2>
        {alerts.map(a => (
          <div key={a.id} className="bg-white rounded-xl border p-4 flex items-center gap-3">
            <Bell size={16} className={a.is_read ? 'text-gray-400' : 'text-primary-600'} />
            <div>
              <p className="text-sm font-medium capitalize">{a.trigger?.replace('_', ' ')}</p>
              <p className="text-xs text-gray-400">{new Date(a.created_at).toLocaleString()}</p>
            </div>
          </div>
        ))}
        {alerts.length === 0 && <p className="text-gray-400 text-center py-8">No alerts yet.</p>}
      </div>
    </div>
  )
}
