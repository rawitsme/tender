import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search as SearchIcon, ArrowUpDown, Download, GitCompare, X, Plus } from 'lucide-react'
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
  { label: 'Active', value: 'ACTIVE', archived: false },
  { label: 'All (incl. Archived)', value: null, archived: true },
]

const SUGGESTED_KEYWORDS = [
  'construction', 'road', 'water', 'IT', 'medical', 'railway',
  'electrical', 'furniture', 'cleaning', 'security', 'transport', 'printing'
]

export default function TenderSearch() {
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [keywords, setKeywords] = useState([])       // refinement keyword chips
  const [keywordInput, setKeywordInput] = useState('')
  const [filters, setFilters] = useState({})
  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [sort, setSort] = useState('relevance')
  const [tab, setTab] = useState('ACTIVE')
  const [bookmarkIds, setBookmarkIds] = useState(new Set())
  const [compareIds, setCompareIds] = useState(new Set())
  const [exporting, setExporting] = useState(false)
  const [showKeywordSuggestions, setShowKeywordSuggestions] = useState(false)
  const [processingDetails, setProcessingDetails] = useState(new Set())

  // Sync state from URL params whenever they change
  useEffect(() => {
    const q = searchParams.get('q') || ''
    setQuery(q)
    setKeywords([])
    const f = {}
    if (searchParams.get('source')) f.sources = [searchParams.get('source')]
    if (searchParams.get('state')) f.states = [searchParams.get('state')]
    if (searchParams.get('department')) f.department = searchParams.get('department')
    setFilters(f)
    setPage(1)
  }, [searchParams])

  useEffect(() => {
    api.get('/bookmarks/ids').then(r => setBookmarkIds(new Set(r.data))).catch(() => {})
  }, [])

  // Combine query + keywords into search query
  const fullQuery = [query, ...keywords].filter(Boolean).join(' ')

  const buildSearchBody = useCallback(() => {
    const [sortBy, sortOrder] = sort === 'relevance' ? ['created_at', 'desc'] : sort.split(':')
    return {
      query: fullQuery || undefined,
      ...filters,
      status: tab ? [tab.toLowerCase()] : undefined,
      include_archived: TABS.find(t => t.value === tab)?.archived ?? false,
      page,
      page_size: 20,
      sort_by: sortBy,
      sort_order: sortOrder,
    }
  }, [fullQuery, filters, page, sort, tab])

  const doSearch = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.post('/tenders/search', buildSearchBody())
      setResults(res.data.tenders)
      setTotal(res.data.total)
    } catch (err) {
      console.error('Search failed:', err)
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

  const addKeyword = (kw) => {
    const k = kw.trim().toLowerCase()
    if (k && !keywords.includes(k)) {
      setKeywords(prev => [...prev, k])
      setPage(1)
    }
    setKeywordInput('')
    setShowKeywordSuggestions(false)
  }

  const removeKeyword = (kw) => {
    setKeywords(prev => prev.filter(k => k !== kw))
    setPage(1)
  }

  const handleKeywordKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (keywordInput.trim()) addKeyword(keywordInput)
    }
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

  const toggleCompare = (tenderId) => {
    setCompareIds(prev => {
      const n = new Set(prev)
      if (n.has(tenderId)) n.delete(tenderId)
      else if (n.size < 5) n.add(tenderId)
      return n
    })
  }

  const handleExport = async (format) => {
    setExporting(true)
    try {
      const res = await api.post(`/export/${format}`, buildSearchBody(), { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `tenders_export.${format}`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export failed:', err)
    } finally {
      setExporting(false)
    }
  }

  const handleGetDetails = async (tenderId) => {
    setProcessingDetails(prev => new Set(prev).add(tenderId))
    try {
      const res = await api.post(`/details/fetch/${tenderId}`)
      if (res.data.status === 'existing') {
        alert(`Details already fetched!\n\n${res.data.summary.substring(0, 500)}...`)
      } else {
        alert('Details are being fetched in the background. This may take a few minutes. Check the tender detail page for updates.')
      }
    } catch (err) {
      console.error('Get details failed:', err)
      alert('Failed to fetch details. Please try again.')
    } finally {
      setProcessingDetails(prev => {
        const next = new Set(prev)
        next.delete(tenderId)
        return next
      })
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
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Search Tenders</h1>
        <p className="text-gray-500 mt-1">Search across {total.toLocaleString()}+ government tenders from 7 portals</p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="relative flex-1">
          <SearchIcon size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" value={query} onChange={e => setQuery(e.target.value)}
            placeholder="Search tenders by keyword, department, NIT number..."
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none" />
        </div>
        <button type="submit" className="px-6 py-3 bg-primary-600 text-white rounded-xl text-sm font-medium hover:bg-primary-700 transition-colors shrink-0">
          Search
        </button>
      </form>

      {/* Keyword Chips + Add */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          {keywords.map(kw => (
            <span key={kw} className="inline-flex items-center gap-1 px-3 py-1 bg-primary-100 text-primary-800 rounded-full text-sm font-medium">
              {kw}
              <button onClick={() => removeKeyword(kw)} className="hover:text-primary-600">
                <X size={14} />
              </button>
            </span>
          ))}
          <div className="relative">
            <div className="inline-flex items-center gap-1">
              <input
                type="text"
                value={keywordInput}
                onChange={e => { setKeywordInput(e.target.value); setShowKeywordSuggestions(true) }}
                onKeyDown={handleKeywordKeyDown}
                onFocus={() => setShowKeywordSuggestions(true)}
                onBlur={() => setTimeout(() => setShowKeywordSuggestions(false), 200)}
                placeholder="+ Add keyword to refine..."
                className="w-44 px-3 py-1 border border-dashed border-gray-300 rounded-full text-sm focus:border-primary-400 focus:outline-none"
              />
              {keywordInput.trim() && (
                <button onClick={() => addKeyword(keywordInput)}
                  className="p-1 bg-primary-600 text-white rounded-full hover:bg-primary-700">
                  <Plus size={14} />
                </button>
              )}
            </div>
            {/* Suggestions dropdown */}
            {showKeywordSuggestions && !keywordInput && (
              <div className="absolute top-full left-0 mt-1 bg-white border rounded-lg shadow-lg py-1 z-20 w-56">
                <p className="px-3 py-1 text-xs text-gray-400 uppercase">Suggested Keywords</p>
                <div className="flex flex-wrap gap-1 px-3 py-2">
                  {SUGGESTED_KEYWORDS
                    .filter(k => !keywords.includes(k))
                    .map(k => (
                      <button key={k} onClick={() => addKeyword(k)}
                        className="px-2 py-0.5 bg-gray-100 hover:bg-primary-100 hover:text-primary-800 rounded-full text-xs transition-colors">
                        {k}
                      </button>
                    ))}
                </div>
              </div>
            )}
            {showKeywordSuggestions && keywordInput && (
              <div className="absolute top-full left-0 mt-1 bg-white border rounded-lg shadow-lg py-1 z-20 w-56">
                {SUGGESTED_KEYWORDS
                  .filter(k => k.includes(keywordInput.toLowerCase()) && !keywords.includes(k))
                  .slice(0, 5)
                  .map(k => (
                    <button key={k} onClick={() => addKeyword(k)}
                      className="block w-full px-3 py-1.5 text-sm text-left hover:bg-gray-50">
                      {k}
                    </button>
                  ))}
                <button onClick={() => addKeyword(keywordInput)}
                  className="block w-full px-3 py-1.5 text-sm text-left text-primary-600 hover:bg-primary-50 border-t">
                  Add "{keywordInput.trim()}"
                </button>
              </div>
            )}
          </div>
          {keywords.length > 0 && (
            <button onClick={() => { setKeywords([]); setPage(1) }}
              className="text-xs text-red-500 hover:text-red-700">Clear all</button>
          )}
        </div>
      </div>

      {/* Tabs + Sort + Actions */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {TABS.map(t => (
            <button key={t.label} onClick={() => { setTab(t.value); setPage(1) }}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                tab === t.value ? 'bg-white text-primary-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}>{t.label}</button>
          ))}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {compareIds.size >= 2 && (
            <a href={`/compare?ids=${[...compareIds].join(',')}`}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-purple-600 text-white rounded-lg text-xs font-medium hover:bg-purple-700">
              <GitCompare size={14} /> Compare ({compareIds.size})
            </a>
          )}
          <div className="relative group">
            <button disabled={exporting}
              className="inline-flex items-center gap-1 px-3 py-1.5 border rounded-lg text-xs font-medium hover:bg-gray-50 disabled:opacity-50">
              <Download size={14} /> {exporting ? 'Exporting...' : 'Export'}
            </button>
            <div className="absolute right-0 mt-1 bg-white border rounded-lg shadow-lg py-1 hidden group-hover:block z-10 min-w-[120px]">
              <button onClick={() => handleExport('xlsx')} className="block w-full px-4 py-2 text-sm text-left hover:bg-gray-50">📊 Excel (.xlsx)</button>
              <button onClick={() => handleExport('csv')} className="block w-full px-4 py-2 text-sm text-left hover:bg-gray-50">📄 CSV (.csv)</button>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <ArrowUpDown size={14} className="text-gray-400" />
            <select value={sort} onChange={e => { setSort(e.target.value); setPage(1) }}
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-primary-500 outline-none">
              {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
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
            {loading ? 'Searching...' : `${total.toLocaleString()} tenders found`}
            {keywords.length > 0 && ` for "${keywords.join(' + ')}"`}
          </p>

          <div className="space-y-3">
            {results.map(t => (
              <div key={t.id} className="relative">
                <TenderCard 
                  tender={t} 
                  bookmarked={bookmarkIds.has(t.id)} 
                  onToggleBookmark={toggleBookmark}
                  onGetDetails={handleGetDetails}
                />
                <label className="absolute bottom-3 right-3 flex items-center gap-1 text-xs text-gray-400 cursor-pointer hover:text-gray-600">
                  <input type="checkbox" checked={compareIds.has(t.id)} onChange={() => toggleCompare(t.id)}
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                  Compare
                </label>
              </div>
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

      {/* Mobile filters */}
      <div className="md:hidden">
        <SearchFilters filters={filters} onChange={(f) => { setFilters(f); setPage(1) }} />
      </div>
    </div>
  )
}
