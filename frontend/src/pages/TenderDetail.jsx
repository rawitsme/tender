import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Calendar, MapPin, Building2, FileText, ExternalLink, Bookmark, Share2, Copy, Check } from 'lucide-react'
import { format } from 'date-fns'
import api from '../api/client'

export default function TenderDetail() {
  const { id } = useParams()
  const [tender, setTender] = useState(null)
  const [loading, setLoading] = useState(true)
  const [bookmarked, setBookmarked] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    api.get(`/tenders/${id}`)
      .then(r => setTender(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
    api.get('/bookmarks/ids')
      .then(r => setBookmarked(r.data.includes(id)))
      .catch(() => {})
  }, [id])

  const toggleBookmark = async () => {
    try {
      if (bookmarked) { await api.delete(`/bookmarks/${id}`) }
      else { await api.post(`/bookmarks/${id}`) }
      setBookmarked(!bookmarked)
    } catch (err) { console.error(err) }
  }

  const shareLink = () => {
    navigator.clipboard.writeText(window.location.href)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>
  if (!tender) return <div className="text-center py-12 text-red-500">Tender not found</div>

  const fmt = (d) => d ? format(new Date(d), 'dd MMM yyyy, hh:mm a') : '—'
  const fmtVal = (v) => v ? `₹${Number(v).toLocaleString('en-IN')}` : '—'

  return (
    <div className="max-w-4xl space-y-6">
      <Link to="/search" className="flex items-center gap-1 text-sm text-primary-600 hover:underline">
        <ArrowLeft size={16} /> Back to search
      </Link>

      {/* Header */}
      <div className="bg-white rounded-xl border p-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 uppercase">{tender.source}</span>
          <span className={`px-2.5 py-1 rounded-full text-xs font-medium capitalize ${
            tender.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
          }`}>{tender.status}</span>
          {tender.human_verified && <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">✓ Verified</span>}
        </div>
        <h1 className="text-xl font-bold text-gray-900 mb-2">{tender.title}</h1>
        {tender.tender_id && <p className="text-sm text-gray-500">NIT/Ref: {tender.tender_id}</p>}
        {/* Organization Chain */}
        {tender.organization && tender.organization.includes('||') && (
          <div className="flex flex-wrap gap-1 mt-3">
            {tender.organization.split('||').map((part, i) => (
              <span key={i} className="inline-flex items-center">
                {i > 0 && <span className="text-gray-400 mx-1">→</span>}
                <span className="px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-700">{part.trim()}</span>
              </span>
            ))}
          </div>
        )}
        <div className="flex items-center gap-3 mt-3">
          {tender.source_url && (
            <a href={tender.source_url} target="_blank" rel="noopener"
              className="inline-flex items-center gap-1 text-sm text-primary-600 hover:underline">
              <ExternalLink size={14} /> View on source portal
            </a>
          )}
          <button onClick={toggleBookmark}
            className={`inline-flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg border transition-colors ${
              bookmarked ? 'bg-primary-50 border-primary-300 text-primary-700' : 'hover:bg-gray-50'
            }`}>
            <Bookmark size={14} className={bookmarked ? 'fill-primary-600' : ''} />
            {bookmarked ? 'Bookmarked' : 'Bookmark'}
          </button>
          <button onClick={shareLink}
            className="inline-flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg border hover:bg-gray-50">
            {copied ? <><Check size={14} className="text-green-600" /> Copied!</> : <><Copy size={14} /> Share Link</>}
          </button>
        </div>
      </div>

      {/* Key Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border p-5 space-y-3">
          <h2 className="font-semibold text-gray-900">Details</h2>
          <dl className="space-y-2 text-sm">
            {[
              ['Department', tender.department],
              ['Organization', tender.organization],
              ['State', tender.state],
              ['Category', tender.category],
              ['Type', tender.tender_type],
            ].map(([k, v]) => v && (
              <div key={k} className="flex justify-between">
                <dt className="text-gray-500">{k}</dt>
                <dd className="text-gray-900 font-medium text-right">{v}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="bg-white rounded-xl border p-5 space-y-3">
          <h2 className="font-semibold text-gray-900">Financials & Dates</h2>
          <dl className="space-y-2 text-sm">
            {[
              ['Estimated Value', fmtVal(tender.tender_value_estimated)],
              ['EMD', fmtVal(tender.emd_amount)],
              ['Document Fee', fmtVal(tender.document_fee)],
              ['Published', fmt(tender.publication_date)],
              ['Bid Opens', fmt(tender.bid_open_date)],
              ['Bid Closes', fmt(tender.bid_close_date)],
              ['Pre-Bid Meeting', fmt(tender.pre_bid_meeting_date)],
            ].map(([k, v]) => v !== '—' && (
              <div key={k} className="flex justify-between">
                <dt className="text-gray-500">{k}</dt>
                <dd className="text-gray-900 font-medium text-right">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {/* Contact */}
      {(tender.contact_person || tender.contact_email || tender.contact_phone) && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-900 mb-2">Contact</h2>
          <div className="text-sm space-y-1 text-gray-700">
            {tender.contact_person && <p>👤 {tender.contact_person}</p>}
            {tender.contact_email && <p>📧 {tender.contact_email}</p>}
            {tender.contact_phone && <p>📞 {tender.contact_phone}</p>}
          </div>
        </div>
      )}

      {/* Documents */}
      {tender.documents?.length > 0 && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Documents</h2>
          <div className="space-y-2">
            {tender.documents.map(doc => (
              <a key={doc.id} href={`/api/v1/documents/${doc.id}`}
                className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                <FileText size={16} className="text-gray-500" />
                <span className="text-sm">{doc.filename}</span>
                {doc.file_size && <span className="text-xs text-gray-400 ml-auto">{(doc.file_size / 1024).toFixed(0)} KB</span>}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* BOQ */}
      {tender.boq_items?.length > 0 && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Bill of Quantities</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">#</th>
                  <th className="text-left px-3 py-2">Description</th>
                  <th className="text-right px-3 py-2">Qty</th>
                  <th className="text-left px-3 py-2">Unit</th>
                  <th className="text-right px-3 py-2">Rate</th>
                  <th className="text-right px-3 py-2">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {tender.boq_items.map((item, i) => (
                  <tr key={item.id || i}>
                    <td className="px-3 py-2">{item.item_number || i + 1}</td>
                    <td className="px-3 py-2">{item.description}</td>
                    <td className="px-3 py-2 text-right">{item.quantity}</td>
                    <td className="px-3 py-2">{item.unit}</td>
                    <td className="px-3 py-2 text-right">{fmtVal(item.estimated_rate)}</td>
                    <td className="px-3 py-2 text-right">{fmtVal(item.total_amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Description */}
      {tender.description && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-900 mb-2">Description</h2>
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{tender.description}</p>
        </div>
      )}
    </div>
  )
}
