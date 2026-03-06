import { useState, useEffect, useCallback } from 'react'
import { Search as SearchIcon, Archive as ArchiveIcon, ArrowUpDown, RotateCcw, RefreshCw } from 'lucide-react'
import api from '../api/client'
import TenderCard from '../components/TenderCard'
import SearchFilters from '../components/SearchFilters'

const SORT_OPTIONS = [
  { label: 'Relevance', value: 'relevance' },
  { label: 'Newest First', value: 'publication_date:desc' },
  { label: 'Closed Recently', value: 'bid_close_date:desc' },
  { label: 'Value: High → Low', value: 'tender_value_estimated:desc' },
]

const STATUS_TABS = [
  { label: 'All Archived', value: null },
  { label: 'Closed', value: 'CLOSED' },
  { label: 'Awarded', value: 'AWARDED' },
  { label: 'Cancelled', value: 'CANCELLED' },
]

export default function Archive() {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState({})
  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [sort, setSort] = useState('bid_close_date:desc')
  const [statusTab, setStatusTab] = useState(null)
  const [stats, setStats] = useState(null)
  const [autoArchiving, setAutoArchiving] = useState(false)

  useEffect(() => {
    api.get('/archive/stats').then(r => setStats(r.data)).catch(() => {})
  }, [])

  const buildSearchBody = useCallback(() => {
    const [sortBy, sortOrder] = sort === 'relevance' ? ['created_at', 'desc'] : sort.split(':')
    return {
      query: query || undefined,
      ...filters,
      status: statusTab ? [statusTab.toLowerCase()] : undefined,
      page,
      page_size: 20,
      sort_by: sortBy,
      sort_order: sortOrder,
    }
  }, [query, filters, page, sort, statusTab])

  const doSearch = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.post('/archive/search', buildSearchBody())
      setResults(res.data.tenders)
      setTotal(res.data.total)
    } catch (err) {
      console.error('Archive search failed:', err)
    } finally {
      setLoading(false)
    }
  }, [buildSearchBody])

  useEffect(() => { doSearch() }, [doSearch])

  const handleSearch = (e) => {
    e.preventDefault()
    setPage(1)
    doSearch()
  }

  const handleAutoArchive = async () => {
    setAutoArchiving(true)
    try {
      const res = await api.post('/archive/auto')
      setStats(prev => prev ? { ...prev, ...res.data } : res.data)
      alert(`Archived ${res.data.archived_closed + res.data.archived_expired} tenders.\n\nTotal archived: ${res.data.total_archived}\nActive: ${res.data.total_active}`)
      doSearch()
      api.get('/archive/stats').then(r => setStats(r.data)).catch(() => {})
    } catch (err) {
      alert('Auto-archive failed')
    } finally {
      setAutoArchiving(false)
    }
  }

  const handleUnarchive = async (tenderId) => {
    try {
      await api.delete(`/archive/${tenderId}`)
      setResults(prev => prev.filter(t => t.id !== tenderId))
      setTotal(prev => prev - 1)
    } catch (err) {
      alert('Failed to unarchive')
    }
  }

  const totalPages = Math.ceil(total / 20)
  const pageNumbers = []
  const maxPages = 7
  let startPage = Math.max(1, page - Math.floor(maxPages / 2))
  let endPage = Math.min(totalPages, startPage + maxPages - 1)
  if (endPage - startPage < maxPages - 1) startPage = Math.max(1, endPage - maxPages + 1)
  for (let i = startPage; i <= endPage; i++) pageNumbers.push(i)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <ArchiveIcon size={24} className="text-gray-500" />
            Archived Tenders
          </h1>
          <p className="text-gray-500 mt-1">
            Closed, awarded, and expired tenders — fully searchable with all details preserved
          </p>
        </div>
        <button
          onClick={handleAutoArchive}
          disabled={autoArchiving}
          className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
        >
          <RefreshCw size={16} className={autoArchiving ? 'animate-spin' : ''} />
          {autoArchiving ? 'Archiving...' : 'Auto-Archive Now'}
        </button>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { label: 'Total Archived', value: stats.archived, color: 'bg-gray-100 text-gray-800' },
            { label: 'Active (Not Archived)', value: stats.active, color: 'bg-green-50 text-green-800' },
            { label: 'Closed', value: stats.closed, color: 'bg-blue-50 text-blue-800' },
            { label: 'Awarded', value: stats.awarded, color: 'bg-purple-50 text-purple-800' },
            { label: 'Cancelled', value: stats.cancelled, color: 'bg-red-50 text-red-800' },
          ].map(s => (
            <div key={s.label} className={`${s.color} rounded-xl px-4 py-3`}>
              <p className="text-2xl font-bold">{s.value?.toLocaleString() || 0}</p>
              <p className="text-xs mt-0.5 opacity-70">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Search bar */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="relative flex-1">
          <SearchIcon size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" value={query} onChange={e => setQuery(e.target.value)}
            placeholder="Search archived tenders by keyword, department, NIT number..."
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none" />
        </div>
        <button type="submit" className="px-6 py-3 bg-primary-600 text-white rounded-xl text-sm font-medium hover:bg-primary-700 transition-colors shrink-0">
          Search
        </button>
      </form>

      {/* Status tabs + Sort */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {STATUS_TABS.map(t => (
            <button key={t.label} onClick={() => { setStatusTab(t.value); setPage(1) }}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                statusTab === t.value ? 'bg-white text-primary-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}>{t.label}</button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <ArrowUpDown size={14} className="text-gray-400" />
          <select value={sort} onChange={e => { setSort(e.target.value); setPage(1) }}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-primary-500 outline-none">
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Filters sidebar */}
        <div className="w-72 shrink-0 hidden md:block">
          <SearchFilters filters={filters} onChange={(f) => { setFilters(f); setPage(1) }} />
        </div>

        {/* Results */}
        <div className="flex-1 space-y-4 min-w-0">
          <p className="text-sm text-gray-500">
            {loading ? 'Searching...' : `${total.toLocaleString()} archived tenders found`}
          </p>

          <div className="space-y-3">
            {results.map(t => (
              <div key={t.id} className="relative">
                <TenderCard tender={t} />
                <button
                  onClick={() => handleUnarchive(t.id)}
                  className="absolute bottom-3 right-3 inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors"
                  title="Restore to active"
                >
                  <RotateCcw size={12} /> Unarchive
                </button>
              </div>
            ))}
            {!loading && results.length === 0 && (
              <div className="text-center py-16">
                <ArchiveIcon size={48} className="mx-auto text-gray-300 mb-4" />
                <p className="text-gray-400">No archived tenders match your search.</p>
              </div>
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-1 pt-4">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="px-3 py-2 border rounded-lg text-sm disabled:opacity-30 hover:bg-gray-50">←</button>
              {startPage > 1 && <>
                <button onClick={() => setPage(1)} className="w-8 h-8 rounded-lg text-sm hover:bg-gray-100">1</button>
                {startPage > 2 && <span className="px-1 text-gray-400">…</span>}
              </>}
              {pageNumbers.map(p => (
                <button key={p} onClick={() => setPage(p)}
                  className={`w-8 h-8 rounded-lg text-sm ${page === p ? 'bg-primary-600 text-white' : 'hover:bg-gray-100'}`}>{p}</button>
              ))}
              {endPage < totalPages && <>
                {endPage < totalPages - 1 && <span className="px-1 text-gray-400">…</span>}
                <button onClick={() => setPage(totalPages)} className="w-8 h-8 rounded-lg text-sm hover:bg-gray-100">{totalPages}</button>
              </>}
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
                className="px-3 py-2 border rounded-lg text-sm disabled:opacity-30 hover:bg-gray-50">→</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
