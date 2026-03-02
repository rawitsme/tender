import { useState, useEffect, useCallback } from 'react'
import { Search as SearchIcon, ArrowUpDown, Bookmark, Save } from 'lucide-react'
import api from '../api/client'
import TenderCard from '../components/TenderCard'
import SearchFilters from '../components/SearchFilters'

const SORT_OPTIONS = [
  { label: 'Relevance', value: 'relevance' },
  { label: 'Newest First', value: 'publication_date:desc' },
  { label: 'Closing Soon', value: 'bid_close_date:asc' },
  { label: 'Value: High → Low', value: 'tender_value_estimated:desc' },
  { label: 'Value: Low → High', value: 'tender_value_estimated:asc' },
]

const TABS = [
  { label: 'Active', value: 'ACTIVE' },
  { label: 'Closed', value: 'CLOSED' },
  { label: 'All', value: null },
]

export default function TenderSearch() {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState({})
  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [sort, setSort] = useState('relevance')
  const [tab, setTab] = useState('ACTIVE')
  const [bookmarkIds, setBookmarkIds] = useState(new Set())

  // Load bookmark IDs
  useEffect(() => {
    api.get('/bookmarks/ids').then(r => setBookmarkIds(new Set(r.data))).catch(() => {})
  }, [])

  const doSearch = useCallback(async () => {
    setLoading(true)
    try {
      const [sortBy, sortOrder] = sort === 'relevance' ? ['created_at', 'desc'] : sort.split(':')
      const res = await api.post('/tenders/search', {
        query: query || undefined,
        ...filters,
        status: tab ? [tab.toLowerCase()] : undefined,
        page,
        page_size: 20,
        sort_by: sortBy,
        sort_order: sortOrder,
      })
      setResults(res.data.tenders)
      setTotal(res.data.total)
    } catch (err) {
      console.error('Search failed:', err)
    } finally {
      setLoading(false)
    }
  }, [query, filters, page, sort, tab])

  useEffect(() => { doSearch() }, [doSearch])

  const handleSearch = (e) => {
    e.preventDefault()
    setPage(1)
    doSearch()
  }

  const toggleBookmark = async (tenderId) => {
    const isBookmarked = bookmarkIds.has(tenderId)
    try {
      if (isBookmarked) {
        await api.delete(`/bookmarks/${tenderId}`)
        setBookmarkIds(prev => { const n = new Set(prev); n.delete(tenderId); return n })
      } else {
        await api.post(`/bookmarks/${tenderId}`)
        setBookmarkIds(prev => new Set(prev).add(tenderId))
      }
    } catch (err) { console.error(err) }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Search Tenders</h1>
        <p className="text-gray-500 mt-1">Search across {total.toLocaleString()}+ government tenders from 7 portals</p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="relative flex-1">
          <SearchIcon size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search tenders by keyword, department, NIT number..."
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
          />
        </div>
        <button type="submit" className="px-6 py-3 bg-primary-600 text-white rounded-xl text-sm font-medium hover:bg-primary-700 transition-colors">
          Search
        </button>
      </form>

      {/* Tabs + Sort row */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {TABS.map(t => (
            <button
              key={t.label}
              onClick={() => { setTab(t.value); setPage(1) }}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                tab === t.value ? 'bg-white text-primary-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}
            >{t.label}</button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <ArrowUpDown size={14} className="text-gray-400" />
          <select
            value={sort}
            onChange={e => { setSort(e.target.value); setPage(1) }}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-primary-500 outline-none"
          >
            {SORT_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Filters sidebar */}
        <div className="w-72 shrink-0">
          <SearchFilters filters={filters} onChange={(f) => { setFilters(f); setPage(1) }} />
        </div>

        {/* Results */}
        <div className="flex-1 space-y-4">
          <p className="text-sm text-gray-500">
            {loading ? 'Searching...' : `${total.toLocaleString()} tenders found`}
          </p>

          <div className="space-y-3">
            {results.map(t => (
              <TenderCard
                key={t.id}
                tender={t}
                bookmarked={bookmarkIds.has(t.id)}
                onToggleBookmark={toggleBookmark}
              />
            ))}
            {!loading && results.length === 0 && (
              <div className="text-center py-16">
                <SearchIcon size={48} className="mx-auto text-gray-300 mb-4" />
                <p className="text-gray-400">No tenders match your search.</p>
                <p className="text-gray-300 text-sm mt-1">Try different keywords or adjust filters</p>
              </div>
            )}
          </div>

          {/* Pagination */}
          {total > 20 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 border rounded-lg text-sm disabled:opacity-50 hover:bg-gray-50"
              >Previous</button>
              <div className="flex gap-1">
                {Array.from({ length: Math.min(5, Math.ceil(total / 20)) }, (_, i) => i + 1).map(p => (
                  <button key={p} onClick={() => setPage(p)}
                    className={`w-8 h-8 rounded-lg text-sm ${page === p ? 'bg-primary-600 text-white' : 'hover:bg-gray-100'}`}
                  >{p}</button>
                ))}
                {Math.ceil(total / 20) > 5 && <span className="px-2 text-gray-400">...</span>}
              </div>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={page >= Math.ceil(total / 20)}
                className="px-4 py-2 border rounded-lg text-sm disabled:opacity-50 hover:bg-gray-50"
              >Next</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
