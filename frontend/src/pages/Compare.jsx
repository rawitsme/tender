import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { ArrowLeft, ExternalLink } from 'lucide-react'
import { format } from 'date-fns'
import api from '../api/client'

const FIELDS = [
  { key: 'source', label: 'Source', fmt: v => v?.toUpperCase() },
  { key: 'state', label: 'State' },
  { key: 'department', label: 'Department' },
  { key: 'organization', label: 'Organization', fmt: v => v?.replace(/\|\|/g, ' → ') },
  { key: 'category', label: 'Category' },
  { key: 'tender_type', label: 'Type' },
  { key: 'tender_value_estimated', label: 'Estimated Value', fmt: v => {
    if (!v) return '—'
    const n = Number(v)
    if (n >= 1e7) return `₹${(n/1e7).toFixed(2)} Cr`
    if (n >= 1e5) return `₹${(n/1e5).toFixed(2)} L`
    return `₹${n.toLocaleString('en-IN')}`
  }},
  { key: 'emd_amount', label: 'EMD', fmt: v => v ? `₹${Number(v).toLocaleString('en-IN')}` : '—' },
  { key: 'document_fee', label: 'Document Fee', fmt: v => v ? `₹${Number(v).toLocaleString('en-IN')}` : '—' },
  { key: 'publication_date', label: 'Published', fmt: v => v ? format(new Date(v), 'dd MMM yyyy') : '—' },
  { key: 'bid_open_date', label: 'Bid Opens', fmt: v => v ? format(new Date(v), 'dd MMM yyyy') : '—' },
  { key: 'bid_close_date', label: 'Bid Closes', fmt: v => v ? format(new Date(v), 'dd MMM yyyy') : '—' },
  { key: 'pre_bid_meeting_date', label: 'Pre-Bid Meeting', fmt: v => v ? format(new Date(v), 'dd MMM yyyy') : '—' },
  { key: 'contact_person', label: 'Contact Person' },
  { key: 'contact_email', label: 'Contact Email' },
  { key: 'contact_phone', label: 'Contact Phone' },
  { key: 'status', label: 'Status', fmt: v => v?.toUpperCase() },
]

export default function Compare() {
  const [searchParams] = useSearchParams()
  const [tenders, setTenders] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const ids = (searchParams.get('ids') || '').split(',').filter(Boolean)
    if (ids.length < 2) { setLoading(false); return }

    api.post('/tenders/compare', ids)
      .then(r => setTenders(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [searchParams])

  if (loading) return <div className="text-center py-12 text-gray-500">Loading comparison...</div>
  if (tenders.length < 2) return (
    <div className="text-center py-16">
      <p className="text-gray-400">Select at least 2 tenders to compare.</p>
      <Link to="/search" className="text-primary-600 hover:underline mt-2 inline-block">← Back to search</Link>
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/search" className="flex items-center gap-1 text-sm text-primary-600 hover:underline">
          <ArrowLeft size={16} /> Back to search
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">Compare Tenders ({tenders.length})</h1>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="sticky left-0 bg-gray-100 p-3 text-left text-sm font-medium text-gray-600 min-w-[140px] border-b">Field</th>
              {tenders.map(t => (
                <th key={t.id} className="p-3 text-left text-sm font-medium border-b min-w-[250px] bg-white">
                  <Link to={`/tenders/${t.id}`} className="text-primary-600 hover:underline line-clamp-2 font-semibold">
                    {t.title?.slice(0, 80)}
                  </Link>
                  <div className="mt-1">
                    <span className="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-800 uppercase">{t.source}</span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FIELDS.map(({ key, label, fmt }) => {
              const hasValue = tenders.some(t => t[key])
              if (!hasValue) return null
              return (
                <tr key={key} className="hover:bg-gray-50">
                  <td className="sticky left-0 bg-gray-50 p-3 text-sm font-medium text-gray-600 border-b">{label}</td>
                  {tenders.map(t => {
                    const val = t[key]
                    const display = fmt ? fmt(val) : (val || '—')
                    return (
                      <td key={t.id} className="p-3 text-sm text-gray-900 border-b">{display}</td>
                    )
                  })}
                </tr>
              )
            })}
            {/* Source URL */}
            <tr className="hover:bg-gray-50">
              <td className="sticky left-0 bg-gray-50 p-3 text-sm font-medium text-gray-600 border-b">Source Link</td>
              {tenders.map(t => (
                <td key={t.id} className="p-3 text-sm border-b">
                  {t.source_url ? (
                    <a href={t.source_url} target="_blank" rel="noopener"
                      className="inline-flex items-center gap-1 text-primary-600 hover:underline">
                      <ExternalLink size={12} /> View
                    </a>
                  ) : '—'}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
