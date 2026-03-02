import { useState, useEffect, useCallback } from 'react'
import { Search as SearchIcon } from 'lucide-react'
import api from '../api/client'
import TenderCard from '../components/TenderCard'
import SearchFilters from '../components/SearchFilters'

export default function TenderSearch() {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState({})
  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  const doSearch = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.post('/tenders/search', {
        query: query || undefined,
        ...filters,
        page,
        page_size: 20,
      })
      setResults(res.data.tenders)
      setTotal(res.data.total)
    } catch (err) {
      console.error('Search failed:', err)
    } finally {
      setLoading(false)
    }
  }, [query, filters, page])

  useEffect(() => { doSearch() }, [doSearch])

  const handleSearch = (e) => {
    e.preventDefault()
    setPage(1)
    doSearch()
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Search Tenders</h1>
        <p className="text-gray-500 mt-1">Search across CPPP, GeM, and 5 state portals</p>
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

      <div className="flex gap-6">
        {/* Filters sidebar */}
        <div className="w-64 shrink-0">
          <SearchFilters filters={filters} onChange={(f) => { setFilters(f); setPage(1) }} />
        </div>

        {/* Results */}
        <div className="flex-1 space-y-4">
          <p className="text-sm text-gray-500">
            {loading ? 'Searching...' : `${total.toLocaleString()} tenders found`}
          </p>

          <div className="space-y-3">
            {results.map(t => <TenderCard key={t.id} tender={t} />)}
            {!loading && results.length === 0 && (
              <p className="text-gray-400 text-center py-12">No tenders match your search.</p>
            )}
          </div>

          {/* Pagination */}
          {total > 20 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 border rounded-lg text-sm disabled:opacity-50"
              >Previous</button>
              <span className="text-sm text-gray-500">Page {page} of {Math.ceil(total / 20)}</span>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={page >= Math.ceil(total / 20)}
                className="px-4 py-2 border rounded-lg text-sm disabled:opacity-50"
              >Next</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
