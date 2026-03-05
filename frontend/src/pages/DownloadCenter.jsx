import { useState, useEffect, useCallback, useRef } from 'react'
import { Download, ChevronDown, ChevronRight, Check, X, Search, Filter, FileSpreadsheet, Building2, MapPin, Landmark } from 'lucide-react'
import api from '../api/client'

/* ── Collapsible multi-select with search ─────────────────────────────── */
function FilterSection({ title, icon: Icon, items, selected, onToggle, loading, accentClass }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')

  const filtered = items.filter(i =>
    i.label.toLowerCase().includes(search.toLowerCase())
  )
  const selectedCount = items.filter(i => selected.has(i.id)).length

  return (
    <div className="border rounded-xl overflow-hidden bg-white">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${accentClass || 'bg-indigo-50'}`}>
            <Icon size={18} className="text-gray-600" />
          </div>
          <div className="text-left">
            <p className="font-semibold text-gray-900">{title}</p>
            <p className="text-xs text-gray-500">
              {loading ? 'Loading…' : `${items.length} available`}
              {selectedCount > 0 && (
                <span className="ml-2 px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-medium">
                  {selectedCount} selected
                </span>
              )}
            </p>
          </div>
        </div>
        {open ? <ChevronDown size={18} className="text-gray-400" /> : <ChevronRight size={18} className="text-gray-400" />}
      </button>

      {open && (
        <div className="border-t px-4 pb-4">
          {items.length > 5 && (
            <div className="relative mt-3 mb-2">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder={`Search ${title.toLowerCase()}…`}
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none"
              />
            </div>
          )}

          {selectedCount > 0 && (
            <button
              type="button"
              onClick={() => items.forEach(i => { if (selected.has(i.id)) onToggle(i.id) })}
              className="text-xs text-red-500 hover:text-red-700 mb-2"
            >
              Clear all selections
            </button>
          )}

          <div className="max-h-64 overflow-y-auto space-y-1">
            {filtered.length === 0 && (
              <p className="text-sm text-gray-400 py-4 text-center">No matches</p>
            )}
            {filtered.map(item => {
              const isSelected = selected.has(item.id)
              return (
                <div
                  key={item.id}
                  onClick={() => onToggle(item.id)}
                  className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
                    isSelected ? 'bg-indigo-50 border border-indigo-200' : 'hover:bg-gray-50 border border-transparent'
                  }`}
                >
                  <div className={`w-5 h-5 rounded flex items-center justify-center border-2 transition-colors shrink-0 ${
                    isSelected ? 'bg-indigo-600 border-indigo-600' : 'border-gray-300'
                  }`}>
                    {isSelected && <Check size={12} className="text-white" />}
                  </div>
                  <span className="text-sm text-gray-800 flex-1 truncate">{item.label}</span>
                  <span className="text-xs text-gray-400 tabular-nums shrink-0">{item.count}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Main Page ────────────────────────────────────────────────────────── */
export default function DownloadCenter() {
  /* filter data */
  const [sourceCategories, setSourceCategories] = useState([])
  const [states, setStates]                     = useState([])
  const [authorities, setAuthorities]           = useState([])
  const [departments, setDepartments]           = useState([])

  /* selections – using Set for O(1) lookups */
  const [selSources, setSelSources]       = useState(new Set())
  const [selStates, setSelStates]         = useState(new Set())
  const [selAuthorities, setSelAuth]      = useState(new Set())
  const [selDepartments, setSelDept]      = useState(new Set())

  /* ui states */
  const [loadingSrc, setLoadingSrc]   = useState(true)
  const [loadingSt, setLoadingSt]     = useState(false)
  const [loadingAuth, setLoadingAuth] = useState(false)
  const [loadingDept, setLoadingDept] = useState(false)
  const [exporting, setExporting]     = useState(false)
  const [previewCount, setPreviewCount] = useState(null)
  const [loadingPreview, setLoadingPrev] = useState(false)
  const [customFilename, setCustomFilename] = useState('')

  /* ── helpers ── */
  const arrFrom = (s) => Array.from(s)

  const makeToggle = useCallback((setter) => (id) => {
    setter(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleSource = useCallback((id) => makeToggle(setSelSources)(id), [makeToggle])
  const toggleState  = useCallback((id) => makeToggle(setSelStates)(id), [makeToggle])
  const toggleAuth   = useCallback((id) => makeToggle(setSelAuth)(id), [makeToggle])
  const toggleDept   = useCallback((id) => makeToggle(setSelDept)(id), [makeToggle])

  /* ── load source categories on mount ── */
  useEffect(() => {
    api.get('/download-center/source-categories')
      .then(r => setSourceCategories(r.data.categories || []))
      .catch(() => {})
      .finally(() => setLoadingSrc(false))
  }, [])

  /* ── cascade: sources → states ── */
  useEffect(() => {
    setLoadingSt(true)
    const qs = selSources.size ? `?sources=${arrFrom(selSources).join(',')}` : ''
    api.get(`/download-center/states${qs}`)
      .then(r => {
        setStates(r.data)
        setSelStates(prev => {
          const valid = new Set(r.data.map(d => d.id))
          const next = new Set([...prev].filter(s => valid.has(s)))
          return next.size === prev.size ? prev : next
        })
      })
      .catch(() => {})
      .finally(() => setLoadingSt(false))
  }, [selSources])

  /* ── cascade: sources+states → authorities ── */
  useEffect(() => {
    setLoadingAuth(true)
    const p = new URLSearchParams()
    if (selSources.size) p.set('sources', arrFrom(selSources).join(','))
    if (selStates.size) p.set('states', arrFrom(selStates).join(','))
    const qs = p.toString() ? `?${p}` : ''
    api.get(`/download-center/authorities${qs}`)
      .then(r => {
        setAuthorities(r.data)
        setSelAuth(prev => {
          const valid = new Set(r.data.map(d => d.id))
          const next = new Set([...prev].filter(a => valid.has(a)))
          return next.size === prev.size ? prev : next
        })
      })
      .catch(() => {})
      .finally(() => setLoadingAuth(false))
  }, [selSources, selStates])

  /* ── cascade: sources+states+authorities → departments ── */
  useEffect(() => {
    setLoadingDept(true)
    const p = new URLSearchParams()
    if (selSources.size) p.set('sources', arrFrom(selSources).join(','))
    if (selStates.size) p.set('states', arrFrom(selStates).join(','))
    if (selAuthorities.size) p.set('authorities', arrFrom(selAuthorities).join(','))
    const qs = p.toString() ? `?${p}` : ''
    api.get(`/download-center/departments${qs}`)
      .then(r => {
        setDepartments(r.data)
        setSelDept(prev => {
          const valid = new Set(r.data.map(d => d.id))
          const next = new Set([...prev].filter(d => valid.has(d)))
          return next.size === prev.size ? prev : next
        })
      })
      .catch(() => {})
      .finally(() => setLoadingDept(false))
  }, [selSources, selStates, selAuthorities])

  /* ── preview count ── */
  useEffect(() => {
    setLoadingPrev(true)
    const body = {}
    if (selSources.size) body.sources = arrFrom(selSources)
    if (selStates.size) body.states = arrFrom(selStates)
    if (selAuthorities.size) body.authorities = arrFrom(selAuthorities)
    if (selDepartments.size) body.departments = arrFrom(selDepartments)
    api.post('/download-center/preview-count', body)
      .then(r => setPreviewCount(r.data.count))
      .catch(() => setPreviewCount(null))
      .finally(() => setLoadingPrev(false))
  }, [selSources, selStates, selAuthorities, selDepartments])

  /* ── export ── */
  const handleExport = async () => {
    setExporting(true)
    try {
      const body = {}
      if (selSources.size) body.sources = arrFrom(selSources)
      if (selStates.size) body.states = arrFrom(selStates)
      if (selAuthorities.size) body.authorities = arrFrom(selAuthorities)
      if (selDepartments.size) body.departments = arrFrom(selDepartments)

      const response = await api.post('/download-center/export-xlsx', body, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      const today = new Date()
      const dateStr = `${String(today.getDate()).padStart(2, '0')}${String(today.getMonth() + 1).padStart(2, '0')}${today.getFullYear()}`
      const fname = customFilename.trim()
        ? (customFilename.trim().endsWith('.xlsx') ? customFilename.trim() : `${customFilename.trim()}.xlsx`)
        : `Tender_List_${dateStr}.xlsx`
      link.setAttribute('download', fname)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export failed:', err)
      alert('Export failed. Please try again.')
    } finally {
      setExporting(false)
    }
  }

  /* ── clear all ── */
  const clearAll = () => {
    setSelSources(new Set())
    setSelStates(new Set())
    setSelAuth(new Set())
    setSelDept(new Set())
  }

  const hasFilters = selSources.size || selStates.size || selAuthorities.size || selDepartments.size

  /* ─────────────────────────────────── JSX ───────────────────────────── */
  return (
    <div className="max-w-4xl mx-auto space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <FileSpreadsheet size={24} className="text-indigo-600" />
            Download Center
          </h1>
          <p className="text-gray-500 mt-1">Select filters and download tenders as Excel</p>
        </div>
        {hasFilters ? (
          <button type="button" onClick={clearAll} className="text-sm text-gray-500 hover:text-red-600 flex items-center gap-1">
            <X size={14} /> Clear All Filters
          </button>
        ) : null}
      </div>

      {/* Summary Bar */}
      <div className="bg-gradient-to-r from-indigo-50 to-blue-50 rounded-xl p-4 border border-indigo-100">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Left: count + pills */}
          <div className="flex items-center gap-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-indigo-700">
                {loadingPreview ? '…' : (previewCount ?? '—')}
              </p>
              <p className="text-xs text-gray-500">Matching Tenders</p>
            </div>
            <div className="h-10 w-px bg-indigo-200" />
            <div className="flex flex-wrap gap-2 text-xs text-gray-600">
              {selSources.size > 0 && (
                <span className="px-2 py-1 bg-white rounded-full border">{selSources.size} source{selSources.size > 1 ? 's' : ''}</span>
              )}
              {selStates.size > 0 && (
                <span className="px-2 py-1 bg-white rounded-full border">{selStates.size} state{selStates.size > 1 ? 's' : ''}</span>
              )}
              {selAuthorities.size > 0 && (
                <span className="px-2 py-1 bg-white rounded-full border">{selAuthorities.size} authorit{selAuthorities.size > 1 ? 'ies' : 'y'}</span>
              )}
              {selDepartments.size > 0 && (
                <span className="px-2 py-1 bg-white rounded-full border">{selDepartments.size} dept{selDepartments.size > 1 ? 's' : ''}</span>
              )}
              {!hasFilters && <span className="text-gray-400">No filters — all active tenders</span>}
            </div>
          </div>

          {/* Right: filename + download */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <input
                type="text"
                placeholder="Tender_List_…"
                value={customFilename}
                onChange={e => setCustomFilename(e.target.value)}
                className="w-48 px-3 py-2.5 text-sm border rounded-lg bg-white focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none placeholder:text-gray-400"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400">.xlsx</span>
            </div>
            <button
              type="button"
              onClick={handleExport}
              disabled={exporting || previewCount === 0}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-xl font-semibold text-white transition-all shadow-lg ${
                exporting || previewCount === 0
                  ? 'bg-gray-300 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-700 hover:shadow-xl active:scale-95'
              }`}
            >
              {exporting ? (
                <><div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Generating…</>
              ) : (
                <><Download size={18} /> Download</>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Step 1: Sources */}
      <div className="space-y-3">
        <p className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <Filter size={16} /> Step 1: Choose Portal Sources
        </p>
        {sourceCategories.map(cat => (
          <div key={cat.id} className="ml-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{cat.label}</p>
            <div className="flex flex-wrap gap-2">
              {cat.sources.map(src => {
                const on = selSources.has(src.id)
                return (
                  <button
                    key={src.id}
                    type="button"
                    onClick={() => toggleSource(src.id)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
                      on
                        ? 'bg-indigo-600 text-white border-indigo-600 shadow-md'
                        : 'bg-white text-gray-700 border-gray-200 hover:border-indigo-300 hover:bg-indigo-50'
                    }`}
                  >
                    {on && <Check size={14} />}
                    {src.label}
                    <span className={`text-xs ${on ? 'text-indigo-200' : 'text-gray-400'}`}>({src.count})</span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Step 2: States */}
      <FilterSection
        title="Step 2: Select States"
        icon={MapPin}
        items={states}
        selected={selStates}
        onToggle={toggleState}
        loading={loadingSt}
        accentClass="bg-emerald-50"
      />

      {/* Step 3: Authorities */}
      <FilterSection
        title="Step 3: Select Authorities / Organizations"
        icon={Landmark}
        items={authorities}
        selected={selAuthorities}
        onToggle={toggleAuth}
        loading={loadingAuth}
        accentClass="bg-amber-50"
      />

      {/* Step 4: Departments */}
      <FilterSection
        title="Step 4: Select Departments"
        icon={Building2}
        items={departments}
        selected={selDepartments}
        onToggle={toggleDept}
        loading={loadingDept}
        accentClass="bg-rose-50"
      />

      {/* Sticky bottom download */}
      {hasFilters ? (
        <div className="sticky bottom-4 flex justify-center">
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting || previewCount === 0}
            className={`flex items-center gap-3 px-8 py-4 rounded-2xl font-bold text-lg text-white transition-all shadow-2xl ${
              exporting || previewCount === 0
                ? 'bg-gray-300 cursor-not-allowed'
                : 'bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-700 hover:to-blue-700 active:scale-95'
            }`}
          >
            {exporting ? (
              <><div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Generating Excel…</>
            ) : (
              <><Download size={22} /> Download {previewCount ? `${previewCount} Tenders` : 'Selection'} as Excel</>
            )}
          </button>
        </div>
      ) : null}
    </div>
  )
}
