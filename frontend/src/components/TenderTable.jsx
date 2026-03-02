import { Link } from 'react-router-dom'
import { format } from 'date-fns'

export default function TenderTable({ tenders }) {
  const fmt = (d) => d ? format(new Date(d), 'dd MMM yyyy') : '—'
  const fmtVal = (v) => {
    if (!v) return '—'
    if (v >= 10000000) return `₹${(v/10000000).toFixed(2)} Cr`
    if (v >= 100000) return `₹${(v/100000).toFixed(2)} L`
    return `₹${Number(v).toLocaleString('en-IN')}`
  }

  return (
    <div className="overflow-x-auto bg-white rounded-xl border">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Title</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Source</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">State</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Department</th>
            <th className="text-right px-4 py-3 font-medium text-gray-600">Value</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Closing</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {tenders.map(t => (
            <tr key={t.id} className="hover:bg-gray-50">
              <td className="px-4 py-3">
                <Link to={`/tenders/${t.id}`} className="text-primary-600 hover:underline line-clamp-1">{t.title}</Link>
              </td>
              <td className="px-4 py-3 uppercase text-xs font-medium">{t.source}</td>
              <td className="px-4 py-3">{t.state || '—'}</td>
              <td className="px-4 py-3 line-clamp-1">{t.department || '—'}</td>
              <td className="px-4 py-3 text-right font-medium">{fmtVal(t.tender_value_estimated)}</td>
              <td className="px-4 py-3">{fmt(t.bid_close_date)}</td>
              <td className="px-4 py-3">
                <span className={`px-2 py-0.5 rounded-full text-xs capitalize ${
                  t.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                }`}>{t.status}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
