import { useState } from 'react'
import { Filter, X } from 'lucide-react'

const SOURCES = [
  { value: 'GEM', label: 'GeM', color: 'bg-green-100 text-green-800' },
  { value: 'CPPP', label: 'CPPP', color: 'bg-blue-100 text-blue-800' },
  { value: 'UP', label: 'UP', color: 'bg-orange-100 text-orange-800' },
  { value: 'MAHARASHTRA', label: 'Maharashtra', color: 'bg-purple-100 text-purple-800' },
  { value: 'UTTARAKHAND', label: 'Uttarakhand', color: 'bg-teal-100 text-teal-800' },
  { value: 'HARYANA', label: 'Haryana', color: 'bg-red-100 text-red-800' },
  { value: 'MP', label: 'MP', color: 'bg-yellow-100 text-yellow-800' },
]

const STATES = [
  'Central', 'Uttar Pradesh', 'Maharashtra', 'Uttarakhand', 'Haryana', 'Madhya Pradesh',
]

const CLOSING_OPTIONS = [
  { label: 'Today', value: 'today' },
  { label: '3 Days', value: '3days' },
  { label: '7 Days', value: '7days' },
  { label: '30 Days', value: '30days' },
]

export default function SearchFilters({ filters, onChange }) {
  const [open, setOpen] = useState(true)

  const update = (key, value) => onChange({ ...filters, [key]: value })
  const toggleArray = (key, item) => {
    const arr = filters[key] || []
    const next = arr.includes(item) ? arr.filter(x => x !== item) : [...arr, item]
    update(key, next.length ? next : undefined)
  }

  const hasFilters = Object.keys(filters).some(k => filters[k])
  const activeCount = Object.values(filters).filter(Boolean).length

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 font-semibold text-gray-700 w-full">
        <Filter size={16} /> Filters
        {activeCount > 0 && (
          <span className="ml-auto bg-primary-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">{activeCount}</span>
        )}
      </button>
      {open && (
        <div className="mt-4 space-y-5">

          {/* Source */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Source Portal</label>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {SOURCES.map(({ value, label, color }) => (
                <button key={value}
                  onClick={() => toggleArray('sources', value)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                    (filters.sources || []).includes(value)
                      ? 'bg-primary-600 text-white' : color + ' hover:opacity-80'
                  }`}
                >{label}</button>
              ))}
            </div>
          </div>

          {/* State */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">State</label>
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

          {/* Closing within */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Closing Within</label>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {CLOSING_OPTIONS.map(({ label, value }) => (
                <button key={value}
                  onClick={() => update('closing_within', filters.closing_within === value ? undefined : value)}
                  className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                    filters.closing_within === value
                      ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >{label}</button>
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

          {/* Department */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Department</label>
            <input type="text"
              placeholder="Search department..."
              value={filters.department || ''}
              onChange={e => update('department', e.target.value || undefined)}
              className="w-full mt-1.5 px-3 py-1.5 border rounded-lg text-sm"
            />
          </div>

          {/* Category */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Category</label>
            <input type="text"
              placeholder="Search category..."
              value={filters.category || ''}
              onChange={e => update('category', e.target.value || undefined)}
              className="w-full mt-1.5 px-3 py-1.5 border rounded-lg text-sm"
            />
          </div>

          {/* Clear */}
          {hasFilters && (
            <button
              onClick={() => onChange({})}
              className="flex items-center gap-1 text-xs text-red-600 hover:text-red-700 font-medium"
            >
              <X size={12} /> Clear all filters
            </button>
          )}
        </div>
      )}
    </div>
  )
}
