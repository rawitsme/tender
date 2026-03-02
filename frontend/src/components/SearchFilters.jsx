import { useState } from 'react'
import { Filter, X } from 'lucide-react'

const SOURCES = ['gem']
const STATUSES = ['active', 'closed', 'awarded', 'cancelled']
const DEPARTMENTS = [
  'Ministry of Defence',
  'Ministry of Education',
  'Ministry of Health and Family Welfare',
  'Ministry of Railways',
  'Ministry of Home Affairs',
  'Ministry of Finance',
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

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 font-semibold text-gray-700 w-full">
        <Filter size={16} /> Filters
        {hasFilters && <span className="ml-auto w-2 h-2 rounded-full bg-primary-500" />}
      </button>
      {open && (
        <div className="mt-4 space-y-4">
          {/* Closing within */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Closing Within</label>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {[
                { label: 'Today', value: 'today' },
                { label: '3 Days', value: '3days' },
                { label: '7 Days', value: '7days' },
                { label: '30 Days', value: '30days' },
              ].map(({ label, value }) => (
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

          {/* Department (free text filter) */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Department</label>
            <input type="text"
              placeholder="Filter by department..."
              value={filters.department || ''}
              onChange={e => update('department', e.target.value || undefined)}
              className="w-full mt-1.5 px-3 py-1.5 border rounded-lg text-sm"
            />
          </div>

          {/* Category */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase">Category</label>
            <input type="text"
              placeholder="Filter by category..."
              value={filters.category || ''}
              onChange={e => update('category', e.target.value || undefined)}
              className="w-full mt-1.5 px-3 py-1.5 border rounded-lg text-sm"
            />
          </div>

          {/* Clear */}
          {hasFilters && (
            <button
              onClick={() => onChange({})}
              className="flex items-center gap-1 text-xs text-red-600 hover:text-red-700"
            >
              <X size={12} /> Clear all filters
            </button>
          )}
        </div>
      )}
    </div>
  )
}
