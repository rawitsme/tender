import { useState } from 'react'
import { Filter, X } from 'lucide-react'

const STATES = ['Central', 'Uttar Pradesh', 'Maharashtra', 'Uttarakhand', 'Haryana', 'Madhya Pradesh']
const SOURCES = ['cppp', 'gem', 'up', 'maharashtra', 'uttarakhand', 'haryana', 'mp']
const STATUSES = ['active', 'closed', 'awarded', 'cancelled']

export default function SearchFilters({ filters, onChange }) {
  const [open, setOpen] = useState(true)

  const update = (key, value) => onChange({ ...filters, [key]: value })
  const toggleArray = (key, item) => {
    const arr = filters[key] || []
    const next = arr.includes(item) ? arr.filter(x => x !== item) : [...arr, item]
    update(key, next.length ? next : undefined)
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 font-semibold text-gray-700 w-full">
        <Filter size={16} /> Filters
      </button>
      {open && (
        <div className="mt-4 space-y-4">
          {/* States */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">State</label>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {STATES.map(s => (
                <button key={s}
                  onClick={() => toggleArray('states', s)}
                  className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                    (filters.states || []).includes(s)
                      ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >{s}</button>
              ))}
            </div>
          </div>

          {/* Sources */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Source</label>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {SOURCES.map(s => (
                <button key={s}
                  onClick={() => toggleArray('sources', s)}
                  className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                    (filters.sources || []).includes(s)
                      ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >{s.toUpperCase()}</button>
              ))}
            </div>
          </div>

          {/* Value range */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-medium text-gray-500">Min Value (₹)</label>
              <input type="number" placeholder="0"
                value={filters.min_value || ''}
                onChange={e => update('min_value', e.target.value || undefined)}
                className="w-full mt-1 px-3 py-1.5 border rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500">Max Value (₹)</label>
              <input type="number" placeholder="Any"
                value={filters.max_value || ''}
                onChange={e => update('max_value', e.target.value || undefined)}
                className="w-full mt-1 px-3 py-1.5 border rounded-lg text-sm"
              />
            </div>
          </div>

          {/* Status */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Status</label>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {STATUSES.map(s => (
                <button key={s}
                  onClick={() => toggleArray('status', s)}
                  className={`px-2.5 py-1 rounded-full text-xs capitalize transition-colors ${
                    (filters.status || []).includes(s)
                      ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >{s}</button>
              ))}
            </div>
          </div>

          {/* Clear */}
          <button
            onClick={() => onChange({})}
            className="flex items-center gap-1 text-xs text-red-600 hover:text-red-700"
          >
            <X size={12} /> Clear all filters
          </button>
        </div>
      )}
    </div>
  )
}
