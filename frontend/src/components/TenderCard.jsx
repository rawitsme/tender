import { Link } from 'react-router-dom'
import { Calendar, MapPin, Building2, IndianRupee } from 'lucide-react'
import { format } from 'date-fns'

const sourceColors = {
  cppp: 'bg-blue-100 text-blue-800',
  gem: 'bg-green-100 text-green-800',
  up: 'bg-orange-100 text-orange-800',
  maharashtra: 'bg-purple-100 text-purple-800',
  uttarakhand: 'bg-teal-100 text-teal-800',
  haryana: 'bg-red-100 text-red-800',
  mp: 'bg-yellow-100 text-yellow-800',
}

const statusColors = {
  active: 'bg-green-100 text-green-800',
  closed: 'bg-gray-100 text-gray-600',
  awarded: 'bg-blue-100 text-blue-800',
  cancelled: 'bg-red-100 text-red-800',
}

export default function TenderCard({ tender }) {
  const formatDate = (d) => d ? format(new Date(d), 'dd MMM yyyy') : '—'
  const formatValue = (v) => {
    if (!v) return null
    if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`
    if (v >= 100000) return `₹${(v / 100000).toFixed(2)} L`
    return `₹${Number(v).toLocaleString('en-IN')}`
  }

  return (
    <Link
      to={`/tenders/${tender.id}`}
      className="block bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md hover:border-primary-300 transition-all"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sourceColors[tender.source] || 'bg-gray-100'}`}>
              {tender.source?.toUpperCase()}
            </span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[tender.status] || 'bg-gray-100'}`}>
              {tender.status}
            </span>
            {tender.tender_id && (
              <span className="text-xs text-gray-500">#{tender.tender_id}</span>
            )}
          </div>
          <h3 className="font-semibold text-gray-900 line-clamp-2 mb-2">{tender.title}</h3>
          <div className="flex flex-wrap gap-4 text-sm text-gray-500">
            {tender.department && (
              <span className="flex items-center gap-1"><Building2 size={14} /> {tender.department}</span>
            )}
            {tender.state && (
              <span className="flex items-center gap-1"><MapPin size={14} /> {tender.state}</span>
            )}
            <span className="flex items-center gap-1">
              <Calendar size={14} /> Closes: {formatDate(tender.bid_close_date)}
            </span>
          </div>
        </div>
        {tender.tender_value_estimated && (
          <div className="text-right shrink-0">
            <p className="text-lg font-bold text-primary-700">{formatValue(tender.tender_value_estimated)}</p>
            {tender.emd_amount && (
              <p className="text-xs text-gray-500">EMD: {formatValue(tender.emd_amount)}</p>
            )}
          </div>
        )}
      </div>
    </Link>
  )
}
