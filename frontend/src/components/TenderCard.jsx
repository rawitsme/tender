import { Link } from 'react-router-dom'
import { Calendar, MapPin, Building2, Bookmark } from 'lucide-react'
import { format, formatDistanceToNow, isPast, differenceInDays } from 'date-fns'

const sourceColors = {
  GEM: 'bg-green-100 text-green-800',
  CPPP: 'bg-blue-100 text-blue-800',
  UP: 'bg-orange-100 text-orange-800',
  MAHARASHTRA: 'bg-purple-100 text-purple-800',
  UTTARAKHAND: 'bg-teal-100 text-teal-800',
  HARYANA: 'bg-red-100 text-red-800',
  MP: 'bg-yellow-100 text-yellow-800',
}

const statusColors = {
  ACTIVE: 'bg-green-100 text-green-800',
  CLOSED: 'bg-gray-100 text-gray-600',
  AWARDED: 'bg-blue-100 text-blue-800',
  CANCELLED: 'bg-red-100 text-red-800',
}

export default function TenderCard({ tender, bookmarked, onToggleBookmark }) {
  const formatDate = (d) => d ? format(new Date(d), 'dd MMM yyyy') : '—'
  const formatValue = (v) => {
    if (!v) return null
    if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`
    if (v >= 100000) return `₹${(v / 100000).toFixed(2)} L`
    return `₹${Number(v).toLocaleString('en-IN')}`
  }

  const closeDate = tender.bid_close_date ? new Date(tender.bid_close_date) : null
  const isClosingSoon = closeDate && !isPast(closeDate) && differenceInDays(closeDate, new Date()) <= 3
  const isClosed = closeDate && isPast(closeDate)
  const closingText = closeDate
    ? (isPast(closeDate) ? 'Closed' : formatDistanceToNow(closeDate, { addSuffix: true }))
    : null

  const src = (tender.source || '').toUpperCase()

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md hover:border-primary-300 transition-all relative group">
      {/* Bookmark button */}
      {onToggleBookmark && (
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggleBookmark(tender.id) }}
          className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          title={bookmarked ? 'Remove bookmark' : 'Bookmark this tender'}
        >
          <Bookmark size={18} className={bookmarked ? 'fill-primary-600 text-primary-600' : 'text-gray-400'} />
        </button>
      )}

      <Link to={`/tenders/${tender.id}`}>
        <div className="flex items-start justify-between gap-4 pr-8">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sourceColors[src] || 'bg-gray-100'}`}>
                {src}
              </span>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[tender.status?.toUpperCase()] || 'bg-gray-100'}`}>
                {tender.status}
              </span>
              {isClosingSoon && (
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 animate-pulse">
                  ⚡ Closing Soon
                </span>
              )}
              {tender.tender_id && (
                <span className="text-xs text-gray-400 font-mono">#{tender.tender_id}</span>
              )}
            </div>
            <h3 className="font-semibold text-gray-900 line-clamp-2 mb-2">{tender.title}</h3>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-500">
              {(tender.organization || tender.department) && (
                <span className="flex items-center gap-1 truncate max-w-[300px]">
                  <Building2 size={14} className="shrink-0" />
                  {tender.organization || tender.department}
                </span>
              )}
              {tender.state && (
                <span className="flex items-center gap-1"><MapPin size={14} /> {tender.state}</span>
              )}
              <span className={`flex items-center gap-1 ${isClosingSoon ? 'text-amber-600 font-medium' : isClosed ? 'text-gray-400' : ''}`}>
                <Calendar size={14} />
                {closingText ? `Closes ${closingText}` : `Closes: ${formatDate(tender.bid_close_date)}`}
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
    </div>
  )
}
